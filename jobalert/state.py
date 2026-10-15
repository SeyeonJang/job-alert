"""이미 본 공고·보낸 공고 기록 (state/seen.json)."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "state" / "seen.json"
SAME_TITLE_DAYS = 30      # 같은 회사·같은 직무명이 이 기간 안에 다시 올라오면 안 보냄
FORGET_AFTER_DAYS = 180   # 목록에서 사라진 지 이만큼 지난 공고는 기록에서 지움


def _title_key(company: str, title: str) -> str:
    return company + "|" + re.sub(r"\s+", " ", title).strip().lower()


class State:
    def __init__(self, data: dict):
        self.data = data
        data.setdefault("version", 1)
        data.setdefault("companies", {})
        data.setdefault("jobs", {})
        data.setdefault("sent_titles", {})

    @classmethod
    def load(cls) -> "State":
        if PATH.exists():
            return cls(json.loads(PATH.read_text(encoding="utf-8")))
        return cls({})

    def save(self):
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    # 회사
    def company(self, name: str) -> dict:
        return self.data["companies"].setdefault(name, {"initialized": False, "last_count": 0, "fail_streak": 0})

    # 공고
    def job(self, key: str):
        return self.data["jobs"].get(key)

    def touch(self, key: str, today: date):
        rec = self.data["jobs"].get(key)
        if rec:
            rec["last_seen"] = today.isoformat()

    def first_seen(self, key: str, today: date) -> str:
        rec = self.data["jobs"].get(key)
        return rec["first_seen"] if rec else today.isoformat()

    def mark(self, key: str, title: str, status: str, today: date, reason: str = ""):
        rec = self.data["jobs"].setdefault(key, {"first_seen": today.isoformat(), "attempts": 0})
        rec.update({"title": title, "status": status, "reason": reason, "last_seen": today.isoformat()})
        return rec

    def bump_attempt(self, key: str, title: str, today: date) -> int:
        rec = self.mark(key, title, "pending", today, "상세 페이지 확인 실패")
        rec["attempts"] = rec.get("attempts", 0) + 1
        return rec["attempts"]

    # 30일 내 같은 제목
    def recently_sent(self, company: str, title: str, today: date) -> bool:
        d = self.data["sent_titles"].get(_title_key(company, title))
        return bool(d) and (today - date.fromisoformat(d)).days < SAME_TITLE_DAYS

    def remember_sent(self, company: str, title: str, today: date):
        self.data["sent_titles"][_title_key(company, title)] = today.isoformat()

    def prune(self, today: date):
        cutoff = (today - timedelta(days=FORGET_AFTER_DAYS)).isoformat()
        jobs = self.data["jobs"]
        for k in [k for k, v in jobs.items() if v.get("last_seen", "") < cutoff]:
            del jobs[k]
        tcut = (today - timedelta(days=SAME_TITLE_DAYS * 2)).isoformat()
        st = self.data["sent_titles"]
        for k in [k for k, v in st.items() if v < tcut]:
            del st[k]
