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
            was at home or away. We apply a 101.9-point home court advantage and use a K-factor
            of 21.8 — tuned via Optuna optimization to balance responsiveness with stability.
          </p>
          <p>
            Between seasons, every team&apos;s rating regresses 11% toward 1500. This prevents
            ratings from inflating over time and accounts for roster turnover. Ratings update
            daily from ESPN game results using the exact same formula used to process 40 years
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

      {/* Blended Prediction System */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Blended 6-Signal Prediction System</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Live predictions combine six independent signals into a single win probability.
            This blended approach outperforms any single signal alone, because each captures
            a different dimension of team quality:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Static Model (30%):</strong> LR + LightGBM ensemble trained on 4,302 tournament games (1985–2025) with 31 features. Brier score 0.1413.</li>
            <li><strong>Elo Ratings (30%):</strong> Real-time ratings updated daily from ESPN results. Captures current team strength.</li>
            <li><strong>Momentum (15%):</strong> Last 10 games win percentage and margin of victory. Catches hot/cold streaks.</li>
            <li><strong>Conference Strength (10%):</strong> 70% conference avg Elo + 30% non-conference win rate. Accounts for quality of competition.</li>
            <li><strong>SOS-Adjusted Record (10%):</strong> Win percentage adjusted for strength of schedule — a 25-5 record against tough opponents is more impressive than 25-5 against weak ones.</li>
            <li><strong>Efficiency (5%):</strong> Offensive vs defensive points per 100 possessions. Measures scoring quality independent of pace.</li>
          </ul>
          <p>
            When the static model isn&apos;t available for a team (e.g., mid-majors with limited data),
            the remaining five live signals are re-weighted automatically. This ensures every
            D1 team gets a data-driven prediction, not just teams with full Kaggle coverage.
          </p>
        </div>
      </section>

      {/* Tossup Handling */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Tossup Handling</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            When the blended model&apos;s confidence is below 52% — meaning neither team is
            favored above 52% — the game is labeled a <strong>TOSSUP</strong>. This is the
            model being honest: a 51% prediction is barely better than a coin flip, and
            pretending to have a strong pick would be misleading.
          </p>
          <p>
            Tossup games appear in yellow on the Scores page instead of showing a directional pick.
            They&apos;re excluded from accuracy metrics on the Performance page, so the model&apos;s
            reported accuracy reflects only games where it had genuine conviction. The Performance
            page shows how many games were tossups separately.
          </p>
        </div>
      </section>

      {/* ML Model */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Static Model Details</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            The static model (one of six blended signals) is an ensemble of Logistic Regression
            and LightGBM. Each is trained on 4,302 men&apos;s and women&apos;s NCAA tournament
            games from 1985–2025, using 31 features organized into seven categories:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Elo:</strong> Current rating, rating difference, expected win probability</li>
            <li><strong>Conference:</strong> Average Elo, non-conference win rate, tournament historical win rate</li>
            <li><strong>Four Factors:</strong> eFG%, turnover rate, offensive rebound rate, free throw rate (and opponent versions)</li>
            <li><strong>Efficiency:</strong> Offensive and defensive points per 100 possessions, tempo</li>
            <li><strong>Schedule:</strong> Strength of schedule (average opponent Elo)</li>
            <li><strong>Massey Ordinals:</strong> Composite ranking from 15 independent ranking systems</li>
            <li><strong>Momentum:</strong> Last 10 games win percentage and margin of victory</li>
            <li><strong>Experience:</strong> Coach tenure, seed (when available)</li>
          </ul>
          <p>
            The ensemble weights are 76% LR + 24% LGB, with isotonic calibration applied.
            LR provides stable, well-calibrated probabilities while LGB captures non-linear
            interactions. Together they achieve a Brier score of 0.1413, which is 43.5% better
            than always picking the higher seed.
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

      {/* Coverage */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Men&apos;s and Women&apos;s Coverage</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Every feature works for both men&apos;s and women&apos;s basketball. Rankings,
            conference strength, predictions, live scores, and the bracket builder all support
            a gender toggle. The model is trained on tournament games from both tournaments.
            Elo ratings are computed independently per gender using the same methodology.
          </p>
          <p>
            <strong>A note on Elo scales:</strong> Men&apos;s and women&apos;s Elo ratings
            operate as independent pools. You may notice that top women&apos;s teams have
            higher raw Elo numbers than top men&apos;s teams. This reflects the different
            competitive dynamics in women&apos;s basketball (historically more dominant top
            programs like UConn, South Carolina, Stanford). The raw numbers should only be
            compared within the same gender — a women&apos;s Elo of 2300 and a men&apos;s
            Elo of 2100 both indicate elite teams at the top of their respective pools.
            Prediction quality is calibrated independently within each pool.
          </p>
        </div>
      </section>

      {/* Limitations */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-3">Known Limitations</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>No player-level data — our model operates at the team level</li>
            <li>No injury adjustments — a key player being out is not reflected in predictions</li>
            <li>Four Factors stats are computed from Kaggle box score data (updated seasonally, not after each game)</li>
            <li>Women&apos;s Massey ordinals are not available from Kaggle, reducing feature coverage for women&apos;s predictions</li>
            <li>Early season ratings carry more uncertainty — Elo stabilizes after ~15 games</li>
            <li>Men&apos;s and women&apos;s Elo scales differ in magnitude — compare within gender only</li>
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
