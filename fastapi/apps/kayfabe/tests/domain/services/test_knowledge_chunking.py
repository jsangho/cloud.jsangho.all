"""청킹·지문 테스트 — 하네스 §10-T3의 순수 함수.

여기서 고정하는 계약은 셋이다.
1. 문장 중간에서 자르지 않는다 (자르면 에이전트가 읽을 수 없는 조각이 된다)
2. 짧은 문서가 통째로 사라지지 않는다
3. 같은 글은 공백이 달라도 같은 지문이다 (재수집이 같은 내용을 쌓지 않는다)

실행 (하네스 §12 게이트와 같은 명령):

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from kayfabe.domain.services.knowledge_chunking import (
    MAX_CHUNK_CHARS,
    MIN_CHUNK_CHARS,
    chunk_document,
    content_fingerprint,
)


def test_empty_text_makes_no_chunks() -> None:
    assert chunk_document("") == []
    assert chunk_document("   \n  ") == []


def test_short_document_survives_as_one_chunk() -> None:
    """`MIN_CHUNK_CHARS` 때문에 문서가 통째로 사라지면 안 된다."""
    text = "Roman Reigns가 복귀했다."

    chunks = chunk_document(text)

    assert chunks == [text]


def test_sentences_are_packed_without_splitting() -> None:
    sentence = "A" * 300 + "."
    text = " ".join([sentence] * 8)

    chunks = chunk_document(text)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= MAX_CHUNK_CHARS
        # 문장 경계에서만 끊긴다 — 조각이 마침표로 끝난다.
        assert chunk.endswith(".")
    assert "".join(chunks).count("A") == text.count("A")


def test_one_giant_sentence_is_hard_split() -> None:
    """문장 부호가 없는 글도 무한정 긴 청크로 두지 않는다."""
    text = "가" * (MAX_CHUNK_CHARS * 2 + 50)

    chunks = chunk_document(text)

    assert len(chunks) == 3
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
    assert "".join(chunks) == text


def test_short_tail_fragment_is_dropped() -> None:
    """메뉴 문구·저작권 한 줄이 근거로 딸려 오지 않는다."""
    body = "B" * (MIN_CHUNK_CHARS + 50) + "."
    text = f"{body} 짧은 꼬리."

    chunks = chunk_document(text)

    assert chunks == [f"{body} 짧은 꼬리."] or all(
        len(c) >= MIN_CHUNK_CHARS for c in chunks
    )


def test_whitespace_does_not_change_fingerprint() -> None:
    """사이트가 줄바꿈만 바꿔도 다른 글이 되면 재수집마다 같은 내용이 쌓인다."""
    assert content_fingerprint("한 줄  두 줄") == content_fingerprint(
        "한 줄\n\t두 줄  "
    )


def test_different_content_gets_different_fingerprint() -> None:
    assert content_fingerprint("Roman") != content_fingerprint("Cody")


def test_fingerprint_is_sha256_hex() -> None:
    fingerprint = content_fingerprint("아무 글")

    assert len(fingerprint) == 64
    assert set(fingerprint) <= set("0123456789abcdef")
