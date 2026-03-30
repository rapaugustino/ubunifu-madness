"use client";

import { useState, useEffect, useCallback, useMemo, Fragment } from "react";
import { useGender } from "@/hooks/useGender";
import { TrendingUp, TrendingDown, Minus, Search, RefreshCw, ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from "lucide-react";
import { MetricLabel, METRIC_TOOLTIPS } from "@/components/Tooltip";
import { API_URL } from "@/lib/api";

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
  adjOE: number | null;
  adjDE: number | null;
  adjEM: number | null;
  barthag: number | null;
  luck: number | null;
  trueShooting: number | null;
  oppTrueShooting: number | null;
  threePtRate: number | null;
  astToRatio: number | null;
  drbPct: number | null;
  stlPct: number | null;
  blkPct: number | null;
  marginStdev: number | null;
  floorEff: number | null;
  ceilingEff: number | null;
  upsetVulnerability: number | null;
  closeRecord: string | null;
  closeWinPct: number | null;
  pythWinPct: number | null;
  tempo: number | null;
  sos: number | null;
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
  avgAdjEM: number;
  avgTempo: number;
  avgTsPct: number;
  avgUpsetVuln: number;
  avgBarthag: number;
}

interface StandingTeam {
  seed: number;
  team: { id: number; name: string; logo?: string; color?: string; elo: number };
  confRecord: string;
  confWinPct: number;
  overallRecord: string;
  overallWinPct: number;
  homeRecord: string;
  awayRecord: string;
  streak: string;
  gamesBehind: number;
  avgPointsFor: number;
  avgPointsAgainst: number;
  pointDiff: number;
}

interface ConferenceStanding {
  abbrev: string;
  name: string;
  teams: StandingTeam[];
}

type SortField = "rank" | "adjEM" | "adjOE" | "adjDE" | "barthag" | "luck" | "sos" | "upsetVulnerability" | "tempo";

function fmt(val: number | null, digits = 1): string {
  if (val == null) return "—";
  return val.toFixed(digits);
}

function signedFmt(val: number | null, digits = 1): string {
  if (val == null) return "—";
  const s = val.toFixed(digits);
  return val > 0 ? `+${s}` : s;
}

function pctFmt(val: number | null): string {
  if (val == null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

function luckColor(luck: number | null): string {
  if (luck == null) return "text-muted";
  if (luck > 0.03) return "text-green-400";
  if (luck < -0.03) return "text-red-400";
  return "text-muted";
}

function vulnColor(v: number | null): string {
  if (v == null) return "text-muted";
  if (v >= 60) return "text-red-400";
  if (v >= 40) return "text-yellow-400";
  return "text-green-400";
}

export default function DashboardPage() {
  const [rankings, setRankings] = useState<PowerRanking[]>([]);
  const [conferences, setConferences] = useState<ConferenceRanking[]>([]);
  const [standings, setStandings] = useState<ConferenceStanding[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"teams" | "conferences" | "standings">("teams");
  const [expandedConf, setExpandedConf] = useState<string | null>(null);
  const [gender, setGender] = useGender();
  const [page, setPage] = useState(1);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [sortField, setSortField] = useState<SortField>("rank");
  const [sortAsc, setSortAsc] = useState(true);
  const perPage = 50;

  const fetchRankings = useCallback(async (background = false) => {
    if (!background) setLoading(true);
    else setRefreshing(true);
    try {
      const [rankData, confData, standingsData] = await Promise.all([
        fetch(`${API_URL}/api/rankings/power?gender=${gender}&limit=500`).then((r) => r.json()),
        fetch(`${API_URL}/api/rankings/conferences?gender=${gender}`).then((r) => r.json()),
        fetch(`${API_URL}/api/rankings/conference-standings?gender=${gender}`).then((r) => r.json()),
      ]);
      setRankings(rankData.rankings || []);
      setConferences(confData.conferences || []);
      setStandings(standingsData.conferences || []);
      setLastUpdated(new Date());
    } catch {
      if (!background) {
        setRankings([]);
        setConferences([]);
        setStandings([]);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [gender]);

  useEffect(() => {
    fetchRankings(false);
  }, [fetchRankings]);

  useEffect(() => {
    const onFocus = () => {
      if (lastUpdated && Date.now() - lastUpdated.getTime() > 120000) {
        fetchRankings(true);
      }
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [fetchRankings, lastUpdated]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === "rank" || field === "adjDE");
    }
  };

  const filteredRankings = useMemo(() => {
    let filtered = rankings.filter(
      (r) =>
        r.team.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.conference.toLowerCase().includes(searchQuery.toLowerCase())
    );

    filtered = [...filtered].sort((a, b) => {
      let aVal: number, bVal: number;
      switch (sortField) {
        case "rank": aVal = a.rank; bVal = b.rank; break;
        case "adjEM": aVal = a.adjEM ?? -999; bVal = b.adjEM ?? -999; break;
        case "adjOE": aVal = a.adjOE ?? -999; bVal = b.adjOE ?? -999; break;
        case "adjDE": aVal = a.adjDE ?? 999; bVal = b.adjDE ?? 999; break;
        case "barthag": aVal = a.barthag ?? -1; bVal = b.barthag ?? -1; break;
        case "luck": aVal = a.luck ?? 0; bVal = b.luck ?? 0; break;
        case "sos": aVal = a.sos ?? 0; bVal = b.sos ?? 0; break;
        case "upsetVulnerability": aVal = a.upsetVulnerability ?? 0; bVal = b.upsetVulnerability ?? 0; break;
        case "tempo": aVal = a.tempo ?? 0; bVal = b.tempo ?? 0; break;
        default: aVal = a.rank; bVal = b.rank;
      }
      return sortAsc ? aVal - bVal : bVal - aVal;
    });

    return filtered;
  }, [rankings, searchQuery, sortField, sortAsc]);

  const totalPages = Math.ceil(filteredRankings.length / perPage);
  const paginatedRankings = filteredRankings.slice((page - 1) * perPage, page * perPage);

  useEffect(() => { setPage(1); }, [searchQuery, gender]);

  const SortHeader = ({ field, label, tooltip, className = "" }: { field: SortField; label: string; tooltip: string; className?: string }) => (
    <th
      className={`text-right text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 cursor-pointer select-none hover:text-foreground transition-colors ${className}`}
      onClick={() => handleSort(field)}
    >
      <span className="inline-flex items-center gap-1 justify-end">
        <MetricLabel label={label} tooltip={tooltip} className="justify-end" />
        {sortField === field && (
          sortAsc ? <ChevronUp size={10} className="text-accent" /> : <ChevronDown size={10} className="text-accent" />
        )}
      </span>
    </th>
  );

  return (
    <div className="min-h-screen max-w-[90rem] mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">Power Rankings</h1>
            {refreshing && (
              <RefreshCw size={14} className="text-accent animate-spin" />
            )}
          </div>
          <p className="text-muted text-sm mt-1">
            Advanced analytics with opponent-adjusted efficiency
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
          onClick={() => setActiveTab("standings")}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === "standings"
              ? "bg-accent/15 text-accent"
              : "text-muted hover:text-foreground"
          }`}
        >
          Conference Standings
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

      {/* Conference standings search (only shown on standings tab) */}
      {activeTab === "standings" && (
        <div className="mb-4">
          <div className="relative w-full sm:w-64">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Search conferences or teams..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-2 bg-card border border-card-border rounded-lg text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-accent/50 w-full"
            />
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center text-muted py-20">Loading rankings...</div>
      ) : activeTab === "standings" ? (
        <div className="space-y-3">
          {standings
            .filter((c) =>
              searchQuery === "" ||
              c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              c.teams.some((t) => t.team.name.toLowerCase().includes(searchQuery.toLowerCase()))
            )
            .map((conf) => {
              const isExpanded = expandedConf === conf.abbrev;
              const leader = conf.teams[0];
              return (
                <div key={conf.abbrev} className="rounded-xl border border-card-border overflow-hidden">
                  <button
                    onClick={() => setExpandedConf(isExpanded ? null : conf.abbrev)}
                    className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-white/[0.02] transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-sm">{conf.name}</span>
                      <span className="text-xs text-muted">{conf.teams.length} teams</span>
                    </div>
                    <div className="flex items-center gap-4">
                      {leader && (
                        <span className="text-xs text-muted hidden sm:inline">
                          Leader: <span className="text-foreground font-medium">{leader.team.name}</span> ({leader.confRecord})
                        </span>
                      )}
                      {isExpanded ? <ChevronUp size={16} className="text-muted" /> : <ChevronDown size={16} className="text-muted" />}
                    </div>
                  </button>
                  {isExpanded && (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="bg-card/50 border-t border-card-border">
                            <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 w-8">#</th>
                            <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-4 py-2">Team</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2">Conf</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2">Overall</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 hidden sm:table-cell">Home</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 hidden sm:table-cell">Away</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 hidden md:table-cell">GB</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2">Streak</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 hidden lg:table-cell">PPG</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 hidden lg:table-cell">OppPPG</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 hidden lg:table-cell">Diff</th>
                            <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-2 hidden xl:table-cell">Elo</th>
                          </tr>
                        </thead>
                        <tbody>
                          {conf.teams.map((t) => {
                            const streakIsWin = t.streak.startsWith("W");
                            return (
                              <tr key={t.team.id} className="border-t border-card-border/30 hover:bg-white/[0.02] transition-colors">
                                <td className="px-4 py-2">
                                  <span className="text-xs font-mono text-muted">{t.seed}</span>
                                </td>
                                <td className="px-4 py-2">
                                  <div className="flex items-center gap-2">
                                    {t.team.logo ? (
                                      <img src={t.team.logo} alt="" className="w-5 h-5 object-contain shrink-0" />
                                    ) : (
                                      <div className="w-5 h-5 rounded bg-white/5 shrink-0" />
                                    )}
                                    <span className="text-sm font-medium">{t.team.name}</span>
                                  </div>
                                </td>
                                <td className="px-4 py-2 text-right">
                                  <span className="text-sm font-mono font-semibold">{t.confRecord}</span>
                                </td>
                                <td className="px-4 py-2 text-right">
                                  <span className="text-sm font-mono text-muted">{t.overallRecord}</span>
                                </td>
                                <td className="px-4 py-2 text-right hidden sm:table-cell">
                                  <span className="text-xs font-mono text-muted">{t.homeRecord}</span>
                                </td>
                                <td className="px-4 py-2 text-right hidden sm:table-cell">
                                  <span className="text-xs font-mono text-muted">{t.awayRecord}</span>
                                </td>
                                <td className="px-4 py-2 text-right hidden md:table-cell">
                                  <span className="text-xs font-mono text-muted">{t.gamesBehind === 0 ? "—" : t.gamesBehind}</span>
                                </td>
                                <td className="px-4 py-2 text-right">
                                  <span className={`text-xs font-mono font-medium ${streakIsWin ? "text-green-400" : "text-red-400"}`}>
                                    {t.streak || "—"}
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-right hidden lg:table-cell">
                                  <span className="text-xs font-mono">{t.avgPointsFor.toFixed(1)}</span>
                                </td>
                                <td className="px-4 py-2 text-right hidden lg:table-cell">
                                  <span className="text-xs font-mono">{t.avgPointsAgainst.toFixed(1)}</span>
                                </td>
                                <td className="px-4 py-2 text-right hidden lg:table-cell">
                                  <span className={`text-xs font-mono font-medium ${t.pointDiff > 0 ? "text-green-400" : t.pointDiff < 0 ? "text-red-400" : "text-muted"}`}>
                                    {t.pointDiff > 0 ? "+" : ""}{t.pointDiff}
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-right hidden xl:table-cell">
                                  <span className="text-xs font-mono">{t.team.elo}</span>
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
            })}
        </div>
      ) : activeTab === "teams" ? (
        <div className="rounded-xl border border-card-border overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-card border-b border-card-border">
                <SortHeader field="rank" label="#" tooltip="Overall rank by Elo rating" className="text-left !px-3 w-10" />
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-3 py-3">Team</th>
                <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 hidden sm:table-cell">Conf</th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 hidden md:table-cell">Record</th>
                <SortHeader field="adjEM" label="AdjEM" tooltip={METRIC_TOOLTIPS.adjEM} />
                <SortHeader field="adjOE" label="AdjO" tooltip={METRIC_TOOLTIPS.adjOE} className="hidden lg:table-cell" />
                <SortHeader field="adjDE" label="AdjD" tooltip={METRIC_TOOLTIPS.adjDE} className="hidden lg:table-cell" />
                <SortHeader field="barthag" label="Barthag" tooltip={METRIC_TOOLTIPS.barthag} className="hidden xl:table-cell" />
                <SortHeader field="luck" label="Luck" tooltip={METRIC_TOOLTIPS.luck} className="hidden xl:table-cell" />
                <SortHeader field="sos" label="SOS" tooltip={METRIC_TOOLTIPS.sos} className="hidden xl:table-cell" />
                <SortHeader field="tempo" label="Tempo" tooltip={METRIC_TOOLTIPS.tempo} className="hidden 2xl:table-cell" />
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-3 py-3">
                  <MetricLabel label="Trend" tooltip={METRIC_TOOLTIPS.trend} className="justify-end" />
                </th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {paginatedRankings.map((ranking) => (
                <Fragment key={ranking.team.id}>
                  <tr
                    className="border-b border-card-border/50 hover:bg-white/[0.02] transition-colors cursor-pointer"
                    onClick={() => setExpandedRow(expandedRow === ranking.team.id ? null : ranking.team.id)}
                  >
                    <td className="px-3 py-3">
                      <span className="text-sm font-mono text-muted">{ranking.rank}</span>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2.5">
                        {ranking.team.logo ? (
                          <img src={ranking.team.logo} alt="" className="w-7 h-7 object-contain shrink-0" />
                        ) : (
                          <div className="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center text-xs text-muted">—</div>
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
                    <td className="px-3 py-3 hidden sm:table-cell">
                      <span className="text-xs text-muted">{ranking.conference}</span>
                    </td>
                    <td className="px-3 py-3 text-right hidden md:table-cell">
                      <span className="text-sm text-muted">{ranking.record}</span>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span className="text-sm font-mono font-semibold">{signedFmt(ranking.adjEM)}</span>
                    </td>
                    <td className="px-3 py-3 text-right hidden lg:table-cell">
                      <span className="text-sm font-mono">{fmt(ranking.adjOE)}</span>
                    </td>
                    <td className="px-3 py-3 text-right hidden lg:table-cell">
                      <span className="text-sm font-mono">{fmt(ranking.adjDE)}</span>
                    </td>
                    <td className="px-3 py-3 text-right hidden xl:table-cell">
                      <span className="text-sm font-mono">{fmt(ranking.barthag, 3)}</span>
                    </td>
                    <td className="px-3 py-3 text-right hidden xl:table-cell">
                      <span className={`text-sm font-mono ${luckColor(ranking.luck)}`}>
                        {signedFmt(ranking.luck, 3)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right hidden xl:table-cell">
                      <span className="text-sm font-mono">{fmt(ranking.sos, 0)}</span>
                    </td>
                    <td className="px-3 py-3 text-right hidden 2xl:table-cell">
                      <span className="text-sm font-mono">{fmt(ranking.tempo, 1)}</span>
                    </td>
                    <td className="px-3 py-3 text-right">
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
                    <td className="px-3 py-3 text-right">
                      {expandedRow === ranking.team.id ? (
                        <ChevronUp size={14} className="text-muted" />
                      ) : (
                        <ChevronDown size={14} className="text-muted" />
                      )}
                    </td>
                  </tr>
                  {expandedRow === ranking.team.id && (
                    <tr key={`${ranking.team.id}-detail`} className="border-b border-card-border/50 bg-card/50">
                      <td colSpan={13} className="px-4 py-4">
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
                          <StatCell label="Elo" value={fmt(ranking.elo, 0)} tooltip={METRIC_TOOLTIPS.elo} />
                          <StatCell label="AdjEM" value={signedFmt(ranking.adjEM)} tooltip={METRIC_TOOLTIPS.adjEM} highlight />
                          <StatCell label="AdjO" value={fmt(ranking.adjOE)} tooltip={METRIC_TOOLTIPS.adjOE} />
                          <StatCell label="AdjD" value={fmt(ranking.adjDE)} tooltip={METRIC_TOOLTIPS.adjDE} />
                          <StatCell label="Barthag" value={fmt(ranking.barthag, 3)} tooltip={METRIC_TOOLTIPS.barthag} />
                          <StatCell label="Tempo" value={fmt(ranking.tempo, 1)} tooltip={METRIC_TOOLTIPS.tempo} />
                          <StatCell label="SOS" value={fmt(ranking.sos, 0)} tooltip={METRIC_TOOLTIPS.sos} />
                          <StatCell label="Luck" value={signedFmt(ranking.luck, 3)} tooltip={METRIC_TOOLTIPS.luck} valueClass={luckColor(ranking.luck)} />
                          <StatCell label="True Shooting" value={pctFmt(ranking.trueShooting)} tooltip={METRIC_TOOLTIPS.trueShooting} />
                          <StatCell label="Opp TS%" value={pctFmt(ranking.oppTrueShooting)} tooltip={METRIC_TOOLTIPS.oppTrueShooting} />
                          <StatCell label="3PA Rate" value={pctFmt(ranking.threePtRate)} tooltip={METRIC_TOOLTIPS.threePtRate} />
                          <StatCell label="AST:TO" value={fmt(ranking.astToRatio, 2)} tooltip={METRIC_TOOLTIPS.astToRatio} />
                          <StatCell label="DRB%" value={pctFmt(ranking.drbPct)} tooltip={METRIC_TOOLTIPS.drbPct} />
                          <StatCell label="STL%" value={fmt(ranking.stlPct)} tooltip={METRIC_TOOLTIPS.stlPct} />
                          <StatCell label="BLK%" value={fmt(ranking.blkPct)} tooltip={METRIC_TOOLTIPS.blkPct} />
                          <StatCell label="Close Games" value={ranking.closeRecord ?? "—"} tooltip={METRIC_TOOLTIPS.closeRecord} />
                          <StatCell label="Consistency" value={fmt(ranking.marginStdev)} tooltip={METRIC_TOOLTIPS.marginStdev} />
                          <StatCell label="Floor / Ceiling" value={`${signedFmt(ranking.floorEff)} / ${signedFmt(ranking.ceilingEff)}`} tooltip={METRIC_TOOLTIPS.floorCeiling} />
                          <StatCell label="Upset Risk" value={fmt(ranking.upsetVulnerability)} tooltip={METRIC_TOOLTIPS.upsetVulnerability} valueClass={vulnColor(ranking.upsetVulnerability)} />
                          <StatCell label="Pyth W%" value={pctFmt(ranking.pythWinPct)} tooltip={METRIC_TOOLTIPS.pythWinPct} />
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>

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
                      p === page ? "bg-accent text-white" : "text-muted hover:text-foreground hover:bg-white/5"
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
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden xl:table-cell">
                  <MetricLabel label="Avg AdjEM" tooltip="Average adjusted efficiency margin across all teams in the conference. Higher is better." className="justify-end" />
                </th>
                <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-4 py-3 hidden xl:table-cell">
                  <MetricLabel label="Avg Barthag" tooltip="Average probability of beating an average D1 team. Measures overall conference quality." className="justify-end" />
                </th>
              </tr>
            </thead>
            <tbody>
              {conferences.map((conf) => {
                const parity = Math.max(0, Math.min(1, (250 - conf.depth) / 150));
                return (
                  <tr key={conf.abbrev} className="border-b border-card-border/50 hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3"><span className="text-sm font-mono text-muted">{conf.rank}</span></td>
                    <td className="px-4 py-3"><span className="font-medium text-sm">{conf.name}</span></td>
                    <td className="px-4 py-3 text-right"><span className="text-sm font-mono font-semibold">{conf.avgElo}</span></td>
                    <td className="px-4 py-3 text-right hidden sm:table-cell">
                      <span className="text-sm font-mono text-accent">{(conf.ncWinRate * 100).toFixed(1)}%</span>
                    </td>
                    <td className="px-4 py-3 text-right hidden md:table-cell"><span className="text-sm text-muted">{conf.teams}</span></td>
                    <td className="px-4 py-3 text-right"><span className="text-sm font-semibold">{conf.tourneyBids}</span></td>
                    <td className="px-4 py-3 text-right hidden lg:table-cell">
                      <span className="text-sm font-mono font-semibold">{conf.top5Elo}</span>
                    </td>
                    <td className="px-4 py-3 text-right hidden lg:table-cell">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 h-1.5 bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-500 rounded-full" style={{ width: `${parity * 100}%` }} />
                        </div>
                        <span className="text-xs text-muted font-mono">{(parity * 100).toFixed(0)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right hidden xl:table-cell">
                      <span className={`text-sm font-mono font-semibold ${conf.avgAdjEM > 0 ? "text-emerald-400" : conf.avgAdjEM < 0 ? "text-red-400" : "text-muted"}`}>
                        {conf.avgAdjEM > 0 ? "+" : ""}{conf.avgAdjEM.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right hidden xl:table-cell">
                      <span className="text-sm font-mono">{conf.avgBarthag.toFixed(3)}</span>
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

function StatCell({
  label, value, tooltip, highlight, valueClass = "",
}: {
  label: string; value: string; tooltip: string; highlight?: boolean; valueClass?: string;
}) {
  return (
    <div className="px-3 py-2 rounded-lg bg-card border border-card-border/50">
      <MetricLabel label={label} tooltip={tooltip} className="text-xs text-muted uppercase tracking-wider mb-1" />
      <div className={`text-sm font-mono ${highlight ? "font-bold text-accent" : valueClass || "text-foreground"}`}>
        {value}
      </div>
    </div>
  );
}
