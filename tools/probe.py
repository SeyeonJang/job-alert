"""개발용: 각 채용 페이지의 원본 HTML과 화면이 불러오는 JSON을 저장한다.

python tools/probe.py <sheet_csv_url> <out_dir> [회사명 ...]
"""
import csv
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


def slug(name):
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", name).strip("_")


def load_sheet(url):
    r = requests.get(url, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    out = []
    for row in rows[1:]:
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            out.append((row[0].strip(), row[1].strip()))
    return out


def probe(name, url, out, browser):
    d = out / slug(name)
    d.mkdir(parents=True, exist_ok=True)
    meta = {"name": name, "url": url}
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
        meta["static_status"] = r.status_code
        meta["static_final_url"] = r.url
        (d / "static.html").write_text(r.text, encoding="utf-8")
    except Exception as e:
        meta["static_error"] = repr(e)

    jsons = []
    page = browser.new_page(user_agent=UA, locale="ko-KR")

    def on_response(resp):
        try:
            ct = resp.headers.get("content-type", "")
            if "json" not in ct and not resp.url.endswith(".json"):
                return
            if resp.request.resource_type not in ("xhr", "fetch", "document", "other"):
                return
            body = resp.text()
            jsons.append({
                "url": resp.url, "status": resp.status, "method": resp.request.method,
                "post_data": resp.request.post_data, "len": len(body), "body": body[:400000],
            })
        except Exception as e:  # noqa
            jsons.append({"url": resp.url, "error": repr(e)})

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        for _ in range(6):
            page.mouse.wheel(0, 4000)
            time.sleep(1.2)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        (d / "rendered.html").write_text(page.content(), encoding="utf-8")
        anchors = page.eval_on_selector_all(
            "a", "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim().slice(0,300), onclick: e.getAttribute('onclick')}))")
        (d / "anchors.json").write_text(json.dumps(anchors, ensure_ascii=False, indent=1), encoding="utf-8")
        meta["rendered_final_url"] = page.url
        meta["anchor_count"] = len(anchors)
    except Exception as e:
        meta["render_error"] = repr(e)
    finally:
        page.close()
    (d / "xhr.json").write_text(json.dumps(jsons, ensure_ascii=False, indent=1), encoding="utf-8")
    meta["xhr_count"] = len(jsons)
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(name, meta.get("static_status"), meta.get("anchor_count"), meta.get("xhr_count"),
          meta.get("render_error", ""), flush=True)


def main():
    sheet, out = sys.argv[1], Path(sys.argv[2])
    only = set(sys.argv[3:])
    out.mkdir(parents=True, exist_ok=True)
    targets = load_sheet(sheet) if sheet.startswith("http") else []
    extra = Path("tools/probe_extra.txt")
    if extra.exists():
        for line in extra.read_text(encoding="utf-8").splitlines():
            if "," in line and not line.startswith("#"):
                n, u = line.split(",", 1)
                targets.append((n.strip(), u.strip()))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, url in targets:
            if only and name not in only:
                continue
            probe(name, url, out, browser)
        browser.close()


if __name__ == "__main__":
    main()
