from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    """사이트에서 가져온 공고 한 건. 값은 사이트 원문 그대로 둔다."""

    company: str            # 시트에 적힌 회사명
    job_id: str             # 사이트 안에서 고유한 공고 ID
    title: str              # 공고 제목 원문
    url: str                # 공고 상세 링크
    employment: str = ""    # 고용형태 원문 (정규직 / 계약직 / 인턴 ...)
    career: str = ""        # 경력 원문 (신입 / 경력 / 경력 3년 이상 / 경력 무관 ...)
    category: str = ""      # 직군·직무 원문 (사이트가 주는 경우)
    keywords: str = ""      # 사이트가 주는 검색 키워드 (Greenhouse 등)
    posted_at: Optional[str] = None   # 사이트가 주는 게시일 (YYYY-MM-DD)
    deadline: Optional[str] = None    # 마감일 (YYYY-MM-DD)
    body: Optional[str] = None        # 상세 본문 텍스트 (필요할 때만 채움)
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.company}|{self.job_id}"


@dataclass
class Verdict:
    """필터 판정 결과."""

    send: bool
    reason: str = ""                 # 제외 사유 (로그용)
    career_label: str = ""           # 알림에 표시할 경력 라벨 (인턴 · 신입 / 경력 1년↑ ...)
    evidence: str = ""               # 연차 근거 문장
    flags: list = field(default_factory=list)   # ❔직무 확인, ⚠️연차 미기재 ...
    retry: bool = False              # 상세 페이지를 못 읽어서 다음 실행에 다시 판단
