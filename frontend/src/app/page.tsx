"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Trophy,
  BarChart3,
  GitCompareArrows,
  MessageSquare,
  Brain,
  Target,
  TrendingUp,
  Radio,
  Award,
  Database,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const features = [
  {
    icon: Radio,
    title: "Live Scores & Predictions",
    description:
      "Real-time ESPN scores with model win probabilities locked before tipoff. Track accuracy as games finish.",
    href: "/scores",
  },
  {
    icon: Trophy,
    title: "Interactive Bracket",
    description:
      "Build your bracket with model win probabilities for every matchup. Click to advance teams or let the model auto-fill.",
    href: "/bracket",
  },
  {
    icon: BarChart3,
    title: "Power Rankings",
    description:
      "Composite power rankings for 700+ teams blending Elo, efficiency, win rate, SOS, momentum, and Barthag — updated daily from ESPN.",
    href: "/dashboard",
  },
  {
    icon: GitCompareArrows,
    title: "Head-to-Head Compare",
    description:
      "Compare any two teams side-by-side — Elo, efficiency, style matchup analysis, conference context, and recent meetings.",
    href: "/compare",
  },
  {
    icon: MessageSquare,
    title: "Madness Agent",
    description:
      "An AI assistant with 6 tools — powered by our prediction model. Look up teams, get matchup breakdowns, find upset picks.",
    href: "/chat",
  },
  {
    icon: Award,
    title: "Player Leaderboard",
    description:
      "Top performers across men's and women's NCAA — points, rebounds, assists, shooting splits, and player importance.",
    href: "/players",
  },
  {
    icon: Target,
    title: "Performance Tracking",
    description:
      "Full transparency: cumulative accuracy, daily breakdowns, calibration curves, and a game-by-game prediction log.",
    href: "/performance",
  },
];

interface AccuracyData {
  men: { total: number; correct: number; accuracy: number | null };
  women: { total: number; correct: number; accuracy: number | null };
  overall: { total: number; correct: number; accuracy: number | null };
}

export default function Home() {
  const [accuracy, setAccuracy] = useState<AccuracyData | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/performance/homepage-stats`)
      .then((r) => r.json())
      .then(setAccuracy)
      .catch(() => {});
  }, []);

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
              A machine learning system that predicts NCAA basketball outcomes
              — men&apos;s and women&apos;s. A calibrated LR+LightGBM ensemble
              trained on 4,300+ tournament games, combined with Elo ratings and
              win-loss records via backtest-optimized weights. Composite power
              rankings blend six metrics. Predictions locked before tipoff,
              accuracy tracked transparently.
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

      {/* Live accuracy + model stats */}
      <section className="border-y border-card-border bg-card/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-6">
            {/* Live accuracy */}
            <div className="text-center">
              <div className="text-3xl font-bold text-accent">
                {accuracy?.overall.accuracy
                  ? `${(accuracy.overall.accuracy * 100).toFixed(1)}%`
                  : "—"}
              </div>
              <div className="text-sm font-medium text-foreground mt-1">Overall Accuracy</div>
              <div className="text-xs text-muted mt-0.5">
                {accuracy ? `${accuracy.overall.correct}/${accuracy.overall.total} games` : "Loading..."}
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-400">
                {accuracy?.men.accuracy
                  ? `${(accuracy.men.accuracy * 100).toFixed(1)}%`
                  : "—"}
              </div>
              <div className="text-sm font-medium text-foreground mt-1">Men&apos;s</div>
              <div className="text-xs text-muted mt-0.5">
                {accuracy?.men ? `${accuracy.men.correct}/${accuracy.men.total}` : "—"}
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-pink-400">
                {accuracy?.women.accuracy
                  ? `${(accuracy.women.accuracy * 100).toFixed(1)}%`
                  : "—"}
              </div>
              <div className="text-sm font-medium text-foreground mt-1">Women&apos;s</div>
              <div className="text-xs text-muted mt-0.5">
                {accuracy?.women ? `${accuracy.women.correct}/${accuracy.women.total}` : "—"}
              </div>
            </div>

            {/* Divider on desktop */}
            <div className="hidden lg:flex items-center justify-center">
              <div className="h-12 w-px bg-card-border" />
            </div>

            {/* Model stats */}
            <div className="text-center">
              <div className="text-3xl font-bold text-foreground">6</div>
              <div className="text-sm font-medium text-foreground mt-1">Ranking Signals</div>
              <div className="text-xs text-muted mt-0.5">Power rating blend</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-foreground">28</div>
              <div className="text-sm font-medium text-foreground mt-1">Model Features</div>
              <div className="text-xs text-muted mt-0.5">LR + LightGBM ensemble</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-foreground">0.154</div>
              <div className="text-sm font-medium text-foreground mt-1">CV Brier Score</div>
              <div className="text-xs text-muted mt-0.5">2012–2025 test set</div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-20">
        <h2 className="text-3xl font-bold text-center mb-4">How It Works</h2>
        <p className="text-muted text-center mb-12 max-w-xl mx-auto">
          Data in. Predictions out. Full transparency.
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          <div className="p-6 rounded-xl bg-card border border-card-border">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4">
              <Database className="text-blue-400" size={20} />
            </div>
            <h3 className="font-semibold text-lg mb-2">1. Daily Data Pipeline</h3>
            <p className="text-sm text-muted">
              ESPN game results flow in daily. Elo ratings update, advanced stats
              recompute, records reconcile. Every prediction uses the latest state.
            </p>
          </div>

          <div className="p-6 rounded-xl bg-card border border-card-border">
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center mb-4">
              <Brain className="text-accent" size={20} />
            </div>
            <h3 className="font-semibold text-lg mb-2">2. Backtest-Optimized Predictions</h3>
            <p className="text-sm text-muted">
              A calibrated LR+LightGBM ensemble (28 features, 4,300+ games),
              blended with Elo ratings and win-loss records using weights
              optimized on 255 conference tournament games. Six metrics power
              composite rankings.
            </p>
          </div>

          <div className="p-6 rounded-xl bg-card border border-card-border">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center mb-4">
              <TrendingUp className="text-green-400" size={20} />
            </div>
            <h3 className="font-semibold text-lg mb-2">3. Lock, Track, Learn</h3>
            <p className="text-sm text-muted">
              Predictions lock before tipoff and never change. Every outcome is
              scored. Calibration curves, Brier scores, and game logs — all public.
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
