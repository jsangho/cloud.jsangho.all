"""기사와 댓글 (하네스 §3-D87).

§3-D31이 만든 것은 사건 한 줄이었다 — 헤드라인과 군중 반응 한 마디. 서른 해를 훑어도
읽을 거리가 두 줄뿐이었다.

여기서 지키는 것 넷:

1. **되짚기다** — 같은 세이브면 같은 기사다 (§3-D4). 저장하지 않는다
2. **사실을 지어내지 않는다** — 본문은 이미 일어난 일만 다시 말한다
3. **판정에 안 닿는다** — 굴림 채널이 완전히 갈려 있다 (§3-D56과 같은 자리)
4. **댓글창이지 합창이 아니다** — 한 명은 늘 반대편에 선다
"""

from __future__ import annotations

import pytest
from wwe_game.domain.services import news_article
from wwe_game.domain.services.news_feed import CrowdMood, NewsItem, NewsKind

SEED = 4242


def item(
    *,
    week: int = 300,
    kind: NewsKind = NewsKind.TITLE_WON,
    mood: CrowdMood = CrowdMood.ROAR,
    headline: str = "장상호, 데이비드에게서 인터컨티넨탈을 가져왔다.",
) -> NewsItem:
    return NewsItem(
        week=week,
        kind=kind,
        headline=headline,
        mood=mood,
        crowd_line="아레나가 통째로 일어섰다",
    )


class TestItIsRecomputed:
    """**저장하지 않는다** — `title_scene`(§3-D38)·별점(§3-D56)과 같은 자리다."""

    def test_the_same_save_builds_the_same_article(self) -> None:
        first = news_article.build(item(), SEED)
        second = news_article.build(item(), SEED)
        assert first == second

    def test_a_different_seed_reads_differently(self) -> None:
        """세계선이 다르면 기사도 다르다 — 아니면 시드가 기사에 안 닿는 것이다."""
        mine = news_article.build(item(), SEED)
        other = news_article.build(item(), SEED + 1)
        assert (mine.outlet, mine.comments) != (other.outlet, other.comments)

    def test_two_articles_in_one_week_do_not_share_comments(self) -> None:
        """같은 주차에 내 일과 배경 소식이 함께 서면 댓글이 같으면 안 된다."""
        mine = news_article.build(item(kind=NewsKind.TITLE_WON), SEED)
        scene = news_article.build(
            item(kind=NewsKind.TITLE_SCENE, headline="벨트의 주인이 바뀌었다."), SEED
        )
        assert mine.comments != scene.comments


class TestTheTitleInventsNothing:
    def test_it_keeps_the_headline_intact(self) -> None:
        """**제목은 `headline`에 말투만 입힌다** — 새 문장을 지으면 거짓이 될 수 있다."""
        news = item()
        title = news_article.title_for(news)
        assert "인터컨티넨탈을 가져왔다" in title

    def test_big_events_get_a_prefix(self) -> None:
        assert news_article.title_for(item(kind=NewsKind.TITLE_WON)).startswith("[속보]")
        assert news_article.title_for(item(kind=NewsKind.INJURY)).startswith("[현장]")

    def test_background_news_gets_none(self) -> None:
        """배경 소식까지 전부 [속보]면 속보가 아니다."""
        plain = news_article.title_for(item(kind=NewsKind.MOVED, headline="옮겼다."))
        assert not plain.startswith("[")

    def test_the_trailing_period_is_dropped(self) -> None:
        assert not news_article.title_for(item()).endswith(".")


class TestTheBodySaysOnlyWhatHappened:
    def test_it_carries_the_when_and_the_what(self) -> None:
        body = news_article.body_for(item(week=300))
        assert "년차" in body and "월" in body
        assert "인터컨티넨탈을 가져왔다" in body

    def test_it_carries_the_sound_of_the_room(self) -> None:
        """군중 반응은 §3-D31이 이미 정했다 — 기사가 다시 정하지 않는다."""
        assert "아레나가 통째로 일어섰다" in news_article.body_for(item())

    def test_it_is_longer_than_the_headline(self) -> None:
        """읽을 거리가 되려면 한 줄보다는 길어야 한다 (2026-08-14 사용자 요청)."""
        news = item()
        assert len(news_article.body_for(news)) > len(news.headline) * 2


class TestTheComments:
    def test_there_are_five(self) -> None:
        assert len(news_article.comments_for(item(), SEED)) == news_article.COMMENT_COUNT

    def test_every_comment_carries_votes(self) -> None:
        for c in news_article.comments_for(item(), SEED):
            assert c.author and c.text
            assert c.up >= 0 and c.down >= 0

    def test_one_of_them_disagrees(self) -> None:
        """**다섯 줄이 전부 같은 말이면 댓글창이 아니라 합창이다.**"""
        texts = [c.text for c in news_article.comments_for(item(), SEED)]
        assert any(t in news_article._DISSENT for t in texts)
        assert sum(t in news_article._DISSENT for t in texts) == 1

    def test_the_rest_follow_the_room(self) -> None:
        """넷은 그 밤의 소리를 따른다 — `CrowdMood`를 다시 읽을 뿐이다."""
        news = item(mood=CrowdMood.HUSH)
        texts = [c.text for c in news_article.comments_for(news, SEED)]
        agreeing = [t for t in texts if t not in news_article._DISSENT]
        assert len(agreeing) == news_article.COMMENT_COUNT - 1
        assert all(t in news_article._COMMENTS[CrowdMood.HUSH] for t in agreeing)

    def test_no_comment_repeats_inside_one_article(self) -> None:
        texts = [c.text for c in news_article.comments_for(item(), SEED)]
        assert len(set(texts)) == len(texts)

    @pytest.mark.parametrize("mood", list(CrowdMood))
    def test_every_mood_has_enough_lines(self, mood: CrowdMood) -> None:
        """반응마다 후보가 댓글 수보다 넉넉해야 한 꼭지 안에서 안 겹친다."""
        assert len(news_article._COMMENTS[mood]) > news_article.COMMENT_COUNT

    def test_the_room_and_the_dissent_never_overlap(self) -> None:
        """반대 의견이 분위기 풀에 섞여 있으면 "한 명"을 셀 수 없다."""
        for lines in news_article._COMMENTS.values():
            assert not set(lines) & set(news_article._DISSENT)


class TestItNeverTouchesTheRules:
    def test_the_outlets_are_fictional(self) -> None:
        """실존 매체를 쓰면 그 매체가 하지 않은 말을 한 것이 된다 (§3-D13)."""
        assert news_article.OUTLETS
        real = {"SPOTV", "ESPN", "KBS", "SBS", "MBC", "연합뉴스"}
        assert not set(news_article.OUTLETS) & real

    def test_the_news_channel_is_its_own(self) -> None:
        """**댓글을 한 줄 더해도 경기 결과가 밀리면 안 된다** (§3-D56과 같은 이유)."""
        from wwe_game.domain.services import seeded_roll

        assert seeded_roll.NEWS not in {
            seeded_roll.MATCH,
            seeded_roll.INJURY,
            seeded_roll.TITLE,
            seeded_roll.EVENT,
            seeded_roll.RATING,
        }
