"""Builders for the OddsPortal DOM shapes the parsers key on.

The site carries no data-testid since 2026-09 (issue #86), so the parsers anchor
on hrefs, HTML semantics and text shape. These builders mirror the markup
captured live on 2026-09-02 and keep the fixtures in one place; see
`docs/agentic-gotchas.md` §20.
"""


def page(body: str) -> str:
    """Wrap markup in the nested <main> the SPA renders its content in."""
    return f"<main><div>nav</div><main>{body}</main></main>"


def listing_row(href: str, status: str = "21:00", home: str = "Home", away: str = "Away", style: str = "") -> str:
    """A listing row: the match link, its kickoff/status column and participants."""
    style_attr = f' style="{style}"' if style else ""
    return (
        f'<a href="{href}"{style_attr}>'
        f"<div><div><p>{status}</p></div></div>"
        f'<div><p class="truncate">{home}</p><p class="truncate">{away}</p></div>'
        f"</a>"
    )


def date_header(text: str) -> str:
    """A listing date-header: a leaf element holding only the group date."""
    return f"<div>{text}</div>"


def match_header(
    home: str = "Home",
    away: str = "Away",
    weekday: str = "Friday,",
    date: str = "04 Sep 2026,",
    time: str = "21:00",
    home_score: str = "",
    away_score: str = "",
    date_row_extra: str = "",
    breadcrumb: tuple[tuple[str, str], ...] = (("/football/", "Football"), ("/football/england/", "Premier League")),
) -> str:
    """The match header: breadcrumb, participants row and date row."""
    return page(match_header_body(home, away, weekday, date, time, home_score, away_score, date_row_extra, breadcrumb))


def match_header_body(
    home: str = "Home",
    away: str = "Away",
    weekday: str = "Friday,",
    date: str = "04 Sep 2026,",
    time: str = "21:00",
    home_score: str = "",
    away_score: str = "",
    date_row_extra: str = "",
    breadcrumb: tuple[tuple[str, str], ...] = (("/football/", "Football"), ("/football/england/", "Premier League")),
) -> str:
    """The match header markup, without the page wrapper."""
    crumbs = "".join(f'<li><a href="{href}">{label}</a></li>' for href, label in breadcrumb)
    home_cell = f"<div>{home_score}</div>" if home_score else ""
    away_cell = f"<div>{away_score}</div>" if away_score else ""
    return (
        f"<ul>{crumbs}</ul>"
        f"<div>"
        f'<div class="inline-flex font-secondary">'
        f'<div><div><p class="truncate">{home}</p></div>{home_cell}</div>'
        f"<span>-</span>"
        f'<div><div><p class="truncate">{away}</p></div>{away_cell}</div>'
        f"</div>"
        f"<hr/>"
        f"<div><div><p>{weekday}</p><p>{date}</p><p>{time}</p></div>{date_row_extra}</div>"
        f"</div>"
    )


def live_block(period: str, score: str, partial: str = "") -> str:
    """The header's live block: the pulse marker, period, running score, partial."""
    partial_html = f"<div><span>(</span><div>{partial}</div><span>)</span></div>" if partial else ""
    return (
        f'<div><div><p class="result-live"></p>'
        f'<div class="text-red-dark">{period}</div>'
        f'<div class="font-bold text-red-dark">{score}</div>{partial_html}</div></div>'
    )


def odds_cell(value: str, blocked: bool = False, betslip_slug: str | None = None) -> str:
    """One odds column cell: the value block the parsers pick odds columns by.

    Per-bookmaker cells link to that bookmaker's betslip; collapsed line rows
    show the same value block without a link.
    """
    inner = f'<span class="line-through">{value}</span>' if blocked else value
    if betslip_slug:
        inner = f'<a href="/proxy/bookmakers/{betslip_slug}/betslip/p/">{inner}</a>'
    return f'<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>{inner}</p></div></td>'


def bookmaker_row(name: str, odds: list[str], payout: str = "90.0%", blocked: tuple[int, ...] = ()) -> str:
    """An odds-table row for one bookmaker, identified by its bookmaker links."""
    slug = name.lower().replace(" ", "-").replace(".", "-")
    cells = "".join(odds_cell(value, blocked=i in blocked, betslip_slug=slug) for i, value in enumerate(odds))
    return (
        "<tr>"
        f'<td><a href="/proxy/bookmakers/{slug}/link/"><p>{name}</p></a>'
        f'<a href="/bookmakers/{slug}/">review</a></td>'
        f'{cells}<td class="w-[68px]"><span>{payout}</span></td>'
        "</tr>"
    )


def line_row(label: str, odds: list[str], short_label: str | None = None) -> str:
    """A collapsed submarket line row, marked by its expand arrow."""
    short = short_label or label
    cells = "".join(odds_cell(value) for value in odds)
    return (
        '<tr class="h-9 cursor-pointer">'
        '<td><img alt="arrow"/><span class="text-xs">'
        f'<span class="max-sm:hidden">{label}</span><span class="hidden max-sm:inline">{short}</span>'
        "</span></td>"
        f'{cells}<td class="w-[68px]"><span>90.0%</span></td>'
        "</tr>"
    )


def odds_table(rows: str, headers: tuple[str, ...] = ("Bookmakers", "1", "X", "2", "Payout")) -> str:
    """The odds table wrapped in the page content root."""
    head = "".join(f"<th>{h}</th>" for h in headers)
    return page(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")


def community_column(label: str, odds: str, pct: str, picked: bool = False) -> str:
    """One outcome column of a community row: label header, odds, vote percentage."""
    pick = '<div class="user-pred-pick"><span>PICK</span></div>' if picked else ""
    return (
        f'<div><div class="bg-gray-light">{label}</div>'
        f'<div><div><p class="font-bold">{odds}</p></div>'
        f"<div><div></div><div>{pct}</div></div>{pick}</div></div>"
    )


def community_row(
    href: str,
    columns: str,
    date: str = "Today",
    time: str = "20:45",
    market: str = "1X2",
    home: str = "Home",
    away: str = "Away",
    scores: tuple[str, str] | None = None,
) -> str:
    """A community row: the match link (date/market, participants) and its outcome columns."""
    home_score = f'<span class="font-bold">{scores[0]}</span>' if scores else ""
    away_score = f'<span class="font-bold">{scores[1]}</span>' if scores else ""
    return (
        f'<div><div><a href="{href}"><div>'
        f"<div><p>{date}</p><p>{time}</p><p>{date}, {time}</p><p><span>{market}</span></p></div>"
        f'<div>{home_score}<p class="truncate">{home}</p>{away_score}<p class="truncate">{away}</p></div>'
        f"</div></a></div>"
        f"<div>{columns}</div></div>"
    )


def community_section(
    rows: str, sport: str = "football", country: str = "England", league: str = "championship"
) -> str:
    """A community section: its sport/country/league breadcrumb followed by rows."""
    return page(
        "<div>"
        f'<div><a href="/{sport}/">{sport.title()}</a>'
        f'<a href="/{sport}/{country.lower()}/">{country}</a>'
        f'<a href="/{sport}/{country.lower()}/{league}/">{league.title()}</a></div>'
        f"{rows}</div>"
    )


def sub_nav_button(label: str, active: bool = False) -> str:
    """A sub-nav button (bookies filter or period); the selected one is bold."""
    style = ' style="background-color: rgb(47, 47, 47); font-weight: 700; color: rgb(255, 255, 255);"' if active else ""
    return f'<button type="button"{style}>{label}</button>'


def market_tab(label: str, active: bool = False) -> str:
    """A market tab; the active one carries font-bold on its label span."""
    weight = "font-bold" if active else "font-normal"
    return f'<li class="tab-item"><button><span><span class="{weight}">{label}</span></span></button></li>'


def votes_row(percentages: list[str]) -> str:
    """The User Predictions row rendered under the odds table."""
    cells = "".join(f"<div><div>{pct}</div></div>" for pct in percentages)
    return f'<div class="grid"><div><p>User Predictions</p></div>{cells}</div>'


def match_view(
    home: str = "Home",
    away: str = "Away",
    market: str = "1X2",
    scope: str = "Full Time",
    headers: tuple[str, ...] = ("Bookmakers", "1", "X", "2", "Payout"),
    rows: str = "",
    votes: list[str] | None = None,
    date_row_extra: str = "",
    home_score: str = "",
    away_score: str = "",
    **header_kwargs,
) -> str:
    """A rendered match view: header, market tabs, sub-nav, odds table and vote row."""
    tabs = "".join(market_tab(label, active=label == market) for label in ("1X2", "Over/Under", market))
    sub_nav = "".join(
        sub_nav_button(label, active=label == scope) for label in ("All Bookies", "Full Time", "1st Half", scope)
    )
    head = "".join(f"<th>{h}</th>" for h in headers)
    table = f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
    votes_html = votes_row(votes) if votes else ""
    return page(
        match_header_body(
            home=home,
            away=away,
            home_score=home_score,
            away_score=away_score,
            date_row_extra=date_row_extra,
            **header_kwargs,
        )
        + f"<ul>{tabs}</ul><div>{sub_nav}</div><div>{table}{votes_html}</div>"
    )


def profile_page(
    username: str = "BLAPRO",
    roi: str = "18.20%",
    member_since: str = "23 May 2026",
    country: str = "France",
    privacy: str = "Public",
    statistics: str = "",
    rows: str = "",
) -> str:
    """A community user profile: header, monthly statistics table and prediction rows."""
    table = (
        "<table><thead><tr><th>Month</th><th>Total Predictions</th><th>Won</th>"
        f"<th>Lost</th><th>+ / -</th><th>ROI</th></tr></thead><tbody>{statistics}</tbody></table>"
        if statistics
        else ""
    )
    return page(
        f"<div><h1>{username}</h1><div>ROI {roi}</div>"
        f"<ul><li><span>Member since: </span>{member_since}</li>"
        f"<li><span>Country:</span> {country}</li>"
        f"<li><span>Profile Privacy:</span> {privacy}</li></ul></div>"
        f"{table}{rows}"
    )


def statistics_row(month: str, cells: list[str]) -> str:
    """One month of the profile statistics table."""
    return "<tr>" + "".join(f"<td>{c}</td>" for c in [month, *cells]) + "</tr>"
