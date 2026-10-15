"""HTTP 요청과 (필요할 때만) 헤드리스 브라우저."""
from __future__ import annotations

import json
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6"})


def get(url: str, *, tries: int = 3, **kw) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            r = _session.get(url, timeout=kw.pop("timeout", 30), **kw)
            if r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} {url}")
            r.raise_for_status()
            time.sleep(0.4)  # 사이트에 부담 주지 않도록
            return r
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise last


def post(url: str, *, tries: int = 3, **kw) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            r = _session.post(url, timeout=kw.pop("timeout", 30), **kw)
            r.raise_for_status()
            time.sleep(0.4)
            return r
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise last


def get_text(url: str, **kw) -> str:
    r = get(url, **kw)
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def get_json(url: str, **kw):
    return get(url, **kw).json()


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def html_to_text(html: str) -> str:
    """상세 페이지 HTML에서 본문 텍스트를 줄 단위로 뽑는다."""
    s = soup(html)
    for tag in s(["script", "style", "noscript", "svg", "header", "footer", "nav", "form"]):
        tag.decompose()
    # 줄바꿈이 사라지지 않도록 블록 요소 뒤에 개행을 넣는다
    for br in s.find_all("br"):
        br.replace_with("\n")
    text = s.get_text("\n")
    lines = [re.sub(r"[ \t ​]+", " ", l).strip() for l in text.splitlines()]
    return "\n".join(l for l in lines if l)


def next_data(html: str) -> Optional[dict]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


# ── 헤드리스 브라우저 (자바스크립트로만 그려지는 사이트용) ─────────────
_pw = None
_browser = None


def browser():
    global _pw, _browser
    if _browser is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch()
    return _browser


def render(url: str, *, scrolls: int = 4, wait_ms: int = 1200, capture_json: bool = False):
    """페이지를 브라우저로 열어 (html, anchors, json_responses)를 돌려준다."""
    page = browser().new_page(user_agent=UA, locale="ko-KR")
    captured = []
    if capture_json:
        def on_response(resp):
            try:
                if "json" in resp.headers.get("content-type", ""):
                    captured.append((resp.url, resp.json()))
            except Exception:
                pass
        page.on("response", on_response)
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        for _ in range(scrolls):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(wait_ms)
        html = page.content()
        anchors = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim()}))")
        return html, anchors, captured
    finally:
        page.close()


def close():
    global _pw, _browser
    if _browser is not None:
        _browser.close()
        _pw.stop()
        _browser = _pw = None
