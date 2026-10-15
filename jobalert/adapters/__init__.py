"""회사 채용 페이지 주소를 보고 맞는 수집기를 고른다."""
from __future__ import annotations

from urllib.parse import urlparse

from .. import net
from .base import Adapter
from .generic import GenericAdapter
from .greeting import GreetingAdapter
from .sites import (AblyAdapter, BanksaladAdapter, GreenhouseAdapter, KakaoAdapter, KakaoBankAdapter,
                    NaverAdapter, NexonAdapter, NinehireAdapter, ShinsegaeAdapter, SuccessFactorsAdapter,
                    TossAdapter)

BY_HOST = {
    "careers.daangn.com": GreenhouseAdapter,
    "boards.greenhouse.io": GreenhouseAdapter,
    "boards-api.greenhouse.io": GreenhouseAdapter,
    "toss.im": TossAdapter,
    "careers.kakao.com": KakaoAdapter,
    "careers.apgroup.com": SuccessFactorsAdapter,
    "careers.nexon.com": NexonAdapter,
    "job.shinsegae.com": ShinsegaeAdapter,
    "recruit.kakaobank.com": KakaoBankAdapter,
    "ably.team": AblyAdapter,
    "corp.banksalad.com": BanksaladAdapter,
}


class AutoAdapter(Adapter):
    """처음 보는 주소: 페이지를 한 번 받아 보고 솔루션을 알아낸다."""

    name = "auto"

    def __init__(self, company, url):
        super().__init__(company, url)
        self.inner = None

    def _pick(self):
        if self.inner:
            return self.inner
        try:
            html = net.get_text(self.url)
        except Exception:
            html = ""
        if net.next_data(html) and "greetinghr" in html:
            cls = GreetingAdapter
        elif "/rcrt/loadJobList.do" in html:
            cls = NaverAdapter
        elif "ninehire" in html or "Vercel Security Checkpoint" in html:
            cls = NinehireAdapter
        elif "career.greetinghr.com/" in html and "/o/" in html:
            cls = GreetingAdapter
        elif "successfactors" in html:
            cls = SuccessFactorsAdapter
        else:
            cls = GenericAdapter
        self.inner = cls(self.company, self.url)
        self.name = self.inner.name
        return self.inner

    def fetch_list(self):
        return self._pick().fetch_list()

    def enrich(self, job):
        return self._pick().enrich(job)

    def fetch_body(self, job):
        return self._pick().fetch_body(job)


def pick_adapter(company: str, url: str) -> Adapter:
    u = urlparse(url)
    host = u.netloc.lower().split(":")[0]
    if host.endswith(".greetinghr.com"):
        return GreetingAdapter(company, url)
    if "/rcrt/list.do" in u.path:
        return NaverAdapter(company, url)
    if host in ("career.kakaostyle.com", "recruit.ab180.co") or host.endswith(".ninehire.site"):
        return NinehireAdapter(company, url)
    for h, cls in BY_HOST.items():
        if host == h or host.endswith("." + h):
            return cls(company, url)
    return AutoAdapter(company, url)
