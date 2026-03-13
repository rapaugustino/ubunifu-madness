"""Generate the V5 model notebook as valid .ipynb JSON.

V5 Key Changes from V4:
- Recency-weighted training — exponential decay favoring recent seasons (half-life 5 seasons)
- All V4 features retained (40 features)

V4 features (retained):
- Trains on ALL games (regular + conf tourney + NCAA tourney) = 163K+ games
- game_type as a feature (regular/conf_tourney/tourney)
- Location feature (H/A/N)
- Rest days, KenPom/NET/consensus ranks, AdjEM, Barthag, quality wins
"""
import json

cells = []

def md(lines):
    if isinstance(lines, str):
        lines = lines.strip().split('\n')
    src = [line + '\n' for line in lines[:-1]] + [lines[-1]]
    cells.append({"cell_type": "markdown", "metadata": {}, "source": src})

def code(lines):
    if isinstance(lines, str):
        lines = lines.strip().split('\n')
    src = [line + '\n' for line in lines[:-1]] + [lines[-1]]
    cells.append({"cell_type": "code", "metadata": {}, "source": src, "outputs": [], "execution_count": None})

# =========================================================================
# NOTEBOOK CONTENT
# =========================================================================

md("""# Ubunifu Madness — V5 Model

**Key changes from V4:**
- **Recency-weighted training** — exponential decay favoring recent seasons (half-life 5 seasons)
- 40 features (same as V4)

**Retained from V4:**
- All game types (regular + conf tourney + NCAA tourney) = 163K+ games
- Game context features, rest days, rankings, AdjEM, Barthag, quality wins
- LR + LightGBM ensemble with smooth isotonic calibration

**Notebook outputs:**
1. `artifacts/lr_v5.joblib` — Logistic Regression model
2. `artifacts/lgb_v5.joblib` — LightGBM model
3. `artifacts/calibrator_v5.joblib` — Isotonic calibrator
4. `artifacts/model_metadata_v5.json` — Feature cols, weights, config
5. `submissions/` — Kaggle submissions""")

# --- Cell: Imports and Config ---
code("""import warnings
warnings.filterwarnings("ignore")

import json
import os
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, accuracy_score
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression
import lightgbm as lgb
import joblib

DATA_DIR = Path("../data/raw")
OUT_DIR = Path("artifacts")
SUB_DIR = Path("submissions")
OUT_DIR.mkdir(exist_ok=True)
SUB_DIR.mkdir(exist_ok=True)

# Config
MIN_TRAIN_SEASON = 2012  # Modern era only
TARGET_SEASON = 2026
MEAN_ELO = 1500
K_FACTOR = 21.8
HOME_ADV = 101.9
SEASON_REGRESSION = 0.89
LR_WEIGHT = 0.378        # V3 optimal blend weights
LGB_WEIGHT = 0.622
INCLUDE_REGULAR_SEASON = True  # V4: train on all games

RECENCY_HALF_LIFE = 5  # seasons — weight halves every 5 years

print(f"V5 Model — training on {'all games' if INCLUDE_REGULAR_SEASON else 'tournament only'}")
print(f"Modern era: {MIN_TRAIN_SEASON}+, Target: {TARGET_SEASON}")
print(f"Recency half-life: {RECENCY_HALF_LIFE} seasons")""")

# --- Cell: Load Data ---
md("""## Part 1 — Load Data

Load all CSVs needed for feature engineering and training.""")

code("""# Regular season results (compact + detailed)
m_compact = pd.read_csv(DATA_DIR / "MRegularSeasonCompactResults.csv")
w_compact = pd.read_csv(DATA_DIR / "WRegularSeasonCompactResults.csv")
m_detail = pd.read_csv(DATA_DIR / "MRegularSeasonDetailedResults.csv")
w_detail = pd.read_csv(DATA_DIR / "WRegularSeasonDetailedResults.csv")

# Tournament results
m_tourney = pd.read_csv(DATA_DIR / "MNCAATourneyCompactResults.csv")
w_tourney = pd.read_csv(DATA_DIR / "WNCAATourneyCompactResults.csv")
m_tourney_detail = pd.read_csv(DATA_DIR / "MNCAATourneyDetailedResults.csv")
w_tourney_detail = pd.read_csv(DATA_DIR / "WNCAATourneyDetailedResults.csv")

# Conference tournament games
m_conf_tourney = pd.read_csv(DATA_DIR / "MConferenceTourneyGames.csv")
w_conf_tourney = pd.read_csv(DATA_DIR / "WConferenceTourneyGames.csv")

# Seeds, conferences, coaches
m_seeds = pd.read_csv(DATA_DIR / "MNCAATourneySeeds.csv")
w_seeds = pd.read_csv(DATA_DIR / "WNCAATourneySeeds.csv")
m_conf = pd.read_csv(DATA_DIR / "MTeamConferences.csv")
w_conf = pd.read_csv(DATA_DIR / "WTeamConferences.csv")
coaches_df = pd.read_csv(DATA_DIR / "MTeamCoaches.csv")

# Massey Ordinals (external rankings — KenPom, NET, Sagarin, etc.)
massey_df = pd.read_csv(DATA_DIR / "MMasseyOrdinals.csv")

# Teams
m_teams = pd.read_csv(DATA_DIR / "MTeams.csv")
w_teams = pd.read_csv(DATA_DIR / "WTeams.csv")

# Tag gender
for df in [m_compact, m_detail, m_tourney, m_tourney_detail]: df["Gender"] = "M"
for df in [w_compact, w_detail, w_tourney, w_tourney_detail]: df["Gender"] = "W"
m_conf["Gender"] = "M"
w_conf["Gender"] = "W"
m_conf_tourney["Gender"] = "M"
w_conf_tourney["Gender"] = "W"

# Combine
all_compact = pd.concat([m_compact, w_compact], ignore_index=True)
all_compact["GameType"] = "regular"
detail_df = pd.concat([m_detail, w_detail], ignore_index=True)
detail_df["GameType"] = "regular"
all_tourney = pd.concat([m_tourney, w_tourney], ignore_index=True)
all_tourney["GameType"] = "tourney"
conf_df = pd.concat([m_conf, w_conf], ignore_index=True)
conf_tourney_df = pd.concat([m_conf_tourney, w_conf_tourney], ignore_index=True)

# All results for Elo
all_results = pd.concat([all_compact, all_tourney], ignore_index=True)
all_results = all_results.sort_values(["Season", "DayNum"]).reset_index(drop=True)

# Seeds
seeds_df = pd.concat([m_seeds, w_seeds], ignore_index=True)
seeds_df["SeedNum"] = seeds_df["Seed"].str.extract(r"(\\d+)").astype(int)

print(f"Regular season: {len(all_compact):,} games")
print(f"Detailed box scores: {len(detail_df):,} games")
print(f"NCAA tournament: {len(all_tourney):,} games")
print(f"Conference tourney: {len(conf_tourney_df):,} games")
print(f"Massey ordinals: {len(massey_df):,} rows ({massey_df['SystemName'].nunique()} systems)")
print(f"Seeds: {len(seeds_df):,} entries")""")

# --- Cell: Elo ---
md("""## Part 2 — Elo Ratings

Same proven Elo system from V3 (K=21.8, HOME_ADV=101.9).
But only **2012+ snapshots** are used as features for the ML model.""")

code("""def compute_elo(all_results_df, k_factor=K_FACTOR, home_adv=HOME_ADV, season_regression=SEASON_REGRESSION):
    \"\"\"Compute Elo ratings through all seasons. Returns (elo_dict, elo_snapshots).\"\"\"
    import math

    elo = defaultdict(lambda: MEAN_ELO)
    snapshots = {}
    last_season = None

    for _, g in all_results_df.iterrows():
        season = g["Season"]

        # Season regression
        if season != last_season:
            if last_season is not None:
                for tid in list(elo.keys()):
                    elo[tid] = MEAN_ELO + (elo[tid] - MEAN_ELO) * season_regression
                    snapshots[(season, tid)] = elo[tid]  # Pre-season snapshot
            last_season = season

        w, l = g["WTeamID"], g["LTeamID"]
        w_elo = elo[w] + (home_adv if g.get("WLoc") == "H" else 0)
        l_elo = elo[l] + (home_adv if g.get("WLoc") == "A" else 0)

        exp_w = 1 / (1 + 10 ** ((l_elo - w_elo) / 400))
        mov = abs(g["WScore"] - g["LScore"])
        mult = math.log(mov + 1) * (2.2 / ((abs(w_elo - l_elo) * 0.001) + 2.2))
        update = k_factor * mult * (1 - exp_w)

        elo[w] += update
        elo[l] -= update

        # Post-game snapshot (for regular season feature computation)
        snapshots[(season, w)] = elo[w]
        snapshots[(season, l)] = elo[l]

    return dict(elo), snapshots

elo_final, elo_snapshots = compute_elo(all_results)
# Pre-tourney snapshots: last Elo before DayNum 132 (tourney starts ~134)
elo_by_season = {}
for (season, tid), e in elo_snapshots.items():
    elo_by_season[(season, tid)] = e

print(f"Elo computed for {len(elo_final):,} teams")
print(f"Pre-tourney snapshots: {len(elo_by_season):,}")""")

# --- Cell: Feature Engineering ---
md("""## Part 3 — Feature Engineering

V4 features (~40 total):

**Core (from V3, 28 features):**
- Elo (4): elo_a, elo_b, elo_diff, elo_prob
- Seeds (3): seed_a, seed_b, seed_diff
- Conference (3): avg Elo diff, NC win rate diff, tourney history diff
- Four Factors (6): eFG%, TO%, OR%, FTR, opp_eFG%, opp_TO%
- Efficiency (3): off eff diff, def eff diff, tempo diff
- Massey (2): avg rank diff, disagreement diff
- Season (5): win_pct, last_n_winpct, last_n_mov, efg_trend, sos
- Coach (1): tenure diff
- Conf tourney (1): wins diff

**NEW in V4 (12 features):**
- game_type (2): is_conf_tourney, is_ncaa_tourney (one-hot)
- Location (1): is_neutral_site
- Rest (1): rest_days_diff
- KenPom (1): kenpom_rank_diff (from Massey POM)
- NET (1): net_rank_diff (from Massey NET)
- Consensus (1): consensus_rank_diff (median of all systems)
- Adjusted efficiency (2): adj_eff_margin_diff, barthag_diff
- Quality (1): quality_wins_pct_diff (win% vs top-50 Elo opponents)
- Record (2): win_pct_a, win_pct_b (raw values for LGB nonlinearities)""")

code("""def safe_diff(a, b, default=0.0):
    \"\"\"Safely compute a - b with default for None.\"\"\"
    a = a if a is not None else default
    b = b if b is not None else default
    return a - b

# --- Conference Strength ---
def build_conference_strength(elo_by_season, all_results, conf_df):
    \"\"\"Conference-level metrics: avg Elo, NC win rate, tourney history.\"\"\"
    team_conf = {}
    for _, r in conf_df.iterrows():
        team_conf[(r["Season"], r["TeamID"])] = r["ConfAbbrev"]

    # Build conference metrics per season+gender
    tourney = all_results[all_results["GameType"] == "tourney"]

    conf_strength = {}
    for season in all_results["Season"].unique():
        for gender in ["M", "W"]:
            teams_in_conf = defaultdict(list)
            for (s, tid), conf in team_conf.items():
                if s == season:
                    g = "M" if tid < 3000 else "W"
                    if g == gender:
                        teams_in_conf[conf].append(tid)

            sg = tourney[(tourney["Season"] == season) & (tourney["Gender"] == gender)]
            for conf, tids in teams_in_conf.items():
                elos = [elo_by_season.get((season, t), MEAN_ELO) for t in tids]
                avg_elo = np.mean(elos) if elos else MEAN_ELO
                # NC win rate
                nc_games = all_results[
                    (all_results["Season"] == season) & (all_results["Gender"] == gender)
                ]
                nc_wins = nc_losses = 0
                for _, g in nc_games.iterrows():
                    w_conf = team_conf.get((season, g["WTeamID"]))
                    l_conf = team_conf.get((season, g["LTeamID"]))
                    if w_conf == conf and l_conf != conf:
                        nc_wins += 1
                    elif l_conf == conf and w_conf != conf:
                        nc_losses += 1
                nc_winrate = nc_wins / max(nc_wins + nc_losses, 1)
                # Tournament history
                t_wins = len(sg[sg["WTeamID"].isin(tids)])
                t_total = t_wins + len(sg[sg["LTeamID"].isin(tids)])
                t_hist = t_wins / max(t_total, 1)

                conf_strength[(season, gender, conf)] = {
                    "avg_elo": avg_elo, "nc_winrate": nc_winrate, "tourney_hist": t_hist
                }

    return conf_strength, team_conf

conf_strength, team_conf = build_conference_strength(elo_by_season, all_results, conf_df)
print(f"Conference strength: {len(conf_strength):,} entries")""")

# --- Box Score Features ---
code("""def build_box_score_features(detail_df):
    \"\"\"Four Factors + efficiency from detailed box scores.\"\"\"
    import math

    features = {}
    for (season, gender, tid), group in detail_df.groupby(["Season", "Gender", "WTeamID"]):
        pass  # Will aggregate below

    team_games = defaultdict(list)
    for _, g in detail_df.iterrows():
        season = g["Season"]
        for is_winner in [True, False]:
            pfx = "W" if is_winner else "L"
            opfx = "L" if is_winner else "W"
            tid = g[f"{pfx}TeamID"]

            fga = g[f"{pfx}FGA"]
            fga3 = g[f"{pfx}FGA3"]
            fgm = g[f"{pfx}FGM"]
            fgm3 = g[f"{pfx}FGM3"]
            fta = g[f"{pfx}FTA"]
            ftm = g[f"{pfx}FTM"]
            orb = g[f"{pfx}OR"]
            drb = g[f"{pfx}DR"]
            ast = g.get(f"{pfx}Ast", 0) or 0
            to = g.get(f"{pfx}TO", 0) or 0
            stl = g.get(f"{pfx}Stl", 0) or 0
            blk = g.get(f"{pfx}Blk", 0) or 0
            score = g[f"{pfx}Score"]

            o_fga = g[f"{opfx}FGA"]
            o_fgm = g[f"{opfx}FGM"]
            o_fgm3 = g[f"{opfx}FGM3"]
            o_fta = g[f"{opfx}FTA"]
            o_to = g.get(f"{opfx}TO", 0) or 0
            o_orb = g[f"{opfx}OR"]
            o_score = g[f"{opfx}Score"]

            poss = fga - orb + to + 0.44 * fta
            o_poss = o_fga - o_orb + o_to + 0.44 * o_fta
            avg_poss = max((poss + o_poss) / 2, 1)

            team_games[(season, tid)].append({
                "efg": (fgm + 0.5 * fgm3) / max(fga, 1),
                "to": to / max(poss, 1),
                "orb": orb / max(orb + g[f"{opfx}DR"], 1),
                "ftr": ftm / max(fga, 1),
                "opp_efg": (o_fgm + 0.5 * o_fgm3) / max(o_fga, 1),
                "opp_to": o_to / max(o_poss, 1),
                "off_eff": score / avg_poss * 100,
                "def_eff": o_score / avg_poss * 100,
                "tempo": avg_poss,
                "poss": avg_poss,
            })

    for key, games in team_games.items():
        features[key] = {k: np.mean([g[k] for g in games]) for k in games[0].keys()}

    return features

box_features = build_box_score_features(detail_df)
print(f"Box score features: {len(box_features):,} (season, team) entries")""")

# --- Massey Ordinals Features (V4: much richer) ---
code("""TOP_MASSEY_SYSTEMS = ["POM", "SAG", "MOR", "DOL", "COL", "AP", "USA", "NET"]

def build_massey_features(massey_df, systems=TOP_MASSEY_SYSTEMS):
    \"\"\"Pre-tournament Massey ordinal features including KenPom, NET.\"\"\"
    recent = massey_df[massey_df["Season"] >= MIN_TRAIN_SEASON].copy()
    # Use latest ranking before day 133 (pre-tourney)
    pre_t = recent[recent["RankingDayNum"] <= 133]

    features = {}
    for (season, tid), group in pre_t.groupby(["Season", "TeamID"]):
        last_day = group.groupby("SystemName").agg({"RankingDayNum": "max", "OrdinalRank": "last"})
        ranks = last_day["OrdinalRank"]
        top_ranks = ranks[ranks.index.isin(systems)]

        # Average rank across top systems
        avg_rank = top_ranks.mean() if len(top_ranks) > 0 else 200
        # Disagreement (spread among systems)
        disagreement = top_ranks.std() if len(top_ranks) > 1 else 50

        # KenPom rank specifically
        kenpom_rank = ranks.get("POM", 200)
        # NET rank specifically
        net_rank = ranks.get("NET", 200)
        # Consensus rank (median of ALL available systems)
        consensus_rank = ranks.median() if len(ranks) > 0 else 200

        features[(season, tid)] = {
            "avg_rank": avg_rank,
            "disagreement": disagreement,
            "kenpom_rank": kenpom_rank,
            "net_rank": net_rank,
            "consensus_rank": consensus_rank,
        }

    return features

massey_features = build_massey_features(massey_df)
print(f"Massey features: {len(massey_features):,} entries")
# Show a sample
sample_key = list(massey_features.keys())[-1]
print(f"Sample ({sample_key}): {massey_features[sample_key]}")""")

# --- Season Features ---
code("""def build_season_features(all_compact, elo_by_season, coaches_df, conf_tourney_df):
    \"\"\"Per-team season-level features: record, momentum, SOS, quality wins.\"\"\"
    features = {}

    for (season, gender), group in all_compact.groupby(["Season", "Gender"]):
        if season < MIN_TRAIN_SEASON:
            continue

        # Build team records and game lists
        team_wins = defaultdict(int)
        team_losses = defaultdict(int)
        team_margins = defaultdict(list)
        team_opponents = defaultdict(list)

        for _, g in group.iterrows():
            w, l = g["WTeamID"], g["LTeamID"]
            margin = g["WScore"] - g["LScore"]
            team_wins[w] += 1
            team_losses[l] += 1
            team_margins[w].append(margin)
            team_margins[l].append(-margin)
            team_opponents[w].append(l)
            team_opponents[l].append(w)

        all_team_ids = set(team_wins.keys()) | set(team_losses.keys())

        # SOS = average opponent Elo
        sos = {}
        for tid in all_team_ids:
            opp_elos = [elo_by_season.get((season, opp), MEAN_ELO) for opp in team_opponents.get(tid, [])]
            sos[tid] = np.mean(opp_elos) if opp_elos else MEAN_ELO

        # Quality wins: wins against top-50 Elo opponents
        top50_elos = sorted(
            [(tid, elo_by_season.get((season, tid), MEAN_ELO)) for tid in all_team_ids],
            key=lambda x: -x[1]
        )[:50]
        top50_ids = set(t[0] for t in top50_elos)

        for tid in all_team_ids:
            total_games = team_wins.get(tid, 0) + team_losses.get(tid, 0)
            if total_games < 5:
                continue

            win_pct = team_wins.get(tid, 0) / total_games
            margins = team_margins.get(tid, [])
            last_n = margins[-10:] if len(margins) >= 10 else margins

            # EFG trend: compare last-10 to full season (proxy)
            last_n_winpct = sum(1 for m in last_n if m > 0) / max(len(last_n), 1)
            last_n_mov = np.mean(last_n) if last_n else 0

            # Quality wins %
            quality_wins = sum(1 for opp in team_opponents.get(tid, [])
                             if opp in top50_ids and opp in [g for g in team_opponents.get(tid, [])])
            # More precise: count actual wins vs top 50
            q_wins = 0
            q_games = 0
            for opp in team_opponents.get(tid, []):
                if opp in top50_ids:
                    q_games += 1
            # Check wins specifically against top50
            for _, g in group.iterrows():
                if g["WTeamID"] == tid and g["LTeamID"] in top50_ids:
                    q_wins += 1
            quality_win_pct = q_wins / max(q_games, 1)

            features[(season, tid)] = {
                "win_pct": win_pct,
                "last_n_winpct": last_n_winpct,
                "last_n_mov": last_n_mov,
                "efg_trend": last_n_winpct - win_pct,
                "sos": sos.get(tid, MEAN_ELO),
                "quality_win_pct": quality_win_pct,
            }

    # Conference tourney wins
    for _, g in conf_tourney_df.iterrows():
        key = (g["Season"], g["WTeamID"])
        if key in features:
            features[key]["conf_tourney_wins"] = features[key].get("conf_tourney_wins", 0) + 1

    # Coach features (men's only)
    for _, row in coaches_df.iterrows():
        season, tid = row["Season"], row["TeamID"]
        if (season, tid) in features:
            # Coach tenure at this school
            coach_history = coaches_df[
                (coaches_df["CoachName"] == row["CoachName"]) &
                (coaches_df["TeamID"] == tid) &
                (coaches_df["Season"] <= season)
            ]
            tenure = len(coach_history)
            features[(season, tid)]["coach_tenure"] = tenure

    return features

season_features = build_season_features(
    all_compact, elo_by_season, coaches_df, conf_tourney_df
)
print(f"Season features: {len(season_features):,} entries")""")

# --- Adjusted Efficiency & Barthag (V4 new) ---
code("""def build_adj_efficiency(detail_df, elo_by_season):
    \"\"\"Compute opponent-adjusted efficiency margin and Barthag per team-season.\"\"\"
    ADJ_ITERS = 10
    BARTHAG_EXP = 11.5
    features = {}

    for (season, gender), group in detail_df.groupby(["Season", "Gender"]):
        if season < MIN_TRAIN_SEASON:
            continue

        # Compute raw per-game efficiencies
        team_games = defaultdict(list)
        for _, g in group.iterrows():
            poss_w = g["WFGA"] - g["WOR"] + g.get("WTO", 0) + 0.44 * g["WFTA"]
            poss_l = g["LFGA"] - g["LOR"] + g.get("LTO", 0) + 0.44 * g["LFTA"]
            poss = max((poss_w + poss_l) / 2, 1)

            team_games[(season, g["WTeamID"])].append({
                "oe": g["WScore"] / poss * 100,
                "de": g["LScore"] / poss * 100,
                "opp": g["LTeamID"], "poss": poss,
            })
            team_games[(season, g["LTeamID"])].append({
                "oe": g["LScore"] / poss * 100,
                "de": g["WScore"] / poss * 100,
                "opp": g["WTeamID"], "poss": poss,
            })

        if not team_games:
            continue

        # Raw averages (possession-weighted)
        raw_oe = {}
        raw_de = {}
        for key, games in team_games.items():
            poss_arr = np.array([g["poss"] for g in games])
            raw_oe[key] = np.average([g["oe"] for g in games], weights=poss_arr)
            raw_de[key] = np.average([g["de"] for g in games], weights=poss_arr)

        nat_avg_oe = np.mean(list(raw_oe.values()))
        nat_avg_de = np.mean(list(raw_de.values()))

        adj_oe = dict(raw_oe)
        adj_de = dict(raw_de)

        for _ in range(ADJ_ITERS):
            new_oe = {}
            new_de = {}
            for key, games in team_games.items():
                oe_vals, de_vals, poss_w = [], [], []
                for g in games:
                    opp_key = (key[0], g["opp"])
                    opp_de = adj_de.get(opp_key, nat_avg_de)
                    opp_oe = adj_oe.get(opp_key, nat_avg_oe)
                    oe_vals.append(g["oe"] * (nat_avg_de / max(opp_de, 1)))
                    de_vals.append(g["de"] * (nat_avg_oe / max(opp_oe, 1)))
                    poss_w.append(g["poss"])
                pa = np.array(poss_w)
                new_oe[key] = np.average(oe_vals, weights=pa)
                new_de[key] = np.average(de_vals, weights=pa)
            adj_oe = new_oe
            adj_de = new_de

        for key in adj_oe:
            oe = adj_oe[key]
            de = adj_de[key]
            aem = oe - de
            barthag = oe ** BARTHAG_EXP / (oe ** BARTHAG_EXP + de ** BARTHAG_EXP)
            features[key] = {"adj_eff_margin": aem, "barthag": barthag}

    return features

adj_eff_features = build_adj_efficiency(detail_df, elo_by_season)
print(f"Adjusted efficiency features: {len(adj_eff_features):,} entries")""")

# --- Rest Days Feature (V4 new) ---
code("""def build_rest_days(all_results_df):
    \"\"\"Compute days since last game for each team at each game.\"\"\"
    rest = {}  # (season, daynum, team_id) -> rest_days
    last_game = {}  # team_id -> last daynum

    for _, g in all_results_df.sort_values(["Season", "DayNum"]).iterrows():
        season, day = g["Season"], g["DayNum"]
        w, l = g["WTeamID"], g["LTeamID"]

        for tid in [w, l]:
            prev = last_game.get((season, tid))
            if prev is not None:
                rest[(season, day, tid)] = day - prev
            else:
                rest[(season, day, tid)] = 7  # Default for first game
            last_game[(season, tid)] = day

    return rest

rest_days = build_rest_days(all_results)
print(f"Rest days entries: {len(rest_days):,}")""")

# --- Build Matchup Feature Matrix (V5) ---
code("""FEATURE_COLS = [
    # Core Elo (4)
    "elo_a", "elo_b", "elo_diff", "elo_prob",
    # Seeds (3)
    "seed_a", "seed_b", "seed_diff",
    # Conference (3)
    "conf_avg_elo_diff", "conf_nc_winrate_diff", "conf_tourney_hist_winrate_diff",
    # Four Factors (6)
    "efg_diff", "to_diff", "or_diff", "ftr_diff", "opp_efg_diff", "opp_to_diff",
    # Efficiency (3)
    "off_eff_diff", "def_eff_diff", "tempo_diff",
    # Massey (2)
    "massey_rank_diff", "massey_disagreement_diff",
    # Season (5)
    "win_pct_diff", "last_n_winpct_diff", "last_n_mov_diff", "efg_trend_diff", "sos_diff",
    # Coach (1)
    "coach_tenure_diff",
    # Conf tourney (1)
    "conf_tourney_wins_diff",
    # === NEW V4 FEATURES (12) ===
    # Game context (3)
    "is_conf_tourney", "is_ncaa_tourney", "is_neutral_site",
    # Rest (1)
    "rest_days_diff",
    # External rankings (3)
    "kenpom_rank_diff", "net_rank_diff", "consensus_rank_diff",
    # Adjusted efficiency (2)
    "adj_eff_margin_diff", "barthag_diff",
    # Quality (1)
    "quality_win_pct_diff",
    # Raw record for LGB nonlinearities (2)
    "win_pct_a", "win_pct_b",
]

print(f"Feature columns: {len(FEATURE_COLS)}")

def build_matchup_row(season, team_a, team_b, game_type="regular", day_num=134, w_loc="N"):
    \"\"\"Build one feature row for team_a vs team_b.\"\"\"
    ea = elo_by_season.get((season, team_a), MEAN_ELO)
    eb = elo_by_season.get((season, team_b), MEAN_ELO)
    elo_diff = ea - eb
    elo_prob = 1 / (1 + 10 ** (-elo_diff / 400))

    sa = seeds_lookup.get((season, team_a), 8)
    sb = seeds_lookup.get((season, team_b), 8)

    ga = "M" if team_a < 3000 else "W"
    ca = team_conf.get((season, team_a))
    cb = team_conf.get((season, team_b))
    cs_a = conf_strength.get((season, ga, ca), {})
    cs_b = conf_strength.get((season, ga, cb), {})

    bx_a = box_features.get((season, team_a), {})
    bx_b = box_features.get((season, team_b), {})
    ms_a = massey_features.get((season, team_a), {})
    ms_b = massey_features.get((season, team_b), {})
    sf_a = season_features.get((season, team_a), {})
    sf_b = season_features.get((season, team_b), {})
    ae_a = adj_eff_features.get((season, team_a), {})
    ae_b = adj_eff_features.get((season, team_b), {})

    # Rest days
    rd_a = rest_days.get((season, day_num, team_a), 3)
    rd_b = rest_days.get((season, day_num, team_b), 3)

    # Game type one-hot
    is_conf_t = 1 if game_type == "conf_tourney" else 0
    is_ncaa_t = 1 if game_type == "tourney" else 0
    is_neutral = 1 if w_loc == "N" else 0

    f = {
        "elo_a": ea, "elo_b": eb, "elo_diff": elo_diff, "elo_prob": elo_prob,
        "seed_a": sa, "seed_b": sb, "seed_diff": sa - sb,
        "conf_avg_elo_diff": safe_diff(cs_a.get("avg_elo"), cs_b.get("avg_elo")),
        "conf_nc_winrate_diff": safe_diff(cs_a.get("nc_winrate"), cs_b.get("nc_winrate")),
        "conf_tourney_hist_winrate_diff": safe_diff(cs_a.get("tourney_hist"), cs_b.get("tourney_hist")),
        "efg_diff": safe_diff(bx_a.get("efg"), bx_b.get("efg")),
        "to_diff": safe_diff(bx_a.get("to"), bx_b.get("to")),
        "or_diff": safe_diff(bx_a.get("orb"), bx_b.get("orb")),
        "ftr_diff": safe_diff(bx_a.get("ftr"), bx_b.get("ftr")),
        "opp_efg_diff": safe_diff(bx_a.get("opp_efg"), bx_b.get("opp_efg")),
        "opp_to_diff": safe_diff(bx_a.get("opp_to"), bx_b.get("opp_to")),
        "off_eff_diff": safe_diff(bx_a.get("off_eff"), bx_b.get("off_eff")),
        "def_eff_diff": safe_diff(bx_a.get("def_eff"), bx_b.get("def_eff")),
        "tempo_diff": safe_diff(bx_a.get("tempo"), bx_b.get("tempo")),
        "win_pct_diff": safe_diff(sf_a.get("win_pct"), sf_b.get("win_pct")),
        "massey_rank_diff": safe_diff(ms_a.get("avg_rank"), ms_b.get("avg_rank")),
        "massey_disagreement_diff": safe_diff(ms_a.get("disagreement"), ms_b.get("disagreement")),
        "last_n_winpct_diff": safe_diff(sf_a.get("last_n_winpct"), sf_b.get("last_n_winpct")),
        "last_n_mov_diff": safe_diff(sf_a.get("last_n_mov"), sf_b.get("last_n_mov")),
        "efg_trend_diff": safe_diff(sf_a.get("efg_trend"), sf_b.get("efg_trend")),
        "coach_tenure_diff": safe_diff(sf_a.get("coach_tenure"), sf_b.get("coach_tenure")),
        "conf_tourney_wins_diff": safe_diff(sf_a.get("conf_tourney_wins"), sf_b.get("conf_tourney_wins")),
        "sos_diff": safe_diff(sf_a.get("sos"), sf_b.get("sos")),
        # V4 new
        "is_conf_tourney": is_conf_t,
        "is_ncaa_tourney": is_ncaa_t,
        "is_neutral_site": is_neutral,
        "rest_days_diff": rd_a - rd_b,
        "kenpom_rank_diff": safe_diff(ms_a.get("kenpom_rank", 200), ms_b.get("kenpom_rank", 200)),
        "net_rank_diff": safe_diff(ms_a.get("net_rank", 200), ms_b.get("net_rank", 200)),
        "consensus_rank_diff": safe_diff(ms_a.get("consensus_rank", 200), ms_b.get("consensus_rank", 200)),
        "adj_eff_margin_diff": safe_diff(ae_a.get("adj_eff_margin"), ae_b.get("adj_eff_margin")),
        "barthag_diff": safe_diff(ae_a.get("barthag"), ae_b.get("barthag")),
        "quality_win_pct_diff": safe_diff(sf_a.get("quality_win_pct"), sf_b.get("quality_win_pct")),
        "win_pct_a": sf_a.get("win_pct", 0.5),
        "win_pct_b": sf_b.get("win_pct", 0.5),
    }

    return [f.get(c, 0.0) for c in FEATURE_COLS]

# Build seed lookup
seeds_lookup = {}
for _, row in seeds_df.iterrows():
    seeds_lookup[(row["Season"], row["TeamID"])] = row["SeedNum"]

print("Feature builder ready.")""")

# --- Build Training Data (V4: ALL GAMES) ---
code("""# V4: Train on all game types
print("Building training data from ALL game types...")

# 1) NCAA tournament games (always included)
training_games = all_tourney.copy()
training_games["TrainGameType"] = "tourney"

# 2) Regular season games with box scores (only detailed results have the stats we need)
if INCLUDE_REGULAR_SEASON:
    reg = detail_df.copy()
    reg["TrainGameType"] = "regular"
    # Add WLoc if missing
    if "WLoc" not in reg.columns:
        reg["WLoc"] = "H"
    training_games = pd.concat([training_games, reg], ignore_index=True)
    print(f"  Added {len(reg):,} regular season games with box scores")

# 3) Conference tournament games
ct = conf_tourney_df.copy()
if "WScore" not in ct.columns:
    # Conf tourney CSV lacks scores — skip if no scores available
    print("  Conf tourney games lack scores — looking up from compact results...")
    # Merge scores from compact results
    ct_merged = []
    for _, g in ct.iterrows():
        match = all_compact[
            (all_compact["Season"] == g["Season"]) &
            (all_compact["WTeamID"] == g["WTeamID"]) &
            (all_compact["LTeamID"] == g["LTeamID"]) &
            (all_compact["DayNum"] == g["DayNum"])
        ]
        if len(match) > 0:
            row = match.iloc[0].copy()
            row["TrainGameType"] = "conf_tourney"
            ct_merged.append(row)
    if ct_merged:
        ct_df = pd.DataFrame(ct_merged)
        ct_df["WLoc"] = "N"
        training_games = pd.concat([training_games, ct_df], ignore_index=True)
        print(f"  Added {len(ct_df):,} conference tournament games")
else:
    ct["TrainGameType"] = "conf_tourney"
    ct["WLoc"] = ct.get("WLoc", "N")
    training_games = pd.concat([training_games, ct], ignore_index=True)

# Filter to modern era
training_games = training_games[training_games["Season"] >= MIN_TRAIN_SEASON].reset_index(drop=True)
# Ensure we have scores
training_games = training_games.dropna(subset=["WScore", "LScore"])

print(f"\\nTotal training games: {len(training_games):,}")
print(f"  Regular: {(training_games['TrainGameType'] == 'regular').sum():,}")
print(f"  Conf tourney: {(training_games['TrainGameType'] == 'conf_tourney').sum():,}")
print(f"  NCAA tourney: {(training_games['TrainGameType'] == 'tourney').sum():,}")
print(f"  Seasons: {training_games['Season'].min()}-{training_games['Season'].max()}")""")

# --- Build Feature Matrix ---
code("""X_rows = []
y_rows = []
meta = []
skipped = 0

for _, g in training_games.iterrows():
    season = g["Season"]
    if season < MIN_TRAIN_SEASON:
        continue

    w = int(g["WTeamID"])
    l = int(g["LTeamID"])
    game_type = g.get("TrainGameType", "regular")
    day_num = int(g.get("DayNum", 134))
    w_loc = g.get("WLoc", "N")

    # Convention: team_a = lower ID, team_b = higher ID
    if w < l:
        team_a, team_b = w, l
        label = 1  # team_a won
    else:
        team_a, team_b = l, w
        label = 0  # team_a lost

    try:
        row = build_matchup_row(season, team_a, team_b, game_type=game_type,
                                 day_num=day_num, w_loc=w_loc if w < l else ("A" if w_loc == "H" else ("H" if w_loc == "A" else "N")))
        X_rows.append(row)
        y_rows.append(label)
        meta.append({"season": season, "team_a": team_a, "team_b": team_b, "game_type": game_type})
    except Exception as e:
        skipped += 1

X = np.array(X_rows, dtype=np.float32)
y = np.array(y_rows, dtype=np.int32)
meta_df = pd.DataFrame(meta)

print(f"Feature matrix: {X.shape}")
print(f"Positive rate: {y.mean():.3f}")
print(f"Skipped: {skipped}")
print(f"NaN check: {np.isnan(X).sum()} NaN values")

# Replace NaN with 0
X = np.nan_to_num(X, nan=0.0)

# V5: Recency weights — exponential decay by season
max_season = meta_df["season"].max()
decay_rate = np.log(2) / RECENCY_HALF_LIFE
sample_weights = np.exp(-decay_rate * (max_season - meta_df["season"].values))
print(f"\\nRecency weights: newest={sample_weights.max():.3f}, oldest={sample_weights.min():.3f}")
print(f"Weight ratio (newest/oldest): {sample_weights.max() / sample_weights.min():.1f}x")""")

# --- Train Models ---
md("""## Part 4 — Model Training

LR + LightGBM ensemble with smooth isotonic calibration.
V5: recency-weighted training (exponential decay by season).""")

code("""# Season-based CV (like V3)
unique_seasons = sorted(meta_df["season"].unique())
# Use last 4 seasons as validation folds
val_seasons = unique_seasons[-4:]
train_mask = meta_df["season"].isin(unique_seasons[:-4]).values
val_mask = meta_df["season"].isin(val_seasons).values

X_train, X_val = X[train_mask], X[val_mask]
y_train, y_val = y[train_mask], y[val_mask]
w_train, w_val = sample_weights[train_mask], sample_weights[val_mask]

print(f"Train: {X_train.shape[0]:,} games (seasons {unique_seasons[0]}-{unique_seasons[-5]})")
print(f"Val: {X_val.shape[0]:,} games (seasons {val_seasons})")
print(f"Val game types: {meta_df[val_mask]['game_type'].value_counts().to_dict()}")
print(f"Train weight range: [{w_train.min():.3f}, {w_train.max():.3f}]")""")

code("""# Logistic Regression
lr = LogisticRegression(C=0.05, max_iter=2000, solver="lbfgs")
lr.fit(X_train, y_train, sample_weight=w_train)
lr_pred_val = lr.predict_proba(X_val)[:, 1]
lr_pred_train = lr.predict_proba(X_train)[:, 1]

print("=== Logistic Regression ===")
print(f"Train Brier: {brier_score_loss(y_train, lr_pred_train):.4f}")
print(f"Val Brier: {brier_score_loss(y_val, lr_pred_val):.4f}")
print(f"Val Accuracy: {accuracy_score(y_val, (lr_pred_val > 0.5).astype(int)):.4f}")
print(f"Val LogLoss: {log_loss(y_val, lr_pred_val):.4f}")

# Feature importance (LR coefficients)
print("\\nTop LR features:")
coef_df = pd.DataFrame({"feature": FEATURE_COLS, "coef": lr.coef_[0]})
coef_df = coef_df.reindex(coef_df["coef"].abs().sort_values(ascending=False).index)
print(coef_df.head(15).to_string(index=False))""")

code("""# LightGBM
lgb_params = {
    "objective": "binary",
    "metric": "binary_logloss",
    "verbosity": -1,
    "n_estimators": 800,
    "learning_rate": 0.03,
    "max_depth": 6,
    "num_leaves": 31,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 50,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
}

lgb_model = lgb.LGBMClassifier(**lgb_params)
lgb_model.fit(
    X_train, y_train,
    sample_weight=w_train,
    eval_set=[(X_val, y_val)],
    eval_sample_weight=[w_val],
    callbacks=[lgb.early_stopping(50, verbose=False)],
)
lgb_pred_val = lgb_model.predict_proba(X_val)[:, 1]
lgb_pred_train = lgb_model.predict_proba(X_train)[:, 1]

print("=== LightGBM ===")
print(f"Train Brier: {brier_score_loss(y_train, lgb_pred_train):.4f}")
print(f"Val Brier: {brier_score_loss(y_val, lgb_pred_val):.4f}")
print(f"Val Accuracy: {accuracy_score(y_val, (lgb_pred_val > 0.5).astype(int)):.4f}")
print(f"Val LogLoss: {log_loss(y_val, lgb_pred_val):.4f}")

# Feature importance
print("\\nTop LGB features:")
imp_df = pd.DataFrame({"feature": FEATURE_COLS, "importance": lgb_model.feature_importances_})
imp_df = imp_df.sort_values("importance", ascending=False)
print(imp_df.head(15).to_string(index=False))""")

# --- Ensemble + Calibration ---
code("""# Ensemble blend
ensemble_val = LR_WEIGHT * lr_pred_val + LGB_WEIGHT * lgb_pred_val
ensemble_train = LR_WEIGHT * lr_pred_train + LGB_WEIGHT * lgb_pred_train

print("=== Ensemble (LR {:.0f}% + LGB {:.0f}%) ===".format(LR_WEIGHT * 100, LGB_WEIGHT * 100))
print(f"Val Brier: {brier_score_loss(y_val, ensemble_val):.4f}")
print(f"Val Accuracy: {accuracy_score(y_val, (ensemble_val > 0.5).astype(int)):.4f}")

# Break down by game type
for gt in ["regular", "conf_tourney", "tourney"]:
    mask = meta_df[val_mask]["game_type"].values == gt
    if mask.sum() > 0:
        brier = brier_score_loss(y_val[mask], ensemble_val[mask])
        acc = accuracy_score(y_val[mask], (ensemble_val[mask] > 0.5).astype(int))
        print(f"  {gt:15s}: Brier={brier:.4f}, Acc={acc:.4f} ({mask.sum()} games)")""")

code("""# Isotonic calibration (smooth)
# Use OOF predictions from recent seasons
calibration_mask = meta_df["season"].isin(unique_seasons[-4:]).values
calib_preds = LR_WEIGHT * lr.predict_proba(X[calibration_mask])[:, 1] + \\
              LGB_WEIGHT * lgb_model.predict_proba(X[calibration_mask])[:, 1]
calib_labels = y[calibration_mask]

calibrator = IsotonicRegression(out_of_bounds="clip")
calibrator.fit(calib_preds, calib_labels)

# Smooth calibration (linear interp between midpoints)
from scipy.interpolate import interp1d

iso_x = calibrator.X_thresholds_
iso_y = calibrator.y_thresholds_
midpoints_x = (iso_x[:-1] + iso_x[1:]) / 2
midpoints_y = (iso_y[:-1] + iso_y[1:]) / 2
# Add endpoints
smooth_x = np.concatenate([[0.0], midpoints_x, [1.0]])
smooth_y = np.concatenate([[0.0], midpoints_y, [1.0]])
smooth_cal = interp1d(smooth_x, smooth_y, kind="linear", bounds_error=False, fill_value=(0.01, 0.99))

# Test calibrated predictions
cal_val = smooth_cal(ensemble_val)
print("=== Calibrated Ensemble ===")
print(f"Val Brier: {brier_score_loss(y_val, cal_val):.4f}")
print(f"Val Accuracy: {accuracy_score(y_val, (cal_val > 0.5).astype(int)):.4f}")

# Compare V3 vs V4
print("\\n=== V5 Summary ===")
print(f"Training games: {len(X):,}")
print(f"Features: {len(FEATURE_COLS)}")
print(f"Recency half-life: {RECENCY_HALF_LIFE} seasons")
print(f"Val Brier (calibrated): {brier_score_loss(y_val, cal_val):.4f}")""")

# --- Save Artifacts ---
code("""# Save models
joblib.dump(lr, OUT_DIR / "lr_v5.joblib")
joblib.dump(lgb_model, OUT_DIR / "lgb_v5.joblib")
joblib.dump(calibrator, OUT_DIR / "calibrator_v5.joblib")

# Save smooth calibration data
np.savez(OUT_DIR / "smooth_cal_v5.npz", x=smooth_x, y=smooth_y)

# Save metadata
metadata = {
    "version": "v5",
    "feature_cols": FEATURE_COLS,
    "n_features": len(FEATURE_COLS),
    "lr_weight": LR_WEIGHT,
    "lgb_weight": LGB_WEIGHT,
    "n_training_games": int(X.shape[0]),
    "n_training_regular": int((meta_df["game_type"] == "regular").sum()),
    "n_training_conf_tourney": int((meta_df["game_type"] == "conf_tourney").sum()),
    "n_training_tourney": int((meta_df["game_type"] == "tourney").sum()),
    "min_train_season": MIN_TRAIN_SEASON,
    "elo_config": {"k_factor": K_FACTOR, "home_adv": HOME_ADV, "mean_elo": MEAN_ELO, "season_regression": SEASON_REGRESSION},
    "val_brier": float(brier_score_loss(y_val, cal_val)),
    "val_accuracy": float(accuracy_score(y_val, (cal_val > 0.5).astype(int))),
}

with open(OUT_DIR / "model_metadata_v5.json", "w") as f:
    json.dump(metadata, f, indent=2)

print("Artifacts saved!")
print(json.dumps(metadata, indent=2))""")

# --- Kaggle Submission ---
md("""## Part 5 — Kaggle Submission

Generate predictions for all possible tournament matchups.""")

code("""# Load submission template
sub_template = pd.read_csv(DATA_DIR / "SampleSubmissionStage2.csv")
print(f"Submission template: {len(sub_template):,} matchups")

results = []
for _, row in sub_template.iterrows():
    parts = row["ID"].split("_")
    season = int(parts[0])
    team_a = int(parts[1])
    team_b = int(parts[2])

    features = build_matchup_row(season, team_a, team_b, game_type="tourney")
    features = np.array([features], dtype=np.float32)
    features = np.nan_to_num(features, nan=0.0)

    lr_prob = lr.predict_proba(features)[:, 1][0]
    lgb_prob = lgb_model.predict_proba(features)[:, 1][0]
    raw_prob = LR_WEIGHT * lr_prob + LGB_WEIGHT * lgb_prob
    cal_prob = float(smooth_cal(raw_prob))
    cal_prob = np.clip(cal_prob, 0.01, 0.99)

    results.append({"ID": row["ID"], "Pred": cal_prob})

sub_df = pd.DataFrame(results)
sub_df.to_csv(SUB_DIR / "stage2_submission_v5.csv", index=False)
print(f"Submission saved: {len(sub_df):,} predictions")
print(f"Pred range: [{sub_df['Pred'].min():.3f}, {sub_df['Pred'].max():.3f}]")
print(f"Mean pred: {sub_df['Pred'].mean():.3f}")""")

# =========================================================================
# Write notebook
# =========================================================================
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13.0"},
    },
    "cells": cells,
}

from pathlib import Path as _Path
out_path = _Path("Ubunifu_Madness_V5.ipynb")
with open(out_path, "w") as f:
    json.dump(nb, f, indent=1)

print(f"Notebook written to {out_path} ({len(cells)} cells)")
