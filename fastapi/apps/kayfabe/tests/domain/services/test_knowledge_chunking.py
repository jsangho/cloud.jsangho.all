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
    strip_source_boilerplate,
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


class TestStripSourceBoilerplate:
    """위키 상용구 걷어내기 (2026-09-22).

    **`worlds-collide` 예측이 두 번 연속 0건으로 끝난 원인이 여기였다.** 검색은
    정상이었고 잡혀 온 것이 내비게이션·각주 목록·navbox였다. 코퍼스 1179청크 중
    598건(50%)이 그런 조각이었고, 필터를 넣자 796청크 중 2건으로 떨어졌다.
    """

    def test_lead_chrome_is_removed(self) -> None:
        text = (
            "Jump to content From Wikipedia, the free encyclopedia "
            "American professional wrestler born in 2000 and trained in Sacramento."
        )

        assert strip_source_boilerplate(text).startswith("American professional")

    def test_everything_from_references_is_cut(self) -> None:
        body = (
            "He debuted in 2024 and won the cruiserweight title in a ladder "
            "match that same year in front of a sold-out crowd."
        )
        text = f'{body} References [ edit ] ↑ "Some source" . Retrieved May 27, 2024 .'

        assert strip_source_boilerplate(text) == body

    def test_external_links_and_navbox_go_with_it(self) -> None:
        body = (
            "She retained the championship at the November event in Mexico City "
            "after a twenty minute match against the former champion."
        )
        text = f"{body} External links [ edit ] Omos Pagano Pimpinela Escarlata Rey Mysterio"

        assert strip_source_boilerplate(text) == body

    def test_the_earliest_tail_heading_wins(self) -> None:
        """`See also`가 `References`보다 앞서면 거기서 끊는다."""
        body = (
            "He held the cruiserweight title for one hundred days in total before "
            "dropping it in a four-way match at the summer show."
        )
        text = f"{body} See also [ edit ] Something References [ edit ] ↑ cite"

        assert strip_source_boilerplate(text) == body

    def test_citation_arrow_is_the_fallback_cut(self) -> None:
        """절 제목이 없는 문서도 있다 — 그때는 첫 각주 화살표에서 끊는다."""
        body = (
            "The match was announced for the September card in Rosemont, Illinois, "
            "and was billed as the first meeting between the two."
        )
        text = f'{body} ↑ "Source title" . Retrieved December 26, 2025 .'

        assert strip_source_boilerplate(text) == body

    def test_edit_and_inline_ref_tokens_are_scrubbed(self) -> None:
        text = "He won the title [ 14 ] in 2025. Career [ edit ] He then defended it twice."

        out = strip_source_boilerplate(text)

        assert "[ 14 ]" not in out
        assert "[ edit ]" not in out
        assert "He won the title" in out and "defended it twice" in out

    def test_a_marker_at_the_very_start_does_not_erase_the_document(self) -> None:
        """**표지가 엉뚱한 자리에 맞으면 자르지 않는다.** 잡음이 남는 편이 낫다."""
        text = (
            "References [ edit ] "
            + "He wrestled in Mexico for a decade and held three titles. " * 3
        )

        out = strip_source_boilerplate(text)

        assert "wrestled in Mexico" in out

    def test_chunking_applies_the_filter(self) -> None:
        """`chunk_document`를 거치면 자동으로 걸러진다 — 부르는 쪽이 잊을 수 없다."""
        body = (
            "He debuted in 2024 and quickly became a fan favourite across the country. "
        )
        text = (
            "Jump to content From Wikipedia, the free encyclopedia "
            + body * 3
            + " ↑ cite . Retrieved May 1, 2024 ."
        )

        chunks = chunk_document(text)

        assert chunks
        assert all("Jump to content" not in c for c in chunks)
        assert all("↑" not in c for c in chunks)
