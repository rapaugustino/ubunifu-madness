"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import WinProbBar from "@/components/WinProbBar";
import { ArrowLeftRight, Sparkles } from "lucide-react";
import { MetricLabel, METRIC_TOOLTIPS } from "@/components/Tooltip";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Team {
  id: number;
  name: string;
  gender: string;
  seed: number | null;
  conference: string | null;
  elo: number | null;
  record: string | null;
  winPct: number | null;
  logo: string | null;
  color: string | null;
}

interface FeatureComparison {
  label: string;
  teamA: number;
  teamB: number;
  unit: string;
  lowerBetter: boolean;
}

interface TeamDetail {
  id: number;
  name: string;
  gender: string;
  seed: number | null;
  conference: string | null;
  elo: number | null;
  record: string | null;
  winPct: number | null;
  stats: Record<string, number | null> | null;
  conferenceContext: {
    confAbbrev: string;
    confName: string;
    avgElo: number;
    depth: number;
    top5Elo: number;
    ncWinrate: number;
    tourneyHistWinrate: number;
  } | null;
}

interface CompareResult {
  teamA: TeamDetail;
  teamB: TeamDetail;
  winProbA: number;
  winProbB: number;
  featureComparison: FeatureComparison[];
}

const statCategories = [
  { key: "elo", label: "Elo Rating", format: (v: number | null) => v ? v.toFixed(0) : "—", tip: METRIC_TOOLTIPS.elo },
  { key: "seed", label: "Seed", format: (v: number | null) => v ? `#${v}` : "—", tip: METRIC_TOOLTIPS.seed },
  { key: "winPct", label: "Win %", format: (v: number | null) => v ? `${(v * 100).toFixed(1)}%` : "—", tip: "" },
];

const featureTooltipMap: Record<string, string> = {
  "Offensive Efficiency": METRIC_TOOLTIPS.offEfficiency,
  "Defensive Efficiency": METRIC_TOOLTIPS.defEfficiency,
  "Tempo": METRIC_TOOLTIPS.tempo,
  "eFG%": METRIC_TOOLTIPS.efgPct,
  "Turnover Rate": METRIC_TOOLTIPS.toPct,
  "Rebound Rate": METRIC_TOOLTIPS.orPct,
  "Free Throw Rate": METRIC_TOOLTIPS.ftRate,
  "Opp eFG%": METRIC_TOOLTIPS.oppEfgPct,
};

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-muted">Loading...</div>}>
      <CompareContent />
    </Suspense>
  );
}

function CompareContent() {
  const searchParams = useSearchParams();
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamAId, setTeamAId] = useState<number | null>(null);
  const [teamBId, setTeamBId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [gender, setGender] = useState<"M" | "W" | "all">("M");
  const [analysisText, setAnalysisText] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [initializedFromParams, setInitializedFromParams] = useState(false);

  // Fetch team list
  useEffect(() => {
    fetch(`${API_URL}/api/teams?gender=${gender}&limit=500`)
      .then((r) => r.json())
      .then((data) => {
        setTeams(data.teams || []);
        // On first load, check URL params for pre-selected teams
        if (!initializedFromParams) {
          const paramA = searchParams.get("teamA");
          const paramB = searchParams.get("teamB");
          if (paramA && paramB) {
            setTeamAId(Number(paramA));
            setTeamBId(Number(paramB));
            // Detect gender from the team IDs (3xxx = Women's)
            if (Number(paramA) >= 3000) {
              setGender("W");
            }
            setInitializedFromParams(true);
            return;
          }
          setInitializedFromParams(true);
        }
        if (!teamAId && data.teams?.length >= 2) {
          setTeamAId(data.teams[0].id);
          setTeamBId(data.teams[1].id);
        }
      })
      .catch(() => setTeams([]));
  }, [gender]);

  // Fetch comparison when teams change
  useEffect(() => {
    if (!teamAId || !teamBId || teamAId === teamBId) return;
    setLoading(true);
    setAnalysisText("");
    fetch(`${API_URL}/api/compare/${teamAId}/${teamBId}`)
      .then((r) => r.json())
      .then((data) => setComparison(data))
      .catch(() => setComparison(null))
      .finally(() => setLoading(false));
  }, [teamAId, teamBId]);

  const getAIAnalysis = async () => {
    if (!comparison) return;
    setAnalyzing(true);
    setAnalysisText("");

    const { teamA, teamB, winProbA } = comparison;
    const prompt = `Compare these two teams for a potential March Madness matchup: ${teamA.name} (${teamA.record}, Elo ${teamA.elo}, ${teamA.conference}) vs ${teamB.name} (${teamB.record}, Elo ${teamB.elo}, ${teamB.conference}). Our model gives ${teamA.name} a ${(winProbA * 100).toFixed(0)}% win probability. Briefly analyze strengths, weaknesses, and what would decide this game.`;

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{ role: "user", content: prompt }],
          gender: teamA.gender === "W" ? "W" : "M",
        }),
      });
      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let text = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (line.startsWith("data: ") && !line.includes("[DONE]")) {
            try {
              const data = JSON.parse(line.slice(6));
              text += data.text;
              setAnalysisText(text);
            } catch {}
          }
        }
      }
    } catch {
      setAnalysisText("Unable to generate analysis.");
    }
    setAnalyzing(false);
  };

  return (
    <div className="min-h-screen max-w-7xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Head-to-Head Comparison</h1>
          <p className="text-muted text-sm mt-1">
            Compare teams with real stats and ML win probability
          </p>
        </div>
        <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
          {(["M", "W"] as const).map((g) => (
            <button
              key={g}
              onClick={() => { setGender(g); setTeamAId(null); setTeamBId(null); setComparison(null); }}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                gender === g ? "bg-accent text-white" : "text-muted hover:text-foreground"
              }`}
            >
              {g === "M" ? "Men" : "Women"}
            </button>
          ))}
        </div>
      </div>

      {/* Team selectors */}
      <div className="grid grid-cols-[1fr,auto,1fr] gap-4 items-start mb-8">
        <div>
          <label className="text-xs text-muted uppercase tracking-wider block mb-2">Team A</label>
          <select
            value={teamAId || ""}
            onChange={(e) => setTeamAId(Number(e.target.value))}
            className="w-full px-4 py-3 bg-card border border-card-border rounded-lg text-foreground focus:outline-none focus:border-accent/50 text-sm"
          >
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} — {t.conference} ({t.record || "N/A"})
              </option>
            ))}
          </select>
        </div>

        <div className="pt-8">
          <div className="w-10 h-10 rounded-full bg-card border border-card-border flex items-center justify-center">
            <ArrowLeftRight size={16} className="text-muted" />
          </div>
        </div>

        <div>
          <label className="text-xs text-muted uppercase tracking-wider block mb-2">Team B</label>
          <select
            value={teamBId || ""}
            onChange={(e) => setTeamBId(Number(e.target.value))}
            className="w-full px-4 py-3 bg-card border border-card-border rounded-lg text-foreground focus:outline-none focus:border-accent/50 text-sm"
          >
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} — {t.conference} ({t.record || "N/A"})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="text-center text-muted py-12">Loading comparison...</div>
      )}

      {comparison && !loading && (
        <>
          {/* Win probability */}
          <div className="p-6 rounded-xl bg-card border border-card-border mb-6">
            <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">
              Model Win Probability
            </h2>
            <WinProbBar
              teamA={comparison.teamA.name}
              teamB={comparison.teamB.name}
              probA={comparison.winProbA}
              seedA={comparison.teamA.seed ?? undefined}
              seedB={comparison.teamB.seed ?? undefined}
            />
            <div className="mt-4 flex justify-center">
              <button
                onClick={getAIAnalysis}
                disabled={analyzing}
                className="flex items-center gap-1.5 text-sm text-accent hover:text-accent-secondary transition-colors disabled:opacity-50"
              >
                <Sparkles size={14} />
                {analyzing ? "Analyzing..." : "Get Analysis"}
              </button>
            </div>
          </div>

          {/* AI Analysis */}
          {analysisText && (
            <div className="p-4 rounded-xl bg-accent/5 border border-accent/10 mb-6">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-accent" />
                <span className="text-xs font-medium text-accent uppercase tracking-wider">Matchup Analysis</span>
              </div>
              <p className="text-sm text-muted leading-relaxed whitespace-pre-line">{analysisText}</p>
            </div>
          )}

          {/* Stats comparison */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Quick stats */}
            <div className="p-6 rounded-xl bg-card border border-card-border">
              <h3 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">
                Key Stats
              </h3>
              <div className="space-y-3">
                {statCategories.map((stat) => {
                  const valA = comparison.teamA[stat.key as keyof typeof comparison.teamA] as number | null;
                  const valB = comparison.teamB[stat.key as keyof typeof comparison.teamB] as number | null;
                  const aWins =
                    valA != null && valB != null
                      ? stat.key === "seed"
                        ? valA < valB
                        : valA > valB
                      : false;
                  return (
                    <div key={stat.key} className="flex items-center justify-between">
                      <span className={`text-sm font-mono ${aWins ? "text-accent font-semibold" : "text-muted"}`}>
                        {stat.format(valA)}
                      </span>
                      {stat.tip ? (
                        <MetricLabel label={stat.label} tooltip={stat.tip} className="text-xs text-muted" />
                      ) : (
                        <span className="text-xs text-muted">{stat.label}</span>
                      )}
                      <span className={`text-sm font-mono ${!aWins && valB != null ? "text-blue-400 font-semibold" : "text-muted"}`}>
                        {stat.format(valB)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Feature breakdown */}
            <div className="p-6 rounded-xl bg-card border border-card-border">
              <h3 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">
                Feature Breakdown
              </h3>
              <div className="space-y-3">
                {comparison.featureComparison.length === 0 ? (
                  <p className="text-xs text-muted">No advanced stats available for these teams.</p>
                ) : (
                  comparison.featureComparison.map((feat) => {
                    const aWins = feat.lowerBetter
                      ? feat.teamA < feat.teamB
                      : feat.teamA > feat.teamB;
                    const tip = featureTooltipMap[feat.label];
                    return (
                      <div key={feat.label} className="flex items-center justify-between">
                        <span className={`text-sm font-mono ${aWins ? "text-accent font-semibold" : "text-muted"}`}>
                          {feat.unit === "%" ? (feat.teamA * 100).toFixed(1) : feat.teamA?.toFixed(1)}
                        </span>
                        <span className="text-xs text-muted text-center flex-1">
                          {tip ? <MetricLabel label={feat.label} tooltip={tip} className="justify-center" /> : feat.label}
                        </span>
                        <span className={`text-sm font-mono ${!aWins ? "text-blue-400 font-semibold" : "text-muted"}`}>
                          {feat.unit === "%" ? (feat.teamB * 100).toFixed(1) : feat.teamB?.toFixed(1)}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* Conference context */}
          <div className="mt-6 p-6 rounded-xl bg-card border border-card-border">
            <h3 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">
              Conference Context
            </h3>
            <div className="grid md:grid-cols-2 gap-6">
              {[comparison.teamA, comparison.teamB].map((team, idx) => {
                const ctx = team.conferenceContext;
                return (
                  <div key={idx}>
                    <div className="text-sm font-medium mb-1">{team.name}</div>
                    <div className="text-xs text-muted mb-3">
                      {ctx ? ctx.confName : team.conference} &middot; {team.record || "N/A"}
                    </div>
                    {ctx ? (
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-muted">Conf Avg Elo</span>
                          <span className="font-mono">{ctx.avgElo?.toFixed(0)}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted">NC Win Rate</span>
                          <span className="font-mono text-accent">{(ctx.ncWinrate * 100).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted">Tourney Win Rate</span>
                          <span className="font-mono">{(ctx.tourneyHistWinrate * 100).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted">Conf Depth</span>
                          <span className="font-mono">{ctx.depth?.toFixed(0)}</span>
                        </div>
                      </div>
                    ) : (
                      <div className="text-xs text-muted">Conference data not available</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
