"""Canonical OddsPortal betting-type / scope IDs (stable across the site).

Used to decode the numeric ids embedded in match-page community vote keys
(E-<eventId>_<bettingTypeId>_<scopeId>_<col>_<handicap>). Unknown ids fall back
to a generic name so a new/unseen market never crashes the parse.
"""

BETTING_TYPE_NAMES = {
    1: "1X2",
    2: "Over/Under",
    3: "Home/Away",
    4: "Double Chance",
    5: "Asian Handicap",
    6: "Draw No Bet",
    8: "Correct Score",
    9: "HT/FT",
    12: "Odd/Even",
    13: "Both Teams To Score",
}

SCOPE_NAMES = {
    2: "Full Time",
    3: "1st Half",
    4: "2nd Half",
}
