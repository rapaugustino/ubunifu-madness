"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Tv, Clock, Activity, ArrowRight, RefreshCw } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TeamScore {
  espnId: number;
  name: string;
  abbreviation: string;
  logo: string | null;
  color: string | null;
  score: number;
  homeAway: string;
  record: string | null;
  rank: number | null;
  kaggleId: number | null;
  elo: number | null;
}

interface Game {
  id: string;
  date: string;
  venue: string | null;
  status: string;
  statusDetail: string;
  clock: string | null;
  period: number | null;
  broadcast: string | null;
  away: TeamScore;
  home: TeamScore;
  winProb: { away: number; home: number } | null;
}

function formatDate(d: Date): string {
  // Use local date parts to avoid UTC timezone shift
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
}

function displayDate(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function GameCard({ game }: { game: Game }) {
  const isLive = game.status === "STATUS_IN_PROGRESS";
  const isFinal = game.status === "STATUS_FINAL";
  const isScheduled = game.status === "STATUS_SCHEDULED";

  const tipoff = isScheduled
    ? new Date(game.date).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  const canCompare = game.away.kaggleId && game.home.kaggleId;
  const compareHref = canCompare
    ? `/compare?teamA=${game.away.kaggleId}&teamB=${game.home.kaggleId}`
    : undefined;

  const card = (
    <div
      className={`bg-card border rounded-xl p-4 transition-colors ${
        isLive ? "border-accent/50" : "border-card-border"
      } ${canCompare ? "hover:border-accent/40 cursor-pointer" : ""}`}
    >
      {/* Status bar */}
      <div className="flex items-center justify-between mb-3 text-xs">
        <div className="flex items-center gap-2">
          {isLive && (
            <span className="flex items-center gap-1 text-accent font-medium">
              <Activity size={12} className="animate-pulse" />
              LIVE
            </span>
          )}
          {isFinal && <span className="text-muted">Final</span>}
          {isScheduled && (
            <span className="flex items-center gap-1 text-muted">
              <Clock size={12} />
              {tipoff}
            </span>
          )}
          {isLive && (
            <span className="text-muted">
              {game.statusDetail}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {game.broadcast && (
            <span className="flex items-center gap-1 text-muted">
              <Tv size={12} />
              {game.broadcast}
            </span>
          )}
          {canCompare && (
            <ArrowRight size={12} className="text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
          )}
        </div>
      </div>

      {/* Teams */}
      <div className="space-y-2">
        <TeamRow team={game.away} isFinal={isFinal} isWinner={isFinal && game.away.score > game.home.score} />
        <TeamRow team={game.home} isFinal={isFinal} isWinner={isFinal && game.home.score > game.away.score} />
      </div>

      {/* Our model's prediction */}
      {game.winProb && (
        <div className="mt-3 pt-3 border-t border-card-border">
          <div className="flex items-center justify-between text-xs text-muted mb-1">
            <span>{game.away.abbreviation} {(game.winProb.away * 100).toFixed(0)}%</span>
            <span className="text-[10px]">ML MODEL</span>
            <span>{game.home.abbreviation} {(game.winProb.home * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden flex">
            <div
              className="h-full bg-accent/70 rounded-l-full"
              style={{ width: `${game.winProb.away * 100}%` }}
            />
            <div
              className="h-full bg-white/20 rounded-r-full"
              style={{ width: `${game.winProb.home * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );

  if (compareHref) {
    return <Link href={compareHref} className="group block">{card}</Link>;
  }
  return card;
}

function TeamRow({
  team,
  isFinal,
  isWinner,
}: {
  team: TeamScore;
  isFinal: boolean;
  isWinner: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2.5 min-w-0">
        {team.logo ? (
          <img src={team.logo} alt="" className="w-6 h-6 object-contain shrink-0" />
        ) : (
          <div className="w-6 h-6 rounded bg-white/10 shrink-0" />
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            {team.rank && team.rank <= 25 && (
              <span className="text-xs text-accent font-medium">#{team.rank}</span>
            )}
            <span
              className={`text-sm truncate ${
                isWinner ? "font-bold" : isFinal ? "text-muted" : "font-medium"
              }`}
            >
              {team.name}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-muted">
            {team.record && <span>{team.record}</span>}
            {team.elo && <span>Elo {team.elo.toFixed(0)}</span>}
          </div>
        </div>
      </div>
      <span
        className={`text-lg tabular-nums ${
          isWinner ? "font-bold" : isFinal ? "text-muted" : "font-semibold"
        }`}
      >
        {team.score || (isFinal ? "0" : "")}
      </span>
    </div>
  );
}

export default function ScoresPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [date, setDate] = useState(new Date());
  const [gender, setGender] = useState<"M" | "W">("M");
  const isInitial = useRef(true);

  const fetchScores = useCallback(async (background = false) => {
    if (!background) setLoading(true);
    else setRefreshing(true);
    try {
      const dateStr = formatDate(date);
      const res = await fetch(`${API_URL}/api/scores?date=${dateStr}&gender=${gender}`);
      const data = await res.json();
      setGames(data.games || []);
      setLastUpdated(new Date());
    } catch {
      if (!background) setGames([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [date, gender]);

  useEffect(() => {
    isInitial.current = true;
    fetchScores(false);
  }, [fetchScores]);

  // Auto-refresh every 30s if any games are live (background, no loading flash)
  useEffect(() => {
    const hasLive = games.some((g) => g.status === "STATUS_IN_PROGRESS");
    if (!hasLive) return;
    const interval = setInterval(() => fetchScores(true), 30000);
    return () => clearInterval(interval);
  }, [games, fetchScores]);

  // Refresh on window focus (if data is >60s old)
  useEffect(() => {
    const onFocus = () => {
      if (lastUpdated && Date.now() - lastUpdated.getTime() > 60000) {
        fetchScores(true);
      }
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [fetchScores, lastUpdated]);

  const changeDate = (delta: number) => {
    setDate((d) => {
      const next = new Date(d);
      next.setDate(next.getDate() + delta);
      return next;
    });
  };

  const liveGames = games.filter((g) => g.status === "STATUS_IN_PROGRESS");
  const finalGames = games.filter((g) => g.status === "STATUS_FINAL");
  const scheduledGames = games.filter((g) => g.status === "STATUS_SCHEDULED");

  return (
    <div className="min-h-screen max-w-5xl mx-auto px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">Scores</h1>
            {refreshing && (
              <RefreshCw size={14} className="text-accent animate-spin" />
            )}
          </div>
          <p className="text-muted text-sm">
            Live games with ML predictions
            {lastUpdated && (
              <span className="ml-2 text-xs">
                &middot; Updated {lastUpdated.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
              </span>
            )}
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

      {/* Date picker */}
      <div className="flex items-center justify-center gap-4 mb-6">
        <button
          onClick={() => changeDate(-1)}
          className="p-2 rounded-lg bg-card border border-card-border hover:border-accent/30 transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm font-medium min-w-[240px] text-center">
          {displayDate(date)}
        </span>
        <button
          onClick={() => changeDate(1)}
          className="p-2 rounded-lg bg-card border border-card-border hover:border-accent/30 transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {loading ? (
        <div className="text-center text-muted py-20">Loading scores...</div>
      ) : games.length === 0 ? (
        <div className="text-center text-muted py-20">No games scheduled for this date.</div>
      ) : (
        <div className="space-y-6">
          {/* Live games first */}
          {liveGames.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-accent mb-3 flex items-center gap-1.5">
                <Activity size={14} className="animate-pulse" />
                In Progress ({liveGames.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {liveGames.map((g) => (
                  <GameCard key={g.id} game={g} />
                ))}
              </div>
            </div>
          )}

          {/* Final games */}
          {finalGames.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-muted mb-3">
                Final ({finalGames.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {finalGames.map((g) => (
                  <GameCard key={g.id} game={g} />
                ))}
              </div>
            </div>
          )}

          {/* Scheduled games */}
          {scheduledGames.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-muted mb-3">
                Upcoming ({scheduledGames.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {scheduledGames.map((g) => (
                  <GameCard key={g.id} game={g} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
