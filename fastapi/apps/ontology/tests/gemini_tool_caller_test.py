"""도구 호출 어댑터의 판독·조립 테스트.

`genai.Client`를 만들지 않는다 — `_to_step`·`_contents`가 순수 함수라 따로 볼 수 있다.

두 가지를 고정한다.

1. **도구 호출이 하나라도 있으면 글은 버린다.** 모델은 호출과 함께 "이제 찾아
   보겠습니다" 같은 말을 얹는 날이 있고, 그것을 최종 답으로 읽으면 루프가 한 걸음
   만에 끝난다. 끝났다는 신호는 **호출이 없는 것** 하나뿐이다.
2. **후보가 비어도 터지지 않는다.** 안전 필터에 걸리면 `candidates`가 비거나
   `content`가 `None`으로 온다. 그때 예외가 나면 경기 하나가 아니라 실행 전체가 멈춘다.
3. **`thought_signature`를 실어 나른다.** 추론 모델은 이 불투명 토큰을 되받아야 대화를
   이어 간다. 2026-09-28 실측에서 이걸 버렸다가 **둘째 걸음에서** 400이 났고, 첫 걸음만
   보는 테스트로는 잡히지 않았다 — 그래서 `TestContents`가 왕복 두 번을 본다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/ontology/tests/gemini_tool_caller_test.py -q
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ontology.adapter.outbound.gemini_tool_caller import _contents, _to_step
from ontology.app.dtos.gemini_tool_dto import (
    ToolCall,
    ToolDeclaration,
    ToolExchange,
    ToolStepCommand,
)


@dataclass
class FakeCall:
    name: str
    args: dict[str, Any]


@dataclass
class FakePart:
    text: str | None = None
    function_call: FakeCall | None = None
    thought_signature: bytes | None = None


@dataclass
class FakeContent:
    parts: list[FakePart] | None


@dataclass
class FakeCandidate:
    content: FakeContent | None


@dataclass
class FakeResponse:
    candidates: list[FakeCandidate] | None


def _response(*parts: FakePart) -> FakeResponse:
    return FakeResponse(
        candidates=[FakeCandidate(content=FakeContent(parts=list(parts)))]
    )


class TestToStep:
    def test_text_only_is_the_answer(self) -> None:
        step = _to_step(_response(FakePart(text='{"winner_name": null}')), "m")

        assert not step.wants_tools
        assert step.text == '{"winner_name": null}'
        assert step.model == "m"

    def test_split_text_parts_are_joined(self) -> None:
        step = _to_step(_response(FakePart(text="{"), FakePart(text='"a": 1}')), "m")

        assert step.text == '{"a": 1}'

    def test_function_call_is_read(self) -> None:
        step = _to_step(
            _response(
                FakePart(
                    function_call=FakeCall(
                        name="read_wiki_section", args={"title": "X", "index": "3"}
                    )
                )
            ),
            "m",
        )

        assert step.wants_tools
        assert step.calls == (
            ToolCall(name="read_wiki_section", arguments={"title": "X", "index": "3"}),
        )

    def test_text_is_discarded_when_calls_present(self) -> None:
        """이 계약이 깨지면 루프가 첫 걸음에서 끝난다."""
        step = _to_step(
            _response(
                FakePart(text="이제 찾아보겠습니다."),
                FakePart(
                    function_call=FakeCall(name="find_wiki_article", args={"name": "X"})
                ),
            ),
            "m",
        )

        assert step.wants_tools
        assert step.text == ""

    def test_call_without_arguments_is_read(self) -> None:
        step = _to_step(
            _response(
                FakePart(function_call=FakeCall(name="find_wiki_article", args={}))
            ),
            "m",
        )

        assert step.calls[0].arguments == {}

    def test_no_candidates_yields_empty_answer(self) -> None:
        step = _to_step(FakeResponse(candidates=[]), "m")

        assert step.text == ""
        assert not step.wants_tools

    def test_none_content_does_not_raise(self) -> None:
        step = _to_step(FakeResponse(candidates=[FakeCandidate(content=None)]), "m")

        assert step.text == ""

    def test_none_parts_does_not_raise(self) -> None:
        step = _to_step(
            FakeResponse(candidates=[FakeCandidate(content=FakeContent(parts=None))]),
            "m",
        )

        assert step.text == ""


class TestContents:
    def test_first_step_is_prompt_only(self) -> None:
        contents = _contents(
            ToolStepCommand(
                prompt="누가 이겼나요?",
                tools=(ToolDeclaration(name="t", description="d", parameters={}),),
            )
        )

        assert len(contents) == 1
        assert contents[0].role == "user"

    def test_exchanges_become_model_user_pairs(self) -> None:
        """도구 응답의 role이 `user`인 것은 벤더 규약이다."""
        contents = _contents(
            ToolStepCommand(
                prompt="누가 이겼나요?",
                tools=(),
                exchanges=(
                    ToolExchange(
                        call=ToolCall(
                            name="find_wiki_article", arguments={"name": "X"}
                        ),
                        result={"status": "found"},
                    ),
                    ToolExchange(
                        call=ToolCall(
                            name="read_wiki_section",
                            arguments={"title": "X", "index": "3"},
                        ),
                        result={"text": "내용"},
                    ),
                ),
            )
        )

        assert [content.role for content in contents] == [
            "user",
            "model",
            "user",
            "model",
            "user",
        ]
        assert contents[1].parts[0].function_call.name == "find_wiki_article"


class TestThoughtSignature:
    """불투명 토큰 왕복 — 이것이 깨지면 루프가 **둘째 걸음에서** 400으로 죽는다."""

    def test_signature_is_captured_from_the_call_part(self) -> None:
        step = _to_step(
            _response(
                FakePart(
                    function_call=FakeCall(
                        name="find_wiki_article", args={"name": "X"}
                    ),
                    thought_signature=b"opaque-token",
                )
            ),
            "m",
        )

        assert step.calls[0].signature == b"opaque-token"

    def test_missing_signature_is_none_not_a_crash(self) -> None:
        """구형 모델은 이 칸을 안 준다. 없으면 없는 대로 간다."""
        step = _to_step(
            _response(
                FakePart(function_call=FakeCall(name="find_wiki_article", args={}))
            ),
            "m",
        )

        assert step.calls[0].signature is None

    def test_signature_is_sent_back_on_the_next_step(self) -> None:
        """실측으로 뚫린 그 자리. 재조립이 토큰을 버리면 여기서 걸린다."""
        contents = _contents(
            ToolStepCommand(
                prompt="누가 이겼나요?",
                tools=(),
                exchanges=(
                    ToolExchange(
                        call=ToolCall(
                            name="find_wiki_article",
                            arguments={"name": "X"},
                            signature=b"opaque-token",
                        ),
                        result={"status": "found"},
                    ),
                ),
            )
        )

        assert contents[1].parts[0].thought_signature == b"opaque-token"

    def test_round_trip_preserves_the_signature(self) -> None:
        """응답 판독 → 다음 요청 조립까지 한 바퀴 돈다."""
        step = _to_step(
            _response(
                FakePart(
                    function_call=FakeCall(
                        name="read_wiki_section", args={"index": "3"}
                    ),
                    thought_signature=b"sig-2",
                )
            ),
            "m",
        )
        contents = _contents(
            ToolStepCommand(
                prompt="p",
                tools=(),
                exchanges=(ToolExchange(call=step.calls[0], result={"text": "내용"}),),
            )
        )

        assert contents[1].parts[0].thought_signature == b"sig-2"
        assert contents[1].parts[0].function_call.name == "read_wiki_section"
