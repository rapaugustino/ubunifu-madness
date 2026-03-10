import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="min-h-screen max-w-4xl mx-auto px-4 sm:px-6 py-12">
      <h1 className="text-3xl font-bold mb-2">Terms &amp; Disclaimers</h1>
      <p className="text-muted text-sm mb-10">Last updated: March 2026</p>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Prediction Accuracy</h2>
        <p className="text-sm text-muted leading-relaxed">
          All predictions, win probabilities, and analytics on Ubunifu Madness are provided
          for informational and entertainment purposes only. Our model achieves a Brier score
          of 0.1413 on historical tournament data, but past accuracy does not guarantee future
          results. The NCAA tournament is inherently unpredictable — no model can guarantee
          outcomes. A 70% win probability means the underdog still wins 3 out of 10 times.
          Use these predictions as one input alongside your own knowledge, not as the sole
          basis for any decision.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Not for Gambling</h2>
        <p className="text-sm text-muted leading-relaxed">
          Ubunifu Madness is designed exclusively for bracket prediction analytics, education,
          and entertainment. This platform is not intended to facilitate, encourage, or support
          sports gambling or wagering of any kind. We do not provide odds, point spreads, or
          any betting-related information.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Data Sources &amp; Attribution</h2>
        <div className="text-sm text-muted leading-relaxed space-y-3">
          <p>
            Historical game data is sourced from the{" "}
            <a
              href="https://www.kaggle.com/competitions/march-machine-learning-mania-2026/overview"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              Kaggle March Machine Learning Mania 2026
            </a>{" "}
            competition dataset, used under the CC BY 4.0 license.
          </p>
          <p>
            Live scores, team records, rosters, and tournament bracket data are sourced from
            ESPN. Team logos and branding are property of their respective institutions.
          </p>
          <p>
            Massey ordinal rankings aggregate data from multiple independent ranking systems
            as compiled by Kenneth Massey.
          </p>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">No Affiliation</h2>
        <p className="text-sm text-muted leading-relaxed">
          Ubunifu Madness is not affiliated with, endorsed by, or sponsored by the NCAA,
          ESPN, any collegiate athletic conference, or any university. &quot;March
          Madness&quot; and &quot;Final Four&quot; are registered trademarks of the NCAA.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Use at Your Own Risk</h2>
        <p className="text-sm text-muted leading-relaxed">
          This platform is provided &quot;as is&quot; without warranty of any kind, express
          or implied, including but not limited to the warranties of accuracy, completeness,
          or fitness for a particular purpose. In no event shall Ubunifu Madness or its
          contributors be liable for any damages arising from the use of predictions or
          analytics provided on this platform.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Open Source</h2>
        <p className="text-sm text-muted leading-relaxed">
          Ubunifu Madness is an open-source project built for the Kaggle March Machine
          Learning Mania competition. Our methodology is fully transparent — see the{" "}
          <Link href="/about" className="text-accent hover:underline">
            How It Works
          </Link>{" "}
          page for a complete explanation of our models and data pipeline.
        </p>
      </section>

      <div className="border-t border-card-border pt-6 mt-10">
        <p className="text-xs text-muted">
          Questions about these terms?{" "}
          <Link href="/chat" className="text-accent hover:underline">
            Ask the Madness Agent
          </Link>.
        </p>
      </div>
    </div>
  );
}
