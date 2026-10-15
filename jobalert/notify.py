"""디스코드 웹후크로 알림을 보낸다."""
from __future__ import annotations

import time
from datetime import date
from typing import List, Optional

import requests

GRAY = 0x80848E
EMBEDS_PER_MESSAGE = 10


def _mmdd(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{m}.{d}"


def _dday(deadline: Optional[str], today: date) -> str:
    if not deadline:
        return ""
    if deadline == "상시":
        return "상시"
    try:
        n = (date.fromisoformat(deadline[:10]) - today).days
    except ValueError:
        return ""
    if n < 0:
        return ""
    return "D-day" if n == 0 else f"D-{n}"


def build_embed(item: dict, today: date) -> dict:
    job, verdict = item["job"], item["verdict"]
    if job.posted_at:
        when = f"📅 {_mmdd(job.posted_at)} 게시"
    else:
        when = f"📅 {_mmdd(item['first_seen'])} 발견"
    parts = [p for p in [verdict.career_label, when, _dday(job.deadline, today)] if p]
    line = "  |  ".join(parts)
    if verdict.flags:
        line += "  " + " ".join(verdict.flags)
    desc = line
    if verdict.evidence and verdict.career_label.startswith(("경력", "신입 가능", "인턴 · 경력")):
        desc += f"\n> {verdict.evidence}"
    return {
        "author": {"name": job.company + (f" · {job.extra['sub']}" if job.extra.get("sub") else "")},
        "title": job.title[:256],
        "url": job.url,
        "description": desc[:4000],
        "color": GRAY,
    }


def _post(webhook: str, payload: dict):
    for _ in range(5):
        r = requests.post(webhook, json=payload, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            continue
        r.raise_for_status()
        time.sleep(1)
        return
    raise RuntimeError("디스코드 전송 재시도 초과")


def send_jobs(webhook: str, items: List[dict], header: str, today: date, on_sent=None):
    """items를 10개씩 묶어 보낸다. 묶음이 보내질 때마다 on_sent(그 묶음)를 부른다."""
    for i in range(0, len(items), EMBEDS_PER_MESSAGE):
        chunk = items[i:i + EMBEDS_PER_MESSAGE]
        payload = {"embeds": [build_embed(it, today) for it in chunk]}
        if i == 0:
            if len(items) == 1:
                j = items[0]["job"]
                payload["content"] = f"{header} · {j.company} · {j.title}"[:2000]
            else:
                payload["content"] = f"{header} {len(items)}건"
        _post(webhook, payload)
        if on_sent:
            on_sent(chunk)


def send_text(webhook: str, text: str):
    _post(webhook, {"content": text[:2000]})
