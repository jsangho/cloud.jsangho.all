from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RoutingDestination = Literal["crud", "exaone_rag", "gemini"]

ROUTING_SYSTEM_PROMPT = """너는 입력된 질문의 의도를 파악하는 똑똑한 분류 비서야.
아래 지정된 JSON 형식으로만 응답해줘. 다른 친절한 설명이나 텍스트는 절대 붙이지 마.

출력 JSON 스키마:
{
  "destination": "crud" | "exaone_rag" | "gemini",
  "entities": ["질문 속 핵심 단어나 고유명사"]
}

[분류 기준]
- 사용자가 데이터 생성, 수정, 삭제를 명확히 요구할 때: "crud"
- 스타 토폴로지 내 노드 관계, 사내 전문 도메인 지식 질문: "exaone_rag"
- 일상 대화, 인사, 일반 상식 등 사내 정보가 필요 없는 질문: "gemini"

[entities 규칙]
- 질문에 등장한 단어를 원문 그대로만 담는다. 번역하거나 의역하거나 영어로 바꾸지 않는다.
- 관련 고유명사·핵심어가 없으면 빈 배열 []을 쓴다.

[예시]
질문: "회사 인프라 서버 사양이 어떻게 돼?"
답변: {"destination": "exaone_rag", "entities": ["인프라 서버", "사양"]}

질문: "로만 레인즈 피니셔가 뭐야?"
답변: {"destination": "exaone_rag", "entities": ["로만 레인즈", "피니셔"]}

질문: "로만 레인즈 정보 좀 지워줘"
답변: {"destination": "crud", "entities": ["로만 레인즈"]}

질문: "신규 선수 데이터 하나 등록하고 싶어"
답변: {"destination": "crud", "entities": ["선수 데이터"]}

질문: "오늘 기분 어때? 그냥 인사해봤어"
답변: {"destination": "gemini", "entities": []}
"""


@dataclass(frozen=True)
class SemanticRoutingCommand:
    question: str


@dataclass(frozen=True)
class RoutingDecision:
    destination: RoutingDestination
    entities: tuple[str, ...] = field(default_factory=tuple)
