"""BOSS 直聘登录态管理。

职责：
- 加载/保存 cookies
- 检查 cookies 有效性
"""

from __future__ import annotations

import json
from pathlib import Path

AUTH_STATE_PATH = Path(__file__).parent / "cache" / "auth" / "state.json"


def load_cookies() -> dict[str, str]:
    """加载 cookies，返回 {name: value} 字典。"""
    if not AUTH_STATE_PATH.exists():
        return {}
    try:
        state = json.loads(AUTH_STATE_PATH.read_text(encoding="utf-8"))
        cookies = state.get("cookies", [])
        return {c["name"]: c["value"] for c in cookies}
    except Exception:
        return {}


def save_cookies(cookies: dict[str, str]) -> None:
    """保存 cookies 到文件。"""
    AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "cookies": [
            {
                "name": k,
                "value": v,
                "domain": ".zhipin.com",
                "path": "/",
                "httpOnly": k in ("wt2", "zp_at", "wbg"),
                "secure": k == "bst",
                "sameSite": "Lax",
            }
            for k, v in cookies.items()
        ],
        "origins": [],
    }
    AUTH_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def has_valid_cookies() -> bool:
    """检查是否有有效的 cookies。"""
    cookies = load_cookies()
    return bool(cookies.get("wt2"))