"""PLE 카드 로스터명 → 개인 링네임 (태그/스테이블 확장)."""

from __future__ import annotations

import re


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


# frontend/lib/wrestler-info.ts WRESTLER_REGISTRY 와 동기화
TEAM_MEMBERS: dict[str, list[str]] = {
    "#DIY": ["Johnny Gargano", "Tommaso Ciampa"],
    "The Wyatt Sicks": ["Bo Dallas", "Dexter Lumis", "Joe Gacy"],
    "Motor City Machine Guns": ["Alex Shelley", "Chris Sabin"],
    "Fraxiom": ["Nathan Frazer", "Axiom"],
    "The Street Profits": ["Montez Ford", "Angelo Dawkins"],
    "Andrade & Rey Fénix": ["Andrade", "Rey Fénix"],
    "Alexa Bliss & Charlotte Flair": ["Alexa Bliss", "Charlotte Flair"],
    "Raquel Rodriguez & Roxanne Perez": ["Raquel Rodriguez", "Roxanne Perez"],
    "Roman Reigns & Jey Uso": ["Roman Reigns", "Jey Uso"],
    "Bron Breakker & Bronson Reed": ["Bron Breakker", "Bronson Reed"],
    "Drew McIntyre & Logan Paul": ["Drew McIntyre", "Logan Paul"],
    "Randy Orton & Jelly Roll": ["Randy Orton", "Jelly Roll"],
    "Paige & Brie Bella": ["Paige", "Brie Bella"],
    "Nia Jax & Lash Legend": ["Nia Jax", "Lash Legend"],
    "Bayley & Lyra Valkyria": ["Bayley", "Lyra Valkyria"],
    "LA Knight & The Usos": ["LA Knight", "Jey Uso", "Jimmy Uso"],
    "Rhodes & Jey Uso": ["Cody Rhodes", "Jey Uso"],
    "Cena & Logan Paul": ["John Cena", "Logan Paul"],
    "Danhausen & Minihausen": ["Danhausen", "Minihausen"],
    "The Miz & Kit Wilson": ["The Miz", "Kit Wilson"],
    "The Vanity Project": ["Brad Baylor", "Ricky Smokes"],
    "Los Americanos": ["Bravo", "Rayo"],
    # Stand & Deliver 2026 10-person mixed tag (실제 NXT BirthRight)
    "BirthRight": [
        "Arianna Grace",
        "Channing Lorenzo",
        "Lexis King",
        "Uriah Connors",
        "Charlie Dempsey",
    ],
    "Sinclair, Hank & Tank, EK Prosper, Shiloh Hill": [
        "Wren Sinclair",
        "Hank Walker",
        "Tank Ledger",
        "EK Prosper",
        "Shiloh Hill",
    ],
    "IShowSpeed & The Vision": [
        "IShowSpeed",
        "Bron Breakker",
        "Bronson Reed",
        "Logan Paul",
        "Austin Theory",
    ],
}


def is_team_roster_name(name: str) -> bool:
    key = normalize_name(name)
    if key in TEAM_MEMBERS:
        return True
    return " & " in key


def expand_roster_name(name: str) -> list[str]:
    """로스터명(태그팀·스테이블)을 개인 링네임 목록으로 펼친다."""
    key = normalize_name(name)
    if not key:
        return []
    if key in TEAM_MEMBERS:
        return [normalize_name(m) for m in TEAM_MEMBERS[key]]
    if " & " in key:
        return [normalize_name(p) for p in key.split(" & ") if p.strip()]
    return [key]


def individual_in_roster_entry(roster_name: str, individual: str) -> bool:
    target = normalize_name(individual)
    return any(normalize_name(m) == target for m in expand_roster_name(roster_name))


def unique_individuals(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        for member in expand_roster_name(name):
            if member not in seen:
                seen.add(member)
                out.append(member)
    return out
