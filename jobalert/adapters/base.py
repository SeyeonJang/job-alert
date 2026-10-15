from __future__ import annotations

import re
from typing import List, Optional

from .. import net
from ..models import Job

EMPLOYMENT_RE = re.compile(r"정규|계약|인턴|파견|프리랜서|위촉|임원|현장실습|아르바이트|full[- ]?time|intern|contract", re.I)
CAREER_RE = re.compile(r"^(경력|신입|무관)|경력\s*무관|\d+\s*[~\-]\s*\d+\s*년|\d+\s*년\s*이상")


class Adapter:
    """채용 사이트 한 종류를 다루는 수집기."""

    name = "base"

    def __init__(self, company: str, url: str):
        self.company = company
        self.url = url

    def fetch_list(self) -> List[Job]:
        raise NotImplementedError

    def enrich(self, job: Job):
        """목록에 경력·고용형태가 없는 사이트는 여기서 상세 정보를 채운다."""
        return None

    def fetch_body(self, job: Job) -> Optional[str]:
        """상세 본문 텍스트. 실패하면 None."""
        if job.body:
            return job.body
        try:
            html = net.get_text(job.url)
            text = net.html_to_text(html)
            if len(text) < 300:  # 자바스크립트로만 그려지는 페이지
                html, _, _ = net.render(job.url, scrolls=1)
                text = net.html_to_text(html)
            job.body = text
            return text
        except Exception:
            return None


def split_tags(parts: List[str]):
    """'경력 3년 이상', '정규직', '역삼' 같은 태그 목록에서 경력·고용형태·직군을 나눈다."""
    career = employment = ""
    rest = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not career and CAREER_RE.search(p) and len(p) <= 20:
            career = p
        elif not employment and EMPLOYMENT_RE.search(p) and len(p) <= 20:
            employment = p
        else:
            rest.append(p)
    return career, employment, rest
