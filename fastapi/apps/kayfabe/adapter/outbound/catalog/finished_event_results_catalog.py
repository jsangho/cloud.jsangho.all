from __future__ import annotations

from kayfabe.app.dtos.ple_events_dto import MatchResultResponse

FINISHED_EVENT_RESULTS: dict[str, dict[str, MatchResultResponse]] = {
    "royal-rumble": {
        "rr26-gunther-styles": MatchResultResponse(
            winner_side="left", winner_name="Gunther"
        ),
        "rr26-undisputed": MatchResultResponse(
            winner_side="left", winner_name="Drew McIntyre"
        ),
        "rr26-women-rumble": MatchResultResponse(
            winner_index=1, winner_name="Liv Morgan"
        ),
        "rr26-men-rumble": MatchResultResponse(
            winner_index=0, winner_name="Roman Reigns"
        ),
    },
    "elimination-chamber": {
        "ec26-women": MatchResultResponse(winner_index=0, winner_name="Rhea Ripley"),
        "ec26-women-ic": MatchResultResponse(winner_side="left", winner_name="AJ Lee"),
        "ec26-whc": MatchResultResponse(winner_side="left", winner_name="CM Punk"),
        "ec26-men": MatchResultResponse(winner_index=0, winner_name="Randy Orton"),
    },
    "stand-and-deliver": {
        "sad26-preshow": MatchResultResponse(winner_side="left"),
        "sad26-sol-zaria": MatchResultResponse(
            winner_side="left", winner_name="Sol Ruca"
        ),
        "sad26-women-na": MatchResultResponse(
            winner_side="left", winner_name="Tatum Paxley"
        ),
        "sad26-na": MatchResultResponse(winner_side="left", winner_name="Myles Borne"),
        "sad26-tag": MatchResultResponse(
            winner_side="left", winner_name="The Vanity Project"
        ),
        "sad26-women": MatchResultResponse(winner_index=0, winner_name="Lola Vice"),
        "sad26-nxt": MatchResultResponse(winner_index=0, winner_name="Tony D'Angelo"),
    },
    "wrestlemania": {
        "wm42-n1-six": MatchResultResponse(winner_side="left"),
        "wm42-n1-unsanctioned": MatchResultResponse(
            winner_side="left", winner_name="Jacob Fatu"
        ),
        "wm42-n1-women-tag": MatchResultResponse(winner_index=0),
        "wm42-n1-women-ic": MatchResultResponse(
            winner_side="left", winner_name="Becky Lynch"
        ),
        "wm42-n1-gunther-rollins": MatchResultResponse(
            winner_side="left", winner_name="Gunther"
        ),
        "wm42-n1-women-world": MatchResultResponse(
            winner_side="left", winner_name="Liv Morgan"
        ),
        "wm42-n1-undisputed": MatchResultResponse(
            winner_side="left", winner_name="Cody Rhodes"
        ),
        "wm42-n2-femi-lesnar": MatchResultResponse(
            winner_side="left", winner_name="Oba Femi"
        ),
        "wm42-n2-ic-ladder": MatchResultResponse(winner_index=0, winner_name="Penta"),
        "wm42-n2-us": MatchResultResponse(
            winner_side="left", winner_name="Trick Williams"
        ),
        "wm42-n2-street": MatchResultResponse(
            winner_side="left", winner_name="Finn Bálor"
        ),
        "wm42-n2-women": MatchResultResponse(
            winner_side="left", winner_name="Rhea Ripley"
        ),
        "wm42-n2-whc": MatchResultResponse(
            winner_side="left", winner_name="Roman Reigns"
        ),
    },
    "backlash": {
        "bl26-danhausen": MatchResultResponse(winner_side="left"),
        "bl26-iyo-asuka": MatchResultResponse(
            winner_side="left", winner_name="IYO SKY"
        ),
        "bl26-us": MatchResultResponse(
            winner_side="left", winner_name="Trick Williams"
        ),
        "bl26-breakker-rollins": MatchResultResponse(
            winner_side="left", winner_name="Bron Breakker"
        ),
        "bl26-whc": MatchResultResponse(winner_side="left", winner_name="Roman Reigns"),
    },
}

FINISHED_EVENT_SLUGS: frozenset[str] = frozenset(FINISHED_EVENT_RESULTS.keys())
