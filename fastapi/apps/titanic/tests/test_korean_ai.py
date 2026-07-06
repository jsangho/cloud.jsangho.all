"""
한국어 전처리(Kiwi) + Ollama(qwen2.5:3b) 스크립트.

단위 테스트 (mock, Ollama 불필요):
    cd sangho
    python -m pytest apps/titanic/tests/test_korean_ai.py -v

Ollama 통합 테스트:
    python -m pytest apps/titanic/tests/test_korean_ai.py -m ollama -v -s

Ollama 실제 호출 (스크립트):
    python apps/titanic/tests/test_korean_ai.py
"""

from types import SimpleNamespace
from unittest.mock import patch

import ollama
import pytest
from kiwipiepy import Kiwi

kiwi = Kiwi()


def run_korean_ai(user_text):
    print("\n--- [1단계] 입력 문장 전처리 중... ---")

    kiwi.global_config.space_tolerance = 2
    cleaned_text = kiwi.space(user_text, reset_whitespace=True)
    print(f"원본 문장: {user_text}")
    print(f"정제된 문장: {cleaned_text}")

    tokens = kiwi.tokenize(cleaned_text)
    nouns = [t.form for t in tokens if t.tag.startswith("NN")]
    print(f"추출된 핵심 명사: {nouns}")

    print("\n--- [2단계] Qwen2.5 3B 모델 추론 중... ---")

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "user",
                "content": cleaned_text,
            }
        ],
    )

    return response["message"]["content"]


def _ollama_reachable() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        return False


@pytest.fixture
def mock_kiwi():
    with patch(f"{__name__}.kiwi") as mocked:
        mocked.space.return_value = "cleaned user text"
        mocked.tokenize.return_value = [
            SimpleNamespace(form="noun_a", tag="NNG"),
            SimpleNamespace(form="noun_b", tag="NNP"),
            SimpleNamespace(form="noun_c", tag="NNG"),
        ]
        yield mocked


@pytest.fixture
def mock_ollama_chat():
    with patch(f"{__name__}.ollama.chat") as chat:
        chat.return_value = {"message": {"content": "mocked ai response"}}
        yield chat


class TestRunKoreanAi:
    def test_returns_ollama_message_content(self, mock_kiwi, mock_ollama_chat):
        result = run_korean_ai("raw user text")
        assert result == "mocked ai response"

    def test_preprocesses_text_with_kiwi_before_ollama(
        self, mock_kiwi, mock_ollama_chat
    ):
        user_text = "raw user text"

        run_korean_ai(user_text)

        mock_kiwi.space.assert_called_once_with(user_text, reset_whitespace=True)
        mock_ollama_chat.assert_called_once_with(
            model="qwen2.5:3b",
            messages=[{"role": "user", "content": "cleaned user text"}],
        )

    def test_sets_kiwi_space_tolerance(self, mock_kiwi, mock_ollama_chat):
        run_korean_ai("sample input")
        assert mock_kiwi.global_config.space_tolerance == 2


@pytest.mark.ollama
class TestRunKoreanAiIntegration:
    def test_titanic_question_returns_nonempty_answer(self):
        if not _ollama_reachable():
            pytest.skip("Ollama 서버에 연결할 수 없습니다")

        result = run_korean_ai("타이타닉의 생존자는 몇명이야.")

        assert isinstance(result, str)
        assert result.strip()


if __name__ == "__main__":
    question = "타이타닉의 생존자는 몇명이야."
    answer = run_korean_ai(question)

    print("\n--- [3단계] AI 최종 답변 ---")
    print(answer)
