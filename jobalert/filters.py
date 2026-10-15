"""공고를 보낼지 판단한다: 직무 → 고용형태 → 경력 순서."""
from __future__ import annotations

import re
from typing import Optional, Tuple

from . import rules
from .models import Job, Verdict


def _norm(text: str) -> str:
    return " " + re.sub(r"\s+", " ", (text or "")).strip().lower() + " "


def _has_any(text: str, words) -> Optional[str]:
    for w in words:
        k = w.strip()
        if k.isascii() and len(k) <= 3:
            # 짧은 영문 약어(pr, ml, hr ...)는 단어 단위로만 찾는다 (product, html 오탐 방지)
            if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text):
                return k
        elif w in text:
            return k
    return None


def _has_acronym(title: str) -> Optional[str]:
    for a in rules.ROLE_INCLUDE_ACRONYMS:
        if re.search(rf"(?<![A-Za-z]){a}(?![A-Za-z])", title or ""):
            return a
    return None


# ── 직무 ────────────────────────────────────────────────────────────
def classify_role(job: Job) -> Tuple[str, str]:
    """('include' | 'exclude' | 'ambiguous', 근거)"""
    title = _norm(job.title)
    cat = _norm(" ".join([job.category, job.keywords]))

    hit = _has_any(title, rules.ROLE_HARD_EXCLUDE)
    if hit:
        return "exclude", f"제목: {hit}"
    hit = _has_any(title, rules.ROLE_STRONG_INCLUDE)
    if hit:
        return "include", hit
    hit = _has_any(title, rules.ROLE_EXCLUDE)
    if hit:
        return "exclude", f"제목: {hit}"
    hit = _has_any(title, rules.ROLE_INCLUDE) or _has_acronym(job.title)
    if hit:
        return "include", hit
    hit = _has_any(_norm(job.category), rules.CATEGORY_INCLUDE)
    if hit:
        return "include", f"직군: {hit}"
    hit = _has_any(_norm(job.category), rules.CATEGORY_EXCLUDE)
    if hit:
        return "exclude", f"직군: {hit}"
    hit = _has_any(cat, rules.ROLE_STRONG_INCLUDE)
    if hit:
        return "include", f"키워드: {hit}"
    return "ambiguous", ""


# ── 고용형태 ────────────────────────────────────────────────────────
def is_intern(job: Job) -> bool:
    return bool(_has_any(_norm(job.employment + " " + job.title), rules.INTERN_WORDS))


def employment_block(job: Job) -> Optional[str]:
    """제외해야 하는 고용형태면 사유를 돌려준다."""
    # 제목은 괄호 안 표기만 본다 ('당근알바' 같은 서비스명 오탐 방지)
    title_tags = " ".join(re.findall(r"[\(\[]([^\)\]]*)[\)\]]", job.title or ""))
    hit = _has_any(_norm(job.employment + " " + title_tags + " " + (job.title or "").split("_")[-1]), rules.ALWAYS_BLOCK_WORDS)
    if hit:
        return f"고용형태: {hit}"
    if is_intern(job):
        return None
    hit = _has_any(_norm(job.employment + " " + title_tags), rules.CONTRACT_WORDS)
    if hit:
        return f"고용형태: {hit}"
    return None


# ── 경력 ────────────────────────────────────────────────────────────
# 범위 표현(앞쪽 숫자가 최소 연차)은 먼저 찾아서 지운 뒤 나머지 표현을 찾는다
_RANGE_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:년|years?)?\s*[~\-–]\s*\d{1,2}\s*(?:년|years?)"),
]
_YEAR_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:년|yr|years?)\s*(?:차\s*)?(?:이상|↑|\+|over|or more)"),
    re.compile(r"(\d{1,2})\s*\+\s*(?:년|years?)"),
    re.compile(r"경력\s*(\d{1,2})\s*년"),
    re.compile(r"(\d{1,2})\s*년\s*(?:차|간|의|정도|가량)?\s*(?:이상의|이상)?\s*(?:실무|경력|경험|업무)"),
    re.compile(r"at least\s*(\d{1,2})\s*years?"),
    re.compile(r"(\d{1,2})\s*years?\s*of"),
]
_EXPERIENCE_CONTEXT = re.compile(r"경력|경험|실무|업무|근무|연차|years?|experience", re.I)


def years_in_text(text: str) -> Optional[int]:
    """'경력 3년 이상', '2~5년', '5년 ~ 8년', '5+ years' 같은 표현에서 요구 연차를 뽑는다.
    범위는 아래쪽 숫자를 쓰고, 한 문장에 조건이 여러 개면 가장 큰 값을 쓴다
    (예: '1~3년의 PO 경력 (총 경력 5년 이상)' → 5)."""
    if not text:
        return None
    found = []
    rest = text
    for p in _RANGE_PATTERNS:
        for m in p.finditer(rest):
            found.append(int(m.group(1)))
        rest = p.sub(" ", rest)
    for p in _YEAR_PATTERNS:
        for m in p.finditer(rest):
            found.append(int(m.group(1)))
    found = [n for n in found if 0 <= n <= 30]
    return max(found) if found else None


def parse_career_tag(tag: str) -> Tuple[str, Optional[int]]:
    """사이트의 경력 표기를 ('newbie'|'any'|'years'|'career'|'unknown', 연차)로 바꾼다."""
    t = (tag or "").replace(" ", "")
    if not t:
        return "unknown", None
    if "신입" in t:
        return "newbie", None
    if "무관" in t or "누구나" in t:
        return "any", None
    y = years_in_text(tag)
    if y is not None:
        return "years", y
    if "경력" in t or "experienced" in t.lower():
        return "career", None
    return "unknown", None


def _heading_kind(line: str) -> Optional[str]:
    s = line.strip().strip("#*-•·■□▶▷◆◇●○[]【】<>:：").strip().lower()
    if not s or len(s) > 40:
        return None
    if any(h in s for h in rules.PREFERRED_HEADINGS):
        return "pref"
    if any(h in s for h in rules.REQUIREMENT_HEADINGS):
        return "req"
    if any(h in s for h in rules.OTHER_HEADINGS):
        return "other"
    return None


def requirement_section(body: str) -> list:
    """디버그용: 자격요건 구역으로 판단한 줄들."""
    lines = [l.strip() for l in (body or "").splitlines() if l.strip()]
    out, state = [], "neutral"
    for line in lines:
        kind = _heading_kind(line)
        if kind:
            state = kind
            if kind == "req":
                out.append(f"[{line}]")
            continue
        if state == "req":
            out.append(line)
    return out


def requirement_years(body: str) -> Tuple[Optional[int], str]:
    """상세 본문에서 자격요건 구역의 연차(가장 큰 값)와 근거 문장을 찾는다.

    - 자격요건 소제목이 있으면 그 구역만 본다.
    - 없으면 우대사항 구역을 뺀 나머지 전체를 본다.
    - 연차가 여러 개면 전부 충족해야 하므로 가장 큰 값을 쓴다.
    """
    lines = [l.strip() for l in (body or "").splitlines() if l.strip()]
    has_req = any(_heading_kind(l) == "req" for l in lines)
    state = "neutral"
    best: Optional[int] = None
    evidence = ""
    for line in lines:
        kind = _heading_kind(line)
        if kind:
            state = kind
            continue
        if has_req and state != "req":
            continue
        if not has_req and state == "pref":
            continue
        if "우대" in line or "preferred" in line.lower():
            continue
        if not _EXPERIENCE_CONTEXT.search(line):
            continue
        y = years_in_text(line)
        if y is not None and (best is None or y > best):
            best = y
            evidence = line
    evidence = re.sub(r"^(?:[\-•·*▪●○◦■□▶✔︎✓\s]+|\d{1,2}[\.\)]\s+)+", "", evidence)[:90]
    return best, evidence


def judge(job: Job, need_body, enrich=None) -> Verdict:
    """need_body(job) -> 본문 문자열 또는 None(실패). 필요할 때만 호출된다.
    enrich(job) -> 목록에 없던 경력·고용형태를 상세 페이지에서 채운다 (직무가 맞을 때만)."""
    role, role_why = classify_role(job)
    if role == "exclude":
        return Verdict(False, reason=f"직무 제외 ({role_why})")
    if enrich is not None:
        try:
            enrich(job)
        except Exception:
            return Verdict(False, reason="상세 정보 확인 실패", retry=True)
        role, role_why = classify_role(job)
        if role == "exclude":
            return Verdict(False, reason=f"직무 제외 ({role_why})")

    block = employment_block(job)
    if block:
        return Verdict(False, reason=block)

    flags = []
    if role == "ambiguous":
        flags.append("❔직무 확인")
    intern = is_intern(job)

    kind, years = parse_career_tag(job.career)
    if kind == "unknown":
        # 제목에 [신입] / [경력] / (3년 이상) 같은 표기가 있는지 본다
        t = job.title or ""
        if "신입" in t:
            kind = "newbie"
        elif years_in_text(t) is not None:
            kind, years = "years", years_in_text(t)
        elif "경력" in t:
            kind = "career"

    label = ""
    evidence = ""
    if kind == "newbie":
        label = "신입·경력" if "경력" in (job.career or "") else "신입"
    elif kind == "any":
        label = "경력무관"
    elif kind == "years":
        if years > rules.MAX_YEARS:
            return Verdict(False, reason=f"경력 {years}년 이상")
        label = job.career.strip() if job.career else (f"경력 {years}년↑" if years else "신입 가능")
    else:  # 'career' 또는 'unknown' → 상세 본문 확인
        body = need_body(job)
        if body is None:
            return Verdict(False, reason="상세 페이지 확인 실패", retry=True)
        y, ev = requirement_years(body)
        if y is not None:
            if y > rules.MAX_YEARS:
                return Verdict(False, reason=f"자격요건 {y}년 이상: {ev}")
            label = "신입 가능" if y == 0 else f"경력 {y}년↑"
            evidence = ev
        elif kind == "career":
            label = "경력"
            flags.append("⚠️연차 미기재")
        else:
            label = "연차 표기 없음"

    if intern:
        label = "인턴" + (f" · {label}" if label and label != "연차 표기 없음" else "")
    return Verdict(True, career_label=label, evidence=evidence, flags=flags)
