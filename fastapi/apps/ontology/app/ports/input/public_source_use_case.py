"""허용 도메인 안에서만 공개 문서를 가져오는 입력 포트.

허브에 두는 이유: 크롤링·스크래핑 능력은 특정 앱의 지식이 아니고, 이미 여기에
`WebPageFetcherPort`가 있다. **허용 도메인 목록은 허브가 정하지 않는다** — 무엇을 읽을
자격이 있는지는 그 지식을 쓰는 앱이 안다. 목록은 생성자로 받는다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ontology.app.dtos.public_source_dto import PublicDocument


class SourceNotAllowedError(Exception):
    """허용 도메인 목록 밖의 주소다.

    **요청을 보내기 전에** 난다. 부르는 쪽의 실수이므로 조용히 건너뛰지 않는다 —
    목록에 없는 주소가 늘어난 것을 아무도 모르는 상태가 가장 위험하다.
    """


class PublicSourceUseCase(ABC):
    @abstractmethod
    async def collect(self, url: str) -> PublicDocument | None:
        """문서 하나를 가져온다.

        읽을 수 없으면 `None`이다 — robots.txt가 막았거나, 응답이 200이 아니거나,
        본문이 비었을 때다. 이는 실패가 아니라 **읽지 않기로 한 정상 결과**다.

        허용 도메인 밖이면 `SourceNotAllowedError`를 던진다.
        """
