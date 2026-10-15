"""한 번 실행: 시트의 회사들을 돌면서 새 공고를 찾아 디스코드로 보낸다.

환경변수
  DISCORD_WEBHOOK_URL  디스코드 웹후크 주소
  SHEET_CSV_URL        회사 목록 구글 시트 링크 (없으면 tools/test_companies.csv)
  DRY_RUN=1            디스코드로 보내지 않고 report.md 만 만든다 (기록도 저장 안 함)
  ONLY=당근,컬리        일부 회사만 실행
"""
from __future__ import annotations

import os
import sys
import traceback
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import filters, net, notify, sheet
from .adapters import pick_adapter
from .models import Verdict
from .state import State

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent


def _short(e: Exception) -> str:
    s = f"{type(e).__name__}: {e}"
    return s if len(s) < 180 else s[:180] + "…"


def run():
    today = datetime.now(KST).date()
    dry = os.environ.get("DRY_RUN") == "1"
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    source = os.environ.get("SHEET_CSV_URL", "").strip() or str(ROOT / "tools" / "test_companies.csv")
    only = {s.strip() for s in os.environ.get("ONLY", "").split(",") if s.strip()}
    if not dry and not webhook:
        sys.exit("DISCORD_WEBHOOK_URL 이 비어 있어. 레포 Settings → Secrets 에 넣어줘.")
    state = State.load() if (not dry or os.environ.get("USE_STATE") == "1") else State({})

    report = [f"# 실행 결과 {datetime.now(KST):%Y-%m-%d %H:%M} KST", ""]
    warnings, initial, new = [], [], []

    try:
        companies = sheet.load(source)
    except Exception as e:
        companies = []
        warnings.append(f"⚠️ 회사 목록 시트를 읽지 못했어 — {_short(e)}")

    for name, url in companies:
        if only and name not in only:
            continue
        comp = state.company(name)
        adapter = pick_adapter(name, url)
        try:
            jobs = adapter.fetch_list()
            if not jobs and comp.get("last_count", 0) >= 3:
                raise RuntimeError("공고가 0건으로 나와. 사이트 구조가 바뀌었을 수 있어")
        except Exception as e:
            comp["fail_streak"] = comp.get("fail_streak", 0) + 1
            if comp["fail_streak"] == 1:
                if adapter.name == "generic" and not comp.get("initialized"):
                    warnings.append(f"⚠️ {name} 링크 자동 인식 실패 — 맞춤 수집기가 필요해 ({url})")
                else:
                    warnings.append(f"⚠️ {name} 수집 실패 — {_short(e)}")
            report += [f"## {name} ({adapter.name}) — 실패", "", f"`{_short(e)}`", ""]
            traceback.print_exc()
            continue

        initialized = comp.get("initialized", False)
        stats = Counter()
        sent_lines, filtered_lines = [], []
        for job in jobs:
            rec = state.job(job.key)
            if rec and rec.get("status") in ("sent", "filtered"):
                state.touch(job.key, today)
                stats["이미 봄"] += 1
                continue
            try:
                v = filters.judge(job, adapter.fetch_body, adapter.enrich)
            except Exception as e:
                traceback.print_exc()
                v = Verdict(False, reason=f"판단 오류 {_short(e)}", retry=True)
            if v.retry:
                if state.bump_attempt(job.key, job.title, today) < 3:
                    stats["다음에 재시도"] += 1
                    filtered_lines.append(f"- ⏳ {job.title} — {v.reason}")
                    continue
                v = Verdict(True, career_label="경력 확인 필요", flags=["⚠️상세 확인 실패"])
            if v.send and state.recently_sent(name, job.title, today):
                v = Verdict(False, reason="30일 안에 같은 제목을 보냄")
            if not v.send:
                state.mark(job.key, job.title, "filtered", today, v.reason)
                stats["제외"] += 1
                filtered_lines.append(f"- {job.title} — {v.reason}  `{job.career}|{job.employment}|{job.category}`")
                continue
            stats["보냄"] += 1
            item = {"job": job, "verdict": v, "first_seen": state.first_seen(job.key, today)}
            (new if initialized else initial).append(item)
            ev = f" — {v.evidence}" if v.evidence else ""
            sent_lines.append(f"- **{job.title}** · {v.career_label} {' '.join(v.flags)}{ev}  `{job.career}|{job.employment}|{job.category}`  {job.url}")

        comp.update(initialized=True, last_count=len(jobs), fail_streak=0, adapter=adapter.name)
        report += [f"## {name} ({adapter.name}) — {len(jobs)}건 · " + ", ".join(f"{k} {v}" for k, v in stats.items()), ""]
        report += sent_lines + ([""] if sent_lines else []) + filtered_lines + [""]
        print(f"{name}: {len(jobs)} {dict(stats)}", flush=True)

    net.close()

    def on_sent(chunk):
        for it in chunk:
            j = it["job"]
            state.mark(j.key, j.title, "sent", today)
            state.remember_sent(j.company, j.title, today)

    try:
        if not dry and webhook:
            if initial:
                notify.send_jobs(webhook, initial, "📌 지금 열려 있는 공고", today, on_sent)
            if new:
                notify.send_jobs(webhook, new, "🆕 새 공고", today, on_sent)
            for w in warnings:
                notify.send_text(webhook, w)
    finally:
        state.prune(today)
        if not dry:
            state.save()
        report = report[:1] + ["", f"보낼 공고: 처음 {len(initial)}건, 새 공고 {len(new)}건", ""] + \
            [f"- {w}" for w in warnings] + [""] + report[1:]
        (ROOT / "report.md").write_text("\n".join(report), encoding="utf-8")
        print(f"initial={len(initial)} new={len(new)} warnings={len(warnings)}")


if __name__ == "__main__":
    run()
