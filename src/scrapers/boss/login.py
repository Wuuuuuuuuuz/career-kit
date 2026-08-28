"""BOSS 直聘登录工具——patchright（driver 层反检测 fork）驱动。

为什么不用 vanilla Playwright：它对每个页面必然调用 CDP Runtime.enable，
BOSS 前端用 Error.stack 序列化技巧检测该调用，附着后约 5 秒页面自杀。
用户层 stealth 插件救不了驱动层泄漏——已实测证伪。
为什么选 patchright：把 Runtime.enable 替换为 isolated world 方案，
从驱动层消除该检测向量；2026-08-26 实测 zhipin.com 页面 60 秒存活通过。

流程（一条命令到底，全程免手动确认）：
    python -m src.scrapers.boss.login
      → patchright 拉起系统默认浏览器（Chrome 或 Edge，强制直连规避代理风控）
      → 打开 zhipin.com，等待扫码
      → 轮询 cookies：wt2 出现后继续等页面 JS 生成 __zp_stoken__，
        拿齐后才落盘退出（缺 stoken 会被 API 风控拦截）

浏览器选择（重要）：
    只用系统默认浏览器（优先读取 Windows 注册表 http UserChoice，其次按安装
    情况选 Chrome/Edge）。**绝不回退 Chromium**——开源内核自动化指纹太明显，
    BOSS 等站一测一个准；且安装补丁内核的痕迹本身就构成检测特征。

网络策略：默认强制直连（--no-proxy-server，系统代理常把 zhipin 路由到境外
节点，表现为「页面看得到但标签页一直转圈」）；直连失败时回退系统代理再试一轮。
页面持续转圈不判死：风控验证页会无限加载，但域名已打开时仍可扫码、cookies 仍会
出现，继续轮询即可。

依赖：pip install patchright==1.62.1（版本必须 pin 死——该 fork 跟随上游节奏紧，
浮动依赖可能在某次升级后静默失效）。
"""

from __future__ import annotations

import shutil
import sys
import time

from ...paths import CACHE_DIR
from .auth import has_valid_cookies, save_cookies

# 浏览器 profile 属用户资产，与登录态同住 ~/.career-kit/cache/boss/
PROFILE_DIR = CACHE_DIR / "boss" / "chrome_profile"
POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 300.0
STOKEN_WAIT_MAX_SEC = 45.0  # wt2 出现后等待页面 JS 生成 stoken 的上限
ZHIPIN_URL = "https://www.zhipin.com/"

_CHROME_EXES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
_EDGE_EXES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def _detect_channel() -> str | None:
    """返回 patchright 的 channel：'chrome' | 'msedge'。

    优先级：系统默认浏览器（Windows http UserChoice 注册表）> 安装存在性（Chrome 优先）。
    返回 None 表示两者都不可用——此时绝不回退 Chromium。
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        if "ChromeHTML" in prog_id:
            return "chrome"
        if "MSEdgeHTM" in prog_id:
            return "msedge"
    except OSError:
        pass

    for path in _CHROME_EXES:
        if _path_exists(path) or shutil.which("chrome"):
            return "chrome"
    for path in _EDGE_EXES:
        if _path_exists(path) or shutil.which("msedge"):
            return "msedge"
    return None


def _path_exists(p: str) -> bool:
    from pathlib import Path
    return Path(p).exists()


def _launch(p, channel: str, force_direct: bool = True):
    """启动持久化上下文。四件套缺一不可（patchright README 推荐配置）。

    窗口尺寸**由浏览器自己适配**：只传 --start-maximized，让操作系统把窗口
    最大化到实际工作区（取可见区域真实大小）；配合 no_viewport=True 使页面
    布局跟随窗口真实尺寸。不代码规定任何分辨率——强制小视口看不全，
    强制满屏分辨率（如 2560x1440）又会超出可视区域。

    force_direct=True 时加 --no-proxy-server 强制直连：BOSS 对海外/代理出口
    IP 风控极敏感，且系统代理节点不可用时 zhipin 会无限转圈。实测
    Playwright 的 proxy={"server": "direct://"} 在部分环境不生效
    （ERR_PROXY_CONNECTION_FAILED），原生启动参数最可靠。
    """
    window_args = ["--start-maximized"]
    if force_direct:
        window_args += ["--no-proxy-server"]

    kwargs = dict(
        user_data_dir=str(PROFILE_DIR),
        channel=channel,    # chrome / msedge，绝不回退 chromium
        headless=False,     # headless 本身就是被检测特征
        no_viewport=True,   # 页面视口跟随窗口真实尺寸，浏览器自适应
        ignore_default_args=["--enable-automation"],
        args=window_args,
    )
    return p.chromium.launch_persistent_context(**kwargs)


def login() -> bool:
    """打开 BOSS 登录页并轮询 cookies，wt2+stoken 齐备即落盘。返回是否成功。"""
    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        print("[!] 缺少依赖 patchright（反检测浏览器驱动）。请在本项目目录执行：\n"
              "    pip install -e .\n"
              "（pyproject.toml 已声明 patchright==1.62.1 与 iv8，一键安装全部依赖）\n"
              "或单独安装：pip install patchright==1.62.1")
        return False

    channel = _detect_channel()
    if channel is None:
        print("[!] 未检测到 Chrome 或 Edge。本工具只用系统默认浏览器，"
              "绝不回退 Chromium（开源内核自动化指纹太明显，极易触发风控）。\n"
              "[!] 请安装 Google Chrome 或 Microsoft Edge 后重试。")
        return False

    # 先直连（规避代理出口风控），失败再退回系统默认网络栈
    for mode, force_direct in (("直连", True), ("系统代理", False)):
        with sync_playwright() as p:
            result = _attempt_login(p, channel, force_direct=force_direct)
        if result is not None:
            return result
        print(f"[!] {mode}模式下无法打开 zhipin.com，切换下一网络模式重试……")
    print("[!] 所有网络模式均失败。请检查网络/代理设置后重试。")
    return False


def _goto_zhipin(page) -> bool:
    """导航到 zhipin；即使加载超时，只要域名已打开就算成功。

    风控验证页会无限转圈（domcontentloaded 永不触发），但此时用户仍可扫码、
    cookies 仍会出现——判死会导致「页面明明出现了却报失败」。
    """
    for wait, tmo in (("domcontentloaded", 45000), ("commit", 30000)):
        try:
            page.goto(ZHIPIN_URL, wait_until=wait, timeout=tmo)
            return True
        except Exception as exc:
            print(f"[!] 页面加载未完成（{str(exc).splitlines()[0]}）……")
    try:
        url = page.url
    except Exception:
        url = ""
    if "zhipin.com" in url:
        print("[!] 页面持续转圈（疑似风控验证页），但域名已打开——继续等待扫码。")
        return True
    return False


def _attempt_login(p, channel: str, force_direct: bool) -> bool | None:
    """执行一次完整登录流程。

    Returns:
        True/False：流程已有结论（调用方直接返回）；
        None：导航彻底失败，调用方可换网络模式重试。
    """
    ctx = _launch(p, channel, force_direct=force_direct)
    try:
        # 导航到登录页——persistent context 新 profile 无历史会话，必须显式打开
        # （BUG-009：缺失此步会弹出永久空白窗口）
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not _goto_zhipin(page):
            return None  # 域名都没打开，换网络模式重试的信号

        print("[login] 浏览器已启动，请扫码登录……检测到登录态将自动保存退出"
              f"（最长等待 {int(POLL_TIMEOUT_SEC)} 秒）")
        deadline = time.time() + POLL_TIMEOUT_SEC

        # 跨轮次合并采样。关键点：__zp_stoken__ 由页面 JS 在登录后异步生成，
        # 必须真轮询到它出现才落盘——干等固定秒数既不可靠也浪费时间
        accumulated: dict[str, str] = {}
        reloaded = False          # 是否已用 reload 触发过 stoken 生成
        stoken_phase_since: float | None = None

        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)
            try:
                cookies = ctx.cookies(ZHIPIN_URL)
            except Exception:
                continue  # 轮询瞬间页面跳转/关闭，下个周期重试
            for c in cookies:
                accumulated[c["name"]] = c["value"]

            if not accumulated.get("wt2"):
                continue  # 尚未登录，继续等扫码

            has_stoken = "__zp_stoken__" in accumulated

            if has_stoken or (
                stoken_phase_since
                and time.time() - stoken_phase_since > STOKEN_WAIT_MAX_SEC
            ):
                # 理想路径：stoken 已生成；兜底路径：等待超限，带警告保存
                save_cookies(accumulated)
                if not has_valid_cookies():
                    continue
                if has_stoken:
                    print(f"[login] OK 登录态已保存（{len(accumulated)} 条 cookies，"
                          "stoken 已捕获）。fetch_company_jobs(company=\"boss\") 现在可用。")
                else:
                    print(f"[login] △ 登录态已保存（{len(accumulated)} 条 cookies），"
                          "但 stoken 迟迟未生成——首次搜索可能被风控拦截，"
                          "届时重跑本命令即可补采。")
                return True

            # 已登录但 stoken 未生成：触发一次 reload 进入 stoken 等待相
            if not reloaded:
                reloaded = True
                stoken_phase_since = time.time()
                try:
                    page.reload(wait_until="domcontentloaded", timeout=20000)
                    print("[login] 登录成功，等待页面生成反爬 token（__zp_stoken__）……")
                except Exception:
                    pass

        print("[!] 超时未检测到完整登录态。请重新运行本命令重试。")
        return False
    finally:
        ctx.close()


def main() -> None:
    # 本工具设计为零参数（OBS-004）：任何参数都可能是误操作，
    # 直接打印用法退出，绝不带参拉起浏览器
    if len(sys.argv) > 1:
        print(__doc__.strip()[:400])
        print("\n[!] 本工具不接受参数。直接运行 python -m src.scrapers.boss.login 即可。")
        sys.exit(2)
    sys.exit(0 if login() else 1)


if __name__ == "__main__":
    main()
