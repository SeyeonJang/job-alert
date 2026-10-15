"""처음 보는 사이트용: 브라우저로 열어 공고 상세처럼 보이는 링크를 모은다."""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse

from .. import net
from ..models import Job
from .base import Adapter, split_tags

DETAIL_PATTERNS = [
    re.compile(r"/o/(\d+)"),
    re.compile(r"/jobs?/(?:role/|detail/|view/)?([A-Za-z]?-?\d{3,})/?(?:[?#]|$)"),
    re.compile(r"[?&](?:job_id|jobId|gh_jid|annoId|recruitmentId|id)=([\w-]{3,})"),
    re.compile(r"/job_posting/([\w-]{4,})"),
    re.compile(r"/(?:recruit|recruitment|position|positions|career|careers|apply)/(?:detail/|view/)?([\w-]*\d{3,}[\w-]*)/?(?:[?#]|$)"),
]


class RecognizeError(RuntimeError):
    pass


class GenericAdapter(Adapter):
    name = "generic"

    def fetch_list(self) -> List[Job]:
        _, anchors, _ = net.render(self.url, scrolls=6)
        host = urlparse(self.url).netloc.split(":")[0]
        root = ".".join(host.split(".")[-2:])
        jobs, seen = [], set()
        for a in anchors:
            href, text = a.get("href", ""), a.get("text", "")
            if not href.startswith("http") or root not in urlparse(href).netloc:
                continue
            jid = None
            for p in DETAIL_PATTERNS:
                m = p.search(href)
                if m:
                    jid = m.group(1)
                    break
            if not jid or jid in seen:
                continue
            parts = [p.strip() for p in text.split("\n") if p.strip()]
            if not parts or len(parts[0]) < 3:
                continue
            seen.add(jid)
            career, employment, rest = split_tags(parts[1:])
            jobs.append(Job(company=self.company, job_id=jid, title=parts[0], url=href,
                            career=career, employment=employment, category=" / ".join(rest)))
        if not jobs:
            raise RecognizeError("공고 링크를 찾지 못했어")
        return jobs
