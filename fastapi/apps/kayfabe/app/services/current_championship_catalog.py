"""WWE 현역 챔피언 카탈로그 (thesmackdownhotel.com · 2026-06-28 기준)."""

from __future__ import annotations

from typing import Literal, TypedDict

ChampionshipTier = Literal["main", "secondary", "tag", "other"]
BrandId = Literal["raw", "smackdown", "nxt", "global"]
BrandAccent = Literal["red", "blue", "gold", "purple"]

CHAMPIONSHIP_AS_OF = "2026-06-28"


class _TitleReignEntry(TypedDict, total=False):
    belt_name: str
    champions: list[str]
    team_name: str
    won_at: str
    won_event: str
    tier: ChampionshipTier


class _BrandRosterEntry(TypedDict):
    id: BrandId
    label: str
    tagline: str
    accent: BrandAccent
    titles: list[_TitleReignEntry]


WWE_BRAND_CHAMPIONS: list[_BrandRosterEntry] = [
    {
        "id": "raw",
        "label": "Monday Night Raw",
        "tagline": "World Heavyweight · Women's World",
        "accent": "red",
        "titles": [
            {
                "belt_name": "World Heavyweight Championship",
                "champions": ["Roman Reigns"],
                "won_at": "2026-04-19",
                "won_event": "WrestleMania 42",
                "tier": "main",
            },
            {
                "belt_name": "Women's World Championship",
                "champions": ["Liv Morgan"],
                "won_at": "2026-04-18",
                "won_event": "WrestleMania 42",
                "tier": "main",
            },
            {
                "belt_name": "WWE Intercontinental Championship",
                "champions": ["Penta"],
                "won_at": "2026-03-02",
                "won_event": "Raw",
                "tier": "secondary",
            },
            {
                "belt_name": "Women's Intercontinental Championship",
                "champions": ["Sol Ruca"],
                "won_at": "2026-05-31",
                "won_event": "Clash in Italy",
                "tier": "secondary",
            },
            {
                "belt_name": "World Tag Team Championship",
                "team_name": "The Street Profits",
                "champions": ["Angelo Dawkins", "Montez Ford"],
                "won_at": "2026-06-22",
                "won_event": "Raw",
                "tier": "tag",
            },
        ],
    },
    {
        "id": "smackdown",
        "label": "Friday Night SmackDown",
        "tagline": "Undisputed WWE · Women's",
        "accent": "blue",
        "titles": [
            {
                "belt_name": "Undisputed WWE Championship",
                "champions": ["Sami Zayn"],
                "won_at": "2026-06-27",
                "won_event": "Night of Champions",
                "tier": "main",
            },
            {
                "belt_name": "WWE Women's Championship",
                "champions": ["Rhea Ripley"],
                "won_at": "2026-04-19",
                "won_event": "WrestleMania 42",
                "tier": "main",
            },
            {
                "belt_name": "WWE United States Championship",
                "champions": ["Trick Williams"],
                "won_at": "2026-04-19",
                "won_event": "WrestleMania 42",
                "tier": "secondary",
            },
            {
                "belt_name": "Women's United States Championship",
                "champions": ["Tiffany Stratton"],
                "won_at": "2026-04-24",
                "won_event": "SmackDown",
                "tier": "secondary",
            },
            {
                "belt_name": "WWE Tag Team Championship",
                "champions": ["Damian Priest", "R-Truth"],
                "won_at": "2026-03-20",
                "won_event": "SmackDown",
                "tier": "tag",
            },
        ],
    },
    {
        "id": "nxt",
        "label": "NXT",
        "tagline": "Developmental · Gold Rush",
        "accent": "gold",
        "titles": [
            {
                "belt_name": "NXT Championship",
                "champions": ["Tony D'Angelo"],
                "won_at": "2026-04-04",
                "won_event": "Stand & Deliver",
                "tier": "main",
            },
            {
                "belt_name": "NXT Women's Championship",
                "champions": ["Lola Vice"],
                "won_at": "2026-04-04",
                "won_event": "Stand & Deliver",
                "tier": "main",
            },
            {
                "belt_name": "NXT North American Championship",
                "champions": ["Myles Borne"],
                "won_at": "2026-02-24",
                "won_event": "NXT",
                "tier": "secondary",
            },
            {
                "belt_name": "NXT Women's North American Championship",
                "champions": ["Zaria"],
                "won_at": "2026-06-09",
                "won_event": "NXT",
                "tier": "secondary",
            },
            {
                "belt_name": "NXT Tag Team Championship",
                "team_name": "The Vanity Project",
                "champions": ["Brad Baylor", "Ricky Smokes"],
                "won_at": "2026-02-24",
                "won_event": "NXT",
                "tier": "tag",
            },
        ],
    },
    {
        "id": "global",
        "label": "브랜드 공통 · 디벨롭먼트",
        "tagline": "Speed · Evolve · ID",
        "accent": "purple",
        "titles": [
            {
                "belt_name": "WWE Women's Tag Team Championship",
                "champions": ["Paige", "Brie Bella"],
                "won_at": "2026-04-18",
                "won_event": "WrestleMania 42",
                "tier": "tag",
            },
            {
                "belt_name": "WWE Speed Championship",
                "champions": ["Lexis King"],
                "won_at": "2026-04-21",
                "won_event": "NXT Revenge",
                "tier": "other",
            },
            {
                "belt_name": "WWE Women's Speed Championship",
                "champions": ["Wren Sinclair"],
                "won_at": "2026-03-17",
                "won_event": "NXT",
                "tier": "other",
            },
            {
                "belt_name": "WWE Evolve Championship",
                "champions": ["Aaron Rourke"],
                "won_at": "2026-03-18",
                "won_event": "Evolve",
                "tier": "other",
            },
            {
                "belt_name": "WWE Evolve Women's Championship",
                "champions": ["Nikkita Lyons"],
                "won_at": "2026-06-24",
                "won_event": "Evolve Succession III",
                "tier": "other",
            },
            {
                "belt_name": "WWE ID Championship",
                "champions": ["Max Abrams"],
                "won_at": "2026-06-26",
                "tier": "other",
            },
            {
                "belt_name": "WWE ID Women's Championship",
                "champions": ["Laynie Luck"],
                "won_at": "2025-11-17",
                "tier": "other",
            },
        ],
    },
]
