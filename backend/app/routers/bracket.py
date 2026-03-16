import random

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models import (
    Team, TourneySeed, Prediction, EloRating,
    TeamConference, TeamSeasonStats, GameResult, Conference,
)
from app.models.official_bracket import OfficialBracket
from app.services.predictor import predict_matchup

router = APIRouter(tags=["bracket"])

# Standard seed matchups for round 1 (seed_a vs seed_b)
ROUND1_MATCHUPS = [
    (1, 16), (8, 9), (5, 12), (4, 13),
    (6, 11), (3, 14), (7, 10), (2, 15),
]

REGION_NAMES = {"W": "East", "X": "West", "Y": "South", "Z": "Midwest"}
REGION_CODES = {v: k for k, v in REGION_NAMES.items()}

# Final Four pairings by region code (varies by gender in 2026)
# Pairings are diagonal (opposite sides of the bracket)
# Men's 2026: East (W) vs South (Y), Midwest (Z) vs West (X)
# Women's 2026: Regional 1 (W) vs Regional 4 (Z), Regional 2 (X) vs Regional 3 (Y)
FF_PAIRINGS_M = [("W", "Y"), ("Z", "X")]
FF_PAIRINGS_W = [("W", "Z"), ("X", "Y")]

def get_ff_pairings(gender: str):
    return FF_PAIRINGS_W if gender == "W" else FF_PAIRINGS_M

ROUND_NAMES = ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]


def _team_dict(team, elo_map, seed_map, conf_map, stats_map):
    """Build team dict using pre-loaded maps (avoids N+1 queries)."""
    elo_val = elo_map.get(team.id)
    seed_num = seed_map.get(team.id)
    conf = conf_map.get(team.id)
    stats = stats_map.get(team.id)
    record = f"{stats.wins}-{stats.losses}" if stats else None
    return {
        "id": team.id,
        "name": team.name,
        "gender": team.gender,
        "seed": seed_num,
        "conference": conf,
        "elo": round(elo_val, 1) if elo_val else None,
        "record": record,
        "winPct": round(stats.win_pct, 3) if stats else None,
        "logo": team.logo_url,
        "color": team.color,
    }


def _get_pred_from_cache(pred_cache, t1_id, t2_id):
    """Get win probability for t1 vs t2 from cache."""
    lo, hi = min(t1_id, t2_id), max(t1_id, t2_id)
    prob = pred_cache.get((lo, hi))
    if prob is not None:
        return prob if t1_id == lo else (1 - prob)
    return 0.5


def _build_result(result_lookup, team_a_id, team_b_id):
    """Build result dict from the result lookup."""
    key = frozenset([team_a_id, team_b_id])
    if key not in result_lookup:
        return None
    g = result_lookup[key]
    return {
        "winnerId": g.w_team_id,
        "winnerScore": g.w_score,
        "loserScore": g.l_score,
    }


def _batch_load_maps(db, season, team_ids, stats_season=None):
    """Pre-load all related data for a set of team IDs.

    stats_season: if provided, load stats/conf/elo from this season instead
    (useful when bracket is from an older season but we want current records).
    """
    data_season = stats_season or season
    elo_map = {
        r.team_id: r.elo
        for r in db.query(EloRating)
        .filter(EloRating.season == data_season, EloRating.team_id.in_(team_ids))
        .all()
    }
    seed_map = {
        r.team_id: r.seed_number
        for r in db.query(TourneySeed)
        .filter(TourneySeed.season == season, TourneySeed.team_id.in_(team_ids))
        .all()
    }
    # Full conference names
    conf_names = {r.abbrev: r.description for r in db.query(Conference).all()}
    conf_map = {
        r.team_id: conf_names.get(r.conf_abbrev, r.conf_abbrev)
        for r in db.query(TeamConference)
        .filter(TeamConference.season == data_season, TeamConference.team_id.in_(team_ids))
        .all()
    }
    stats_map = {
        r.team_id: r
        for r in db.query(TeamSeasonStats)
        .filter(TeamSeasonStats.season == data_season, TeamSeasonStats.team_id.in_(team_ids))
        .all()
    }
    # Fallback: if stats_map is empty and data_season != season, try the bracket season
    if not stats_map and data_season != season:
        stats_map = {
            r.team_id: r
            for r in db.query(TeamSeasonStats)
            .filter(TeamSeasonStats.season == season, TeamSeasonStats.team_id.in_(team_ids))
            .all()
        }
    return elo_map, seed_map, conf_map, stats_map


@router.get("/bracket/full")
def full_bracket(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = Query(0, description="Season year. 0 = auto-detect latest."),
    db: Session = Depends(get_db),
):
    """Get complete bracket with all rounds and results.

    If season=0 or the requested season has no seeds, falls back to the
    most recent season that has tournament seeds.
    """
    # Auto-detect or fallback to latest season with seeds
    actual_season = season if season > 0 else 2026

    seeds = (
        db.query(TourneySeed, Team)
        .join(Team, Team.id == TourneySeed.team_id)
        .filter(TourneySeed.season == actual_season, Team.gender == gender)
        .all()
    )

    if not seeds:
        # Fallback: find the latest season with seeds for this gender
        latest = (
            db.query(TourneySeed.season)
            .join(Team, Team.id == TourneySeed.team_id)
            .filter(Team.gender == gender)
            .order_by(desc(TourneySeed.season))
            .first()
        )
        if not latest:
            return {"season": actual_season, "gender": gender, "hasBracket": False, "regions": {}, "finalFour": [], "championship": [], "champion": None}
        actual_season = latest[0]
        seeds = (
            db.query(TourneySeed, Team)
            .join(Team, Team.id == TourneySeed.team_id)
            .filter(TourneySeed.season == actual_season, Team.gender == gender)
            .all()
        )

    # Batch load all team data
    all_team_ids = list({team.id for _, team in seeds})
    team_by_id = {team.id: team for _, team in seeds}

    # Use the latest season with stats for records (e.g., 2026 stats for 2025 bracket)
    latest_stats_season = db.query(TeamSeasonStats.season).order_by(desc(TeamSeasonStats.season)).first()
    stats_season = latest_stats_season[0] if latest_stats_season else actual_season
    elo_map, seed_map, conf_map, stats_map = _batch_load_maps(db, actual_season, all_team_ids, stats_season=stats_season)

    # Use static Prediction table for fast bracket display.
    # Live predictor is only used for official bracket generation (one-time).
    preds = (
        db.query(Prediction)
        .filter(
            Prediction.season == actual_season,
            Prediction.team_a_id.in_(all_team_ids),
            Prediction.team_b_id.in_(all_team_ids),
        )
        .all()
    )
    pred_cache = {(p.team_a_id, p.team_b_id): p.win_prob_a for p in preds}

    def get_win_prob(t1_id, t2_id):
        lo, hi = min(t1_id, t2_id), max(t1_id, t2_id)
        prob = pred_cache.get((lo, hi))
        if prob is not None:
            return round(prob if t1_id == lo else (1 - prob), 4)
        # Elo fallback for matchups not in the prediction table
        elo_a = elo_map.get(t1_id, 1500)
        elo_b = elo_map.get(t2_id, 1500)
        return round(1 / (1 + 10 ** ((elo_b - elo_a) / 400)), 4)

    # Load tournament game results
    tourney_games = (
        db.query(GameResult)
        .filter(
            GameResult.season == actual_season,
            GameResult.game_type == "tourney",
            GameResult.gender == gender,
        )
        .all()
    )
    result_lookup = {}
    for g in tourney_games:
        key = frozenset([g.w_team_id, g.l_team_id])
        result_lookup[key] = g
        # Also track these teams in our maps
        for tid in [g.w_team_id, g.l_team_id]:
            if tid not in team_by_id:
                t = db.query(Team).filter(Team.id == tid).first()
                if t:
                    team_by_id[tid] = t

    is_complete = len(tourney_games) >= 63  # Full tournament = 63 games (67 with play-in)

    def make_team_dict(tid):
        team = team_by_id.get(tid)
        if not team:
            return None
        return _team_dict(team, elo_map, seed_map, conf_map, stats_map)

    def _tbd_team(seed=None, region_code=None):
        label = "TBD"
        if seed and region_code and (region_code, seed) in first_four_pending:
            label = first_four_pending[(region_code, seed)]
        return {"id": None, "name": label, "seed": seed, "elo": None,
                "record": None, "conference": None, "logo": None, "color": None, "winPct": None, "gender": gender}

    def make_matchup(team_a_id, team_b_id, tbd_seed=None, region_code=None):
        team_a = make_team_dict(team_a_id) if team_a_id else _tbd_team(tbd_seed, region_code)
        team_b = make_team_dict(team_b_id) if team_b_id else _tbd_team(tbd_seed, region_code)
        if team_a_id is None or team_b_id is None:
            return {"teamA": team_a, "teamB": team_b, "winProbA": 0.5, "result": None}
        result = _build_result(result_lookup, team_a_id, team_b_id)
        return {
            "teamA": team_a,
            "teamB": team_b,
            "winProbA": get_win_prob(team_a_id, team_b_id),
            "result": result,
        }

    # Group seeds by region, handling play-in (multiple teams per seed)
    by_region = {}  # region_code -> {seed: [team_ids]}
    for seed_row, team in seeds:
        region = seed_row.region
        if region not in by_region:
            by_region[region] = {}
        if seed_row.seed_number not in by_region[region]:
            by_region[region][seed_row.seed_number] = []
        by_region[region][seed_row.seed_number].append(team.id)

    # Build First Four matchups and resolve play-in games.
    # Track which First Four matchup feeds each TBD slot.
    first_four = []
    first_four_pending = {}  # (region, seed) -> "TeamA / TeamB"
    for region in by_region:
        for seed_num, team_ids in list(by_region[region].items()):
            if len(team_ids) == 2:
                t1, t2 = team_ids[0], team_ids[1]
                matchup = make_matchup(t1, t2)
                if matchup:
                    matchup["region"] = REGION_NAMES.get(region, region)
                    matchup["seed"] = seed_num
                    first_four.append(matchup)
                key = frozenset(team_ids)
                if key in result_lookup:
                    winner_id = result_lookup[key].w_team_id
                    by_region[region][seed_num] = [winner_id]
                else:
                    # First Four not yet played: mark as None (TBD)
                    t1_name = team_by_id[t1].name if t1 in team_by_id else "TBD"
                    t2_name = team_by_id[t2].name if t2 in team_by_id else "TBD"
                    first_four_pending[(region, seed_num)] = f"{t1_name} / {t2_name}"
                    by_region[region][seed_num] = [None]

    # Build bracket region by region
    regions = {}
    region_winners = {}  # region_code -> team_id

    for region_code in sorted(by_region.keys()):
        region_name = REGION_NAMES.get(region_code, region_code)
        teams_by_seed = {s: ids[0] for s, ids in by_region[region_code].items() if ids}

        rounds = []

        # Round 1
        r1 = []
        r1_winners = []
        for seed_a, seed_b in ROUND1_MATCHUPS:
            tid_a = teams_by_seed.get(seed_a)
            tid_b = teams_by_seed.get(seed_b)
            # Both teams known: normal matchup
            # One team is None (First Four pending): show matchup with TBD slot
            if tid_a is not None and tid_b is not None:
                matchup = make_matchup(tid_a, tid_b)
                r1.append(matchup)
                if matchup and matchup["result"]:
                    r1_winners.append(matchup["result"]["winnerId"])
                else:
                    r1_winners.append(None)
            elif seed_a in teams_by_seed or seed_b in teams_by_seed:
                # One side is TBD from unresolved First Four
                tbd_seed = seed_a if tid_a is None else seed_b
                matchup = make_matchup(tid_a, tid_b, tbd_seed=tbd_seed, region_code=region_code)
                r1.append(matchup)
                r1_winners.append(None)
            else:
                r1.append(None)
                r1_winners.append(None)

        rounds.append(r1)

        # Subsequent rounds within region (R2, S16, E8)
        current_winners = r1_winners
        for round_idx in range(1, 4):  # R2, S16, E8
            round_matchups = []
            next_winners = []
            for i in range(0, len(current_winners), 2):
                tid_a = current_winners[i] if i < len(current_winners) else None
                tid_b = current_winners[i + 1] if i + 1 < len(current_winners) else None

                if tid_a and tid_b:
                    matchup = make_matchup(tid_a, tid_b)
                    round_matchups.append(matchup)
                    if matchup and matchup["result"]:
                        next_winners.append(matchup["result"]["winnerId"])
                    else:
                        next_winners.append(None)
                elif tid_a or tid_b:
                    round_matchups.append(None)
                    next_winners.append(tid_a or tid_b)
                else:
                    round_matchups.append(None)
                    next_winners.append(None)

            rounds.append(round_matchups)
            current_winners = next_winners

        # Region winner
        region_winner = current_winners[0] if current_winners else None
        region_winners[region_code] = region_winner

        regions[region_name] = {
            "regionCode": region_code,
            "rounds": rounds,
            "winner": make_team_dict(region_winner) if region_winner else None,
        }

    # Final Four
    final_four = []
    ff_winners = []
    for rc_a, rc_b in get_ff_pairings(gender):
        tid_a = region_winners.get(rc_a)
        tid_b = region_winners.get(rc_b)
        if tid_a and tid_b:
            matchup = make_matchup(tid_a, tid_b)
            final_four.append(matchup)
            if matchup and matchup["result"]:
                ff_winners.append(matchup["result"]["winnerId"])
            else:
                ff_winners.append(None)
        else:
            final_four.append(None)
            ff_winners.append(tid_a or tid_b)

    # Championship
    championship = []
    champion = None
    if len(ff_winners) == 2:
        tid_a = ff_winners[0]
        tid_b = ff_winners[1]
        if tid_a and tid_b:
            matchup = make_matchup(tid_a, tid_b)
            championship.append(matchup)
            if matchup and matchup["result"]:
                champion = make_team_dict(matchup["result"]["winnerId"])
        else:
            championship.append(None)

    return {
        "season": actual_season,
        "gender": gender,
        "hasBracket": True,
        "isComplete": is_complete,
        "firstFour": first_four,
        "regions": regions,
        "finalFour": final_four,
        "ffPairings": [
            [REGION_NAMES.get(a, a), REGION_NAMES.get(b, b)]
            for a, b in get_ff_pairings(gender)
        ],
        "championship": championship,
        "champion": champion,
        "roundNames": ROUND_NAMES,
    }


@router.get("/bracket/matchups")
def bracket_matchups(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = 2026,
    db: Session = Depends(get_db),
):
    # Get all seeds for this season/gender
    seeds = (
        db.query(TourneySeed, Team)
        .join(Team, Team.id == TourneySeed.team_id)
        .filter(TourneySeed.season == season, Team.gender == gender)
        .all()
    )

    if not seeds:
        return {"season": season, "gender": gender, "matchups": []}

    all_team_ids = [team.id for _, team in seeds]
    elo_map, seed_map, conf_map, stats_map = _batch_load_maps(db, season, all_team_ids)

    # Build prediction cache
    preds = (
        db.query(Prediction)
        .filter(Prediction.season == season, Prediction.team_a_id.in_(all_team_ids), Prediction.team_b_id.in_(all_team_ids))
        .all()
    )
    pred_cache = {(p.team_a_id, p.team_b_id): p.win_prob_a for p in preds}

    # Group by region
    by_region = {}
    for seed_row, team in seeds:
        region = seed_row.region
        if region not in by_region:
            by_region[region] = {}
        by_region[region][seed_row.seed_number] = (seed_row, team)

    matchups = []
    for region, teams_by_seed in by_region.items():
        for seed_a, seed_b in ROUND1_MATCHUPS:
            if seed_a in teams_by_seed and seed_b in teams_by_seed:
                _, team_a = teams_by_seed[seed_a]
                _, team_b = teams_by_seed[seed_b]

                prob_a = _get_pred_from_cache(pred_cache, team_a.id, team_b.id)

                matchups.append({
                    "teamA": _team_dict(team_a, elo_map, seed_map, conf_map, stats_map),
                    "teamB": _team_dict(team_b, elo_map, seed_map, conf_map, stats_map),
                    "winProbA": round(prob_a, 4),
                    "round": 1,
                    "region": REGION_NAMES.get(region, region),
                    "slot": f"R1{region}{seed_a}",
                })

    return {"season": season, "gender": gender, "matchups": matchups}


@router.post("/bracket/simulate")
def simulate_bracket(
    season: int = 2026,
    gender: str = "M",
    num_simulations: int = 1000,
    db: Session = Depends(get_db),
):
    # Get all seeds
    seeds = (
        db.query(TourneySeed, Team)
        .join(Team, Team.id == TourneySeed.team_id)
        .filter(TourneySeed.season == season, Team.gender == gender)
        .all()
    )

    if not seeds:
        raise HTTPException(404, "No seeds found for this season/gender")

    all_team_ids = [team.id for _, team in seeds]

    # Use live V5 predictor with cache for simulation
    _sim_cache: dict[tuple[int, int], float] = {}

    def get_prob(t1, t2):
        key = (min(t1, t2), max(t1, t2))
        if key not in _sim_cache:
            prob_a, _ = predict_matchup(
                db, key[0], key[1],
                is_ncaa_tourney=True, is_neutral=True,
            )
            _sim_cache[key] = prob_a
        prob = _sim_cache[key]
        return prob if t1 == key[0] else (1 - prob)

    # Group by region
    by_region = {}
    for seed_row, team in seeds:
        if seed_row.region not in by_region:
            by_region[seed_row.region] = []
        by_region[seed_row.region].append((seed_row.seed_number, team.id, team.name))

    for region in by_region:
        by_region[region].sort(key=lambda x: x[0])

    champion_counts = {}
    ff_counts = {}

    for _ in range(num_simulations):
        ff_teams = []
        for region, team_list in by_region.items():
            bracket_order = []
            seed_to_team = {s: (tid, name) for s, tid, name in team_list}
            for sa, sb in ROUND1_MATCHUPS:
                if sa in seed_to_team and sb in seed_to_team:
                    bracket_order.append([seed_to_team[sa], seed_to_team[sb]])

            current = []
            for pair in bracket_order:
                (t1_id, t1_name), (t2_id, t2_name) = pair
                prob = get_prob(t1_id, t2_id)
                winner = (t1_id, t1_name) if random.random() < prob else (t2_id, t2_name)
                current.append(winner)

            while len(current) > 1:
                next_round = []
                for j in range(0, len(current), 2):
                    if j + 1 < len(current):
                        t1_id, t1_name = current[j]
                        t2_id, t2_name = current[j + 1]
                        prob = get_prob(t1_id, t2_id)
                        winner = (t1_id, t1_name) if random.random() < prob else (t2_id, t2_name)
                        next_round.append(winner)
                    else:
                        next_round.append(current[j])
                current = next_round

            if current:
                ff_teams.append(current[0])
                tid, tname = current[0]
                ff_counts[tid] = ff_counts.get(tid, 0) + 1

        while len(ff_teams) > 1:
            next_round = []
            for j in range(0, len(ff_teams), 2):
                if j + 1 < len(ff_teams):
                    t1_id, t1_name = ff_teams[j]
                    t2_id, t2_name = ff_teams[j + 1]
                    prob = get_prob(t1_id, t2_id)
                    winner = (t1_id, t1_name) if random.random() < prob else (t2_id, t2_name)
                    next_round.append(winner)
                else:
                    next_round.append(ff_teams[j])
            ff_teams = next_round

        if ff_teams:
            tid, tname = ff_teams[0]
            champion_counts[tid] = champion_counts.get(tid, 0) + 1

    name_map = {team.id: team.name for _, team in seeds}

    champ_probs = sorted(
        [
            {"teamId": tid, "teamName": name_map.get(tid, ""), "probability": round(cnt / num_simulations, 4)}
            for tid, cnt in champion_counts.items()
        ],
        key=lambda x: -x["probability"],
    )[:20]

    ff_probs = sorted(
        [
            {"teamId": tid, "teamName": name_map.get(tid, ""), "probability": round(cnt / num_simulations, 4)}
            for tid, cnt in ff_counts.items()
        ],
        key=lambda x: -x["probability"],
    )[:20]

    return {
        "championProbabilities": champ_probs,
        "finalFourProbabilities": ff_probs,
    }


# ---------------------------------------------------------------------------
# Official brackets (model + agent) -- generated once, then locked
# ---------------------------------------------------------------------------

@router.get("/bracket/official")
def get_official_bracket(
    gender: str = Query("M", pattern="^(M|W)$"),
    bracket_type: str = Query("model", pattern="^(model|agent|consensus)$"),
    season: int = Query(0),
    db: Session = Depends(get_db),
):
    """Retrieve a locked official bracket. Returns null if not yet generated."""
    actual_season = season if season > 0 else 2026
    row = (
        db.query(OfficialBracket)
        .filter(
            OfficialBracket.season == actual_season,
            OfficialBracket.gender == gender,
            OfficialBracket.bracket_type == bracket_type,
        )
        .first()
    )
    if not row:
        return {"exists": False, "bracket_type": bracket_type, "season": actual_season, "gender": gender}
    return {
        "exists": True,
        "bracket_type": bracket_type,
        "season": actual_season,
        "gender": gender,
        "picks": row.picks,
        "metadata": row.metadata_,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/bracket/official/generate")
def generate_official_bracket(
    gender: str = Query("M", pattern="^(M|W)$"),
    bracket_type: str = Query("model", pattern="^(model|agent)$"),
    season: int = Query(0),
    db: Session = Depends(get_db),
):
    """Generate and lock an official bracket. Fails if one already exists.

    Model bracket: always picks the favorite (chalk).
    Agent bracket: uses a balanced strategy with slight upset variance.
    """
    actual_season = season if season > 0 else 2026

    # Check if already generated
    existing = (
        db.query(OfficialBracket)
        .filter(
            OfficialBracket.season == actual_season,
            OfficialBracket.gender == gender,
            OfficialBracket.bracket_type == bracket_type,
        )
        .first()
    )
    if existing:
        return {
            "error": f"{bracket_type.title()} bracket already generated and locked.",
            "exists": True,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
        }

    # Load seeds
    seeds = (
        db.query(TourneySeed, Team)
        .join(Team, Team.id == TourneySeed.team_id)
        .filter(TourneySeed.season == actual_season, Team.gender == gender)
        .all()
    )
    if not seeds:
        raise HTTPException(404, "No tournament seeds available yet.")

    all_team_ids = list({team.id for _, team in seeds})

    # Use the live V5 ML ensemble predictor for each matchup.
    # Cache results to avoid recomputing the same pair.
    _prob_cache: dict[tuple[int, int], float] = {}

    def get_prob(t1, t2):
        key = (min(t1, t2), max(t1, t2))
        if key not in _prob_cache:
            prob_a, _ = predict_matchup(
                db, key[0], key[1],
                is_ncaa_tourney=True, is_neutral=True,
            )
            _prob_cache[key] = prob_a
        prob = _prob_cache[key]
        return prob if t1 == key[0] else (1 - prob)

    # Group by region, resolve play-ins
    by_region = {}
    for seed_row, team in seeds:
        region = seed_row.region
        if region not in by_region:
            by_region[region] = {}
        if seed_row.seed_number not in by_region[region]:
            by_region[region][seed_row.seed_number] = []
        by_region[region][seed_row.seed_number].append(team.id)

    # Load game results for play-in resolution
    tourney_games = (
        db.query(GameResult)
        .filter(
            GameResult.season == actual_season,
            GameResult.game_type == "tourney",
            GameResult.gender == gender,
        )
        .all()
    )
    result_lookup = {}
    for g in tourney_games:
        result_lookup[frozenset([g.w_team_id, g.l_team_id])] = g

    for region in by_region:
        for seed_num, team_ids in by_region[region].items():
            if len(team_ids) == 2:
                key = frozenset(team_ids)
                if key in result_lookup:
                    by_region[region][seed_num] = [result_lookup[key].w_team_id]
                else:
                    by_region[region][seed_num] = [team_ids[0]]

    def pick_winner(t1_id, t2_id):
        """Return winner team_id based on bracket type strategy."""
        prob_t1 = get_prob(t1_id, t2_id)
        if bracket_type == "model":
            # Chalk: always pick the favorite
            return t1_id if prob_t1 >= 0.5 else t2_id
        else:
            # Agent: balanced -- 30% chance to pick underdog if >35% win prob
            if prob_t1 >= 0.5:
                fav, dog = t1_id, t2_id
                dog_prob = 1 - prob_t1
            else:
                fav, dog = t2_id, t1_id
                dog_prob = prob_t1
            if dog_prob >= 0.35 and random.random() < 0.30:
                return dog
            return fav

    # Build the bracket picks dict (slotId -> teamId)
    # Slot format matches frontend: "{regionName}_r{roundIdx}_{matchIdx}"
    picks = {}
    metadata = {"strategy": "chalk" if bracket_type == "model" else "balanced"}
    region_winners = {}

    for region_code in sorted(by_region.keys()):
        region_name = REGION_NAMES.get(region_code, region_code)
        teams_by_seed = {s: ids[0] for s, ids in by_region[region_code].items() if ids}

        # Round of 64
        r1_winners = []
        for match_idx, (sa, sb) in enumerate(ROUND1_MATCHUPS):
            tid_a = teams_by_seed.get(sa)
            tid_b = teams_by_seed.get(sb)
            if tid_a and tid_b:
                winner = pick_winner(tid_a, tid_b)
                picks[f"{region_name}_r0_{match_idx}"] = winner
                r1_winners.append(winner)
            else:
                w = tid_a or tid_b
                if w:
                    picks[f"{region_name}_r0_{match_idx}"] = w
                    r1_winners.append(w)
                else:
                    r1_winners.append(None)

        # Rounds 2-4 (R32, S16, E8)
        current = r1_winners
        for round_idx in range(1, 4):
            next_round = []
            match_idx = 0
            for i in range(0, len(current), 2):
                tid_a = current[i] if i < len(current) else None
                tid_b = current[i + 1] if i + 1 < len(current) else None
                if tid_a and tid_b:
                    winner = pick_winner(tid_a, tid_b)
                    picks[f"{region_name}_r{round_idx}_{match_idx}"] = winner
                    next_round.append(winner)
                elif tid_a or tid_b:
                    w = tid_a or tid_b
                    picks[f"{region_name}_r{round_idx}_{match_idx}"] = w
                    next_round.append(w)
                else:
                    next_round.append(None)
                match_idx += 1
            current = next_round

        region_winners[region_code] = current[0] if current else None

    # Final Four
    ff_teams = []
    for pair_idx, (rc_a, rc_b) in enumerate(get_ff_pairings(gender)):
        tid_a = region_winners.get(rc_a)
        tid_b = region_winners.get(rc_b)
        if tid_a and tid_b:
            winner = pick_winner(tid_a, tid_b)
            picks[f"ff_{pair_idx}"] = winner
            ff_teams.append(winner)
        else:
            w = tid_a or tid_b
            if w:
                picks[f"ff_{pair_idx}"] = w
                ff_teams.append(w)
            else:
                ff_teams.append(None)

    # Championship
    if len(ff_teams) == 2 and ff_teams[0] and ff_teams[1]:
        winner = pick_winner(ff_teams[0], ff_teams[1])
        picks["champ_0"] = winner
        # Store champion name in metadata
        champ_team = db.query(Team).filter(Team.id == winner).first()
        metadata["champion"] = champ_team.name if champ_team else str(winner)

    # Save to DB
    official = OfficialBracket(
        season=actual_season,
        gender=gender,
        bracket_type=bracket_type,
        picks=picks,
        metadata_=metadata,
    )
    db.add(official)
    db.commit()
    db.refresh(official)

    return {
        "exists": True,
        "bracket_type": bracket_type,
        "season": actual_season,
        "gender": gender,
        "picks": picks,
        "metadata": metadata,
        "created_at": official.created_at.isoformat() if official.created_at else None,
    }


@router.post("/bracket/official/consensus")
def generate_consensus_bracket(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = Query(0),
    db: Session = Depends(get_db),
):
    """Generate a consensus bracket by combining model and agent brackets.

    Where both agree: pick that team (high confidence).
    Where they disagree: use the model's prediction probability to decide,
    and flag the slot as contested.
    """
    actual_season = season if season > 0 else 2026

    # Check if consensus already exists
    existing = (
        db.query(OfficialBracket)
        .filter(
            OfficialBracket.season == actual_season,
            OfficialBracket.gender == gender,
            OfficialBracket.bracket_type == "consensus",
        )
        .first()
    )
    if existing:
        return {
            "error": "Consensus bracket already generated and locked.",
            "exists": True,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
        }

    # Load model and agent brackets
    model_bracket = (
        db.query(OfficialBracket)
        .filter(
            OfficialBracket.season == actual_season,
            OfficialBracket.gender == gender,
            OfficialBracket.bracket_type == "model",
        )
        .first()
    )
    agent_bracket = (
        db.query(OfficialBracket)
        .filter(
            OfficialBracket.season == actual_season,
            OfficialBracket.gender == gender,
            OfficialBracket.bracket_type == "agent",
        )
        .first()
    )

    if not model_bracket or not agent_bracket:
        raise HTTPException(
            400,
            "Both model and agent brackets must be generated before creating a consensus bracket.",
        )

    model_picks = model_bracket.picks
    agent_picks = agent_bracket.picks

    # Merge: collect all slot keys from both
    all_slots = set(model_picks.keys()) | set(agent_picks.keys())
    consensus_picks = {}
    agreed = []
    contested = []

    for slot in sorted(all_slots):
        m_pick = model_picks.get(slot)
        a_pick = agent_picks.get(slot)

        if m_pick == a_pick:
            # Both agree
            consensus_picks[slot] = m_pick
            agreed.append(slot)
        elif m_pick and a_pick:
            # Disagree: model wins (data-driven tiebreaker)
            consensus_picks[slot] = m_pick
            contested.append(slot)
        else:
            # One is missing: use whichever exists
            consensus_picks[slot] = m_pick or a_pick

    metadata = {
        "strategy": "consensus",
        "agreed_slots": len(agreed),
        "contested_slots": len(contested),
        "contested_details": contested,
        "agreement_pct": round(len(agreed) / max(len(all_slots), 1) * 100, 1),
    }

    official = OfficialBracket(
        season=actual_season,
        gender=gender,
        bracket_type="consensus",
        picks=consensus_picks,
        metadata_=metadata,
    )
    db.add(official)
    db.commit()
    db.refresh(official)

    return {
        "exists": True,
        "bracket_type": "consensus",
        "season": actual_season,
        "gender": gender,
        "picks": consensus_picks,
        "metadata": metadata,
        "created_at": official.created_at.isoformat() if official.created_at else None,
    }
