"""
Compute derived stats and populate EloRating, ConferenceStrength, and TeamSeasonStats tables.

Reads directly from raw CSVs for speed. Computes:
1. Elo ratings (all seasons, all teams)
2. Conference strength (all seasons, all genders)
3. Team season stats for the current season (2026) only — box scores, massey, momentum, coach

Run from backend/:
    python -m scripts.compute_stats [--all-seasons]
"""

import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import (
    Team, EloRating, ConferenceStrength, TeamSeasonStats,
    TeamConference,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def r(val, digits=2):
    """Round and convert to Python float (avoids np.float64 in SQL)."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return float(round(val, digits))

# Elo config (from V2 Optuna tuning)
K_FACTOR = 21.8
HOME_ADV = 101.9
SEASON_REGRESSION = 0.89
MEAN_ELO = 1500

TARGET_SEASON = 2026


def load_all_results():
    """Load all compact results (men + women, regular + tourney)."""
    dfs = []
    for csv_file, game_type, gender in [
        ("MRegularSeasonCompactResults.csv", "regular", "M"),
        ("WRegularSeasonCompactResults.csv", "regular", "W"),
        ("MNCAATourneyCompactResults.csv", "tourney", "M"),
        ("WNCAATourneyCompactResults.csv", "tourney", "W"),
    ]:
        path = DATA_DIR / csv_file
        if path.exists():
            df = pd.read_csv(path)
            df["GameType"] = game_type
            df["Gender"] = gender
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def expected_win_prob(elo_a, elo_b):
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def compute_elo_ratings(all_results):
    """Compute Elo ratings for all teams across all seasons. Returns dict of (season, team_id) -> elo."""
    print("Computing Elo ratings...")
    all_results = all_results.sort_values(["Season", "DayNum"]).reset_index(drop=True)

    elo = {}  # team_id -> current elo
    elo_by_season = {}  # (season, team_id) -> end-of-season elo

    current_season = None
    for _, g in all_results.iterrows():
        season = int(g["Season"])

        # Season change: save & regress
        if season != current_season:
            if current_season is not None:
                for tid, e in elo.items():
                    elo_by_season[(current_season, tid)] = e
                for tid in elo:
                    elo[tid] = elo[tid] * SEASON_REGRESSION + MEAN_ELO * (1 - SEASON_REGRESSION)
            current_season = season

        w_id = int(g["WTeamID"])
        l_id = int(g["LTeamID"])

        for tid in [w_id, l_id]:
            if tid not in elo:
                elo[tid] = MEAN_ELO

        elo_w = elo[w_id]
        elo_l = elo[l_id]

        w_loc = g.get("WLoc", "N")
        if w_loc == "H":
            elo_w += HOME_ADV
        elif w_loc == "A":
            elo_l += HOME_ADV

        exp_w = expected_win_prob(elo_w, elo_l)
        mov = int(g["WScore"]) - int(g["LScore"])
        mult = np.log(abs(mov) + 1) * (2.2 / ((abs(elo_w - elo_l) * 0.001) + 2.2))

        update = K_FACTOR * mult * (1 - exp_w)
        elo[w_id] += update
        elo[l_id] -= update

    # Save final season
    if current_season is not None:
        for tid, e in elo.items():
            elo_by_season[(current_season, tid)] = e

    print(f"  {len(elo_by_season)} Elo ratings computed")
    return elo_by_season


def store_elo_ratings(session, elo_by_season):
    """Store Elo ratings in DB."""
    print("Storing Elo ratings...")
    session.query(EloRating).delete()
    session.commit()

    records = [
        EloRating(season=season, team_id=team_id, elo=r(elo_val), snapshot_day=154)
        for (season, team_id), elo_val in elo_by_season.items()
    ]

    batch_size = 5000
    for i in range(0, len(records), batch_size):
        session.bulk_save_objects(records[i:i + batch_size])
    session.commit()
    print(f"  {len(records)} stored")


def compute_conference_strength(session, elo_by_season, all_results):
    """Compute conference strength metrics."""
    print("Computing conference strength...")

    # Load team conferences (use Team.gender from DB, not ID heuristic)
    team_gender_map = {t.id: t.gender for t in session.query(Team).all()}
    tc_rows = session.query(TeamConference).all()
    team_conf = {}  # (season, team_id) -> conf_abbrev
    conf_teams = defaultdict(list)  # (season, gender, conf) -> [team_ids]
    for tc in tc_rows:
        team_conf[(tc.season, tc.team_id)] = tc.conf_abbrev
        gender = team_gender_map.get(tc.team_id, "M")
        conf_teams[(tc.season, gender, tc.conf_abbrev)].append(tc.team_id)

    # Precompute non-conf game lookups by season
    regular = all_results[all_results["GameType"] == "regular"]
    tourney = all_results[all_results["GameType"] == "tourney"]

    session.query(ConferenceStrength).delete()
    session.commit()

    records = []
    for (season, gender, conf), team_ids in conf_teams.items():
        # Elo metrics
        elos = [elo_by_season.get((season, tid), MEAN_ELO) for tid in team_ids]
        avg_elo = np.mean(elos) if elos else MEAN_ELO
        elo_depth = np.std(elos) if len(elos) > 1 else 0
        top5_elo = np.mean(sorted(elos, reverse=True)[:5]) if elos else MEAN_ELO

        # Non-conference win rate
        season_games = regular[
            (regular["Season"] == season) & (regular["Gender"] == gender)
        ]
        nc_wins, nc_total = 0, 0
        for _, g in season_games.iterrows():
            w_conf = team_conf.get((season, int(g["WTeamID"])))
            l_conf = team_conf.get((season, int(g["LTeamID"])))
            if w_conf != l_conf:
                if w_conf == conf:
                    nc_wins += 1
                    nc_total += 1
                elif l_conf == conf:
                    nc_total += 1
        nc_winrate = nc_wins / max(nc_total, 1)

        # Tourney hist (rolling 5 years)
        t_wins, t_total = 0, 0
        for s in range(max(season - 4, 1985), season + 1):
            sg = tourney[(tourney["Season"] == s) & (tourney["Gender"] == gender)]
            for _, g in sg.iterrows():
                w_c = team_conf.get((s, int(g["WTeamID"])))
                l_c = team_conf.get((s, int(g["LTeamID"])))
                if w_c == conf:
                    t_wins += 1
                    t_total += 1
                if l_c == conf:
                    t_total += 1
        t_hist = t_wins / max(t_total, 1)

        records.append(ConferenceStrength(
            season=season, gender=gender, conf_abbrev=conf,
            avg_elo=r(avg_elo), elo_depth=r(elo_depth), top5_elo=r(top5_elo),
            nc_winrate=r(nc_winrate, 4), tourney_hist_winrate=r(t_hist, 4),
        ))

    batch_size = 5000
    for i in range(0, len(records), batch_size):
        session.bulk_save_objects(records[i:i + batch_size])
    session.commit()
    print(f"  {len(records)} conference strength records stored")


def compute_team_season_stats(session, elo_by_season):
    """Compute per-team stats for TARGET_SEASON using vectorized pandas operations."""
    print(f"Computing team season stats for {TARGET_SEASON}...")

    # Load detailed results
    detail_dfs = []
    for csv_file, gender in [
        ("MRegularSeasonDetailedResults.csv", "M"),
        ("WRegularSeasonDetailedResults.csv", "W"),
    ]:
        path = DATA_DIR / csv_file
        if path.exists():
            df = pd.read_csv(path)
            df["Gender"] = gender
            detail_dfs.append(df)
    detail_df = pd.concat(detail_dfs, ignore_index=True) if detail_dfs else pd.DataFrame()

    # Filter to target season
    if not detail_df.empty:
        detail_df = detail_df[detail_df["Season"] == TARGET_SEASON]

    # Load compact results
    compact_dfs = []
    for csv_file, gender in [
        ("MRegularSeasonCompactResults.csv", "M"),
        ("WRegularSeasonCompactResults.csv", "W"),
    ]:
        path = DATA_DIR / csv_file
        if path.exists():
            df = pd.read_csv(path)
            df["Gender"] = gender
            compact_dfs.append(df)
    compact_df = pd.concat(compact_dfs, ignore_index=True)
    compact_season = compact_df[compact_df["Season"] == TARGET_SEASON]

    # Load Massey ordinals (men's and women's if available)
    massey_lookup = {}
    top_systems = ["POM", "SAG", "MOR", "WOL", "DOL", "RPI", "AP", "USA",
                   "COL", "RTH", "WLK", "ARG", "KPK", "BIH", "LOG"]
    for massey_file in ["MMasseyOrdinals.csv", "WMasseyOrdinals.csv"]:
        massey_path = DATA_DIR / massey_file
        if massey_path.exists():
            print(f"  Loading {massey_file}...")
            massey = pd.read_csv(massey_path)
            massey = massey[
                (massey["Season"] == TARGET_SEASON)
                & (massey["RankingDayNum"] == 133)
                & (massey["SystemName"].isin(top_systems))
            ]
            for tid, grp in massey.groupby("TeamID"):
                massey_lookup[int(tid)] = {
                    "avg_rank": grp["OrdinalRank"].mean(),
                    "disagreement": grp["OrdinalRank"].std(),
                }
    print(f"  Massey: {len(massey_lookup)} teams")

    # Precompute tournament participation and results for coach history
    tourney_team_seasons = defaultdict(set)   # season -> set of team_ids that appeared
    tourney_win_counts = defaultdict(int)     # (season, team_id) -> wins
    tourney_game_counts = defaultdict(int)    # (season, team_id) -> games played
    for csv_file in ["MNCAATourneyCompactResults.csv", "WNCAATourneyCompactResults.csv"]:
        path = DATA_DIR / csv_file
        if path.exists():
            tdf = pd.read_csv(path)
            for _, row in tdf.iterrows():
                s = int(row["Season"])
                w = int(row["WTeamID"])
                l = int(row["LTeamID"])
                tourney_team_seasons[s].add(w)
                tourney_team_seasons[s].add(l)
                tourney_win_counts[(s, w)] += 1
                tourney_game_counts[(s, w)] += 1
                tourney_game_counts[(s, l)] += 1

    # Load coaches (men's and women's if available)
    coach_lookup = {}
    for coaches_file in ["MTeamCoaches.csv", "WTeamCoaches.csv"]:
        coaches_path = DATA_DIR / coaches_file
        if coaches_path.exists():
            print(f"  Loading {coaches_file}...")
            coaches_df = pd.read_csv(coaches_path)
            season_coaches = coaches_df[coaches_df["Season"] == TARGET_SEASON]
            for tid, grp in season_coaches.groupby("TeamID"):
                last = grp.iloc[-1]
                cname = last["CoachName"]

                all_same = coaches_df[
                    (coaches_df["TeamID"] == tid)
                    & (coaches_df["CoachName"] == cname)
                    & (coaches_df["Season"] <= TARGET_SEASON)
                ]
                tenure = len(all_same["Season"].unique())

                # Compute coach's tournament history at this team
                tourney_apps = 0
                tourney_wins = 0
                tourney_games = 0
                coach_seasons = sorted(all_same["Season"].unique())
                for cs in coach_seasons:
                    if cs >= TARGET_SEASON:
                        continue
                    if int(tid) in tourney_team_seasons.get(cs, set()):
                        tourney_apps += 1
                        tourney_wins += tourney_win_counts.get((cs, int(tid)), 0)
                        tourney_games += tourney_game_counts.get((cs, int(tid)), 0)
                march_wr = tourney_wins / tourney_games if tourney_games > 0 else None

                coach_lookup[int(tid)] = {
                    "name": cname,
                    "tenure": tenure,
                    "tourney_apps": tourney_apps if tourney_apps > 0 else None,
                    "march_winrate": r(march_wr, 3),
                }

    # Conference tourney wins
    conf_tourney_wins = defaultdict(int)
    for csv_file, gender in [("MConferenceTourneyGames.csv", "M"), ("WConferenceTourneyGames.csv", "W")]:
        path = DATA_DIR / csv_file
        if path.exists():
            df = pd.read_csv(path)
            df_s = df[df["Season"] == TARGET_SEASON]
            for _, g in df_s.iterrows():
                conf_tourney_wins[int(g["WTeamID"])] += 1

    # Get all teams for target season
    tc_rows = session.query(TeamConference).filter(TeamConference.season == TARGET_SEASON).all()
    team_ids = [tc.team_id for tc in tc_rows]
    print(f"  Computing stats for {len(team_ids)} teams...")

    # Precompute records from compact results
    win_counts = compact_season.groupby("WTeamID").size().to_dict()
    loss_counts = compact_season.groupby("LTeamID").size().to_dict()

    # Precompute box score stats per team from detailed results
    box_stats = {}
    if not detail_df.empty:
        # Process winner stats
        for tid in team_ids:
            w_games = detail_df[detail_df["WTeamID"] == tid]
            l_games = detail_df[detail_df["LTeamID"] == tid]

            efg_list, to_list, or_list, ftr_list = [], [], [], []
            opp_efg_list, opp_to_list = [], []
            off_eff_list, def_eff_list, tempo_list = [], [], []

            for _, g in w_games.iterrows():
                poss_w = g["WFGA"] - g.get("WOR", 0) + g["WTO"] + 0.44 * g["WFTA"]
                poss_l = g["LFGA"] - g.get("LOR", 0) + g["LTO"] + 0.44 * g["LFTA"]
                poss = max((poss_w + poss_l) / 2, 1)

                efg_list.append((g["WFGM"] + 0.5 * g["WFGM3"]) / max(g["WFGA"], 1))
                to_list.append(g["WTO"] / max(poss_w, 1) * 100)
                or_list.append(g.get("WOR", 0) / max(g.get("WOR", 0) + g.get("LDR", 0), 1))
                ftr_list.append(g["WFTA"] / max(g["WFGA"], 1))
                opp_efg_list.append((g["LFGM"] + 0.5 * g["LFGM3"]) / max(g["LFGA"], 1))
                opp_to_list.append(g["LTO"] / max(poss_l, 1) * 100)
                off_eff_list.append(g["WScore"] / max(poss, 1) * 100)
                def_eff_list.append(g["LScore"] / max(poss, 1) * 100)
                tempo_list.append(poss)

            for _, g in l_games.iterrows():
                poss_w = g["WFGA"] - g.get("WOR", 0) + g["WTO"] + 0.44 * g["WFTA"]
                poss_l = g["LFGA"] - g.get("LOR", 0) + g["LTO"] + 0.44 * g["LFTA"]
                poss = max((poss_w + poss_l) / 2, 1)

                efg_list.append((g["LFGM"] + 0.5 * g["LFGM3"]) / max(g["LFGA"], 1))
                to_list.append(g["LTO"] / max(poss_l, 1) * 100)
                or_list.append(g.get("LOR", 0) / max(g.get("LOR", 0) + g.get("WDR", 0), 1))
                ftr_list.append(g["LFTA"] / max(g["LFGA"], 1))
                opp_efg_list.append((g["WFGM"] + 0.5 * g["WFGM3"]) / max(g["WFGA"], 1))
                opp_to_list.append(g["WTO"] / max(poss_w, 1) * 100)
                off_eff_list.append(g["LScore"] / max(poss, 1) * 100)
                def_eff_list.append(g["WScore"] / max(poss, 1) * 100)
                tempo_list.append(poss)

            if efg_list:
                box_stats[tid] = {
                    "efg": np.mean(efg_list),
                    "to": np.mean(to_list),
                    "or": np.mean(or_list),
                    "ftr": np.mean(ftr_list),
                    "opp_efg": np.mean(opp_efg_list),
                    "opp_to": np.mean(opp_to_list),
                    "off_eff": np.mean(off_eff_list),
                    "def_eff": np.mean(def_eff_list),
                    "tempo": np.mean(tempo_list),
                }

    # Precompute strength of schedule (average opponent Elo)
    sos_map = {}
    current_elo = {tid: e for (s, tid), e in elo_by_season.items() if s == TARGET_SEASON}
    for tid in team_ids:
        opp_elos = []
        w_games = compact_season[compact_season["WTeamID"] == tid]
        l_games = compact_season[compact_season["LTeamID"] == tid]
        for _, g in w_games.iterrows():
            opp_id = int(g["LTeamID"])
            opp_elos.append(current_elo.get(opp_id, MEAN_ELO))
        for _, g in l_games.iterrows():
            opp_id = int(g["WTeamID"])
            opp_elos.append(current_elo.get(opp_id, MEAN_ELO))
        if opp_elos:
            sos_map[tid] = np.mean(opp_elos)

    # Precompute momentum (last 10 games) for all teams
    momentum = {}
    for tid in team_ids:
        team_games = compact_season[
            (compact_season["WTeamID"] == tid) | (compact_season["LTeamID"] == tid)
        ].sort_values("DayNum")
        last_n = team_games.tail(10)
        if len(last_n) > 0:
            last_wins = len(last_n[last_n["WTeamID"] == tid])
            movs = []
            for _, g in last_n.iterrows():
                if g["WTeamID"] == tid:
                    movs.append(g["WScore"] - g["LScore"])
                else:
                    movs.append(g["LScore"] - g["WScore"])
            momentum[tid] = {
                "winpct": last_wins / len(last_n),
                "mov": np.mean(movs),
            }

    # Build records
    session.query(TeamSeasonStats).delete()
    session.commit()

    records = []
    for tid in team_ids:
        wins = win_counts.get(tid, 0)
        losses = loss_counts.get(tid, 0)
        total = wins + losses
        win_pct = wins / total if total > 0 else 0

        bs = box_stats.get(tid, {})
        ms = massey_lookup.get(tid, {})
        mo = momentum.get(tid, {})
        co = coach_lookup.get(tid, {})

        records.append(TeamSeasonStats(
            season=TARGET_SEASON,
            team_id=tid,
            wins=wins,
            losses=losses,
            win_pct=r(win_pct, 4),
            avg_efg_pct=r(bs.get("efg"), 4),
            avg_to_pct=r(bs.get("to")),
            avg_or_pct=r(bs.get("or"), 4),
            avg_ft_rate=r(bs.get("ftr"), 4),
            avg_opp_efg_pct=r(bs.get("opp_efg"), 4),
            avg_opp_to_pct=r(bs.get("opp_to")),
            avg_off_eff=r(bs.get("off_eff")),
            avg_def_eff=r(bs.get("def_eff")),
            avg_tempo=r(bs.get("tempo"), 1),
            sos=r(sos_map.get(tid), 1),
            massey_avg_rank=r(ms.get("avg_rank"), 1),
            massey_disagreement=r(ms.get("disagreement"), 1),
            last_n_winpct=r(mo.get("winpct"), 3),
            last_n_mov=r(mo.get("mov"), 1),
            conf_tourney_wins=conf_tourney_wins.get(tid, 0),
            coach_name=co.get("name"),
            coach_tenure=co.get("tenure"),
            coach_tourney_appearances=co.get("tourney_apps"),
            coach_march_winrate=co.get("march_winrate"),
        ))

    session.bulk_save_objects(records)
    session.commit()
    print(f"  {len(records)} team-season stats computed for {TARGET_SEASON}")


def main():
    all_results = load_all_results()
    print(f"Loaded {len(all_results)} total game results from CSVs")

    elo_by_season = compute_elo_ratings(all_results)

    session = SessionLocal()
    try:
        store_elo_ratings(session, elo_by_season)
        compute_conference_strength(session, elo_by_season, all_results)
        compute_team_season_stats(session, elo_by_season)
        print("\nAll computed stats stored successfully!")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
