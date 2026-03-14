import Link from "next/link";

export default function AboutPage() {
  return (
    <div className="min-h-screen max-w-4xl mx-auto px-4 sm:px-6 py-12">
      <h1 className="text-3xl font-bold mb-2">How Ubunifu Madness Works</h1>
      <p className="text-muted mb-10">
        A transparent look at the data, models, and methods behind every prediction.
      </p>

      {/* Elo Ratings */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Elo Ratings</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Every team starts at 1500. After each game, the winner gains points and the loser
            drops by the same amount. How many points depends on three things: how likely the
            win was (upsets move the needle more), the margin of victory, and whether the game
            was at home or away. We apply a 90.9-point home court advantage and use a K-factor
            of 19.6 — tuned via Optuna optimization to balance responsiveness with stability.
          </p>
          <p>
            Between seasons, every team&apos;s rating regresses 5% toward 1500. This prevents
            ratings from inflating over time and accounts for roster turnover. Ratings update
            daily from ESPN game results using the exact same formula used to process 41 years
            of historical games.
          </p>
          <p>
            An average D1 team sits around 1500. Top 25 teams are typically 1800+. The #1 team
            is usually around 2100. The system has been validated against 4,302 tournament games
            from 1985 to present.
          </p>
        </div>
      </section>

      {/* Strength of Schedule */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Strength of Schedule</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Strength of schedule (SOS) is the average Elo rating of all opponents a team has
            faced during the season. A team with a high SOS has been tested against tough
            competition, while a low SOS suggests a softer schedule. This matters because
            a 25-5 record against a weak schedule is very different from 25-5 against elite
            opponents.
          </p>
          <p>
            SOS is available on the Compare page and through the Madness Agent. It helps
            contextualize win-loss records and Elo ratings — a team with a high Elo and high
            SOS has proven themselves against quality opponents.
          </p>
        </div>
      </section>

      {/* Conference Strength */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Conference Strength</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Conference rankings use four metrics. <strong>Average Elo</strong> is the mean
            rating across all teams in the conference — it tells you overall depth.{" "}
            <strong>Non-Conference Win Rate</strong> counts how a conference performs against
            outside opponents in regular season games, removing the noise of intra-conference
            cannibalization. <strong>Top 5 Elo</strong> measures elite talent at the top.{" "}
            <strong>Parity</strong> is the inverse of Elo standard deviation — higher parity
            means teams are more evenly matched with no weak links.
          </p>
          <p>
            These metrics refresh automatically as new game results come in. Non-conference
            win rate is the most telling — it directly measures how a conference performs
            against the rest of D1.
          </p>
        </div>
      </section>

      {/* Prediction System */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">ML Ensemble Prediction System</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Predictions are powered by a V5 ML ensemble model that builds features from live
            database state — Elo, efficiency, records, rankings — and outputs a calibrated win
            probability. The model is trained on 163,000+ games (regular season, conference
            tournaments, and NCAA tournaments from 2012–2025) using 40 features.
          </p>
          <p>
            The model uses <strong>game-type context</strong> as a feature — it knows whether
            a game is regular season, conference tournament, or NCAA tournament and adjusts
            predictions accordingly. This eliminates the need for manual probability compression.
          </p>
          <p>
            If the ML model is unavailable (e.g., during first deployment), the system falls
            back to a live blend of Elo ratings and SOS-adjusted win records. This ensures every
            D1 team gets a prediction even without the full ML pipeline.
          </p>
        </div>
      </section>

      {/* Tossup Handling */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Tossup Handling</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            When the blended model&apos;s confidence is below 55% — meaning neither team is
            favored above 55% — the game is labeled a <strong>TOSSUP</strong>. This is the
            model being honest: a 54% prediction is barely better than a coin flip, and
            pretending to have a strong pick would be misleading.
          </p>
          <p>
            Tossup games still receive a prediction — the model picks whichever side has the
            higher probability — and they count toward overall accuracy. On the Scores page,
            tossup games show the model&apos;s result (correct or missed) with a yellow
            &quot;TOSSUP&quot; label so you can see which low-confidence picks landed. The
            Performance page includes tossups in its accuracy totals.
          </p>
        </div>
      </section>

      {/* ML Model */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">V5 Model Details</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            The V5 model is an ensemble of Logistic Regression (37.8%) and LightGBM (62.2%),
            trained on 163,000+ men&apos;s and women&apos;s games from 2012–2025 across all game
            types with recency-weighted training (5-season half-life — recent games matter ~7x more).
            It uses 40 features organized into nine categories:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Elo:</strong> Current rating, rating difference, expected win probability</li>
            <li><strong>Conference:</strong> Average Elo, non-conference win rate, tournament historical win rate</li>
            <li><strong>Four Factors:</strong> eFG%, turnover rate, offensive rebound rate, free throw rate (and opponent versions)</li>
            <li><strong>Efficiency:</strong> Offensive and defensive points per 100 possessions, tempo, adjusted efficiency margin</li>
            <li><strong>Schedule:</strong> Strength of schedule (average opponent Elo)</li>
            <li><strong>Rankings:</strong> KenPom rank, NET rank, consensus rank from Massey Ordinals</li>
            <li><strong>Momentum:</strong> Last 10 games win percentage and margin of victory</li>
            <li><strong>Game Context:</strong> Is conference tournament, is NCAA tournament, is neutral site, rest days difference</li>
            <li><strong>Quality:</strong> Win percentage vs top-50 Elo teams, Barthag, coach tenure, raw win percentages</li>
          </ul>
          <p>
            Smooth isotonic calibration ensures well-distributed probabilities.
            LR provides stable baselines while LGB captures non-linear interactions.
            Validation Brier score: 0.137, accuracy: 80.0% on 2023–2026 holdout.
          </p>
        </div>
      </section>

      {/* Live Data */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Live Data Pipeline</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Historical data comes from Kaggle&apos;s March Machine Learning Mania dataset,
            covering every D1 game from 1985 to present. This seeds the database with initial
            Elo ratings, conference strength, and team stats.
          </p>
          <p>
            Once the database is populated, the app runs independently of the CSV files. A
            daily cron job fetches completed game scores from ESPN, computes Elo updates using our
            own formula, updates team records, refreshes conference strength metrics, recomputes
            player stats, and recalculates strength of schedule for every team. ESPN
            provides the raw scores — every analytical metric is computed by us.
          </p>
          <p>
            Live scores on the Scores page come directly from ESPN&apos;s scoreboard API,
            enriched with our Elo ratings and model win probabilities. Crucially, every
            prediction is <strong>locked before tipoff</strong> — once a game starts, the
            pre-game prediction is frozen and never updated retroactively. This ensures honest
            performance tracking. After games finish, the Scores page shows whether the locked
            prediction was correct, along with a daily accuracy summary.
          </p>
          <p>
            The <strong>Performance page</strong> aggregates all locked predictions into
            cumulative accuracy charts, daily breakdowns, calibration curves, and a game-by-game
            log. This gives you full transparency into how well the model actually performs over
            time — no cherry-picking, no retroactive changes.
          </p>
        </div>
      </section>

      {/* AI Agent */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Madness Agent</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            The chat agent uses Claude (Anthropic&apos;s AI) with tool access to query our
            entire database in real time. It doesn&apos;t just get a static text dump — it
            actively looks up data to answer your questions. The agent has six tools:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Team Lookup:</strong> Search any D1 team by name — get Elo, record, conference, stats, momentum, coach info, and strength of schedule</li>
            <li><strong>Matchup Prediction:</strong> Get head-to-head win probabilities with stat comparisons for any two teams</li>
            <li><strong>Conference Analysis:</strong> Conference strength metrics, top teams in each conference</li>
            <li><strong>Rankings:</strong> Top teams by Elo, filterable by conference</li>
            <li><strong>Live Scores:</strong> Today&apos;s games and results from ESPN</li>
            <li><strong>Upset Finder:</strong> Identify potential upsets where underdogs have meaningful win probability</li>
          </ul>
          <p>
            When you ask &quot;Who should I pick in a Duke vs. UNC matchup?&quot;, the agent
            calls the matchup prediction tool, pulls real win probabilities and stats, then
            explains its reasoning with specific numbers. It doesn&apos;t guess — every claim
            is grounded in data.
          </p>
        </div>
      </section>

      {/* Advanced Analytics */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Advanced Analytics</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Beyond Elo, the Power Rankings surface advanced metrics computed from every
            game&apos;s box score data. Click any team row to see its full analytics profile.
            All metrics update daily via our ESPN data pipeline.
          </p>
          <ul className="list-disc list-inside space-y-2 ml-2">
            <li>
              <strong>Adjusted Efficiency (AdjOE / AdjDE / AdjEM):</strong> Points per 100
              possessions, iteratively adjusted for opponent strength. A team scoring 80 points
              against an elite defense is more impressive than 80 against a weak one. AdjEM (net
              margin) is the single best predictor of team quality. Inspired by the methodology
              popularized by Ken Pomeroy.
            </li>
            <li>
              <strong>Barthag:</strong> Win probability against an average D1 team on a neutral
              court, derived from adjusted efficiency using a Pythagorean formula
              (AdjOE<sup>11.5</sup> / (AdjOE<sup>11.5</sup> + AdjDE<sup>11.5</sup>)). More
              intuitive than raw Elo — 0.95 means a team would beat 95% of D1 opponents. This
              concept was introduced by T-Rank.
            </li>
            <li>
              <strong>Luck:</strong> Actual win percentage minus Pythagorean expected win
              percentage (based on total points scored vs. allowed). Positive luck means a team
              is winning more close games than expected — a signal that performance may regress.
              Our Pythagorean formula uses an exponent of 9, tuned for college basketball.
            </li>
            <li>
              <strong>Floor / Ceiling:</strong> The 10th and 90th percentile of a team&apos;s
              game-by-game net efficiency. This reveals the range of outcomes — a team with a high
              ceiling but low floor is a classic March Madness dark horse. This metric is unique
              to Ubunifu Madness.
            </li>
            <li>
              <strong>Upset Vulnerability:</strong> A composite score (0–100) combining margin
              volatility, luck, three-point reliance, and free throw shooting. Higher scores
              indicate teams more prone to losing games they &quot;should&quot; win. This
              original metric is exclusive to our platform.
            </li>
            <li>
              <strong>True Shooting %:</strong> Overall scoring efficiency capturing 2-point
              field goals, 3-pointers, and free throws in a single number:
              PTS / (2 × (FGA + 0.44 × FTA)). More complete than eFG% alone.
            </li>
            <li>
              <strong>Additional metrics:</strong> 3-point attempt rate (offensive style),
              assist-to-turnover ratio (ball movement quality), defensive rebound % (second-chance
              denial), steal % (perimeter pressure), block % (rim protection), close-game record
              (clutch performance), and margin consistency (scoring variance).
            </li>
          </ul>
        </div>
      </section>

      {/* Coverage */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Equal Coverage: Men&apos;s and Women&apos;s NCAA</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Ubunifu Madness provides full-depth analytics for both men&apos;s and women&apos;s
            basketball — same advanced metrics, same prediction model, same UI treatment. Most
            bracket tools treat women&apos;s basketball as an afterthought or ignore it entirely.
            We believe the women&apos;s tournament deserves the same analytical depth.
          </p>
          <p>
            Every feature works across both tournaments: advanced power rankings, opponent-adjusted
            efficiency, live scores, bracket builder, head-to-head comparisons, the AI agent, and
            player stats. A persistent gender toggle in the navigation bar lets you switch seamlessly.
            Your preference is remembered across pages and sessions.
          </p>
          <p>
            <strong>A note on Elo scales:</strong> Men&apos;s and women&apos;s Elo ratings
            operate as independent pools. Top women&apos;s teams may have higher raw Elo numbers
            than top men&apos;s teams — this reflects different competitive dynamics (historically
            more dominant programs like UConn and South Carolina in women&apos;s basketball). The
            raw numbers should only be compared within the same gender. Adjusted efficiency and all
            other analytics are computed independently per gender.
          </p>
        </div>
      </section>

      {/* Limitations */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Known Limitations</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>No injury adjustments — a key player being out is not reflected in predictions</li>
            <li>Predictions operate at team level — individual player matchups are not modeled</li>
            <li>Women&apos;s Massey ordinals are not available from Kaggle, reducing feature coverage for women&apos;s static model</li>
            <li>Early season ratings carry more uncertainty — Elo and adjusted efficiency stabilize after ~15 games</li>
            <li>Men&apos;s and women&apos;s Elo scales differ in magnitude — compare within gender only</li>
            <li>Adjusted efficiency assumes all possessions are equally valuable (no late-game situation modeling)</li>
          </ul>
        </div>
      </section>

      <div className="border-t border-card-border pt-6 mt-10">
        <p className="text-xs text-muted">
          Built by{" "}
          <a
            href="https://linkedin.com/in/rapaugustino"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            Richard Pallangyo
          </a>{" "}
          for the Kaggle March ML Mania 2026 competition. Questions about
          methodology?{" "}
          <Link href="/chat" className="text-accent hover:underline">
            The Madness Agent can explain
          </Link>
          . See also:{" "}
          <Link href="/terms" className="text-accent hover:underline">
            Terms &amp; Disclaimers
          </Link>.
        </p>
      </div>
    </div>
  );
}
