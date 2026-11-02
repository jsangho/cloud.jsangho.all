"""남자부 / 여자부. **운영 명부에 성별 칸이 없어서 여기 따로 둔다.**

`wrestlers` 표 · CSV · 로스터 카탈로그 어디에도 부(division)가 없다(2026-11-02 실측).
커리어 세계는 한 부의 선수만으로 짓기 때문에(남녀가 한 대진에 서지 않게) 이 명단이
필요하다.

**여자부만 적는다** — 여기 없는 현역은 남자부다. 이름은 운영 명부의 표기를 그대로
쓴다(오타 `Stepahnie Vaquer` 도 명부 표기다 — 고치면 매칭이 끊긴다).

**사람이 검토하는 명단이다.** 명부에 선수가 들어오면 여기도 함께 본다 —
`tests/app/services/test_career_roster.py` 가 카탈로그 현역과 이 명단의 교집합을
세어 여자부가 비지 않았는지 지킨다.
"""

from __future__ import annotations

WOMEN: frozenset[str] = frozenset(
    {
        "AJ Lee",
        "Asuka",
        "Bayley",
        "Becky Lynch",
        "Brie Bella",
        "Ivy Nile",
        "Iyo Sky",
        "Liv Morgan",
        "Lyra Valkyria",
        "Maxxine Dupri",
        "Nattie",
        "Nikki Bella",
        "Raquel Rodriguez",
        "Roxanne Perez",
        "Sol Ruca",
        "Stepahnie Vaquer",
        "Alexa Bliss",
        "B-Fab",
        "Bianca Belair",
        "Blake Monroe",
        "Candice LeRae",
        "Charlotte Flair",
        "Chelsea Green",
        "Fallon Henley",
        "Giulia",
        "Jacy Jayne",
        "Jade Cargill",
        "Jordynne Grace",
        "Kiana James",
        "Lainey Reid",
        "Lash Legend",
        "Michin",
        "Nia Jax",
        "Naomi",
        "Piper Niven",
        "Rhea Ripley",
        "Tiffany Stratton",
        "Paige",
        "Arianna Grace",
        "Izzi Dame",
        "Jaida Parker",
        "Kali Armstrong",
        "Karmen Petrovic",
        "Kelani Jordan",
        "Kendal Grey",
        "Layla Diggs",
        "Lizzy Rain",
        "Lola Vice",
        "Myka Lockwood",
        "Nikkita Lyons",
        "Reina Volcán",
        "Skylar Raye",
        "Tatum Paxley",
        "Thea Hail",
        "Wren Sinclair",
        "Zaria",
    }
)
