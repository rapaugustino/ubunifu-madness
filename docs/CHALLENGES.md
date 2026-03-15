# Technical Challenges & Solutions

A record of the key technical challenges encountered while building Ubunifu Madness, how we diagnosed them, and the solutions we implemented. Useful for interviews, blog posts, and future development.

---

## 1. Prediction Clustering (Isotonic Calibration Step Function)

**Problem:** After deploying the V3 model, predictions clustered at ~15 discrete values (e.g., 0.245, 0.580, 0.598). Very different matchups showed identical probabilities on the frontend.

**Root Cause:** Isotonic regression is a non-parametric calibration method that fits a **monotonic step function**. It groups raw model outputs into bins where the observed win rate is constant. With only ~900 out-of-fold predictions from LOSO cross-validation, the calibrator learned just 17 "steps" — each a flat plateau.

Any raw prediction falling within the same step (e.g., 0.226 through 0.311) got mapped to the exact same output (0.2451), destroying the continuous signal from the LR+LGB ensemble.

**Diagnosis:**
1. Verified the raw ensemble produced 50 unique values across 50 games — no clustering at the model level
2. Inspected `calibrator.X_thresholds_` and `calibrator.y_thresholds_` — found 34 thresholds forming 17 step pairs
3. Confirmed the calibrator's `predict()` method produces a piecewise-constant function

**Solution:** Replaced `calibrator.predict()` with **smooth calibration via linear interpolation** between step midpoints. Instead of snapping to the nearest step, we linearly interpolate between them:

```python
# Find midpoints of each step plateau
mid_x = [(step_start + step_end) / 2 for each step]
mid_y = [step_value for each step]

# Linear interpolation instead of step function
result = np.interp(raw_prediction, mid_x, mid_y)
```

**Result:** 15/50 unique values -> 50/50 unique values, while preserving the calibrator's overall shape.

**Key Insight:** This is a fundamental limitation of non-parametric calibration on small datasets. Platt scaling (logistic sigmoid) wouldn't have this problem but can't capture non-linear miscalibration. Our approach combines the flexibility of isotonic regression with the continuity of parametric methods.

**Data Science Takeaway:** When using isotonic calibration with <1000 samples, always check if the output is a coarse step function. If so, apply smoothing via interpolation or consider Platt scaling as an alternative.

---

## 2. Conference Tournament Overconfidence

**Problem:** The model's 60-70% confidence bin was badly miscalibrated — it predicted 65% but the actual win rate was only 43-53%. Overall prediction accuracy was 66% with confident accuracy at only 62.8%.

**Root Cause:** A **train/deploy domain gap**. The model was trained exclusively on NCAA tournament games (teams from different conferences meeting on neutral courts) but was being evaluated on conference tournament games during the daily prediction pipeline. Conference tournament games have fundamentally different dynamics:

1. **Familiarity:** Same-conference teams play each other 2-3 times per season. Coaches know each other's playbooks, tendencies, and key players.
2. **Rivalry intensity:** Conference tournament games often feature intense rivalries with higher variance outcomes.
3. **Auto-bid pressure:** For mid-major conferences, the tournament winner gets an automatic NCAA bid — motivation asymmetry.
4. **Home-court proximity:** Conference tournaments are often held in one team's home region.

These factors reduce predictability compared to NCAA tournament games where teams often haven't played each other that season.

**Diagnosis:**
1. Pulled all 159 locked predictions from the production API
2. Computed per-bin calibration: the 60-70% bin had 43-53% actual win rate
3. Cross-referenced with ESPN game data: 121/133 recent games were conference tournament games
4. Compared model confidence distributions between training data (NCAA tourney) and live data (conf tourney)

**V3 Solution:** Conference tournament compression — reduce prediction confidence 20% toward 0.5 for detected conference tournament games:

```python
prob = 0.5 + (prob - 0.5) * 0.80  # e.g., 0.70 -> 0.66
```

**V4 Approach:** Removed manual compression. Trained on all game types (163K games) with `is_conf_tourney` as a feature — model learns compression itself.

**V5 Refinement:** Empirical calibration on 270 live conference tournament games revealed gender-specific overconfidence. Women's predictions needed compression; men's were already well-calibrated. Added gender-specific post-calibration compression:

```python
if is_conf_tourney:
    gender = get_team_gender(team_a_id)
    factor = 0.90 if gender == "W" else 1.0  # women compress 10%, men no change
    if factor < 1.0:
        prob = 0.5 + (prob - 0.5) * factor
```

The `is_conf_tourney` model feature handles structural differences (familiarity, rivalry intensity); the women's compression handles residual overconfidence from higher volatility in women's conference tournaments.

**Key Insight:** Domain shift between training and deployment is one of the most common ML failure modes. Sometimes it takes multiple iterations: V3 used crude compression, V4 tried to learn it from data, V5 combines both — model features plus empirical post-hoc correction.

---

## 3. Stale Training Data (Pre-Modern Basketball Era)

**Problem:** The V2 model trained on 2003-2025 data (23 seasons) but basketball changed fundamentally after ~2012:

- **3-Point Revolution (2012+):** Steph Curry's impact transformed offensive strategy. Teams went from ~20 three-point attempts per game to 30+.
- **Transfer Portal (2018+):** Players can transfer freely, increasing roster turnover and reducing the value of "program continuity" features.
- **NIL (2021+):** Name, Image, Likeness deals redistributed talent, making traditional power program advantages less predictable.

The model learned patterns from 2003-2011 (dominant big men, program loyalty, mid-major Cinderellas being rare) that no longer apply.

**Diagnosis:**
1. Computed per-season Brier scores — no clear trend, but pre-2012 seasons contributed noise without improving modern predictions
2. Analyzed feature importance shifts: `seed_diff` was less dominant in modern era (more parity), while `efg_diff` and `tempo_diff` gained importance
3. Tested model variants with different training cutoffs

**Solution:** Restricted training to **2012+ only** (modern era). In V3, this reduced the training set from ~4,300 to ~1,705 tournament games. V4 then expanded to train on ALL game types (163K games) while keeping the 2012+ cutoff.

**Result:** CV Brier improved from 0.1607 (V2) to 0.1543 (V3) to **0.137 (V4)**.

**Key Insight:** More data isn't always better. When the data-generating process has changed (regime shift), older data introduces noise. The right amount of training data depends on how stable the underlying patterns are.

---

## 4. Empty Model Artifact Pipeline

**Problem:** The V2 system had an `ml_ensemble` prediction path in code but the `ModelArtifact` table was empty — no trained models were ever uploaded. Every prediction fell through to signal blending or static CSV lookups, meaning the sophisticated model architecture was never actually used.

**Root Cause:** The original development focused on the Kaggle submission pipeline (notebook -> CSV -> upload CSV to `predictions` table). The live prediction pipeline queried this static predictions table. The model artifact infrastructure was built but never connected — no script existed to export and upload trained models.

**Diagnosis:**
1. Queried `model_artifacts` table — 0 rows
2. Traced prediction flow: `predict_matchup()` always fell through `bundle = load_model_bundle(db)` -> `None` -> blended path
3. Checked git history: the `ml_ensemble` path was added anticipating artifact upload but the upload script was never written

**Solution:**
1. Added Part 7 to the V3 notebook: exports `lr_v3.joblib`, `lgb_v3.joblib`, `calibrator_v3.joblib`, and `model_metadata_v3.json`
2. Created `backend/scripts/upload_model_artifacts.py` to upload joblib artifacts to the DB
3. The live predictor now successfully loads and uses the V3 models

**Key Insight:** End-to-end testing matters. The prediction pipeline had a working model, a working feature builder, and a working artifact loader — but they were never connected. Integration testing would have caught this immediately.

---

## 5. "model_v2" Source Mystery

**Problem:** 86/108 locked predictions in the production database had source `"model_v2"`, but the current codebase didn't have any code that produced this source label. Only 22 used the current `"blended"` source.

**Root Cause:** Traced through git history (commits `ea2e4d5` -> `93a4361` -> `a8f92e5`) to find that an earlier version of `espn.py` directly queried the `Prediction` table (static CSV predictions) and labeled them as `"model_v2"`. This was later refactored into the blended prediction system, but the old predictions remained locked in the database.

**Diagnosis:**
1. Queried unique `prediction_source` values: `{"model_v2": 86, "blended": 22}`
2. Searched current codebase for `"model_v2"` — not found
3. Used `git log --all -S "model_v2"` to find the commit that introduced and removed it
4. Confirmed: old code directly looked up static predictions, new code uses the blending pipeline

**Key Insight:** Locked predictions are immutable by design (for honest performance tracking), which means old source labels persist even after code refactors. This is a feature, not a bug — but it can be confusing when auditing the system.

---

## 6. ESPN API Null Fields

**Problem:** Production 500 error on `GET /api/scores?date=20260308&gender=W`:

```
AttributeError: 'NoneType' object has no attribute 'lower'
```

**Root Cause:** The ESPN API returns `headline: null` for some games (particularly older or less prominent games). The code used `game.get("headline", "")` which returns `None` if the key exists with a null value (Python's `dict.get()` only uses the default if the key is missing, not if the value is None).

```python
# Bug: headline = None when ESPN returns {"headline": null}
headline = game.get("headline", "")  # Returns None, not ""
"conference" in headline.lower()  # NoneType has no attribute 'lower'
```

**Solution:** Use `or` to coalesce None to empty string:

```python
headline = game.get("headline") or ""
```

**Key Insight:** When working with external APIs, always handle null values explicitly. Python's `dict.get(key, default)` only applies the default when the key is absent — if the key exists with value `None`, you get `None`. The `or ""` pattern is more defensive.

---

## 7. Tossup Threshold Calibration

**Problem:** With a 52% tossup threshold, only 7/159 games were classified as tossups. The model was being scored on games it had essentially no opinion about, dragging down apparent accuracy.

**Root Cause:** A 52% threshold is too aggressive — it only excludes games within 2% of a coin flip. Many games in the 52-55% range are genuinely unpredictable, and including them in accuracy metrics creates misleading results (the model gets "credit" or "blame" for what are essentially random outcomes).

**Solution:** Raised tossup threshold to **55%** across the entire codebase (7 files: predictor.py, performance.py, chat.py, scores/page.tsx, scores/[gameId]/page.tsx, performance/page.tsx, about/page.tsx).

**Result:** Tossups increased from 7 to 16-18 per period. Confident accuracy became a more meaningful metric — it now measures the model's performance on games where it actually has a prediction.

**Key Insight:** Evaluation metric design is as important as model design. A model that says "I don't know" on genuinely uncertain games is more useful than one that forces a prediction and gets it wrong half the time. The tossup threshold is essentially a confidence interval for the model's predictions.

---

## 8. Head-to-Head Label Leakage (V5)

**Problem:** When adding season head-to-head record as a training feature (`h2h_win_pct_diff`, `h2h_games`), validation Brier score dropped to 0.042 and accuracy jumped to 92.4% — obviously too good to be real.

**Root Cause:** Regular season series almost perfectly predicts conference tournament rematches. If Team A went 2-0 against Team B in the regular season, they win the conference tournament rematch ~99% of the time. The h2h feature had the largest LR coefficient (4.53) by far, and conference tournament accuracy was 99.4%.

**Diagnosis:**
1. Validation metrics were suspiciously perfect — Brier 0.042 is better than Vegas lines
2. Inspected LR coefficients: `h2h_win_pct_diff` had coefficient 4.53, next largest was ~1.5
3. Conference tournament accuracy was 99.4% (vs ~75% baseline)
4. Attempted fix: only count h2h games before current game's `day_num`. Still leaked — the regular season record is inherently predictive of the rematch outcome

**Solution:** Removed h2h from training entirely. Kept `_compute_h2h_record()` in the live predictor for explanation text only — at prediction time, the h2h record is genuinely historical context (not a model input).

**Key Insight:** A feature that perfectly correlates with the label isn't a good feature — it's a leak. Head-to-head record captures the same information as the outcome label for rematches. This is a textbook example of leakage through transitive correlation: both h2h record and the label reflect the same underlying team quality difference within a conference.

**Data Science Takeaway:** When a new feature produces implausibly good validation metrics, investigate the feature's relationship with the label before celebrating. Features computed from the same games used for labels are prime leakage candidates.

---

## 9. Misleading Matchup Explanations (V5)

**Problem:** The `explain_matchup()` function reported "stronger record" for a team with a 16-17 record vs an opponent with 19-13. More generally, the explanations often contradicted reality.

**Root Cause:** The old explanation system used a hardcoded 7-signal blend (Elo, SOS, record, momentum, conference strength, etc.) that was completely disconnected from the actual V4/V5 ML ensemble prediction. The blend weights determined which factors to highlight, but these weights had nothing to do with the model's actual feature importances. A factor could be highlighted as the "reason" even when the favored team was actually worse on that dimension.

**Diagnosis:**
1. User screenshot showed Missouri State (16-17) described as having a "stronger record" than Louisiana Tech (19-13)
2. Traced through `explain_matchup()` — it sorted factors by `abs(signal - 0.5) * weight` which only measured magnitude, not direction relative to the favored team
3. Confirmed the 7-signal weights were static constants unrelated to model feature importances

**Solution:** Complete rewrite of `explain_matchup()`:
1. Uses the actual model feature differences (same features the ML ensemble uses)
2. Only reports a factor when the favored team genuinely has the edge (`favored_has_edge = (favored_is_a and diff > 0) or (not favored_is_a and diff < 0)`)
3. Falls back to "ML model edge" when no single factor clearly explains the prediction
4. Each factor has a minimum threshold to avoid reporting trivial differences

**Key Insight:** Explanations must be grounded in the actual model, not a parallel system. When explanations and predictions use different logic, they will inevitably contradict each other.

---

## Architecture Decisions Summary

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| Train on 2012+ only | Modern basketball era | Full 2003+ (more data but noisy) |
| LR + LGB ensemble (not XGBoost) | XGB added no value; LGB captures nonlinearities LR misses | Single model (less robust) |
| Isotonic + smooth interpolation | Preserves calibration accuracy with continuous output | Platt scaling (can't capture non-linear biases) |
| V4: Train on all game types | 163K games vs 4.3K; game-type as feature | V3's tournament-only approach with manual compression |
| V5: Recency-weighted training | Modern-era patterns matter more; 5-season half-life | Equal weighting (ignores era shifts) |
| V5: Home court adjustment in AdjEM | Neutralizes venue advantage for fairer rankings | Unadjusted (inflates home-heavy team stats) |
| V5: Feature-diff explanations | Grounded in actual model; prevents contradictions | Disconnected 7-signal blend (V3/V4) |
| H2h rejected as feature | Label leakage (Val Brier 0.042) | Include as feature (leaks) |
| 55% tossup threshold | Honest about model uncertainty | 52% (too few tossups) or 60% (too many excluded) |
| Locked predictions (never retroactive) | Honest performance tracking | Update predictions mid-game (dishonest) |
| Model artifacts in DB (not files) | Works with Railway/Docker deployment | Local file system (doesn't scale) |
| Separate M/W Elo pools | Women's Elo runs ~245pts higher | Combined pool (distorts ratings) |
