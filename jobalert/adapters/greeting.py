"""그리팅(greetinghr) 채용 페이지.

그리팅 채용 페이지는 공고 목록을 페이지 안의 __NEXT_DATA__ 에 넣어서 보낸다.
제목, 직군, 경력(신입/경력 N년/무관), 고용형태, 게시일, 마감일이 다 들어 있다.
목록이 그리팅 바깥(회사 자체 사이트)에 있고 링크만 그리팅으로 걸린 경우에는
상세 페이지에서 같은 정보를 채운다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from .. import net
from ..models import Job
from .base import Adapter

KST = timezone(timedelta(hours=9))
OPENING_RE = re.compile(r"/o/(\d+)")
EMPLOYMENT = {
    "FULL_TIME_WORKER": "정규직", "CONTRACT_WORKER": "계약직", "INTERN_WORKER": "인턴",
    "PART_TIME_WORKER": "아르바이트", "FREELANCER": "프리랜서", "DISPATCH_WORKER": "파견직",
}


def kst_date(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.date().isoformat()
        return dt.astimezone(KST).date().isoformat()
    except ValueError:
        return iso[:10]


def career_text(c: dict) -> str:
    t = (c or {}).get("careerType") or (c or {}).get("type")
    f = (c or {}).get("careerFrom", (c or {}).get("from"))
    to = (c or {}).get("careerTo", (c or {}).get("to"))
    if t in ("NEW_COMER", "NEWCOMER"):
        return "신입"
    if t in ("NOT_MATTER", "IRRELEVANT"):
        return "경력 무관"
    if t == "EXPERIENCED":
        if f is not None and to is not None:
            return f"경력 {f}~{to}년"
        if f is not None:
            return f"경력 {f}년 이상"
        return "경력"
    return ""


def _career_rank(c: dict) -> int:
    t = (c or {}).get("careerType")
    if t in ("NEW_COMER", "NOT_MATTER"):
        return -1
    f = (c or {}).get("careerFrom")
    return f if isinstance(f, int) else 99


def _queries(html: str) -> list:
    nd = net.next_data(html) or {}
    return (((nd.get("props") or {}).get("pageProps") or {}).get("dehydratedState") or {}).get("queries") or []


def openings_from_html(html: str) -> Optional[list]:
    for q in _queries(html):
        if q.get("queryKey") == ["openings"]:
            return (q.get("state") or {}).get("data") or []
    return None


def fill_from_positions(job: Job, positions: list):
    """여러 포지션이 묶인 공고는 가장 문턱이 낮은 포지션을 기준으로 삼는다."""
    if not positions:
        return
    best = min(positions, key=lambda p: _career_rank(p.get("jobPositionCareer")))
    job.career = career_text(best.get("jobPositionCareer"))
    emp = (best.get("jobPositionEmployment") or {}).get("employmentType")
    job.employment = EMPLOYMENT.get(emp, emp or "")
    cats = []
    for p in positions:
        for key, field in (("workspaceOccupation", "occupation"), ("workspaceJob", "job")):
            v = (p.get(key) or {}).get(field)
            if v and v not in cats:
                cats.append(v)
    job.category = " / ".join(cats)


class GreetingAdapter(Adapter):
    name = "greeting"

    def __init__(self, company, url):
        super().__init__(company, url)
        self._detail_cache = {}

    def fetch_list(self) -> List[Job]:
        html = net.get_text(self.url)
        ops = openings_from_html(html)
        if ops is not None:
            return [self._from_opening(o) for o in ops if o.get("deploy", True)]
        # 회사 자체 페이지에 그리팅 공고 링크만 있는 경우
        jobs = self._from_links(html)
        if not jobs:
            html, _, _ = net.render(self.url)
            jobs = self._from_links(html)
        return jobs

    def _origin(self) -> str:
        u = urlparse(self.url)
        return f"{u.scheme}://{u.netloc}"

    def _locale(self) -> str:
        seg = urlparse(self.url).path.strip("/").split("/")
        return seg[0] if seg and seg[0] in ("ko", "en", "ja") else "ko"

    def _from_opening(self, o: dict) -> Job:
        oid = str(o.get("openingId"))
        job = Job(
            company=self.company, job_id=oid, title=(o.get("title") or "").strip(),
            url=f"{self._origin()}/{self._locale()}/o/{oid}",
            posted_at=kst_date(o.get("openDate")), deadline=kst_date(o.get("dueDate")),
        )
        fill_from_positions(job, ((o.get("openingJobPosition") or {}).get("openingJobPositions") or []))
        div = (o.get("workspaceDivision") or {}).get("division")
        if div:
            job.extra["division"] = div
        return job

    def _from_links(self, html: str) -> List[Job]:
        s = net.soup(html)
        jobs, seen = [], set()
        for a in s.select('a[href*="/o/"]'):
            href = urljoin(self.url, a.get("href", ""))
            m = OPENING_RE.search(href)
            if not m or "greetinghr.com" not in href and urlparse(href).netloc != urlparse(self.url).netloc:
                continue
            oid = m.group(1)
            title = a.get_text(" ", strip=True)
            if oid in seen or not title:
                continue
            seen.add(oid)
            job = Job(company=self.company, job_id=oid, title=title, url=href)
            job.extra["needs_detail"] = True
            jobs.append(job)
        return jobs

    # 상세 페이지
    def _detail(self, job: Job) -> Optional[dict]:
        if job.job_id in self._detail_cache:
            return self._detail_cache[job.job_id]
        html = net.get_text(job.url)
        data = None
        for q in _queries(html):
            if len(q.get("queryKey") or []) > 1 and q["queryKey"][1] == "getOpeningById":
                data = ((q.get("state") or {}).get("data") or {}).get("data")
        self._detail_cache[job.job_id] = {"data": data, "html": html}
        return self._detail_cache[job.job_id]

    def enrich(self, job: Job):
        if not job.extra.get("needs_detail"):
            return
        d = self._detail(job)
        data = (d or {}).get("data") or {}
        info = data.get("openingsInfo") or {}
        if info.get("title"):
            job.title = info["title"].strip()
        job.posted_at = kst_date(info.get("openDate"))
        job.deadline = kst_date(info.get("dueDate"))
        fill_from_positions(job, (data.get("jobPositionSetting") or {}).get("jobPositions") or [])
        job.extra["needs_detail"] = False

    def fetch_body(self, job: Job) -> Optional[str]:
        if job.body:
            return job.body
        try:
            d = self._detail(job)
            info = ((d.get("data") or {}).get("openingsInfo") or {})
            html = info.get("detail") or d.get("html") or ""
            job.body = net.html_to_text(html)
            return job.body
        except Exception:
            return None
