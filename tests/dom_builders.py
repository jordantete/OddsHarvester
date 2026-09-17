"""Builders for the OddsPortal DOM shapes the parsers key on.

The site carries no data-testid since 2026-09 (issue #86), so the parsers anchor
on hrefs, HTML semantics and text shape. These builders mirror the markup
captured live on 2026-09-02 and keep the fixtures in one place; see
`docs/agentic-gotchas.md` §20.
"""

import json
from urllib.parse import quote


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


def form_event(text: str, url: str) -> dict:
    """One entry of the Last 6 Games block: its tooltip text and the match it links to."""
    return {"text": text, "url": url}


def team_page(
    name: str = "Liverpool",
    full_name: str = "Liverpool Football Club",
    logo_src: str = "/proxy/serve/images/team-logo/Men/K00665Rc-KCp4zq5F.png?260917091420",
    basic_info: dict | None = None,
    last_performance: dict | None = None,
    with_payload: bool = True,
    sport_href: str = "/football/",
    leagues: tuple[tuple[str, str], ...] = (),
) -> str:
    """A team page: breadcrumb, header logo and the flight-data payload the parser reads.

    A page built with ``with_payload=False`` is what a wrong team id returns: the
    breadcrumb and heading are still built from the URL slug, so it looks valid.
    """
    # The nav menus end on a link-less item too, just like the breadcrumb does.
    nav = '<ul><li><a href="/football/">Football</a></li><li><span>More</span></li></ul>'
    crumb = (
        '<ul class="hidden items-center min-md:flex">'
        f'<li class="flex items-center"><a class="text-orange-deep" href="{sport_href}">Football</a>'
        '<span class="mx-2 text-xs">&gt;</span></li>'
        f'<li class="flex items-center"><span class="text-[0.70rem] capitalize">{name}</span></li></ul>'
    )
    # The header logo only ever appears URL-encoded inside a Next image srcset.
    srcset = f"/_next/image?url={quote(logo_src, safe='')}&amp;w=48&amp;q=75 1x"
    header = (
        f'<div class="my-3 flex flex-col gap-2"><div class="flex items-center gap-2">'
        f'<div class="flex-center h-[47px] w-[47px]">'
        f'<img alt="{full_name}" loading="lazy" width="47" height="44" srcset="{srcset}"/>'
        f'</div><h1 class="title w-full">{name} Betting Odds, Results &amp; Fixtures</h1></div></div>'
    )
    script = ""
    if with_payload:
        payload = json.dumps(
            {
                # Fixture rows carry their own teams' logos, ahead of the header's.
                "opponentLogo": "/proxy/serve/images/team-logo/Men/0n1ffK6k-vcNAdtF9.png?260917091420",
                "alt": full_name,
                "data": {
                    "basicInfo": basic_info if basic_info is not None else _LIVERPOOL_BASIC_INFO,
                    "lastPerformance": (
                        last_performance if last_performance is not None else _LIVERPOOL_LAST_PERFORMANCE
                    ),
                    "matchFacts": [],
                },
            }
        )
        # The flight data ships inside a JS string literal, so its quotes arrive escaped.
        script = f'<script>self.__next_f.push([1,"9a:{payload.replace(chr(34), chr(92) + chr(34))}"])</script>'
    rows = "".join(
        f'<div class="flex min-w-0 gap-1 text-xs"><a class="flex min-w-0 items-center" href="{href}">'
        f'<p class="font-primary min-w-0 truncate">{label}</p></a></div>'
        for href, label in leagues
    )
    # The footer repeats the breadcrumb's list-item shape with unrelated text.
    footer = "<ul><li><span>label</span></li></ul>"
    return page(f"{nav}{crumb}{header}{rows}{script}{footer}")


_LIVERPOOL_BASIC_INFO = {
    "countryImage": "https://cci2.oddsportal.com/country-flags/198.svg",
    "venueCountry": "England",
    "venueTown": "Liverpool",
    "venue": "Anfield",
    "coach": "Iraola Andoni",
}

_LIVERPOOL_LAST_PERFORMANCE = {
    "form": ["W", "D", "W", "W", "D", "D"],
    "formEvents": [
        form_event(
            "3:1 (Liverpool - Tottenham) 15.09.2026",
            "https://www.oddsportal.com/football/h2h/liverpool-lId4TMwf/tottenham-UDg08Ohm/#0vdKBukB/",
        ),
        form_event(
            "0:0 (Burnley - Liverpool) 08.09.2026",
            "https://www.oddsportal.com/football/h2h/burnley-Ea2Ehy1c/liverpool-lId4TMwf/#Ln4JsV3x/",
        ),
        # The URL leads with the page's own team while the tooltip has it away:
        # the two orders disagree, as they do on the live pages.
        form_event(
            "1:2 (Everton - Liverpool) 01.09.2026",
            "https://www.oddsportal.com/football/h2h/liverpool-lId4TMwf/everton-Oc9WrCqL/#Rt7KpQ2m/",
        ),
    ],
    "avgGoalsScored": "1.8",
    "avgGoalsConceded": "1.0",
    "metric": "goals",
    "scoredBtsPercent": "67%",
    "scoredOverPercent": "33%",
    "shutoutGamesPercent": "",
    "_meta": {"overThreshold": 2.5},
}
