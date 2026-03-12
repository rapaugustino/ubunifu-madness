"use client";

import { useState, useEffect, useCallback } from "react";
import { useGender } from "@/hooks/useGender";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { MetricLabel, METRIC_TOOLTIPS } from "@/components/Tooltip";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CATEGORIES = [
  { key: "ppg", label: "Points", unit: "PPG", tip: "ppg" },
  { key: "rpg", label: "Rebounds", unit: "RPG", tip: "rpg" },
  { key: "apg", label: "Assists", unit: "APG", tip: "apg" },
  { key: "spg", label: "Steals", unit: "SPG", tip: "spg" },
  { key: "bpg", label: "Blocks", unit: "BPG", tip: "bpg" },
  { key: "fg_pct", label: "FG%", unit: "FG%", tip: "fgPct" },
  { key: "fg3_pct", label: "3PT%", unit: "3P%", tip: "fg3Pct" },
  { key: "ft_pct", label: "FT%", unit: "FT%", tip: "ftPct" },
] as const;

type CategoryKey = (typeof CATEGORIES)[number]["key"];

const MIN_GAMES_OPTIONS = [5, 10, 15, 20];
const PER_PAGE = 25;

// Secondary stat columns shown alongside the primary category.
// We skip whichever stat matches the active category to avoid duplication.
const SECONDARY_STATS = [
  { key: "ppg", label: "PPG", tip: "ppg", getValue: (p: PlayerLeader) => formatStat(p.stats.ppg), hide: "md" },
  { key: "rpg", label: "RPG", tip: "rpg", getValue: (p: PlayerLeader) => formatStat(p.stats.rpg), hide: "md" },
  { key: "apg", label: "APG", tip: "apg", getValue: (p: PlayerLeader) => formatStat(p.stats.apg), hide: "lg" },
  { key: "fg_pct", label: "FG%", tip: "fgPct", getValue: (p: PlayerLeader) => formatPct(p.stats.fgPct), hide: "lg" },
] as const;

interface PlayerLeader {
  rank: number;
  playerId: number;
  name: string;
  position: string;
  headshot: string | null;
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  teamColor: string | null;
  gamesPlayed: number;
  statValue: number;
  stats: {
    ppg: number | null;
    rpg: number | null;
    apg: number | null;
    mpg: number | null;
    fgPct: number | null;
    fg3Pct: number | null;
    ftPct: number | null;
    spg: number | null;
    bpg: number | null;
    importanceScore: number | null;
  };
}

function formatPct(v: number | null): string {
  if (v == null) return "—";
  return (v * 100).toFixed(1) + "%";
}

function formatStat(v: number | null, decimals = 1): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

export default function PlayersPage() {
  const [gender] = useGender();
  const [category, setCategory] = useState<CategoryKey>("ppg");
  const [minGames, setMinGames] = useState(10);
  const [page, setPage] = useState(1);
  const [players, setPlayers] = useState<PlayerLeader[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const totalPages = Math.ceil(total / PER_PAGE);

  const fetchLeaderboard = useCallback(async () => {
    setLoading(true);
    try {
      const offset = (page - 1) * PER_PAGE;
      const res = await fetch(
        `${API_URL}/api/players/leaderboard?gender=${gender}&category=${category}&min_games=${minGames}&limit=${PER_PAGE}&offset=${offset}`
      );
      const data = await res.json();
      setPlayers(data.players || []);
      setTotal(data.total || 0);
    } catch {
      setPlayers([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [gender, category, minGames, page]);

  useEffect(() => {
    fetchLeaderboard();
  }, [fetchLeaderboard]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [gender, category, minGames]);

  const currentCategory = CATEGORIES.find((c) => c.key === category)!;
  const isPct = ["fg_pct", "fg3_pct", "ft_pct"].includes(category);

  return (
    <div className="min-h-screen pt-24 pb-12">
      <div className="max-w-[90rem] mx-auto px-4 sm:px-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold mb-1">Player Leaderboard</h1>
          <p className="text-sm text-muted">
            Top performers across {gender === "M" ? "men's" : "women's"} NCAA basketball
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          {/* Category pills */}
          <div className="flex flex-wrap gap-1">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.key}
                onClick={() => setCategory(cat.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  category === cat.key
                    ? "bg-accent text-white"
                    : "bg-card border border-card-border text-muted hover:text-foreground"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Min games dropdown */}
          <select
            value={minGames}
            onChange={(e) => setMinGames(Number(e.target.value))}
            className="bg-card border border-card-border rounded-lg px-3 py-1.5 text-xs font-medium text-foreground"
          >
            {MIN_GAMES_OPTIONS.map((n) => (
              <option key={n} value={n}>
                Min {n} games
              </option>
            ))}
          </select>
        </div>

        {/* Table */}
        <div className="bg-card border border-card-border rounded-xl overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : players.length === 0 ? (
            <div className="text-center py-20 text-muted text-sm">
              No players found. {gender === "W" && "Women's player data may still be loading."}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-card-border bg-card/80">
                    <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 w-12">#</th>
                    <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-3 py-3">Player</th>
                    <th className="text-left text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 hidden sm:table-cell">Team</th>
                    <th className="text-center text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 w-12">
                      <MetricLabel label="GP" tooltip={METRIC_TOOLTIPS.gp} className="justify-center" />
                    </th>
                    <th className="text-right text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 w-20">
                      <MetricLabel label={currentCategory.unit} tooltip={METRIC_TOOLTIPS[currentCategory.tip]} className="justify-end" />
                    </th>
                    {SECONDARY_STATS.filter((s) => s.key !== category).map((s) => (
                      <th key={s.key} className={`text-right text-xs font-medium text-muted uppercase tracking-wider px-3 py-3 hidden ${s.hide}:table-cell w-16`}>
                        <MetricLabel label={s.label} tooltip={METRIC_TOOLTIPS[s.tip]} className="justify-end" />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {players.map((p) => (
                    <tr
                      key={p.playerId}
                      className="border-b border-card-border/50 hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-3 py-3">
                        <span className="text-sm font-mono text-muted">{p.rank}</span>
                      </td>
                      <td className="px-3 py-3">
                        <Link href={`/teams/${p.teamId}`} className="flex items-center gap-2.5 group">
                          {p.headshot ? (
                            <img
                              src={p.headshot}
                              alt=""
                              className="w-8 h-8 rounded-full object-cover bg-white/5 shrink-0"
                            />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-xs text-muted shrink-0">
                              —
                            </div>
                          )}
                          <div>
                            <div className="font-medium text-sm group-hover:text-accent transition-colors">
                              {p.name}
                            </div>
                            <div className="text-xs text-muted">
                              {p.position || "—"}
                              <span className="sm:hidden"> · {p.teamName}</span>
                            </div>
                          </div>
                        </Link>
                      </td>
                      <td className="px-3 py-3 hidden sm:table-cell">
                        <div className="flex items-center gap-2">
                          {p.teamLogo && (
                            <img src={p.teamLogo} alt="" className="w-5 h-5 object-contain shrink-0" />
                          )}
                          <span className="text-xs text-muted">{p.teamName}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-center">
                        <span className="text-sm text-muted">{p.gamesPlayed}</span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="text-sm font-semibold text-accent">
                          {isPct ? formatPct(p.statValue) : formatStat(p.statValue)}
                        </span>
                      </td>
                      {/* Secondary stats — skip active category */}
                      {SECONDARY_STATS.filter((s) => s.key !== category).map((s) => (
                        <td key={s.key} className={`px-3 py-3 text-right hidden ${s.hide}:table-cell`}>
                          <span className="text-xs text-muted">{s.getValue(p)}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-card-border">
              <span className="text-xs text-muted">
                {((page - 1) * PER_PAGE) + 1}–{Math.min(page * PER_PAGE, total)} of {total}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-xs text-muted px-2">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
