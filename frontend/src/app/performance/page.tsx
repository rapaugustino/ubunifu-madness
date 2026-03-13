"use client";

import { useState, useEffect, useCallback } from "react";
import { useGender } from "@/hooks/useGender";
import { TrendingUp, Check, X, Activity, Target, BarChart3, Info } from "lucide-react";
import { Tooltip } from "@/components/Tooltip";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DailyData {
  date: string;
  total: number;
  correct: number;
  accuracy: number | null;
  cumulativeTotal: number;
  cumulativeCorrect: number;
  cumulativeAccuracy: number;
}

interface CalibrationBin {
  binCenter: number;
  avgPredicted: number;
  avgActual: number;
  count: number;
}

interface Summary {
  total: number;
  correct: number;
  accuracy: number | null;
  confidentTotal: number;
  confidentCorrect: number;
  confidentAccuracy: number | null;
  tossups: number;
  brierScore: number | null;
  bySource: Record<string, { total: number; correct: number; accuracy: number | null }>;
}

interface RecentGame {
  id: number;
  espnGameId: string;
  date: string;
  awayName: string;
  homeName: string;
  awayScore: number;
  homeScore: number;
  lockedProbAway: number;
  source: string;
  correct: boolean;
}

function formatDate(dateStr: string, includeYear = false): string {
  if (dateStr.length !== 8) return dateStr;
  const y = dateStr.slice(0, 4);
  const m = dateStr.slice(4, 6);
  const d = dateStr.slice(6, 8);
  const date = new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  if (includeYear) opts.year = "2-digit";
  return date.toLocaleDateString("en-US", opts);
}

function AccuracyBar({ accuracy, size = "md" }: { accuracy: number; size?: "sm" | "md" }) {
  const pct = accuracy * 100;
  const color =
    pct >= 70 ? "bg-green-500" : pct >= 55 ? "bg-accent" : "bg-red-500";
  const h = size === "sm" ? "h-1.5" : "h-2.5";
  return (
    <div className={`w-full ${h} bg-white/5 rounded-full overflow-hidden`}>
      <div className={`${h} ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function StatCard({ label, value, sub, icon: Icon, tooltip }: { label: string; value: string; sub?: string; icon: React.ElementType; tooltip?: string }) {
  return (
    <div className="bg-card border border-card-border rounded-xl p-4">
      <div className="flex items-center gap-2 text-muted text-xs mb-2">
        <Icon size={14} />
        {label}
        {tooltip && (
          <Tooltip text={tooltip}>
            <Info size={12} className="text-muted/40 hover:text-muted cursor-help" />
          </Tooltip>
        )}
      </div>
      <div className="text-2xl font-bold">{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export default function PerformancePage() {
  const [gender, setGender] = useGender();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [daily, setDaily] = useState<DailyData[]>([]);
  const [calibration, setCalibration] = useState<CalibrationBin[]>([]);
  const [recentGames, setRecentGames] = useState<RecentGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "daily" | "calibration" | "games">("overview");

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, dailyRes, calRes, recentRes] = await Promise.all([
        fetch(`${API_URL}/api/performance/summary?gender=${gender}`),
        fetch(`${API_URL}/api/performance/daily?gender=${gender}`),
        fetch(`${API_URL}/api/performance/calibration?gender=${gender}`),
        fetch(`${API_URL}/api/performance/recent?gender=${gender}&limit=100`),
      ]);
      const [sumData, dailyData, calData, recentData] = await Promise.all([
        sumRes.json(), dailyRes.json(), calRes.json(), recentRes.json(),
      ]);
      setSummary(sumData);
      setDaily(dailyData.daily || []);
      setCalibration(calData.bins || []);
      setRecentGames(recentData.games || []);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [gender]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const hasData = summary && summary.total > 0;

  return (
    <div className="min-h-screen max-w-5xl mx-auto px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Model Performance</h1>
          <p className="text-muted text-sm">
            Tracking prediction accuracy with locked pre-game predictions
          </p>
        </div>
        <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
          <button
            onClick={() => setGender("M")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              gender === "M" ? "bg-accent text-white" : "text-muted hover:text-foreground"
            }`}
          >
            Men
          </button>
          <button
            onClick={() => setGender("W")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              gender === "W" ? "bg-accent text-white" : "text-muted hover:text-foreground"
            }`}
          >
            Women
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center text-muted py-20">Loading performance data...</div>
      ) : !hasData ? (
        <div className="text-center text-muted py-20">
          <Target size={32} className="mx-auto mb-3 opacity-50" />
          <p>No resolved predictions yet.</p>
          <p className="text-xs mt-1">Predictions are locked before games start and tracked after they finish.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              icon={Target}
              label="Overall Accuracy"
              value={summary!.accuracy ? `${(summary!.accuracy * 100).toFixed(1)}%` : "—"}
              sub={`${summary!.correct}/${summary!.total} correct${summary!.tossups ? ` · ${summary!.tossups} tossup${summary!.tossups > 1 ? "s" : ""}` : ""}`}
              tooltip="Percentage of games where the model's favored team actually won. Includes all games — even tossups (close to 50/50) where the model had low confidence."
            />
            <StatCard
              icon={BarChart3}
              label="Brier Score"
              value={summary!.brierScore?.toFixed(4) || "—"}
              sub="Lower is better (0 = perfect)"
              tooltip="Measures how close predicted probabilities are to actual outcomes. 0 = perfect predictions, 0.25 = coin-flip level. Rewards confident correct picks and penalizes confident wrong ones."
            />
            <StatCard
              icon={Activity}
              label="Games Tracked"
              value={String(summary!.total)}
              sub={`${daily.length} days`}
              tooltip="Total games with locked pre-game predictions that have finished. Predictions are saved before tipoff and never changed — what the model said is what gets scored."
            />
            <StatCard
              icon={TrendingUp}
              label="Best Day"
              value={daily.length > 0
                ? `${Math.max(...daily.filter(d => d.accuracy !== null).map(d => d.accuracy! * 100)).toFixed(0)}%`
                : "—"
              }
              sub={daily.length > 0
                ? formatDate(daily.reduce((best, d) => (d.accuracy || 0) > (best.accuracy || 0) ? d : best).date, true)
                : undefined
              }
              tooltip="Highest single-day accuracy across all tracked days. Days with very few games can skew high."
            />
          </div>

          {/* Source breakdown */}
          {summary!.bySource && Object.keys(summary!.bySource).length > 0 && (
            <div className="bg-card border border-card-border rounded-xl p-4">
              <div className="text-xs text-muted mb-3 flex items-center gap-2">
                Accuracy by Prediction Source
                <Tooltip text="Different prediction methods are used depending on data availability. ML Ensemble uses the trained V5 model (40 features). Live Blend uses Elo ratings and SOS-adjusted records as a fallback.">
                  <Info size={12} className="text-muted/40 hover:text-muted cursor-help" />
                </Tooltip>
              </div>
              <div className="flex flex-wrap gap-4">
                {Object.entries(summary!.bySource).map(([src, data]) => {
                  const label: Record<string, string> = {
                    "ml_ensemble": "ML Ensemble (V5)",
                    "blended": "Blended (Elo + Record fallback)",
                    "live_blend": "Live Blend (Elo + Record fallback)",
                    "elo_fallback": "Elo Only",
                    "model_v2": "Static Model (legacy)",
                  };
                  return (
                  <div key={src} className="flex items-center gap-3">
                    <span className="text-xs text-muted">{label[src] || src}</span>
                    <span className={`text-sm font-semibold ${
                      data.accuracy && data.accuracy >= 0.65 ? "text-green-400" :
                      data.accuracy && data.accuracy >= 0.5 ? "text-accent" : "text-red-400"
                    }`}>
                      {data.correct}/{data.total} ({data.accuracy ? (data.accuracy * 100).toFixed(1) : 0}%)
                    </span>
                  </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1 w-fit">
            {(["overview", "daily", "calibration", "games"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize ${
                  activeTab === tab ? "bg-accent text-white" : "text-muted hover:text-foreground"
                }`}
              >
                {tab === "overview" ? "Cumulative" : tab === "games" ? "Game Log" : tab}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {activeTab === "overview" && (
            <CumulativeChart daily={daily} />
          )}
          {activeTab === "daily" && (
            <DailyChart daily={daily} />
          )}
          {activeTab === "calibration" && (
            <CalibrationChart bins={calibration} />
          )}
          {activeTab === "games" && (
            <GameLog games={recentGames} />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart components
// ---------------------------------------------------------------------------

function CumulativeChart({ daily }: { daily: DailyData[] }) {
  if (daily.length === 0) return <div className="text-muted text-sm">No data yet.</div>;

  return (
    <div className="bg-card border border-card-border rounded-xl p-4">
      <div className="text-xs text-muted mb-4">Cumulative Accuracy Over Time</div>
      <div className="space-y-1">
        {daily.map((d) => {
          const acc = d.cumulativeAccuracy * 100;
          return (
            <div key={d.date} className="flex items-center gap-3 text-xs">
              <span className="w-20 text-muted shrink-0">{formatDate(d.date, true)}</span>
              <div className="flex-1">
                <AccuracyBar accuracy={d.cumulativeAccuracy} size="sm" />
              </div>
              <span className={`w-16 text-right font-mono ${
                acc >= 65 ? "text-green-400" : acc >= 50 ? "text-foreground" : "text-red-400"
              }`}>
                {acc.toFixed(1)}%
              </span>
              <span className="w-16 text-right text-muted">
                {d.cumulativeCorrect}/{d.cumulativeTotal}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DailyChart({ daily }: { daily: DailyData[] }) {
  if (daily.length === 0) return <div className="text-muted text-sm">No data yet.</div>;

  return (
    <div className="bg-card border border-card-border rounded-xl p-4">
      <div className="text-xs text-muted mb-4">Daily Accuracy</div>
      <div className="space-y-2">
        {[...daily].reverse().map((d) => {
          const acc = d.accuracy !== null ? d.accuracy * 100 : 0;
          return (
            <div key={d.date} className="flex items-center gap-3 text-xs">
              <span className="w-20 text-muted shrink-0">{formatDate(d.date, true)}</span>
              <div className="flex-1">
                <AccuracyBar accuracy={d.accuracy || 0} />
              </div>
              <span className={`w-12 text-right font-semibold ${
                acc >= 70 ? "text-green-400" : acc >= 55 ? "text-accent" : "text-red-400"
              }`}>
                {acc.toFixed(0)}%
              </span>
              <span className="w-12 text-right text-muted">
                {d.correct}/{d.total}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  if (bins.length === 0) return <div className="text-muted text-sm">Not enough data for calibration.</div>;

  return (
    <div className="bg-card border border-card-border rounded-xl p-4">
      <div className="text-xs text-muted mb-1 flex items-center gap-2">
        Calibration Curve
        <Tooltip text="Calibration shows whether the model's probabilities are trustworthy. If the model says 70% chance, the team should win ~70% of the time. Good calibration means you can take the percentages at face value.">
          <Info size={12} className="text-muted/40 hover:text-muted cursor-help" />
        </Tooltip>
      </div>
      <div className="text-[10px] text-muted mb-4">
        Perfect calibration: predicted probability matches actual win rate.
        Points close together = well-calibrated.
      </div>

      {/* Simple table-based calibration display */}
      <div className="space-y-2">
        <div className="flex items-center gap-3 text-[10px] text-muted font-medium border-b border-card-border pb-2">
          <span className="w-24">Predicted</span>
          <span className="w-24">Actual Win%</span>
          <span className="flex-1">Calibration</span>
          <span className="w-12 text-right">Games</span>
        </div>
        {bins.map((bin) => {
          const diff = Math.abs(bin.avgPredicted - bin.avgActual);
          const isGood = diff < 0.05;
          const isOk = diff < 0.10;
          return (
            <div key={bin.binCenter} className="flex items-center gap-3 text-xs">
              <span className="w-24 font-mono">{(bin.avgPredicted * 100).toFixed(1)}%</span>
              <span className="w-24 font-mono">{(bin.avgActual * 100).toFixed(1)}%</span>
              <div className="flex-1 flex items-center gap-2">
                <div className="flex-1 h-4 relative">
                  {/* Predicted marker */}
                  <div
                    className="absolute h-4 w-0.5 bg-accent"
                    style={{ left: `${bin.avgPredicted * 100}%` }}
                  />
                  {/* Actual marker */}
                  <div
                    className={`absolute h-4 w-0.5 ${isGood ? "bg-green-400" : isOk ? "bg-yellow-400" : "bg-red-400"}`}
                    style={{ left: `${bin.avgActual * 100}%` }}
                  />
                  <div className="absolute inset-0 border-b border-white/5" style={{ top: "50%" }} />
                </div>
                <span className={`text-[10px] w-14 ${isGood ? "text-green-400" : isOk ? "text-yellow-400" : "text-red-400"}`}>
                  {diff < 0.01 ? "±0" : `${diff > 0 ? "+" : ""}${(diff * 100).toFixed(1)}%`}
                </span>
              </div>
              <span className="w-12 text-right text-muted">{bin.count}</span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex gap-4 text-[10px] text-muted">
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-accent rounded-full" /> Predicted</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-green-400 rounded-full" /> Actual (good)</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-yellow-400 rounded-full" /> Actual (ok)</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-400 rounded-full" /> Actual (off)</span>
      </div>
    </div>
  );
}

function GameLog({ games }: { games: RecentGame[] }) {
  const [page, setPage] = useState(0);
  const pageSize = 25;

  if (games.length === 0) return <div className="text-muted text-sm">No resolved predictions yet.</div>;

  const totalPages = Math.ceil(games.length / pageSize);
  const pageGames = games.slice(page * pageSize, (page + 1) * pageSize);
  const pageCorrect = pageGames.filter(g => g.correct).length;

  return (
    <div className="bg-card border border-card-border rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-card-border text-muted">
              <th className="text-left p-3 font-medium">Date</th>
              <th className="text-left p-3 font-medium">Matchup</th>
              <th className="text-center p-3 font-medium">Score</th>
              <th className="text-center p-3 font-medium">
                <span className="inline-flex items-center gap-1">
                  Our Pick
                  <Tooltip text="The team the model predicted to win, locked before the game started. TOSSUP means confidence was below 55% — essentially a coin flip.">
                    <Info size={10} className="text-muted/40 hover:text-muted cursor-help" />
                  </Tooltip>
                </span>
              </th>
              <th className="text-center p-3 font-medium">
                <span className="inline-flex items-center gap-1">
                  Confidence
                  <Tooltip text="How sure the model was about its pick. 55% = barely leaning one way. 80%+ = very confident. Higher confidence misses are more costly to the Brier score.">
                    <Info size={10} className="text-muted/40 hover:text-muted cursor-help" />
                  </Tooltip>
                </span>
              </th>
              <th className="text-center p-3 font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            {pageGames.map((g) => {
              const favAway = g.lockedProbAway > 0.5;
              const favName = favAway ? g.awayName : g.homeName;
              const confidence = Math.max(g.lockedProbAway, 1 - g.lockedProbAway);
              const isTossup = confidence < 0.55;
              const awayWon = g.awayScore > g.homeScore;
              return (
                <tr key={g.id} className="border-b border-card-border/50 hover:bg-white/[0.02]">
                  <td className="p-3 text-muted">{formatDate(g.date, true)}</td>
                  <td className="p-3">
                    <span className={awayWon ? "font-semibold" : "text-muted"}>{g.awayName}</span>
                    <span className="text-muted mx-1">@</span>
                    <span className={!awayWon ? "font-semibold" : "text-muted"}>{g.homeName}</span>
                  </td>
                  <td className="p-3 text-center font-mono">
                    {g.awayScore}-{g.homeScore}
                  </td>
                  <td className="p-3 text-center">
                    <span className={isTossup ? "text-muted/60" : "text-muted"}>{favName}</span>
                    {isTossup && <span className="text-yellow-400/70 text-[10px] ml-1">TOSSUP</span>}
                  </td>
                  <td className="p-3 text-center font-mono">
                    {(confidence * 100).toFixed(0)}%
                  </td>
                  <td className="p-3 text-center">
                    {g.correct ? (
                      <span className="inline-flex items-center gap-0.5 text-green-400">
                        <Check size={12} /> ✓
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-0.5 text-red-400">
                        <X size={12} /> ✗
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between p-3 border-t border-card-border">
          <span className="text-xs text-muted">
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, games.length)} of {games.length} games
            <span className="ml-2">({pageCorrect}/{pageGames.length} correct on this page)</span>
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2.5 py-1 rounded text-xs border border-card-border hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Prev
            </button>
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                onClick={() => setPage(i)}
                className={`px-2.5 py-1 rounded text-xs border ${
                  page === i
                    ? "bg-accent text-white border-accent"
                    : "border-card-border hover:bg-white/5 text-muted"
                }`}
              >
                {i + 1}
              </button>
            ))}
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page === totalPages - 1}
              className="px-2.5 py-1 rounded text-xs border border-card-border hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
