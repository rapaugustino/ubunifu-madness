"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { TrendingUp, TrendingDown, Minus, Search, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { MetricLabel, METRIC_TOOLTIPS } from "@/components/Tooltip";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RankingTeam {
  id: number;
  name: string;
  seed: number | null;
  conference: string;
  elo: number;
  record: string;
  winPct: number;
  logo?: string;
}

interface PowerRanking {
  rank: number;
  team: RankingTeam;
  elo: number;
  record: string;
  conference: string;
  confStrength: number;
  trend: "up" | "down" | "same";
  trendAmount: number;
}

interface ConferenceRanking {
  rank: number;
  name: string;
  abbrev: string;
  avgElo: number;
  depth: number;
  ncWinRate: number;
  teams: number;
  tourneyBids: number;
  top5Elo: number;
}

export default function DashboardPage() {
  const [rankings, setRankings] = useState<PowerRanking[]>([]);
  const [conferences, setConferences] = useState<ConferenceRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"teams" | "conferences">("teams");
  const [gender, setGender] = useState<"M" | "W">("M");
  const [page, setPage] = useState(1);
  const perPage = 50;

  const fetchRankings = useCallback(async (background = false) => {
    if (!background) setLoading(true);
    else setRefreshing(true);
    try {
      const [rankData, confData] = await Promise.all([
        fetch(`${API_URL}/api/rankings/power?gender=${gender}&limit=500`).then((r) => r.json()),
        fetch(`${API_URL}/api/rankings/conferences?gender=${gender}`).then((r) => r.json()),
      ]);
      setRankings(rankData.rankings || []);
      setConferences(confData.conferences || []);
      setLastUpdated(new Date());
    } catch {
      if (!background) {
        setRankings([]);
        setConferences([]);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [gender]);

  useEffect(() => {
    fetchRankings(false);
  }, [fetchRankings]);

  // Revalidate on window focus if data is >2 min old
  useEffect(() => {
    const onFocus = () => {
      if (lastUpdated && Date.now() - lastUpdated.getTime() > 120000) {
        fetchRankings(true);
      }
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [fetchRankings, lastUpdated]);

  const filteredRankings = useMemo(() =>
    rankings.filter(
      (r) =>
        r.team.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.conference.toLowerCase().includes(searchQuery.toLowerCase())
    ),
    [rankings, searchQuery]
  );

  const totalPages = Math.ceil(filteredRankings.length / perPage);
  const paginatedRankings = filteredRankings.slice((page - 1) * perPage, page * perPage);

  // Reset to page 1 when search or gender changes
  useEffect(() => { setPage(1); }, [searchQuery, gender]);

  return (
    <div className="min-h-screen max-w-7xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">Power Rankings</h1>
            {refreshing && (
              <RefreshCw size={14} className="text-accent animate-spin" />
            )}
          </div>
          <p className="text-muted text-sm mt-1">
            Elo-based rankings with conference strength context
            {lastUpdated && (
              <span className="ml-2 text-xs">
                &middot; Updated {lastUpdated.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
            {(["M", "W"] as const).map((g) => (
              <button
                key={g}
                onClick={() => setGender(g)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  gender === g ? "bg-accent text-white" : "text-muted hover:text-foreground"
                }`}
              >
                {g === "M" ? "Men" : "Women"}
              </button>
            ))}
          </div>

          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Search teams..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-2 bg-card border border-card-border rounded-lg text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-accent/50 w-full sm:w-48"
            />
          </div>
        </div>
      </div>

      {/* Tab toggle */}
      <div className="flex items-center gap-1 mb-6 p-1 bg-card rounded-lg border border-card-border w-fit">
        <button
          onClick={() => setActiveTab("teams")}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === "teams"
              ? "bg-accent/15 text-accent"
              : "text-muted hover:text-foreground"
          }`}
        >
          Team Rankings
        </button>
        <button
          onClick={() => setActiveTab("conferences")}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === "conferences"
              ? "bg-accent/15 text-accent"
              : "text-muted hover:text-foreground"
          }`}
        >
          Conference Strength
        </button>
      </div>

      {loading ? (
        <div className="text-center text-muted py-20">Loading rankings...</div>
      ) : activeTab === "teams" ? (
        <div className="rounded-xl border border-card-border overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-card border-b border-card-border">
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">Rank</th>
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">Team</th>
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden sm:table-cell">Conference</th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">
                  <MetricLabel label="Elo" tooltip={METRIC_TOOLTIPS.elo} className="justify-end" />
                </th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden md:table-cell">Record</th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden lg:table-cell">
                  <MetricLabel label="NC Win %" tooltip={METRIC_TOOLTIPS.confNcWinRate} className="justify-end" />
                </th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">
                  <MetricLabel label="Trend" tooltip={METRIC_TOOLTIPS.trend} className="justify-end" />
                </th>
              </tr>
            </thead>
            <tbody>
              {paginatedRankings.map((ranking) => (
                <tr
                  key={ranking.team.id}
                  className="border-b border-card-border/50 hover:bg-white/[0.02] transition-colors"
                >
                  <td className="px-4 py-3">
                    <span className="text-sm font-mono text-muted">{ranking.rank}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {ranking.team.logo ? (
                        <img src={ranking.team.logo} alt="" className="w-8 h-8 object-contain shrink-0" />
                      ) : (
                        <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-xs text-muted">
                          —
                        </div>
                      )}
                      <div>
                        <div className="flex items-center gap-1.5">
                          {ranking.team.seed && (
                            <span className="text-xs text-accent font-medium">#{ranking.team.seed}</span>
                          )}
                          <span className="font-medium text-sm">{ranking.team.name}</span>
                        </div>
                        <div className="text-xs text-muted sm:hidden">{ranking.conference}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className="text-sm text-muted">{ranking.conference}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-sm font-mono font-semibold">{ranking.elo}</span>
                  </td>
                  <td className="px-4 py-3 text-right hidden md:table-cell">
                    <span className="text-sm text-muted">{ranking.record}</span>
                  </td>
                  <td className="px-4 py-3 text-right hidden lg:table-cell">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-accent rounded-full"
                          style={{ width: `${ranking.confStrength * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted font-mono">
                        {(ranking.confStrength * 100).toFixed(0)}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {ranking.trend === "up" && (
                        <>
                          <TrendingUp size={14} className="text-green-400" />
                          <span className="text-xs text-green-400">+{ranking.trendAmount}</span>
                        </>
                      )}
                      {ranking.trend === "down" && (
                        <>
                          <TrendingDown size={14} className="text-red-400" />
                          <span className="text-xs text-red-400">-{ranking.trendAmount}</span>
                        </>
                      )}
                      {ranking.trend === "same" && (
                        <Minus size={14} className="text-muted" />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 bg-card border-t border-card-border">
              <span className="text-xs text-muted">
                {filteredRankings.length} teams &middot; Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1.5 rounded-md hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft size={16} />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`w-8 h-8 rounded-md text-xs font-medium transition-colors ${
                      p === page
                        ? "bg-accent text-white"
                        : "text-muted hover:text-foreground hover:bg-white/5"
                    }`}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-1.5 rounded-md hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-card-border overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-card border-b border-card-border">
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">#</th>
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">Conference</th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">
                  <MetricLabel label="Avg Elo" tooltip={METRIC_TOOLTIPS.confAvgElo} className="justify-end" />
                </th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden sm:table-cell">
                  <MetricLabel label="NC Win %" tooltip={METRIC_TOOLTIPS.confNcWinRate} className="justify-end" />
                </th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden md:table-cell">Teams</th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3">Tourney Bids</th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden lg:table-cell">
                  <MetricLabel label="Top 5 Elo" tooltip={METRIC_TOOLTIPS.confTop5Elo} className="justify-end" />
                </th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden lg:table-cell">
                  <MetricLabel label="Parity" tooltip={METRIC_TOOLTIPS.confDepth} className="justify-end" />
                </th>
              </tr>
            </thead>
            <tbody>
              {conferences.map((conf) => {
                // Invert depth (std dev) to parity: lower spread = more parity
                // Normalize: 100 std dev = high parity, 250 std dev = low parity
                const parity = Math.max(0, Math.min(1, (250 - conf.depth) / 150));
                return (
                  <tr key={conf.abbrev} className="border-b border-card-border/50 hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      <span className="text-sm font-mono text-muted">{conf.rank}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-sm">{conf.name}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-mono font-semibold">{conf.avgElo}</span>
                    </td>
                    <td className="px-4 py-3 text-right hidden sm:table-cell">
                      <span className="text-sm font-mono text-accent">
                        {(conf.ncWinRate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right hidden md:table-cell">
                      <span className="text-sm text-muted">{conf.teams}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-semibold">{conf.tourneyBids}</span>
                    </td>
                    <td className="px-4 py-3 text-right hidden lg:table-cell">
                      <span className="text-sm font-mono font-semibold">{conf.top5Elo}</span>
                    </td>
                    <td className="px-4 py-3 text-right hidden lg:table-cell">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 h-1.5 bg-white/5 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${parity * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted font-mono">
                          {(parity * 100).toFixed(0)}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
