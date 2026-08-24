"""AI LAB 지식 코퍼스 집계 — Phase 3-4. **순수 함수다** (DB·LLM을 모른다).

이 화면이 답하는 질문은 "코퍼스에 무엇이 있는가"가 아니라 **"그중 무엇이 실제로
쓰였는가"** 다. 둘은 다르다 — 문서 31건을 모아 두고 그중 다섯 건만 프롬프트에 들어갔다면,
나머지 스물여섯 건은 검색 상위에 한 번도 못 든 것이고 그 사실이 코퍼스에 대해 가장 많은
것을 말한다.

**대조가 가능한 이유**는 `AgentReport.sources`가 LLM이 쓴 문장이 아니라 **실제로
프롬프트에 넣은 청크의 출처 URL**이기 때문이다(`gemini_agent_support._sources`). 그래서
여기서 세는 "쓰였다"는 인용 주장이 아니라 적재 기록이다.

**다만 그 기록은 잘려 있다.** 리포트당 상위 5청크·최대 5출처만 남으므로, 여섯 번째로
검색된 문서는 실제로 들어갔더라도 여기서는 안 쓰인 것으로 센다. 그러니 `used_documents`는
**하한**이다 — 이 값을 올려 말하지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from kayfabe.app.services.ai_lab_integrity import ReportRow


@dataclass(frozen=True)
class DocumentRow:
    """출처 URL 하나로 묶은 청크 뭉치. 세는 일은 DB가 하고 잇는 일만 여기서 한다."""

    source_url: str
    source_domain: str
    title: str | None
    chunks: int
    chunks_embedded: int
    chunks_with_published_at: int
    #: 이 문서 청크 중 가장 이른 발행일. 전부 NULL이면 `None`이다.
    first_published_at: datetime | None
    last_collected_at: datetime | None


@dataclass(frozen=True)
class KnowledgeDocument:
    """문서 한 건 + 그 문서가 실제로 쓰인 기록."""

    source_url: str
    source_domain: str
    title: str | None
    chunks: int
    chunks_embedded: int
    chunks_with_published_at: int
    first_published_at: datetime | None
    last_collected_at: datetime | None
    #: 이 문서를 프롬프트에 넣은 리포트 수. **인용 주장이 아니라 적재 기록이다.**
    used_by_reports: int
    #: 그 리포트를 낸 에이전트 이름. 코드의 이름 그대로 둔다.
    used_by_agents: tuple[str, ...]


@dataclass(frozen=True)
class DomainFacts:
    """도메인 한 종. 허용 도메인 목록(하네스 §3-D10)의 사후 감사 단위와 같다."""

    domain: str
    documents: int
    chunks: int
    used_documents: int


@dataclass(frozen=True)
class KnowledgeTotals:
    documents: int
    chunks: int
    chunks_embedded: int
    chunks_with_published_at: int
    domains: int
    last_collected_at: datetime | None
    #: 리포트가 한 번이라도 프롬프트에 넣은 문서 수. **하한이다** (모듈 설명 참조).
    used_documents: int
    #: 위 값 / 문서 수. 문서가 없으면 `None` — 0이 아니다.
    used_document_rate: float | None
    reports_total: int
    reports_with_sources: int
    #: 리포트가 든 출처 중 **지금 코퍼스에 없는** URL 수. 재수집·삭제로 생긴다.
    sources_outside_corpus: int


def summarize_knowledge(
    documents: Sequence[DocumentRow], reports: Sequence[ReportRow]
) -> tuple[KnowledgeTotals, list[KnowledgeDocument], list[DomainFacts]]:
    """코퍼스 문서와 리포트 출처를 URL로 맞춰 본다.

    **집계는 문서 행에서 낸다** — 타일의 숫자와 아래 목록이 같은 원천에서 나와야
    둘이 어긋나지 않는다. `corpus_facts()`로 따로 세면 두 벌이 되고, 언젠가 갈린다.
    """
    used_agents: dict[str, set[str]] = {}
    used_reports: dict[str, int] = {}
    known = {_canonical(row.source_url) for row in documents}
    outside = 0
    reports_with_sources = 0

    for report in reports:
        if report.sources:
            reports_with_sources += 1
        for url in dict.fromkeys(_canonical(u) for u in report.sources):
            if url not in known:
                outside += 1
                continue
            used_reports[url] = used_reports.get(url, 0) + 1
            used_agents.setdefault(url, set()).add(report.agent)

    items = [
        KnowledgeDocument(
            source_url=row.source_url,
            source_domain=row.source_domain,
            title=row.title,
            chunks=row.chunks,
            chunks_embedded=row.chunks_embedded,
            chunks_with_published_at=row.chunks_with_published_at,
            first_published_at=row.first_published_at,
            last_collected_at=row.last_collected_at,
            used_by_reports=used_reports.get(_canonical(row.source_url), 0),
            used_by_agents=tuple(
                sorted(used_agents.get(_canonical(row.source_url), ()))
            ),
        )
        for row in documents
    ]
    # 많이 쓰인 문서가 위로. 같으면 큰 문서 순, 그다음 URL 순 — 재조회에도 안 흔들린다.
    items.sort(key=lambda d: (-d.used_by_reports, -d.chunks, d.source_url))

    used_documents = sum(1 for item in items if item.used_by_reports > 0)
    totals = KnowledgeTotals(
        documents=len(items),
        chunks=sum(item.chunks for item in items),
        chunks_embedded=sum(item.chunks_embedded for item in items),
        chunks_with_published_at=sum(item.chunks_with_published_at for item in items),
        domains=len({item.source_domain for item in items}),
        last_collected_at=_latest(items),
        used_documents=used_documents,
        used_document_rate=(used_documents / len(items)) if items else None,
        reports_total=len(reports),
        reports_with_sources=reports_with_sources,
        sources_outside_corpus=outside,
    )
    return totals, items, _domains(items)


def _domains(items: Sequence[KnowledgeDocument]) -> list[DomainFacts]:
    grouped: dict[str, list[KnowledgeDocument]] = {}
    for item in items:
        grouped.setdefault(item.source_domain, []).append(item)
    facts = [
        DomainFacts(
            domain=domain,
            documents=len(rows),
            chunks=sum(row.chunks for row in rows),
            used_documents=sum(1 for row in rows if row.used_by_reports > 0),
        )
        for domain, rows in grouped.items()
    ]
    facts.sort(key=lambda d: (-d.chunks, d.domain))
    return facts


def _latest(items: Sequence[KnowledgeDocument]) -> datetime | None:
    collected = [item.last_collected_at for item in items if item.last_collected_at]
    return max(collected) if collected else None


def _canonical(url: str) -> str:
    """대조용 URL. **끝 슬래시와 공백만** 정리한다.

    대소문자를 접거나 쿼리를 떼지 않는 이유는, 그렇게 하면 서로 다른 문서가 한 건으로
    합쳐질 수 있기 때문이다 — 이 값이 "코퍼스에 없는 출처" 판정에 쓰이므로 과탐이
    과소탐보다 나쁘다(`cites_own_event`와 같은 기준).
    """
    return url.strip().rstrip("/")
