"""구글 시트에서 회사 목록을 읽는다.

시트 열: 회사명 | 채용 페이지 | (선택) 사용  — '사용'이 X/N/off 이면 건너뛴다.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import List, Tuple

from . import net


def to_csv_url(url: str) -> str:
    m = re.search(r"docs\.google\.com/spreadsheets/d/([^/]+)", url)
    if not m or "format=csv" in url or "output=csv" in url:
        return url
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid.group(1)}" if gid else "")


def parse(text: str) -> List[Tuple[str, str]]:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    use_col = next((i for i, h in enumerate(header) if h in ("사용", "on", "사용여부")), None)
    out = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        name, url = row[0].strip(), row[1].strip()
        if not name or not url.startswith("http"):
            continue
        if use_col is not None and len(row) > use_col and row[use_col].strip().lower() in ("x", "n", "no", "off", "꺼짐", "중지"):
            continue
        out.append((name, url))
    return out


def load(source: str) -> List[Tuple[str, str]]:
    if source.startswith("http"):
        r = net.get(to_csv_url(source))
        return parse(r.content.decode("utf-8"))
    return parse(Path(source).read_text(encoding="utf-8"))
