"""CLI constants for period and odds format mappings."""

# Period short forms -> internal values mapping
# Maps CLI short forms to the original enum values used internally
PERIOD_SHORT_TO_INTERNAL = {
    # Full time variants
    "ft": "full_time",
    "ft-ot": "full_including_ot",
    # Halves
    "1h": "1st_half",
    "2h": "2nd_half",
    # Quarters
    "1q": "1st_quarter",
    "2q": "2nd_quarter",
    "3q": "3rd_quarter",
    "4q": "4th_quarter",
    # Sets (tennis)
    "1s": "1st_set",
    "2s": "2nd_set",
    # Periods (ice hockey)
    "1p": "1st_period",
    "2p": "2nd_period",
    "3p": "3rd_period",
}

# Reverse mapping for display
PERIOD_INTERNAL_TO_SHORT = {v: k for k, v in PERIOD_SHORT_TO_INTERNAL.items()}

# Sport -> valid period short forms
SPORT_PERIODS = {
    "football": ["ft", "1h", "2h"],
    "tennis": ["ft", "1s", "2s"],
    "basketball": ["ft-ot", "1h", "2h", "1q", "2q", "3q", "4q"],
    "rugby-league": ["ft", "1h"],
    "rugby-union": ["ft", "1h"],
    "american-football": ["ft-ot", "1h", "2h", "1q", "2q", "3q", "4q"],
    "ice-hockey": ["ft", "1p", "2p", "3p"],
    "baseball": ["ft-ot", "ft", "1h"],
}

# Default periods per sport
SPORT_DEFAULT_PERIOD = {
    "football": "ft",
    "tennis": "ft",
    "basketball": "ft-ot",
    "rugby-league": "ft",
    "rugby-union": "ft",
    "american-football": "ft-ot",
    "ice-hockey": "ft",
    "baseball": "ft-ot",
}

# Odds format short forms -> internal values
ODDS_FORMAT_SHORT_TO_INTERNAL = {
    "decimal": "Decimal Odds",
    "fractional": "Fractional Odds",
    "american": "Money Line Odds",
    "hong-kong": "Hong Kong Odds",
}

ODDS_FORMAT_CHOICES = list(ODDS_FORMAT_SHORT_TO_INTERNAL.keys())

# Bookmakers filter choices
BOOKMAKERS_CHOICES = ["all", "classic", "crypto"]

# Storage choices
STORAGE_CHOICES = ["local", "remote"]
FORMAT_CHOICES = ["json", "csv"]

# All valid period choices (union of all sports)
ALL_PERIOD_CHOICES = sorted({p for periods in SPORT_PERIODS.values() for p in periods})
