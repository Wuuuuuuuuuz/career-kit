"""BOSS 直聘 __zp_stoken__ 计算模块。

使用 iv8 本地计算 stoken，绕过 code=37 风控。
参考：Yang-hua6/boss- 项目
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
from typing import Any

import requests as req

log = logging.getLogger(__name__)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"

# iv8 Canvas 指纹（固定值）
_CANVAS_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAB9AAAADICAYAAACwGnoBAAAAAXNSR0IArs4c6QAAIABJREFUeF7svXdAVNf2Brr2mc4wA8zQO0iv0kWNDXvvsXeKJiYxzRI1xsSSmKImKjNgLzF2E3tFY0FAsKLYEOm9DszAzOzHPlMAQaO5+eXe9x77L2XO2WefdXZd3/q+haB5iZJ8AADrInrFHXFxSWECwEVJMPzY4pr/5D/Rsf6A0TlHh1tPIiKkRQyWKl/FhUWb10pDAOFTvXpsXeHqlugPGLZLQuDAWz/qVfV7Q9lb1/V3boiU9iPv4e979kyn8AP1GMMDaQh8/tZVzYqzAEqdAADsruG/zvT2TRgJAPYAwAAEMjUFP8QFQPIb1fsf2CQ6BT4GgJ7N+0F0KnTDKvgQKCg+efa9PdnP/A62+p6vsnekdBMgHDNyxIoDZmYvuH/7O7/Ri7dfpLfA5B184Mr3AcKhjk5pY/r2je1MqeFSbAhcbbfS37UARhAl/RYAYoyMi/Z29Ds1y9T0xTNTcXYCYsOiWH8oalGz9htweDUDhw157oSJSYG6+e9qNYMhqzG2KK+w9qlT8FkMSrnRwT9l4RYPqNZfpxnLvwOADQAsdbG+90vPQT/3oRD0wgDWgIFVVWluV1Ji711WYaOurTGe+vDT7b/q79eOv0ED1563tX1Q1+L5GFHV9QaGZaU23jKZibii0rKh1f3aucTWNr22b9/YuyymAr+J9eh5cP2Or0gffNX7v7Ie3VoQsykA1NQxADADgJ9cfBK/jwjf2h0Q9MQYLBECdkMDh1tSaudRVmprW1ZmnSwvsOvz7NtvK+m627L/q9YZ7XvS2GSwInpJU7jcmkrEgHWSn3bcbPUOr1urXrYXQ1FFASzeFCcZTNbZrl32XvP2vljWYp1YtoyCXOu5gPAPAFDD41dNnzLxM1/AEAwI1JWV5qf2/vb1h0bCIothw9YkcrlVdXTbAuHyK22oXZc6ON9UurpdZ3A4skJzs6zriFJ9Kw2GG63ui47tDxgdRQhDaMhhtqPj7fvGxgWZ9Dogkd4na5yzUyq4uV0HvmH5YxNh3pL4cNVvrep53Xo4K84WKPUfAOALCO814VQsGj15QQjdl7Xfs65WaFJY5ORXUmIvyCtw35Gf5zoLpNENb9KfyTUqNYNZWWnhWFll5q6oE6gZLPnX3cxTVizrCUq6jqY2dASAvSbc8vljJy9wxwBDAcCa9CldG8rKrQVFxU6/Zj33n/pSG+g138vzcmqXLnsLKUqlaus71NUJjItL7YMVcj4HIbzbwT95jn5sa+x9UHvfV4MH/HDT2vZRXwTgrFSxhdXVYruKCguX6hpTpkJuuOZmzJEFCIF+7EUlw3cIgSe5X67gC4uLHDtRlKrewuLpdSazQdFWe/JyPfL+OD4vStduxFC9oPdiba3d2nmjd++4Wx2cU3Lo/hofm2FjnREfFHgsz8Li2Y1X9iXy8OjYmYBRPIup2DZ92kdV8np+4O3bfYPF4pwyZ+ebdyikPCINAUmzea4bYHSayWxIDQs7FGxulllkav48maLw2hb9XLtftbJ8HDdkyPcCsl8qLbPfdv9e9x8dHO+48PmVmSLjvKXxnep36etu1u8ogA9nRUazEdnjICg4dvzjAkfHtCXGRgW1puLs33nCmg9bzeMxmxxBTZ0jc7Cl9ZPoYYPXdAUAKwC4qxDDck45hJL9Eek7L9u9gvTFSnNvilIpzExfJJN55bV7bO37BQYeLwroePI2k9FQ8vhR+NoLl6ZtFwpKPAYN+imBzamjrl4ZH1AnFygjeklvcrmyqhbzQZRkHgDMj+ix5dMOrjeGIwSJkrjYNGJfe7t77w0Y8HNnjKBq764V16tkpjsA4ZNOng9muVlf/lwN1Ew7+7s35HKBqLTUNkChMCgTCIon/THkyRn63aJj54NGXw"

# stoken 缓存
_stoken_cache: dict | None = None


def _fetch_js(name: str) -> str | None:
    """下载加密 JS。"""
    js_url = f"https://www.zhipin.com/web/common/security-js/{name}.js"
    try:
        resp = req.get(js_url, headers={"User-Agent": DEFAULT_UA}, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        log.warning(f"下载 JS 失败: {e}")
        return None


def _compute_iv8(seed: str, ts: int, js_code: str, js_url: str, security_url: str) -> str | None:
    """用 iv8 计算 stoken。"""
    try:
        import iv8
    except ImportError:
        log.error("iv8 未安装，请执行: pip install iv8")
        return None

    try:
        environment = {
            "location": {
                "href": security_url,
                "origin": "https://www.zhipin.com",
                "protocol": "https:",
                "host": "www.zhipin.com",
                "hostname": "www.zhipin.com",
                "port": "",
                "pathname": "/web/common/security-check.html",
                "search": "?" + security_url.split("?", 1)[1] if "?" in security_url else "",
                "hash": "",
            },
            "canvas": {"fingerprint": {"toDataURL": {"png": _CANVAS_PNG}}},
            "window": {"origin": "https://www.zhipin.com"},
        }
        html_page = (
            "<!DOCTYPE html><html><head></head><body>"
            f'<script src="{js_url}"></script>'
            "</body></html>"
        )
        with iv8.JSContext(
            environment=environment,
            config={"timezone": "Asia/Shanghai"},
        ) as ctx:
            ctx.expose(
                {
                    "baseURL": environment["location"]["href"],
                    "html": html_page,
                    "headers": [],
                    "resources": {js_url: js_code},
                },
                "snapshot",
            )
            ctx.eval("__iv8__.page.load(__iv8__.data.snapshot)")
            seed_escaped = json.dumps(seed, ensure_ascii=False)
            token = ctx.eval(f"(new window.ABC).z({seed_escaped}, {int(ts)});")
        return str(token)
    except Exception as e:
        log.warning(f"iv8 计算失败: {e}")
        return None


def compute_stoken(seed: str, ts: int, name: str) -> str | None:
    """计算 __zp_stoken__，缓存结果。"""
    js_code = _fetch_js(name)
    if not js_code:
        return None

    js_url = f"https://www.zhipin.com/web/common/security-js/{name}.js"
    security_url = (
        f"https://www.zhipin.com/web/common/security-check.html"
        f"?seed={urllib.parse.quote(str(seed))}&name={name}&ts={ts}&callbackUrl=&srcReferer"
    )

    token = _compute_iv8(seed, int(ts), js_code, js_url, security_url)
    if token:
        global _stoken_cache
        _stoken_cache = {"token": token, "expires_at": time.time() + 20 * 60}
        log.info(f"stoken 计算成功: {token[:8]}...")
    return token


def get_stoken() -> str | None:
    """获取 stoken（从缓存）。"""
    global _stoken_cache
    if _stoken_cache and time.time() < _stoken_cache["expires_at"]:
        return _stoken_cache["token"]
    return None


def invalidate_stoken() -> None:
    """清除 stoken 缓存。"""
    global _stoken_cache
    _stoken_cache = None


def handle_code37(res_json: dict) -> str | None:
    """处理 code=37 响应，计算新的 stoken。"""
    zp_data = res_json.get("zpData") or {}
    seed = zp_data.get("seed")
    ts = zp_data.get("ts")
    name = zp_data.get("name")
    if not seed or not ts or not name:
        log.error(f"code37 响应中缺少 seed/ts/name: {zp_data}")
        return None

    log.info(f"触发 code37，重新计算 stoken（name={name}）")
    invalidate_stoken()
    return compute_stoken(seed, ts, name)