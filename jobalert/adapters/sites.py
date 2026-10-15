"""회사·솔루션별 수집기.

각 사이트가 화면을 그릴 때 쓰는 공개 데이터(JSON 또는 HTML)를 그대로 읽는다.
"""
from __future__ import annotations

import html as htmllib
import json
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from .. import net
from ..models import Job
from .base import Adapter
from .greeting import GreetingAdapter, career_text, kst_date


def _meta(job_meta: list) -> dict:
    return {m.get("name"): m.get("value") for m in (job_meta or [])}


def _date(s: Optional[str]) -> Optional[str]:
    """'2026.10.13', '2026. 10. 13.', '2026-10-13 10:00' → '2026-10-13'"""
    if not s:
        return None
    m = re.search(r"(20\d\d)\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})", s)
    if not m:
        return None
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


# ── Greenhouse (당근) ───────────────────────────────────────────────
class GreenhouseAdapter(Adapter):
    """Greenhouse 공개 Job Board API. 당근은 당근·당근페이 보드가 따로 있다."""

    name = "greenhouse"
    BOARDS = {"careers.daangn.com": ["daangn", "daangnpay"]}

    def boards(self) -> List[str]:
        host = urlparse(self.url).netloc
        if host in self.BOARDS:
            return self.BOARDS[host]
        m = re.search(r"greenhouse\.io/(?:v1/boards/)?([\w-]+)", self.url)
        return [m.group(1)] if m else []

    def detail_url(self, gh: dict) -> str:
        if "careers.daangn.com" in self.url:
            return f"https://careers.daangn.com/jobs/role/{gh['id']}/"
        return gh.get("absolute_url")

    def fetch_list(self) -> List[Job]:
        jobs = []
        ok = False
        for board in self.boards():
            try:
                data = net.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true", tries=2)
            except Exception:
                continue
            ok = True
            for gh in data.get("jobs", []):
                md = _meta(gh.get("metadata"))
                job = Job(
                    company=self.company, job_id=str(gh["id"]), title=gh["title"].strip(),
                    url=self.detail_url(gh),
                    employment=md.get("Employment Type") or "",
                    career=md.get("Prior Experience") or "",
                    category=" / ".join(x for x in [md.get("Division") or "", ", ".join(d["name"] for d in gh.get("departments") or [])] if x),
                    keywords=md.get("Keywords") or "",
                    posted_at=kst_date(gh.get("first_published")),
                    deadline=_date(md.get("Valid Through") or gh.get("application_deadline")),
                    body=net.html_to_text(htmllib.unescape(gh.get("content") or "")),
                )
                sub = md.get("Corporate")
                if sub and sub not in self.company:
                    job.extra["sub"] = sub
                jobs.append(job)
        if not ok:
            raise RuntimeError("Greenhouse 데이터를 받지 못했어")
        if "careers.daangn.com" in self.url:
            jobs += self._site_only(jobs)
        return jobs

    def _site_only(self, have: List[Job]) -> List[Job]:
        """당근 채용 페이지에는 있는데 Greenhouse 보드에 없는 공고 (다른 보드 소속)."""
        known = {j.job_id for j in have}
        s = net.soup(net.get_text(self.url))
        out = []
        for a in s.select('a[href*="/jobs/role/"]'):
            m = re.search(r"/jobs/role/(\d+)", a.get("href", ""))
            parts = [p.strip() for p in a.get_text("\n").split("\n") if p.strip()]
            if not m or m.group(1) in known or not parts:
                continue
            known.add(m.group(1))
            job = Job(company=self.company, job_id=m.group(1), title=parts[0],
                      url=f"https://careers.daangn.com/jobs/role/{m.group(1)}/")
            for p in parts[1:]:
                if p in ("정규직", "계약직", "인턴") or "인턴" in p:
                    job.employment = p
                elif p not in ("추천",) and not p.startswith("D -"):
                    job.extra.setdefault("sub", p) if p != "당근" else None
            out.append(job)
        return out


# ── 토스 (Greenhouse 기반 자체 API) ─────────────────────────────────
class TossAdapter(Adapter):
    name = "toss"
    API = "https://api-public.toss.im/api/v3/ipd-eggnog/career/job-groups"

    def fetch_list(self) -> List[Job]:
        data = net.get_json(self.API, timeout=60)
        jobs = []
        for g in data.get("success") or []:
            pj = g.get("primary_job") or {}
            md = _meta(pj.get("metadata"))
            subs = []
            for j in g.get("jobs") or [pj]:
                s = _meta(j.get("metadata")).get("포지션의 소속 자회사를 선택해 주세요.")
                if s and s not in subs:
                    subs.append(s)
            desc = next((v for k, v in md.items() if k and k.startswith("Job Description")), "") or ""
            gid = g.get("id") or pj.get("id")
            job = Job(
                company=self.company, job_id=str(gid), title=(g.get("title") or pj.get("title") or "").strip(),
                url=f"https://toss.im/career/job-detail?job_id={gid}",
                employment=md.get("Employment_Type") or "",
                category=md.get("커리어 페이지 노출 Job Category 값을 선택해주세요") or "",
                keywords=" ".join(str(v) for k, v in md.items() if k and "키워드" in k and v),
                posted_at=kst_date(pj.get("first_published")),
                deadline=_date(next((v for k, v in md.items() if k and "클로징 일자" in k and v), None)),
                body=desc,
            )
            if subs and subs != ["토스"]:
                job.extra["sub"] = ", ".join(subs)
            jobs.append(job)
        return jobs


# ── 카카오 ─────────────────────────────────────────────────────────
class KakaoAdapter(Adapter):
    name = "kakao"

    def fetch_list(self) -> List[Job]:
        q = {k: v[0] for k, v in parse_qs(urlparse(self.url).query).items()}
        params = {"skillSet": q.get("skillSet", ""), "part": q.get("part", ""),
                  "company": q.get("company", "KAKAO"), "employeeType": q.get("employeeType", ""),
                  "keyword": q.get("keyword", "")}
        jobs, page = [], 1
        while True:
            params["page"] = page
            d = net.get_json("https://careers.kakao.com/public/api/job-list?" + urlencode(params))
            for j in d.get("jobList") or []:
                if j.get("closeFlag") or j.get("privateFlag"):
                    continue
                body = "\n".join([
                    net.html_to_text(htmllib.unescape(j.get("workContentDesc") or "")),
                    "자격요건",
                    net.html_to_text(htmllib.unescape(j.get("qualification") or "")),
                ])
                job = Job(
                    company=self.company, job_id=j["realId"], title=(j.get("jobOfferTitle") or "").strip(),
                    url=f"https://careers.kakao.com/jobs/{j['realId']}",
                    employment=j.get("employeeTypeName") or "", category=j.get("jobTypeName") or "",
                    posted_at=_date(j.get("regDate")), deadline=_date(j.get("endDate")), body=body,
                )
                if j.get("companyName") and j["companyName"] not in self.company:
                    job.extra["sub"] = j["companyName"]
                jobs.append(job)
            if page >= (d.get("totalPage") or 1) or page >= 20:
                break
            page += 1
        return jobs


# ── 네이버 계열 (네이버·크림·네이버페이) ─────────────────────────────
class NaverAdapter(Adapter):
    name = "naver"
    CAREER = {"신입": "신입", "경력": "경력", "무관": "경력 무관"}

    def _origin(self):
        u = urlparse(self.url)
        return f"{u.scheme}://{u.netloc}"

    def _job(self, aid, title, cls, field, career, emp, period, company=""):
        start, end = None, None
        if period:
            parts = period.split("~")
            start = _date(parts[0])
            end = _date(parts[1]) if len(parts) > 1 else None
            if "상시" in period:
                end = "상시"
        job = Job(company=self.company, job_id=str(aid), title=title.strip(),
                  url=f"{self._origin()}/rcrt/view.do?annoId={aid}&lang=ko",
                  career=self.CAREER.get(career.strip(), career.strip()), employment=emp.strip(),
                  category=" / ".join(x.strip() for x in [cls, field] if x and x.strip()),
                  posted_at=start, deadline=end)
        if company:
            job.extra["sub"] = company
        return job

    def fetch_list(self) -> List[Job]:
        html = net.get_text(self.url)
        s = net.soup(html)
        jobs = []
        for li in s.select("li.card_item"):
            if "disabled" in (li.get("class") or []):
                continue
            a = li.select_one("a.card_link")
            m = re.search(r"show\('?(\d+)", (a.get("onclick") or "") if a else "")
            if not m:
                continue
            dd = [d.get_text(" ", strip=True) for d in li.select("dd.info_text")]
            dd += [""] * (5 - len(dd))
            jobs.append(self._job(m.group(1), li.select_one(".card_title").get_text(" ", strip=True), *dd[:5]))
        total = re.search(r'totalRows\s*=\s*"(\d+)"', html)
        total = int(total.group(1)) if total else len(jobs)
        form = s.find("form", attrs={"name": "move_form"})
        params = {i.get("name"): i.get("value") or "" for i in form.find_all("input")} if form else {}
        start = 10
        while start < total and start < 500:
            d = net.get_json(f"{self._origin()}/rcrt/loadJobList.do?" + urlencode({**params, "firstIndex": start}))
            for j in d.get("list") or []:
                jobs.append(self._job(
                    j.get("annoId"), j.get("annoSubject") or "", j.get("classCdNm") or "", j.get("subJobCdNm") or "",
                    j.get("entTypeCdNm") or "", j.get("empTypeCdNm") or "",
                    f"{j.get('staYmdTime') or ''} ~ {j.get('endYmdTime') or ''}", j.get("sysCompanyCdNm") or ""))
            start += 10
        return jobs


# ── 아모레퍼시픽 (SAP SuccessFactors) ───────────────────────────────
class SuccessFactorsAdapter(Adapter):
    name = "successfactors"

    def fetch_list(self) -> List[Job]:
        u = urlparse(self.url)
        origin = f"{u.scheme}://{u.netloc}"
        jobs, seen, start, total = [], set(), 0, None
        while True:
            html = net.get_text(f"{origin}/search/?q=&locale=ko_KR&startrow={start}")
            s = net.soup(html)
            if total is None:
                m = re.search(r"(\d+)\s*개의 작업 중", html) or re.search(r"of\s+(\d+)", html)
                total = int(m.group(1)) if m else 0
            got = 0
            for a in s.select("a.jobTitle-link"):
                m = re.search(r"/(\d+)/?$", a.get("href", ""))
                if not m or m.group(1) in seen:
                    continue
                jid = m.group(1)
                seen.add(jid)
                got += 1

                def field(f):
                    for layout in ("desktop", "tablet", "mobile"):
                        el = s.find(id=f"job-{jid}-{layout}-section-{f}-value")
                        if el:
                            return el.get_text(" ", strip=True)
                    return ""
                job = Job(company=self.company, job_id=jid, title=a.get_text(" ", strip=True),
                          url=urljoin(origin, a["href"]), employment=field("shifttype"),
                          posted_at=_date(field("date")), deadline=_date(field("customfield3")))
                sub = field("customfield2")
                if sub and sub not in self.company:
                    job.extra["sub"] = sub
                jobs.append(job)
            start += 25
            if got == 0 or start >= (total or 0) or start > 500:
                break
        return jobs


# ── 넥슨 ───────────────────────────────────────────────────────────
class NexonAdapter(Adapter):
    name = "nexon"
    API = "https://career-gateway.nexon.com/career/v1/open/job-posts"

    def fetch_list(self) -> List[Job]:
        jobs, page = [], 1
        while True:
            body = {"corpCodes": [], "jobCategories": [], "careerTypes": [], "employmentTypes": [],
                    "workingAreas": [], "query": None, "page": page, "size": 50}
            d = net.post(self.API, json=body).json()
            for j in d.get("list") or []:
                job = Job(
                    company=self.company, job_id=str(j["jobPostNo"]), title=(j.get("title") or "").strip(),
                    url=f"https://careers.nexon.com/recruit/{j['jobPostNo']}",
                    career=(j.get("careerType") or {}).get("description", ""),
                    employment=(j.get("employmentType") or {}).get("description", ""),
                    posted_at=_date(j.get("startDate")), deadline=_date(j.get("endDate")),
                    body=net.html_to_text(j.get("contents") or ""),
                )
                if j.get("corpName") and j["corpName"] not in self.company:
                    job.extra["sub"] = j["corpName"]
                jobs.append(job)
            pg = d.get("pagination") or {}
            if page * pg.get("size", 50) >= pg.get("total", 0) or page >= 20 or not d.get("list"):
                break
            page += 1
        return jobs


# ── 신세계그룹 (SSG닷컴) ────────────────────────────────────────────
class ShinsegaeAdapter(Adapter):
    name = "shinsegae"
    ALIAS = {"ssg": "SSG.COM"}

    def _target(self) -> Optional[str]:
        n = self.company.lower().replace("닷컴", "").strip()
        for k, v in self.ALIAS.items():
            if k in n:
                return v
        return None

    def fetch_list(self) -> List[Job]:
        d = net.get_json("https://job.shinsegae.com/api/rcrut?sort=1&rcrutSeCd=10&rcrutSeCd=11")
        target = self._target()
        jobs = []
        for j in d.get("body") or []:
            co = j.get("coNm") or ""
            if target and co != target:
                continue
            job = Job(company=self.company, job_id=str(j["pbancBscNo"]), title=(j.get("pbancNm") or "").strip(),
                      url=f"https://job.shinsegae.com/rcrut/detail/{j['pbancBscNo']}",
                      career=j.get("rcrutSeNm") or "",
                      category=", ".join(x.get("dutyNm", "") for x in j.get("dutySeCd") or []),
                      posted_at=_date(j.get("pstgBgngDt")), deadline=_date(j.get("rcptEndDt")))
            if not target:
                job.extra["sub"] = co
            jobs.append(job)
        return jobs


# ── 카카오뱅크 ──────────────────────────────────────────────────────
class KakaoBankAdapter(Adapter):
    name = "kakaobank"
    API = "https://recruit.kakaobank.com/api/recruits"

    def fetch_list(self) -> List[Job]:
        jobs, page = [], 1
        while True:
            d = net.post(self.API, json={"receiptFilterType": "ONGOING", "pageNumber": page, "pageSize": 20}).json()
            items = d.get("list") or []
            for j in items:
                end = j.get("receiveEndDatetime") or ""
                if end and end[:10] < datetime.now().strftime("%Y-%m-%d"):
                    continue
                sn = j["recruitNoticeSn"]
                jobs.append(Job(company=self.company, job_id=str(sn), title=(j.get("recruitNoticeName") or "").strip(),
                                url=f"https://recruit.kakaobank.com/jobs/{sn}",
                                category=j.get("recruitClassName") or "",
                                posted_at=_date(j.get("receiveStartDatetime")), deadline=_date(end)))
            if len(items) < 20 or page >= 20:
                break
            page += 1
        return jobs


# ── 에이블리 (나인하이어 기반 자체 페이지) ───────────────────────────
class AblyAdapter(Adapter):
    name = "ably"
    CAREER = {"newcomer": "신입", "irrelevant": "경력 무관"}
    EMP = {"full_time": "정규직", "intern": "인턴", "contractor": "계약직", "part_time": "아르바이트"}

    def fetch_list(self) -> List[Job]:
        nd = net.next_data(net.get_text(self.url)) or {}
        recruits = ((nd.get("props") or {}).get("pageProps") or {}).get("recruits") or []
        jobs = []
        for r in recruits:
            if r.get("status") not in (None, "in_progress") or r.get("isPrivate"):
                continue
            key = (r.get("applyUrl") or "").rstrip("/").split("/")[-1] or r["id"]
            c = r.get("career")
            rng = r.get("careerRange") or {}
            if c == "experienced":
                lo, hi = rng.get("over"), rng.get("below")
                career = f"경력 {lo}~{hi}년" if lo is not None and hi else (f"경력 {lo}년 이상" if lo else "경력")
            else:
                career = self.CAREER.get(c, "")
            jobs.append(Job(
                company=self.company, job_id=key, title=(r.get("title") or "").strip(),
                url=f"https://recruit.ably.team/job_posting/{key}",
                career=career, employment=", ".join(self.EMP.get(e, e) for e in r.get("employmentTypes") or []),
                category=" / ".join(x for x in [r.get("jobGroup") or "", r.get("jobTask") or ""] if x),
                keywords=" ".join(r.get("tags") or []),
                posted_at=kst_date(r.get("createdAt")), deadline=_date(r.get("deadline")),
            ))
        return jobs


# ── 뱅크샐러드 (그리팅 공고를 자체 API로 노출) ───────────────────────
class BanksaladAdapter(GreetingAdapter):
    name = "banksalad"

    def fetch_list(self) -> List[Job]:
        d = net.get_json("https://www.banksalad.com/proxy/api/greeting/openings")
        jobs = []
        for dept in d.get("jobs") or []:
            for o in dept.get("data") or []:
                job = Job(company=self.company, job_id=str(o["id"]), title=(o.get("title") or "").strip(),
                          url=o.get("url") or f"https://banksalad.career.greetinghr.com/o/{o['id']}",
                          employment=o.get("employmentType") or "",
                          career=career_text(o.get("careerInfo") or {}),
                          category=" / ".join(x for x in [dept.get("department"), o.get("job")] if x))
                job.extra["needs_detail"] = True   # 게시일·마감일은 상세에서
                jobs.append(job)
        return jobs

    def enrich(self, job: Job):
        if not job.extra.get("needs_detail"):
            return
        d = self._detail(job)
        info = ((d or {}).get("data") or {}).get("openingsInfo") or {}
        job.posted_at = kst_date(info.get("openDate"))
        job.deadline = kst_date(info.get("dueDate"))
        job.extra["needs_detail"] = False


# ── 나인하이어 (카카오스타일, AB180) ─────────────────────────────────
class NinehireAdapter(Adapter):
    name = "ninehire"

    def fetch_list(self) -> List[Job]:
        r = net._session.get(self.url, timeout=30)
        if r.status_code == 429 or "Security Checkpoint" in r.text:
            raise RuntimeError("사이트 보안 검사(Vercel)가 자동 접속을 막고 있어서 읽을 수 없어")
        raise RuntimeError("나인하이어 공고 목록을 읽는 방법을 아직 못 찾았어")
