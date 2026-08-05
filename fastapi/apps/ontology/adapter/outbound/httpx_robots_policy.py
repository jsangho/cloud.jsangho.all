"""robots.txt 판정 어댑터.

**모르면 가져가지 않는다.** robots.txt를 못 읽었을 때 허용으로 넘기면, 상대 서버가
막아 뒀는지 확인하지 못한 채 계속 긁게 된다. 반대로 막는 쪽은 손해가 수집 실패뿐이다.

호스트당 한 번만 읽고 프로세스 안에서 재사용한다 — 문서 20개를 모으려고 robots.txt를
20번 받아 가면 그 자체가 민폐다.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ontology.app.ports.output.robots_policy_port import RobotsPolicyPort

logger = logging.getLogger("uvicorn.error")

#: `HttpxWebPageFetcher`와 같은 이름을 써야 robots.txt 판정과 실제 요청이 어긋나지 않는다.
USER_AGENT = "jsangho-ontology-crawler/1.0"
_TIMEOUT_SECONDS = 10.0


class HttpxRobotsPolicy(RobotsPolicyPort):
    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser | None] = {}

    async def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            self._cache[origin] = await self._load(origin)

        rules = self._cache[origin]
        if rules is None:
            return False
        return rules.can_fetch(USER_AGENT, url)

    async def _load(self, origin: str) -> RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT_SECONDS, follow_redirects=True
            ) as client:
                response = await client.get(
                    robots_url, headers={"User-Agent": USER_AGENT}
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "[ontology.robots] robots.txt 조회 실패 | url=%s | %r", robots_url, exc
            )
            return None

        if response.status_code == 404:
            # robots.txt가 없으면 제한이 없다는 뜻이다(RFC 9309).
            allow_all = RobotFileParser()
            allow_all.parse([])
            return allow_all

        if response.status_code != 200:
            logger.warning(
                "[ontology.robots] robots.txt 응답이 200이 아님 | url=%s | status=%s",
                robots_url,
                response.status_code,
            )
            return None

        rules = RobotFileParser()
        rules.parse(response.text.splitlines())
        return rules
