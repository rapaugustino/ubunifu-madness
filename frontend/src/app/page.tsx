import Link from "next/link";
import {
  Trophy,
  BarChart3,
  GitCompareArrows,
  MessageSquare,
  Brain,
  Target,
  TrendingUp,
  Radio,
} from "lucide-react";

const features = [
  {
    icon: Radio,
    title: "Live Scores & Predictions",
    description:
      "Real-time ESPN scores with blended win probabilities locked before tipoff. Track model accuracy as games finish.",
    href: "/scores",
  },
  {
    icon: Trophy,
    title: "Interactive Bracket",
    description:
      "Build your bracket with AI win probabilities for every matchup. Click to advance teams or let the model auto-fill.",
    href: "/bracket",
  },
  {
    icon: BarChart3,
    title: "Power Rankings",
    description:
      "Elo-based power rankings for 700+ teams with conference strength, strength of schedule, and daily ESPN updates.",
    href: "/dashboard",
  },
  {
    icon: GitCompareArrows,
    title: "Head-to-Head Compare",
    description:
      "Compare any two teams side-by-side with stat breakdowns, conference context, recent meetings, and AI analysis.",
    href: "/compare",
  },
  {
    icon: MessageSquare,
    title: "Madness Agent",
    description:
      "AI bracket advisor with 6 tools — look up any team, get blended predictions, check live scores, find upset picks.",
    href: "/chat",
  },
  {
    icon: Target,
    title: "Performance Tracking",
    description:
      "Full transparency: cumulative accuracy charts, daily breakdowns, calibration curves, and a game-by-game log.",
    href: "/performance",
  },
];

const stats = [
  { label: "Prediction Signals", value: "6", subtext: "Elo, model, momentum, conf, SOS, efficiency" },
  { label: "Brier Score", value: "0.1413", subtext: "43.5% better than seed baseline" },
  { label: "Training Games", value: "4,302", subtext: "Men's + Women's tournaments" },
  { label: "Model Features", value: "31", subtext: "Elo, conf, box scores, Massey" },
];

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-accent/5 via-transparent to-transparent" />
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-accent/5 blur-[120px]" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 pt-24 pb-20">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
              Ubunifu{" "}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent to-amber-400">
                Madness
              </span>
            </h1>

            <p className="text-xl text-muted mb-8 max-w-2xl mx-auto">
              Six prediction signals blended in real time — Elo, ML model, momentum,
              conference strength, schedule difficulty, and efficiency. Predictions
              locked before tipoff, accuracy tracked transparently. An AI agent
              that breaks down any matchup on demand.
            </p>

            <div className="flex items-center justify-center gap-4">
              <Link
                href="/bracket"
                className="px-6 py-3 bg-accent hover:bg-accent-secondary text-white font-semibold rounded-lg transition-colors glow-accent"
              >
                Build Your Bracket
              </Link>
              <Link
                href="/dashboard"
                className="px-6 py-3 bg-white/5 hover:bg-white/10 border border-card-border text-foreground font-semibold rounded-lg transition-colors"
              >
                View Rankings
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-y border-card-border bg-card/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-3xl font-bold text-accent">
                  {stat.value}
                </div>
                <div className="text-sm font-medium text-foreground mt-1">
                  {stat.label}
                </div>
                <div className="text-xs text-muted mt-0.5">{stat.subtext}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-20">
        <h2 className="text-3xl font-bold text-center mb-4">How It Works</h2>
        <p className="text-muted text-center mb-12 max-w-xl mx-auto">
          ML predicts. AI explains. You decide.
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          <div className="p-6 rounded-xl bg-card border border-card-border">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4">
              <Brain className="text-blue-400" size={20} />
            </div>
            <h3 className="font-semibold text-lg mb-2">1. Six Signals Blend</h3>
            <p className="text-sm text-muted">
              Elo ratings, a 31-feature ML ensemble, momentum, conference strength,
              SOS-adjusted records, and efficiency combine into a single win
              probability — updated daily from ESPN.
            </p>
          </div>

          <div className="p-6 rounded-xl bg-card border border-card-border">
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center mb-4">
              <Target className="text-accent" size={20} />
            </div>
            <h3 className="font-semibold text-lg mb-2">2. AI Explains Why</h3>
            <p className="text-sm text-muted">
              Our AI analyzes every matchup — conference context, momentum, pace
              matchups, historical upset rates. Not vibes, data-driven basketball
              analysis.
            </p>
          </div>

          <div className="p-6 rounded-xl bg-card border border-card-border">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center mb-4">
              <TrendingUp className="text-green-400" size={20} />
            </div>
            <h3 className="font-semibold text-lg mb-2">3. Build Your Bracket</h3>
            <p className="text-sm text-muted">
              Use AI picks, your gut, or a mix. The bracket chat agent helps you
              make informed picks — ask it anything about any matchup.
            </p>
          </div>
        </div>
      </section>

      {/* Features grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-20">
        <h2 className="text-3xl font-bold text-center mb-12">Features</h2>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Link
                key={feature.href}
                href={feature.href}
                className="group p-6 rounded-xl bg-card border border-card-border hover:border-accent/30 transition-colors"
              >
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 group-hover:bg-accent/20 transition-colors">
                    <Icon className="text-accent" size={20} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg mb-1 group-hover:text-accent transition-colors">
                      {feature.title}
                    </h3>
                    <p className="text-sm text-muted">{feature.description}</p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

    </div>
  );
}
