"""
Compute advanced analytics metrics for TeamSeasonStats.

Computes opponent-adjusted efficiency, Pythagorean luck, shooting metrics,
consistency/volatility, floor/ceiling, and upset vulnerability.

Can be called from compute_stats.py (CSV pipeline) or cron (DB pipeline).
"""

import numpy as np
from collections import defaultdict

from app.models import TeamSeasonStats, GameResult


PYTH_EXPONENT = 9       # Sports-Reference uses 9 for CBB
BARTHAG_EXPONENT = 11.5  # BartTorvik's Pythagorean exponent for efficiency
ADJ_ITERATIONS = 10      # Iterations for adjusted efficiency convergence
HOME_COURT_ADJ = 3.5     # KenPom-style home court advantage (eff pts per 100 poss)


def r(val, digits=2):
    """Round and convert to Python float."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return float(round(val, digits))


def compute_advanced_stats(session, season: int, gender: str = None):
    """
    Compute advanced metrics for all teams in a season.
    Updates TeamSeasonStats rows in-place. Caller must commit.

    Args:
        session: SQLAlchemy session
        season: Season year (e.g. 2026)
        gender: 'M', 'W', or None for both
    """
    genders = [gender] if gender else ["M", "W"]
    total_updated = 0

    for g in genders:
        # Load all games for this season+gender with box score data
        games = (
            session.query(GameResult)
            .filter(GameResult.season == season, GameResult.gender == g)
            .all()
        )
        if not games:
            continue

        # Build per-team game-level stats
        team_games = defaultdict(list)  # team_id -> [{off_eff, def_eff, margin, poss, ...}]
        team_totals = defaultdict(lambda: {
            "pts_for": 0, "pts_against": 0,
            "fga": 0, "fga3": 0, "fta": 0, "pts": 0,
            "ast": 0, "tov": 0, "drb": 0, "opp_orb": 0,
            "stl": 0, "blk": 0, "opp_2pa": 0, "opp_poss": 0,
            "opp_pts": 0, "opp_fga": 0, "opp_fta": 0,
            "close_wins": 0, "close_losses": 0,
            "games_with_box": 0, "games_total": 0,
        })

        for game in games:
            margin = game.w_score - game.l_score
            has_box = game.w_fga is not None and game.w_fga > 0

            # Always track points for Pythagorean (compact results have scores)
            team_totals[game.w_team_id]["pts_for"] += game.w_score
            team_totals[game.w_team_id]["pts_against"] += game.l_score
            team_totals[game.w_team_id]["games_total"] += 1
            team_totals[game.l_team_id]["pts_for"] += game.l_score
            team_totals[game.l_team_id]["pts_against"] += game.w_score
            team_totals[game.l_team_id]["games_total"] += 1

            # Close games (decided by 5 or fewer)
            if margin <= 5:
                team_totals[game.w_team_id]["close_wins"] += 1
                team_totals[game.l_team_id]["close_losses"] += 1

            if not has_box:
                # Still record margin for consistency stats
                team_games[game.w_team_id].append({"margin": margin, "has_box": False})
                team_games[game.l_team_id].append({"margin": -margin, "has_box": False})
                continue

            # Compute possessions
            poss_w = game.w_fga - (game.w_or or 0) + (game.w_to or 0) + 0.44 * game.w_fta
            poss_l = game.l_fga - (game.l_or or 0) + (game.l_to or 0) + 0.44 * game.l_fta
            poss = max((poss_w + poss_l) / 2, 1)

            off_eff_w = game.w_score / poss * 100
            def_eff_w = game.l_score / poss * 100
            off_eff_l = game.l_score / poss * 100
            def_eff_l = game.w_score / poss * 100

            # Home court adjustment (KenPom-style): neutralize location
            # Home team gets offense inflated / defense deflated by venue
            loc = game.w_loc  # H=winner at home, A=winner away, N=neutral
            hca = HOME_COURT_ADJ / 2  # Split adjustment between offense and defense
            if loc == "H":
                # Winner was home — subtract advantage from their stats
                off_eff_w -= hca
                def_eff_w += hca
                off_eff_l += hca
                def_eff_l -= hca
            elif loc == "A":
                # Winner was away — add advantage (they performed in hostile venue)
                off_eff_w += hca
                def_eff_w -= hca
                off_eff_l -= hca
                def_eff_l += hca
            # loc == "N" or None: no adjustment

            # Winner game record
            team_games[game.w_team_id].append({
                "margin": margin,
                "off_eff": off_eff_w,
                "def_eff": def_eff_w,
                "net_eff": off_eff_w - def_eff_w,
                "opp_id": game.l_team_id,
                "poss": poss,
                "has_box": True,
            })
            # Loser game record
            team_games[game.l_team_id].append({
                "margin": -margin,
                "off_eff": off_eff_l,
                "def_eff": def_eff_l,
                "net_eff": off_eff_l - def_eff_l,
                "opp_id": game.w_team_id,
                "poss": poss,
                "has_box": True,
            })

            # Accumulate box score totals for winner
            tw = team_totals[game.w_team_id]
            tw["fga"] += game.w_fga
            tw["fga3"] += (game.w_fga3 or 0)
            tw["fta"] += game.w_fta
            tw["pts"] += game.w_score
            tw["ast"] += (game.w_ast or 0)
            tw["tov"] += (game.w_to or 0)
            tw["drb"] += (game.w_dr or 0)
            tw["opp_orb"] += (game.l_or or 0)
            tw["stl"] += (game.w_stl or 0)
            tw["blk"] += (game.w_blk or 0)
            tw["opp_2pa"] += game.l_fga - (game.l_fga3 or 0)
            tw["opp_poss"] += poss
            tw["opp_pts"] += game.l_score
            tw["opp_fga"] += game.l_fga
            tw["opp_fta"] += game.l_fta
            tw["games_with_box"] += 1

            # Accumulate box score totals for loser
            tl = team_totals[game.l_team_id]
            tl["fga"] += game.l_fga
            tl["fga3"] += (game.l_fga3 or 0)
            tl["fta"] += game.l_fta
            tl["pts"] += game.l_score
            tl["ast"] += (game.l_ast or 0)
            tl["tov"] += (game.l_to or 0)
            tl["drb"] += (game.l_dr or 0)
            tl["opp_orb"] += (game.w_or or 0)
            tl["stl"] += (game.l_stl or 0)
            tl["blk"] += (game.l_blk or 0)
            tl["opp_2pa"] += game.w_fga - (game.w_fga3 or 0)
            tl["opp_poss"] += poss
            tl["opp_pts"] += game.w_score
            tl["opp_fga"] += game.w_fga
            tl["opp_fta"] += game.w_fta
            tl["games_with_box"] += 1

        # --- Compute raw efficiency per team (possession-weighted) ---
        raw_oe = {}  # team_id -> raw offensive efficiency
        raw_de = {}  # team_id -> raw defensive efficiency
        for tid, games_list in team_games.items():
            box_games = [g for g in games_list if g.get("has_box") and "off_eff" in g]
            if box_games:
                poss_arr = np.array([g["poss"] for g in box_games])
                total_poss = poss_arr.sum()
                if total_poss > 0:
                    raw_oe[tid] = np.average([g["off_eff"] for g in box_games], weights=poss_arr)
                    raw_de[tid] = np.average([g["def_eff"] for g in box_games], weights=poss_arr)

        if not raw_oe:
            continue

        # National averages
        nat_avg_oe = np.mean(list(raw_oe.values()))
        nat_avg_de = np.mean(list(raw_de.values()))

        # --- Adjusted Efficiency (iterative opponent adjustment) ---
        adj_oe = dict(raw_oe)
        adj_de = dict(raw_de)

        for _ in range(ADJ_ITERATIONS):
            new_adj_oe = {}
            new_adj_de = {}
            for tid, games_list in team_games.items():
                box_games = [g for g in games_list if g.get("has_box") and "opp_id" in g]
                if not box_games:
                    continue

                # Adjust each game's efficiency by opponent strength (possession-weighted)
                adj_oe_games = []
                adj_de_games = []
                poss_weights = []
                for gm in box_games:
                    opp = gm["opp_id"]
                    # Adjust offense: scale by (nat avg defense / opponent's defense)
                    opp_de = adj_de.get(opp, nat_avg_de)
                    adj_oe_games.append(gm["off_eff"] * (nat_avg_de / max(opp_de, 1)))
                    # Adjust defense: scale by (nat avg offense / opponent's offense)
                    opp_oe = adj_oe.get(opp, nat_avg_oe)
                    adj_de_games.append(gm["def_eff"] * (nat_avg_oe / max(opp_oe, 1)))
                    poss_weights.append(gm["poss"])

                poss_arr = np.array(poss_weights)
                new_adj_oe[tid] = np.average(adj_oe_games, weights=poss_arr)
                new_adj_de[tid] = np.average(adj_de_games, weights=poss_arr)

            adj_oe = new_adj_oe
            adj_de = new_adj_de

        # --- Update TeamSeasonStats ---
        stats_rows = (
            session.query(TeamSeasonStats)
            .filter(TeamSeasonStats.season == season)
            .join(TeamSeasonStats.team)
            .all()
        )
        # Filter by gender
        stats_by_tid = {}
        for s in stats_rows:
            if s.team and s.team.gender == g:
                stats_by_tid[s.team_id] = s

        for tid, stat in stats_by_tid.items():
            tt = team_totals.get(tid)
            tg = team_games.get(tid, [])
            if not tt:
                continue

            # Adjusted efficiency
            if tid in adj_oe:
                stat.adj_off_eff = r(adj_oe[tid], 1)
                stat.adj_def_eff = r(adj_de[tid], 1)
                stat.adj_net_eff = r(adj_oe[tid] - adj_de[tid], 1)
                # Barthag: win prob vs average team
                oe = adj_oe[tid]
                de = adj_de[tid]
                barthag = oe ** BARTHAG_EXPONENT / (
                    oe ** BARTHAG_EXPONENT + de ** BARTHAG_EXPONENT
                )
                stat.barthag = r(barthag, 4)

            # Pythagorean luck
            pf = tt["pts_for"]
            pa = tt["pts_against"]
            if pf > 0 and pa > 0:
                pyth = pf ** PYTH_EXPONENT / (
                    pf ** PYTH_EXPONENT + pa ** PYTH_EXPONENT
                )
                stat.pyth_win_pct = r(pyth, 4)
                stat.luck = r((stat.win_pct or 0) - pyth, 4)

            # Shooting & style metrics (need box score data)
            if tt["games_with_box"] > 0:
                # True shooting %
                if tt["fga"] > 0:
                    ts = tt["pts"] / (2 * (tt["fga"] + 0.44 * tt["fta"]))
                    stat.true_shooting_pct = r(ts, 4)

                # Opponent true shooting %
                if tt["opp_fga"] > 0:
                    opp_ts = tt["opp_pts"] / (2 * (tt["opp_fga"] + 0.44 * tt["opp_fta"]))
                    stat.opp_true_shooting_pct = r(opp_ts, 4)

                # 3-point attempt rate
                if tt["fga"] > 0:
                    stat.three_pt_rate = r(tt["fga3"] / tt["fga"], 4)

                # Assist-to-turnover ratio
                if tt["tov"] > 0:
                    stat.ast_to_ratio = r(tt["ast"] / tt["tov"], 2)

                # Defensive rebound %
                total_drb_opp_orb = tt["drb"] + tt["opp_orb"]
                if total_drb_opp_orb > 0:
                    stat.drb_pct = r(tt["drb"] / total_drb_opp_orb, 4)

                # Steal %
                if tt["opp_poss"] > 0:
                    stat.stl_pct = r(tt["stl"] / tt["opp_poss"] * 100, 2)

                # Block %
                if tt["opp_2pa"] > 0:
                    stat.blk_pct = r(tt["blk"] / tt["opp_2pa"] * 100, 2)

            # Close game record
            close_total = tt["close_wins"] + tt["close_losses"]
            stat.close_wins = tt["close_wins"]
            stat.close_losses = tt["close_losses"]
            if close_total > 0:
                stat.close_game_win_pct = r(tt["close_wins"] / close_total, 4)

            # Consistency & volatility
            margins = [gm["margin"] for gm in tg]
            if len(margins) >= 3:
                stat.margin_stdev = r(np.std(margins), 1)

            box_games = [gm for gm in tg if gm.get("has_box") and "off_eff" in gm]
            if len(box_games) >= 5:
                oe_values = [gm["off_eff"] for gm in box_games]
                stat.off_eff_stdev = r(np.std(oe_values), 1)

                # Floor / ceiling (10th/90th percentile net efficiency)
                net_values = [gm["net_eff"] for gm in box_games]
                stat.floor_eff = r(np.percentile(net_values, 10), 1)
                stat.ceiling_eff = r(np.percentile(net_values, 90), 1)

            # Upset vulnerability index (0-100)
            # Combines: high variance, positive luck, 3P reliance, poor FT shooting
            vuln_score = 0
            components = 0

            if stat.margin_stdev is not None:
                # Higher stdev = more volatile (scale: 10 = avg, 15+ = very high)
                vuln_score += min(stat.margin_stdev / 20 * 25, 25)
                components += 1

            if stat.luck is not None:
                # Positive luck = overperforming, likely to regress
                vuln_score += max(0, stat.luck * 100)  # +10% luck -> +10 points
                components += 1

            if stat.three_pt_rate is not None:
                # Higher 3PAr = higher variance outcomes
                vuln_score += stat.three_pt_rate * 30  # 0.40 -> 12 points
                components += 1

            if tt["games_with_box"] > 0 and tt["fta"] > 0:
                ftm = tt["pts"] - 2 * (tt["fga"] - tt["fga3"]) - 3 * tt["fga3"]
                ft_pct = max(ftm / tt["fta"], 0) if tt["fta"] > 0 else 0.7
                # Poor FT% = can't close games (invert: lower = more vulnerable)
                vuln_score += max(0, (0.75 - ft_pct) * 50)  # 65% FT -> +5 points
                components += 1

            if components > 0:
                stat.upset_vulnerability = r(min(vuln_score, 100), 1)

            total_updated += 1

    return total_updated
