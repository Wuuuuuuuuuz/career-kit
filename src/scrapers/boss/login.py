"""BOSS 直聘登录工具——两步法，规避前端 CDP 检测自杀。

背景：BOSS 前端检测到调试协议附着（Runtime.enable 等特征）后约 5 秒
清空页面并跳 about:blank。因此本工具绝不附着浏览器：

step1：subprocess 拉起纯净 Chrome（独立 profile + remote-debugging-port），
       脚本不等待、零附着，用户从容扫码登录。
step2：裸 WebSocket 只调用 Storage.getCookies 读取 cookies，
       按 auth.py 格式落盘，供 fetch_company_jobs 使用。

用法：
    python -m src.scrapers.boss.login            # 完整流程：拉起→扫码→回车→读取
    python -m src.scrapers.boss.login step1      # 仅启动浏览器后退出
    python -m src.scrapers.boss.login step2      # 仅读取并保存（可反复执行）
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None

from .auth import has_valid_cookies, save_cookies

CDP_PORT = 9333
CHROME_PROFILE_DIR = Path(tempfile.gettempdir()) / "ck_boss_chrome_prof"

# Chrome 可执行文件探测顺序：环境变量 > 常见安装位置 > PATH
_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
]


def find_chrome() -> str | None:
    """定位 Chrome 可执行文件。可用环境变量 BOSS_CHROME_PATH 覆盖。"""
    override = os.environ.get("BOSS_CHROME_PATH")
    if override and Path(override).exists():
        return override
    for candidate in _CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return shutil.which("chrome") or shutil.which("google-chrome")


def cdp_alive(port: int = CDP_PORT) -> bool:
    """检测调试端口是否就绪。"""
    try:
        return httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=2).status_code == 200
    except Exception:
        return False


def step1(port: int = CDP_PORT) -> bool:
    """拉起纯净 Chrome 并立即退出——零附着，页面不会被反爬清掉。"""
    chrome = find_chrome()
    if not chrome:
        print("[!] 未找到 Chrome。可通过环境变量 BOSS_CHROME_PATH 指定路径。")
        return False

    subprocess.Popen([
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.zhipin.com/",
    ])

    for _ in range(20):
        time.sleep(0.7)
        if cdp_alive(port):
            break

    ok = cdp_alive(port)
    print(
        f"[step1] Chrome 已启动（CDP 存活={ok}）。请在浏览器中完成扫码登录。\n"
        "[step1] 本脚本不等待也不附着浏览器——页面不会消失。"
    )
    return ok


async def _read_cookies_via_ws(port: int) -> list[dict]:
    """直连 browser 端 WebSocket，仅调用 Storage.getCookies。

    刻意不启用 Runtime/Runtime.evaluate 域——那是 BOSS 反爬的检测面。
    """
    info = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=5).json()
    ws_url = info["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)
            if msg.get("id") == 1:
                return msg.get("result", {}).get("cookies", [])


def step2(port: int = CDP_PORT) -> bool:
    """读取 zhipin cookies 并落盘；返回是否获得有效登录态。"""
    if websockets is None:
        print("[!] 缺少依赖：pip install websockets")
        return False
    if not cdp_alive(port):
        print("[!] 调试端口不在线，请先执行 step1 启动浏览器。")
        return False

    cookies = asyncio.run(_read_cookies_via_ws(port))
    zhipin = {
        c["name"]: c["value"]
        for c in cookies
        if "zhipin.com" in (c.get("domain") or "")
    }
    print(f"[step2] 共 {len(cookies)} 条 cookies，其中 zhipin {len(zhipin)} 条；"
          f"wt2={'有' if 'wt2' in zhipin else '无'}")

    save_cookies(zhipin)
    ok = has_valid_cookies()
    if not ok:
        print("[step2] 尚未登录或读取过早——请在浏览器完成扫码后再执行一次 step2。")
        return False
    print("[step2] 登录态已保存，fetch_company_jobs(company=\"boss\") 现在可用。")
    return True


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    port = int(sys.argv[2]) if len(sys.argv) > 2 else CDP_PORT

    if mode == "step1":
        sys.exit(0 if step1(port) else 1)
    if mode == "step2":
        sys.exit(0 if step2(port) else 1)

    # 默认完整流程：启动 → 用户扫码 → 回车确认 → 读取落盘
    if not step1(port):
        sys.exit(1)
    input("\n[login] 在浏览器完成扫码登录后，回到这里按回车读取 cookies...")
    sys.exit(0 if step2(port) else 1)


if __name__ == "__main__":
    main()
