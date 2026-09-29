"""위키 현 챔피언 표 파서 테스트.

**여기 쓰인 표 조각은 전부 실제 위키 본문이다** — `List of current champions in WWE`의
`Current champions` 절을 `reduce_markup`에 통과시킨 결과를 그대로 옮겼다(2026-09-29,
개정본 1374648912). 그 절에서 파서가 20행을 낸다.

지어낸 예시를 쓰지 않는 이유가 있다. 이 모듈의 첫 판은 **한 번도 실제 본문에 돌려
보지 않은 채** 쓰였고, 그래서 세 가지를 동시에 틀렸다: 사진 두 장인 태그 팀 행의
이미지 칸(`100px<br>100px`)을 챔피언으로 집었고, **사진이 없어 빈 칸으로 오는 행 넷을
통째로 버렸고**, 원문 위키텍스트를 가정해 `[[File:...|100px]]`를 챔피언으로 읽었다.
표 모양을 상상해서 적으면 그 실패가 초록으로 돌아온다.

고정하는 계약 일곱:

1. 사진 한 장·두 장·**없음** 세 모양을 모두 읽는다
2. 팀 이름과 구성원을 가른다 (`{{small|(A and B)}}`)
3. 획득일은 **처음 만난 날짜 칸** — Evolve의 `Days rec.`가 다른 날짜를 들고 뒤에 온다
4. Notes에서 대회명을 뽑되 `Night 2` 같은 꼬리를 뗀다
5. `a ... event`는 설명이라 꼬리를 떼지만 `Sunday Night's Main Event`는 이름이다
6. 주최자 소유격(`The Nightmare Factory's event, ...`)은 대회명으로 적지 않는다
7. 헤더·범례·테두리는 행이 되지 않는다

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from kayfabe.domain.services.champion_table_parser import parse_champion_table

#: Raw 표 머리와 첫 두 행. 범례 표(브랜드 색 안내)가 절 맨 앞에 실제로 온다.
_RAW_TABLE = """
{|class="wikitable" style="margin: auto"
|-
|style="background:#FBB; width:2em" align=center|
|Raw
|}

{| class=wikitable style="font-size: 85%; text-align:center"
|-
!colspan=9 style=background:#FBB|Raw
|-
!Championship
!colspan=2 | Current champion(s)
!Reign
!Date won
!Days<br />held

!Location
!Notes
!Ref.
|-
| World Heavyweight Championship
| 100px
| Roman Reigns
| 1
| April 19, 2026
| {{age in days|April 19, 2026}}
| Paradise, Nevada
| align=left | Defeated CM Punk at WrestleMania 42 Night 2.
|
|-
| Women's World Championship
| 100px
| Stephanie Vaquer
| 2
| September 12, 2026
| {{age in days|September 12, 2026}}
| Santiago, Chile
| align=left | Defeated Liv Morgan at a WWE Live: South America Live Tour event. Becky Lynch was the special guest referee.
|
|-
| World Tag Team Championship
| 100px<br>100px
| The Vision<br>{{small|(Bron Breakker and Austin Theory)}}
| 2
| July 6, 2026
| {{age in days|July 6, 2026}}
| Brooklyn, New York
| align=left | Defeated The Street Profits (Montez Ford and Angelo Dawkins) on Raw.
|
|}
"""

#: 사진이 없어 이미지 칸이 **빈 채로** 오는 행과, 사진 두 장인 태그 팀 행.
_NXT_TABLE = """
{| class=wikitable style="font-size:85%; text-align:center"
|-
!colspan=10 style=background:silver | NXT
|-
| NXT Women's Championship
|
| Kelani Jordan
| 1
| August 30, 2026
| {{age in days|August 30, 2026}}
| Edinburg, Texas
| align=left | Defeated Kendal Grey at Heatwave.
|
|-
| NXT Tag Team Championship
| 100px<br>100px
| The Vanity Project<br>{{small|(Brad Baylor and Ricky Smokes)}}
| 2
| August 30, 2026
| {{age in days|August 30, 2026}}
| Edinburg, Texas
| align=left | Defeated Myles Borne and Tavion Heights at Heatwave.
|
|}
"""

#: Evolve 표에는 `Days rec.` 칸이 하나 더 있고 **거기 다른 날짜가 들어 있다**.
_EVOLVE_TABLE = """
{| class=wikitable style="font-size: 85%; text-align:center"
|-
| WWE Evolve Men's Championship
|
| Harlem Lewis
| 1
| June 19, 2026
| {{age in days|June 19, 2026}}
| {{age in days|July 15, 2026}}
| Orlando, Florida
| align=left | Defeated Aaron Rourke on Evolve. WWE recognizes Lewis' reign as beginning on July 15, 2026, when the episode aired on tape delay.
| <br>
|}
"""

#: WWE ID 표에는 이미지 칸이 아예 없고, Notes가 주최자를 먼저 적는다.
_ID_TABLE = """
{| class=wikitable style="font-size:85%; text-align:center"
|-
| WWE ID Championship
| Max Abrams
| 1
| June 26, 2026
| {{age in days|June 26, 2026}}
| Atlanta, Georgia
| align=left | Defeated Chazz "Starboy" Hall at The Nightmare Factory's event, The ID Showcase.
|
|}
"""


def _row(wikitext: str, belt_name: str):
    rows = {row.belt_name: row for row in parse_champion_table(wikitext)}
    assert belt_name in rows, f"{belt_name}을 읽지 못했다: {sorted(rows)}"
    return rows[belt_name]


class TestRowShapes:
    """표 모양 — 사진 한 장·두 장·없음, 그리고 팀."""

    def test_single_champion_is_read(self) -> None:
        row = _row(_RAW_TABLE, "World Heavyweight Championship")

        assert row.champions == ("Roman Reigns",)
        assert row.team_name is None
        assert row.won_at == "2026-04-19"

    def test_row_without_a_photo_is_read(self) -> None:
        """이 계약이 없으면 NXT·Evolve의 네 행이 조용히 사라진다."""
        row = _row(_NXT_TABLE, "NXT Women's Championship")

        assert row.champions == ("Kelani Jordan",)
        assert row.won_at == "2026-08-30"

    def test_tag_team_splits_team_and_members(self) -> None:
        row = _row(_NXT_TABLE, "NXT Tag Team Championship")

        assert row.team_name == "The Vanity Project"
        assert row.champions == ("Brad Baylor", "Ricky Smokes")

    def test_image_cell_is_not_a_champion(self) -> None:
        row = _row(_RAW_TABLE, "World Tag Team Championship")

        assert row.champions == ("Bron Breakker", "Austin Theory")
        assert "100px" not in str(row.champions)


class TestWonDate:
    """획득일 — 뒤에 오는 날짜 칸에 속지 않는다."""

    def test_first_date_cell_wins(self) -> None:
        """`Days rec.`의 7월 15일은 테이프 딜레이 방영일이고 재위 시작이 아니다."""
        row = _row(_EVOLVE_TABLE, "WWE Evolve Men's Championship")

        assert row.won_at == "2026-06-19"


class TestWonEvent:
    """Notes 문장에서 뽑는 대회명."""

    def test_night_suffix_is_dropped(self) -> None:
        assert (
            _row(_RAW_TABLE, "World Heavyweight Championship").won_event
            == "WrestleMania 42"
        )

    def test_event_tail_is_dropped_only_after_an_article(self) -> None:
        """`a ... Live Tour event`는 설명이지만 `Sunday Night's Main Event`는 이름이다."""
        assert (
            _row(_RAW_TABLE, "Women's World Championship").won_event
            == "WWE Live: South America Live Tour"
        )

        sunday = """
    {| class=wikitable
    |-
    | WWE United States Championship
    | 100px
    | Trick Williams
    | 1
    | September 6, 2026
    | {{age in days|September 6, 2026}}
    | Chicago, Illinois
    | align=left | Defeated Baron Corbin at Sunday Night's Main Event.
    |
    |}
    """
        assert (
            _row(sunday, "WWE United States Championship").won_event
            == "Sunday Night's Main Event"
        )

    def test_only_the_first_at_or_on_is_read(self) -> None:
        """같은 칸 뒤쪽에 `aired on tape delay`가 온다 — 처음 만난 것만 쓴다."""
        assert (
            _row(_EVOLVE_TABLE, "WWE Evolve Men's Championship").won_event == "Evolve"
        )

    def test_organizer_possessive_is_not_an_event(self) -> None:
        """정작 대회명(`The ID Showcase`)은 쉼표 뒤에 있다. 앞을 집으면 주최자를 적는다."""
        row = _row(_ID_TABLE, "WWE ID Championship")

        assert row.champions == ("Max Abrams",)
        assert row.won_event is None


class TestUnreadableRows:
    """행이 되지 않아야 하는 것들."""

    def test_header_and_legend_are_not_rows(self) -> None:
        belts = [row.belt_name for row in parse_champion_table(_RAW_TABLE)]

        assert belts == [
            "World Heavyweight Championship",
            "Women's World Championship",
            "World Tag Team Championship",
        ]

    def test_vacant_is_not_a_champion(self) -> None:
        vacant = """
    {| class=wikitable
    |-
    | WWE Women's ID Championship
    | 100px
    | Vacant
    |
    |
    |
    |
    |}
    """
        assert parse_champion_table(vacant) == ()

    def test_empty_champion_cell_does_not_promote_the_reign_count(self) -> None:
        broken = """
    {| class=wikitable
    |-
    | NXT Championship
    |
    |
    | 1
    | August 30, 2026
    | Edinburg, Texas
    |}
    """
        assert parse_champion_table(broken) == ()
