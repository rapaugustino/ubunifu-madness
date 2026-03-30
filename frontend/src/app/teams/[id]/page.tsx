"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Sparkles, TrendingUp, TrendingDown, Minus, AlertTriangle } from "lucide-react";
import { MetricLabel, METRIC_TOOLTIPS } from "@/components/Tooltip";
import { API_URL } from "@/lib/api";

interface Player {
  id: string;
  name: string;
  jersey: string;
  position: string;
  positionFull: string;
  height: string;
  weight: string;
  experience: string;
  headshot: string | null;
}

interface EnrichedPlayer {
  id: number;
  espnId: number;
  name: string;
  jersey: string | null;
  position: string | null;
  positionFull: string | null;
  height: string | null;
  weight: string | null;
  experience: string | null;
  headshot: string | null;
  injuryStatus: string | null;
  injuryDetail: string | null;
  stats: {
    gamesPlayed: number;
    ppg: number;
    rpg: number;
    apg: number;
    mpg: number;
    fgPct: number | null;
    fg3Pct: number | null;
    ftPct: number | null;
    importanceScore: number | null;
    minutesShare: number | null;
  } | null;
}

interface Coach {
  id: string;
  name: string;
  experience: number;
  headshot: string | null;
}

interface Roster {
  teamId: number;
  teamName: string;
  players: Player[];
  coach: Coach | null;
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
  logo: string | null;
  color: string | null;
  stats: {
    offEfficiency: number | null;
    defEfficiency: number | null;
    tempo: number | null;
    efgPct: number | null;
    toPct: number | null;
    orPct: number | null;
    ftRate: number | null;
    oppEfgPct: number | null;
    oppToPct: number | null;
    masseyRank: number | null;
    momentum: {
      lastNWinPct: number | null;
      lastNMov: number | null;
      efgTrend: number | null;
    } | null;
    coach: {
      name: string | null;
      tenure: number | null;
      tourneyAppearances: number | null;
      marchWinrate: number | null;
    } | null;
  } | null;
  conferenceContext: {
    confAbbrev: string;
    confName: string;
    avgElo: number | null;
    depth: number | null;
    top5Elo: number | null;
    ncWinrate: number | null;
    tourneyHistWinrate: number | null;
  } | null;
}

function formatCoachName(raw: string | null): string {
  if (!raw) return "Unknown";
  return raw
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function StatBar({ label, value, max, unit, tooltip }: { label: string; value: number | null; max: number; unit?: string; tooltip?: string }) {
  const pct = value != null ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        {tooltip ? (
          <MetricLabel label={label} tooltip={tooltip} className="text-muted" />
        ) : (
          <span className="text-muted">{label}</span>
        )}
        <span className="font-mono">
          {value != null ? value.toFixed(1) : "—"}
          {unit && <span className="text-xs text-muted ml-0.5">{unit}</span>}
        </span>
      </div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-accent to-amber-400 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [roster, setRoster] = useState<Roster | null>(null);
  const [enrichedPlayers, setEnrichedPlayers] = useState<EnrichedPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState("");
  const [analysisLoading, setAnalysisLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/teams/${id}`)
      .then((r) => r.json())
      .then((data) => setTeam(data))
      .catch(() => setTeam(null))
      .finally(() => setLoading(false));
    // Fetch roster in parallel
    fetch(`${API_URL}/api/roster/${id}`)
      .then((r) => r.json())
      .then((data) => setRoster(data))
      .catch(() => setRoster(null));
    // Fetch enriched player stats (if available)
    fetch(`${API_URL}/api/players/${id}`)
      .then((r) => r.json())
      .then((data) => setEnrichedPlayers(data.players || []))
      .catch(() => setEnrichedPlayers([]));
  }, [id]);

  const generateReport = () => {
    if (!team) return;
    setAnalysisLoading(true);
    setAnalysis("");

    const prompt = `Give a scouting report for ${team.name} (${team.record}, Elo ${team.elo}, ${team.conference}${team.seed ? `, #${team.seed} seed` : ""}). Their stats: Off Eff ${team.stats?.offEfficiency?.toFixed(1) || "?"}, Def Eff ${team.stats?.defEfficiency?.toFixed(1) || "?"}, eFG% ${team.stats?.efgPct ? (team.stats.efgPct * 100).toFixed(1) + "%" : "?"}, Tempo ${team.stats?.tempo?.toFixed(1) || "?"}. Coach: ${formatCoachName(team.stats?.coach?.name || null)} (${team.stats?.coach?.tourneyAppearances || 0} tourney appearances). Discuss strengths, weaknesses, tournament outlook, and matchup concerns.`;

    fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: prompt }],
        gender: team.gender === "W" ? "W" : "M",
      }),
    })
      .then(async (res) => {
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
                setAnalysis(text);
              } catch {}
            }
          }
        }
      })
      .catch(() => setAnalysis("Unable to generate report. Please try again."))
      .finally(() => setAnalysisLoading(false));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted">Loading team...</div>
      </div>
    );
  }

  if (!team) {
    return (
      <div className="min-h-screen max-w-7xl mx-auto px-4 py-8">
        <Link href="/teams" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground mb-6">
          <ArrowLeft size={14} /> All Teams
        </Link>
        <p className="text-muted">Team not found.</p>
      </div>
    );
  }

  const momentum = team.stats?.momentum;
  const trendUp = momentum?.lastNWinPct != null && team.winPct != null && momentum.lastNWinPct > team.winPct + 0.05;
  const trendDown = momentum?.lastNWinPct != null && team.winPct != null && momentum.lastNWinPct < team.winPct - 0.05;

  return (
    <div className="min-h-screen max-w-7xl mx-auto px-4 sm:px-6 py-8">
      <Link href="/teams" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground mb-6">
        <ArrowLeft size={14} /> All Teams
      </Link>

      {/* Team header */}
      <div className="flex items-start gap-5 mb-8">
        {team.logo ? (
          <img src={team.logo} alt="" className="w-20 h-20 object-contain shrink-0" />
        ) : (
          <div className="w-20 h-20 rounded-2xl bg-accent/10 flex items-center justify-center text-2xl font-bold text-accent">
            {team.name.slice(0, 2)}
          </div>
        )}
        <div>
          <h1 className="text-3xl font-bold">{team.name}</h1>
          <div className="flex items-center gap-3 mt-1 text-muted flex-wrap">
            <span>{team.conference || "—"}</span>
            <span>&middot;</span>
            <span>{team.record || "—"}</span>
            {team.seed && (
              <>
                <span>&middot;</span>
                <span>#{team.seed} seed ({team.gender === "W" ? "Women's" : "Men's"})</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            {team.elo && (
              <span className="px-2 py-1 bg-accent/10 text-accent text-sm rounded-md font-mono">
                Elo {team.elo.toFixed(0)}
              </span>
            )}
            {trendUp && (
              <span className="flex items-center gap-1 px-2 py-1 bg-green-500/10 text-green-400 text-sm rounded-md">
                <TrendingUp size={12} />
                Hot streak (last 10: {((momentum?.lastNWinPct || 0) * 100).toFixed(0)}%)
              </span>
            )}
            {trendDown && (
              <span className="flex items-center gap-1 px-2 py-1 bg-red-500/10 text-red-400 text-sm rounded-md">
                <TrendingDown size={12} />
                Cooling off (last 10: {((momentum?.lastNWinPct || 0) * 100).toFixed(0)}%)
              </span>
            )}
            {!trendUp && !trendDown && momentum?.lastNWinPct != null && (
              <span className="flex items-center gap-1 px-2 py-1 bg-white/5 text-muted text-sm rounded-md">
                <Minus size={12} />
                Steady (last 10: {(momentum.lastNWinPct * 100).toFixed(0)}%)
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Team profile bars */}
        <div className="p-6 rounded-xl bg-card border border-card-border">
          <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">Team Profile</h2>
          <div className="space-y-3">
            <StatBar label="Off. Efficiency" value={team.stats?.offEfficiency ?? null} max={130} unit="pts/100" tooltip={METRIC_TOOLTIPS.offEfficiency} />
            <StatBar label="Def. Efficiency" value={team.stats?.defEfficiency ?? null} max={130} unit="pts/100" tooltip={METRIC_TOOLTIPS.defEfficiency} />
            <StatBar label="Tempo" value={team.stats?.tempo ?? null} max={80} unit="poss/g" tooltip={METRIC_TOOLTIPS.tempo} />
            <StatBar label="eFG%" value={team.stats?.efgPct != null ? team.stats.efgPct * 100 : null} max={65} unit="%" tooltip={METRIC_TOOLTIPS.efgPct} />
            <StatBar label="Rebound Rate" value={team.stats?.orPct != null ? team.stats.orPct * 100 : null} max={50} unit="%" tooltip={METRIC_TOOLTIPS.orPct} />
            <StatBar label="Free Throw Rate" value={team.stats?.ftRate != null ? team.stats.ftRate * 100 : null} max={50} unit="%" tooltip={METRIC_TOOLTIPS.ftRate} />
          </div>
        </div>

        {/* Advanced metrics */}
        <div className="p-6 rounded-xl bg-card border border-card-border">
          <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">Advanced Metrics</h2>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Off. Efficiency", value: team.stats?.offEfficiency?.toFixed(1) || "—", unit: "pts/100", tip: METRIC_TOOLTIPS.offEfficiency },
              { label: "Def. Efficiency", value: team.stats?.defEfficiency?.toFixed(1) || "—", unit: "pts/100", tip: METRIC_TOOLTIPS.defEfficiency },
              { label: "Tempo", value: team.stats?.tempo?.toFixed(1) || "—", unit: "poss/g", tip: METRIC_TOOLTIPS.tempo },
              { label: "eFG%", value: team.stats?.efgPct != null ? (team.stats.efgPct * 100).toFixed(1) + "%" : "—", unit: "", tip: METRIC_TOOLTIPS.efgPct },
              { label: "Turnover Rate", value: team.stats?.toPct?.toFixed(1) || "—", unit: "%", tip: METRIC_TOOLTIPS.toPct },
              { label: "Opp eFG%", value: team.stats?.oppEfgPct != null ? (team.stats.oppEfgPct * 100).toFixed(1) + "%" : "—", unit: "", tip: METRIC_TOOLTIPS.oppEfgPct },
              { label: "Last 10 Win%", value: momentum?.lastNWinPct != null ? (momentum.lastNWinPct * 100).toFixed(0) + "%" : "—", unit: "", tip: METRIC_TOOLTIPS.momentum },
              { label: "Last 10 MOV", value: momentum?.lastNMov?.toFixed(1) || "—", unit: "pts", tip: METRIC_TOOLTIPS.lastNMov },
            ].map((m) => (
              <div key={m.label} className="p-3 rounded-lg bg-white/[0.02]">
                <MetricLabel label={m.label} tooltip={m.tip} className="text-xs text-muted mb-1" />
                <div className="text-lg font-semibold font-mono">
                  {m.value}
                  {m.unit && m.value !== "—" && <span className="text-xs text-muted ml-1">{m.unit}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Conference context */}
        <div className="p-6 rounded-xl bg-card border border-card-border">
          <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">
            Conference Context{team.conferenceContext ? ` — ${team.conferenceContext.confName}` : ""}
          </h2>
          {team.conferenceContext ? (
            <div className="space-y-3">
              {[
                { label: "Conference Avg Elo", value: team.conferenceContext.avgElo?.toFixed(0) || "—" },
                { label: "Conference Depth", value: team.conferenceContext.depth?.toFixed(2) || "—" },
                { label: "Non-Conf Win Rate", value: team.conferenceContext.ncWinrate != null ? (team.conferenceContext.ncWinrate * 100).toFixed(1) + "%" : "—" },
                { label: "Top 5 Avg Elo", value: team.conferenceContext.top5Elo?.toFixed(0) || "—" },
                { label: "Tourney Hist Win Rate", value: team.conferenceContext.tourneyHistWinrate != null ? (team.conferenceContext.tourneyHistWinrate * 100).toFixed(1) + "%" : "—" },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between text-sm">
                  <span className="text-muted">{item.label}</span>
                  <span className="font-mono">{item.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No conference data available.</p>
          )}
        </div>

        {/* Coach info */}
        <div className="p-6 rounded-xl bg-card border border-card-border">
          <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">Coaching</h2>
          {(roster?.coach || team.stats?.coach) ? (
            <div className="flex items-start gap-4">
              {roster?.coach?.headshot && (
                <img src={roster.coach.headshot} alt="" className="w-16 h-16 rounded-lg object-cover shrink-0" />
              )}
              <div className="space-y-3 flex-1">
                {[
                  { label: "Head Coach", value: roster?.coach?.name || formatCoachName(team.stats?.coach?.name || null) },
                  { label: "Tenure", value: (() => { const espnExp = roster?.coach?.experience; const kaggleTenure = team.stats?.coach?.tenure; const tenure = (espnExp && espnExp > 0) ? espnExp : kaggleTenure; return tenure != null ? `${tenure} years` : "—"; })() },
                  { label: "Tourney Appearances", value: team.stats?.coach?.tourneyAppearances?.toString() || "—" },
                  { label: "March Win Rate", value: team.stats?.coach?.marchWinrate != null ? (team.stats.coach.marchWinrate * 100).toFixed(0) + "%" : "—" },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between text-sm">
                    <span className="text-muted">{item.label}</span>
                    <span className="font-mono">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted">No coaching data available.</p>
          )}
        </div>

        {/* Roster with Stats */}
        {(enrichedPlayers.length > 0 || (roster && roster.players.length > 0)) && (
          <div className="md:col-span-2 p-6 rounded-xl bg-card border border-card-border">
            <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-4">
              Roster ({enrichedPlayers.length || roster?.players.length || 0} players)
            </h2>
            <div className="overflow-x-auto">
              {enrichedPlayers.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-card-border">
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium">#</th>
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium">Player</th>
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium hidden sm:table-cell">Pos</th>
                      <th className="text-right py-2 pr-3 text-xs text-muted font-medium">PPG</th>
                      <th className="text-right py-2 pr-3 text-xs text-muted font-medium hidden sm:table-cell">RPG</th>
                      <th className="text-right py-2 pr-3 text-xs text-muted font-medium hidden sm:table-cell">APG</th>
                      <th className="text-right py-2 pr-3 text-xs text-muted font-medium hidden md:table-cell">MPG</th>
                      <th className="text-right py-2 pr-3 text-xs text-muted font-medium hidden md:table-cell">FG%</th>
                      <th className="text-right py-2 text-xs text-muted font-medium hidden lg:table-cell">Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {enrichedPlayers
                      .sort((a, b) => (b.stats?.ppg || 0) - (a.stats?.ppg || 0))
                      .map((p) => {
                        const isKey = p.stats?.importanceScore && p.stats.importanceScore > 0.15;
                        return (
                          <tr key={p.id} className="border-b border-card-border/30 hover:bg-white/[0.02]">
                            <td className="py-2 pr-3 font-mono text-muted">{p.jersey || "—"}</td>
                            <td className="py-2 pr-3">
                              <div className="flex items-center gap-2">
                                {p.headshot ? (
                                  <img src={p.headshot} alt="" className="w-7 h-7 rounded-full object-cover shrink-0" />
                                ) : (
                                  <div className="w-7 h-7 rounded-full bg-white/5 shrink-0" />
                                )}
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span className={`font-medium ${isKey ? "" : ""}`}>{p.name}</span>
                                    {isKey && <span className="text-xs bg-accent/20 text-accent px-1 rounded">KEY</span>}
                                    {p.injuryStatus && (
                                      <span className="flex items-center gap-0.5 text-xs bg-red-500/20 text-red-400 px-1 rounded">
                                        <AlertTriangle size={8} />
                                        {p.injuryStatus}
                                      </span>
                                    )}
                                  </div>
                                  <span className="text-xs text-muted">{p.experience}</span>
                                </div>
                              </div>
                            </td>
                            <td className="py-2 pr-3 text-muted hidden sm:table-cell">{p.position || "—"}</td>
                            <td className="py-2 pr-3 text-right font-mono">{p.stats?.ppg?.toFixed(1) || "—"}</td>
                            <td className="py-2 pr-3 text-right font-mono text-muted hidden sm:table-cell">{p.stats?.rpg?.toFixed(1) || "—"}</td>
                            <td className="py-2 pr-3 text-right font-mono text-muted hidden sm:table-cell">{p.stats?.apg?.toFixed(1) || "—"}</td>
                            <td className="py-2 pr-3 text-right font-mono text-muted hidden md:table-cell">{p.stats?.mpg?.toFixed(1) || "—"}</td>
                            <td className="py-2 pr-3 text-right font-mono text-muted hidden md:table-cell">
                              {p.stats?.fgPct != null ? (p.stats.fgPct * 100).toFixed(1) + "%" : "—"}
                            </td>
                            <td className="py-2 text-right hidden lg:table-cell">
                              {p.stats?.importanceScore != null ? (
                                <div className="flex items-center justify-end gap-1">
                                  <div className="w-12 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                    <div
                                      className={`h-full rounded-full ${isKey ? "bg-accent" : "bg-white/20"}`}
                                      style={{ width: `${Math.min(p.stats.importanceScore * 400, 100)}%` }}
                                    />
                                  </div>
                                  <span className="text-xs text-muted font-mono w-8">
                                    {(p.stats.importanceScore * 100).toFixed(0)}%
                                  </span>
                                </div>
                              ) : "—"}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-card-border">
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium">#</th>
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium">Player</th>
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium hidden sm:table-cell">Pos</th>
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium hidden md:table-cell">Height</th>
                      <th className="text-left py-2 pr-3 text-xs text-muted font-medium hidden md:table-cell">Weight</th>
                      <th className="text-left py-2 text-xs text-muted font-medium hidden lg:table-cell">Class</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roster?.players.map((p) => (
                      <tr key={p.id || p.name} className="border-b border-card-border/30 hover:bg-white/[0.02]">
                        <td className="py-2 pr-3 font-mono text-muted">{p.jersey || "—"}</td>
                        <td className="py-2 pr-3">
                          <div className="flex items-center gap-2">
                            {p.headshot ? (
                              <img src={p.headshot} alt="" className="w-7 h-7 rounded-full object-cover shrink-0" />
                            ) : (
                              <div className="w-7 h-7 rounded-full bg-white/5 shrink-0" />
                            )}
                            <span className="font-medium">{p.name}</span>
                          </div>
                        </td>
                        <td className="py-2 pr-3 text-muted hidden sm:table-cell">{p.positionFull || p.position}</td>
                        <td className="py-2 pr-3 font-mono text-muted hidden md:table-cell">{p.height || "—"}</td>
                        <td className="py-2 pr-3 font-mono text-muted hidden md:table-cell">{p.weight || "—"}</td>
                        <td className="py-2 text-muted hidden lg:table-cell">{p.experience || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* AI Scouting Report */}
        <div className="md:col-span-2 p-6 rounded-xl bg-card border border-card-border">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={16} className="text-accent" />
            <h2 className="text-sm font-medium text-muted uppercase tracking-wider">AI Scouting Report</h2>
          </div>
          {analysis ? (
            <p className="text-sm text-muted leading-relaxed whitespace-pre-line">{analysis}</p>
          ) : (
            <p className="text-sm text-muted leading-relaxed">
              Click below to generate a real-time AI scouting report for {team.name} powered by our model data.
            </p>
          )}
          <button
            onClick={generateReport}
            disabled={analysisLoading}
            className="mt-4 flex items-center gap-1.5 text-sm text-accent hover:text-accent-secondary transition-colors disabled:opacity-50"
          >
            <Sparkles size={14} />
            {analysisLoading ? "Generating..." : analysis ? "Regenerate Report" : "Generate Full Report"}
          </button>
        </div>
      </div>
    </div>
  );
}
