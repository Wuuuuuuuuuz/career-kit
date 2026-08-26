"""BOSS 直聘登录工具——patchright（driver 层反检测 fork）驱动。

为什么不用 vanilla Playwright：它对每个页面必然调用 CDP Runtime.enable，
BOSS 前端用 Error.stack 序列化技巧检测该调用，附着后约 5 秒页面自杀。
用户层 stealth 插件救不了驱动层泄漏——已实测证伪。
为什么选 patchright：把 Runtime.enable 替换为 isolated world 方案，
从驱动层消除该检测向量；2026-08-26 实测 zhipin.com 页面 60 秒存活通过。

流程（一条命令到底，全程免手动确认）：
    python -m src.scrapers.boss.login
      → patchright 拉起真实 Chrome（独立 profile）
      → 打开 zhipin.com，等待扫码
      → 每 2 秒轮询 cookies，发现 wt2 立即落盘并退出

依赖：pip install patchright（版本必须 pin 死——该 fork 跟随上游节奏紧，
浮动依赖可能在某次升级后静默失效）；浏览器用系统 Chrome（channel="chrome"），
无需 patchright install 下载内核；未装 Chrome 时回退 chromium 并提示安装。
"""

from __future__ import annotations

import sys
import time

from ...paths import CACHE_DIR
from .auth import has_valid_cookies, save_cookies

# 浏览器 profile 属用户资产，与登录态同住 ~/.career-kit/cache/boss/
PROFILE_DIR = CACHE_DIR / "boss" / "chrome_profile"
POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 300.0
ZHIPIN_URL = "https://www.zhipin.com/"


def _launch(p):
    """启动持久化上下文。四件套缺一不可（patchright README 推荐配置）。"""
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        channel="chrome",   # 真实 Google Chrome；无则回退 chromium
        headless=False,     # headless 本身就是被检测特征
        no_viewport=True,   # 不强制视口，贴近真人分辨率分布
    )


def login() -> bool:
    """打开 BOSS 登录页并轮询 cookies，wt2 出现即落盘。返回是否成功。"""
    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        print("[!] 缺少依赖：pip install patchright==1.62.1")
        return False

    with sync_playwright() as p:
        ctx = _launch(p)

        # 导航到登录页——persistent context 新 profile 无历史会话，必须显式打开
        # （BUG-009：缺失此步会弹出永久空白窗口）
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(ZHIPIN_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            print(f"[!] 打开 zhipin.com 失败：{exc}\n[!] 请检查网络后重新运行本命令。")
            ctx.close()
            return False

        print("[login] Chrome 已启动，请扫码登录……检测到登录态将自动保存退出"
              f"（最长等待 {int(POLL_TIMEOUT_SEC)} 秒）")
        deadline = time.time() + POLL_TIMEOUT_SEC

        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)
            cookies = ctx.cookies(ZHIPIN_URL)
            named = {c["name"]: c["value"] for c in cookies}
            if not named.get("wt2"):
                continue
            save_cookies(named)
            print(f"[login] ✓ 检测到 wt2，共 {len(named)} 条 cookies 已落盘。"
                  'fetch_company_jobs(company="boss") 现在可用。')
            ctx.close()
            return True

        print("[!] 超时未检测到登录态。请重新运行本命令重试。")
        ctx.close()
        return False


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
