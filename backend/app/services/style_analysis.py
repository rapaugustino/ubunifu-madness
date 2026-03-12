"""Matchup style analysis using Four Factors and advanced stats.

Classifies each team's playing style and identifies key style clashes
that could determine the outcome of a hypothetical matchup.
"""

from sqlalchemy.orm import Session

from app.models import Team, TeamSeasonStats

SEASON = 2026


def _classify_style(stats: TeamSeasonStats) -> dict:
    """Classify a team's playing style from their stats."""
    traits = []

    # Pace
    tempo = stats.avg_tempo or 67
    if tempo >= 70:
        traits.append("fast-paced")
    elif tempo <= 64:
        traits.append("slow, methodical")

    # Shooting profile
    three_pt_rate = stats.three_pt_rate or 0.33
    if three_pt_rate >= 0.40:
        traits.append("perimeter-oriented")
    elif three_pt_rate <= 0.28:
        traits.append("inside-out attack")

    efg = stats.avg_efg_pct or 0.50
    if efg >= 0.54:
        traits.append("elite shooting")
    elif efg <= 0.46:
        traits.append("struggles to score efficiently")

    # Defense
    opp_efg = stats.avg_opp_efg_pct or 0.50
    if opp_efg <= 0.46:
        traits.append("suffocating defense")
    elif opp_efg >= 0.52:
        traits.append("porous defense")

    opp_to = stats.avg_opp_to_pct or 18
    if opp_to >= 22:
        traits.append("disruptive (forces turnovers)")
    elif opp_to <= 16:
        traits.append("disciplined defense (low steals)")

    # Rebounding
    or_pct = stats.avg_or_pct or 30
    if or_pct >= 35:
        traits.append("dominant on the offensive glass")
    drb = stats.drb_pct or 70
    if drb >= 76:
        traits.append("excellent defensive rebounding")

    # Ball security
    to_pct = stats.avg_to_pct or 18
    if to_pct <= 15:
        traits.append("excellent ball security")
    elif to_pct >= 22:
        traits.append("turnover-prone")

    # Free throws
    ft_rate = stats.avg_ft_rate or 0.30
    if ft_rate >= 0.38:
        traits.append("gets to the free throw line")

    # Consistency
    if stats.margin_stdev is not None and stats.margin_stdev <= 8:
        traits.append("consistent game-to-game")
    elif stats.margin_stdev is not None and stats.margin_stdev >= 15:
        traits.append("volatile (boom or bust)")

    # Close games
    if stats.close_game_win_pct is not None:
        close_total = (stats.close_wins or 0) + (stats.close_losses or 0)
        if close_total >= 4 and stats.close_game_win_pct >= 0.70:
            traits.append("clutch in close games")
        elif close_total >= 4 and stats.close_game_win_pct <= 0.30:
            traits.append("struggles in close games")

    if not traits:
        traits.append("balanced")

    return {
        "traits": traits[:5],  # Cap at 5 most notable traits
        "summary": ", ".join(traits[:3]),
    }


def _find_clashes(stats_a: TeamSeasonStats, stats_b: TeamSeasonStats, style_a: dict, style_b: dict) -> list[str]:
    """Identify 2-3 key style clash insights between teams."""
    clashes = []

    # Pace mismatch
    tempo_a = stats_a.avg_tempo or 67
    tempo_b = stats_b.avg_tempo or 67
    tempo_diff = abs(tempo_a - tempo_b)
    if tempo_diff >= 5:
        fast = "A" if tempo_a > tempo_b else "B"
        clashes.append(
            f"Pace battle: {'Team A' if fast == 'A' else 'Team B'} wants to push tempo "
            f"({max(tempo_a, tempo_b):.1f} poss/g) vs a slower opponent ({min(tempo_a, tempo_b):.1f})"
        )

    # 3-point shooting vs interior defense
    three_a = stats_a.three_pt_rate or 0.33
    three_b = stats_b.three_pt_rate or 0.33
    if three_a >= 0.38 and (stats_b.avg_opp_efg_pct or 0.50) <= 0.47:
        clashes.append("Team A's perimeter attack faces a stout defense that limits efficient shooting")
    elif three_b >= 0.38 and (stats_a.avg_opp_efg_pct or 0.50) <= 0.47:
        clashes.append("Team B's perimeter attack faces a stout defense that limits efficient shooting")

    # Turnover battle
    to_a = stats_a.avg_to_pct or 18
    opp_to_b = stats_b.avg_opp_to_pct or 18
    to_b = stats_b.avg_to_pct or 18
    opp_to_a = stats_a.avg_opp_to_pct or 18

    if to_a >= 20 and opp_to_b >= 21:
        clashes.append("Team A's turnover issues could be exploited by Team B's ball-hawking defense")
    elif to_b >= 20 and opp_to_a >= 21:
        clashes.append("Team B's turnover issues could be exploited by Team A's ball-hawking defense")

    # Rebounding advantage
    or_a = stats_a.avg_or_pct or 30
    drb_b = stats_b.drb_pct or 70
    or_b = stats_b.avg_or_pct or 30
    drb_a = stats_a.drb_pct or 70
    if or_a >= 34 and drb_b <= 68:
        clashes.append("Team A's offensive rebounding could dominate Team B's weak defensive boards")
    elif or_b >= 34 and drb_a <= 68:
        clashes.append("Team B's offensive rebounding could dominate Team A's weak defensive boards")

    # Free throw disparity
    ft_a = stats_a.avg_ft_rate or 0.30
    ft_b = stats_b.avg_ft_rate or 0.30
    if abs(ft_a - ft_b) >= 0.10:
        physical = "A" if ft_a > ft_b else "B"
        clashes.append(f"Team {physical} gets to the line much more — could be decisive in a tight game")

    # Close-game experience
    cw_a = (stats_a.close_game_win_pct or 0.5) if (stats_a.close_wins or 0) + (stats_a.close_losses or 0) >= 3 else None
    cw_b = (stats_b.close_game_win_pct or 0.5) if (stats_b.close_wins or 0) + (stats_b.close_losses or 0) >= 3 else None
    if cw_a is not None and cw_b is not None and abs(cw_a - cw_b) >= 0.30:
        clutch = "A" if cw_a > cw_b else "B"
        clashes.append(f"If this comes down to the wire, Team {clutch} has the edge in close games")

    return clashes[:3]


def analyze_style_matchup(
    db: Session,
    team_a_id: int,
    team_b_id: int,
) -> dict | None:
    """Analyze the style matchup between two teams.

    Returns a dict with team styles, clash insights, and a summary,
    or None if stats aren't available.
    """
    team_a = db.query(Team).filter(Team.id == team_a_id).first()
    team_b = db.query(Team).filter(Team.id == team_b_id).first()
    if not team_a or not team_b:
        return None

    stats_a = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id
    ).first()
    stats_b = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id
    ).first()
    if not stats_a or not stats_b:
        return None

    style_a = _classify_style(stats_a)
    style_b = _classify_style(stats_b)

    # Replace "Team A/B" with actual names in clashes
    raw_clashes = _find_clashes(stats_a, stats_b, style_a, style_b)
    clashes = [
        c.replace("Team A", team_a.name).replace("Team B", team_b.name)
        for c in raw_clashes
    ]

    # Build summary
    if clashes:
        summary = f"{team_a.name} ({style_a['summary']}) vs {team_b.name} ({style_b['summary']}). {clashes[0]}"
    else:
        summary = f"{team_a.name} ({style_a['summary']}) vs {team_b.name} ({style_b['summary']})"

    return {
        "teamAStyle": {
            "name": team_a.name,
            "traits": style_a["traits"],
            "summary": style_a["summary"],
        },
        "teamBStyle": {
            "name": team_b.name,
            "traits": style_b["traits"],
            "summary": style_b["summary"],
        },
        "clashInsights": clashes,
        "summary": summary,
    }
