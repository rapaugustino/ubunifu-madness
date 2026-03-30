"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { useGender } from "@/hooks/useGender";
import {
  Trophy,
  BarChart3,
  GitCompareArrows,
  MessageSquare,
  Target,
  Activity,
  Clock,
  Tv,
  ChevronRight,
  TrendingUp,
  Award,
  Calendar,
} from "lucide-react";
import { API_URL } from "@/lib/api";
import type { Game } from "@/lib/types";
import { todayStr, yesterdayStr, tomorrowStr, displayDateLong, displayDateShort } from "@/lib/date-utils";

// ---------- Types ----------

interface AccuracyData {
  men: { total: number; correct: number; accuracy: number | null };
  women: { total: number; correct: number; accuracy: number | null };
  overall: { total: number; correct: number; accuracy: number | null };
}

interface BracketStatus {
  hasBracket: boolean;
  isComplete: boolean;
  currentRound: string;
  totalGamesPlayed: number;
  champion: { name: string; logo: string | null } | null;
}

interface RankedTeam {
  rank: number;
  team: {
    id: number;
    name: string;
    seed: number | null;
    logo: string | null;
  };
  record: string;
  elo: number;
}

// ---------- Helpers ----------

function todayDisplay(): string {
  return displayDateLong(new Date());
}

function yesterdayDisplay(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return displayDateShort(d);
}

function tomorrowDisplay(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return displayDateShort(d);
}

// ---------- Game row (compact ESPN-style) ----------

function GameRow({ game, compact }: { game: Game; compact?: boolean }) {
  const isFinal = game.status === "STATUS_FINAL";
  const isScheduled = game.status === "STATUS_SCHEDULED";
  const isLive = !isFinal && !isScheduled;

  const tipoff = isScheduled
    ? new Date(game.date).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  const pred = game.lockedPrediction;
  const favored = pred
    ? pred.probHome > pred.probAway
      ? "home"
      : "away"
    : null;
  const confidence = pred
    ? Math.round(Math.max(pred.probAway, pred.probHome) * 100)
    : null;

  return (
    <Link
      href={`/scores/${game.id}`}
      className={`block ${compact ? "p-2.5" : "p-3"} rounded-lg border transition-colors hover:border-accent/30 ${
        isLive
          ? "bg-card border-accent/40"
          : "bg-card border-card-border"
      }`}
    >
      {/* Tournament badge */}
      {game.headline && game.gameType !== "regular" && (
        <div className="mb-1.5">
          <span
            className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${
              game.gameType === "tourney"
                ? "bg-accent/15 text-accent"
                : "bg-purple-500/15 text-purple-400"
            }`}
          >
            {game.headline}
          </span>
        </div>
      )}

      {/* Team rows */}
      {[game.away, game.home].map((team, i) => {
        const isHome = i === 1;
        const opponent = isHome ? game.away : game.home;
        const isWinner = isFinal && team.score > opponent.score;
        const isFav = favored === (isHome ? "home" : "away");

        return (
          <div
            key={team.espnId}
            className={`flex items-center gap-2 ${compact ? "py-0.5" : "py-1"} ${
              isFinal && !isWinner ? "opacity-50" : ""
            }`}
          >
            {team.logo ? (
              <img src={team.logo} alt="" className={`${compact ? "w-4 h-4" : "w-5 h-5"} object-contain shrink-0`} />
            ) : (
              <div className={`${compact ? "w-4 h-4 text-[9px]" : "w-5 h-5 text-[10px]"} rounded bg-card-border flex items-center justify-center font-bold text-muted shrink-0`}>
                {team.abbreviation?.slice(0, 2) || "?"}
              </div>
            )}
            {team.rank && (
              <span className="text-xs text-muted font-mono w-4 text-right shrink-0">
                {team.rank}
              </span>
            )}
            <span className={`${compact ? "text-xs" : "text-sm"} flex-1 truncate ${isWinner ? "font-bold" : ""}`}>
              {team.abbreviation || team.name}
            </span>
            {isFav && !isFinal && (
              <span className="text-xs text-accent font-medium shrink-0">
                {confidence}%
              </span>
            )}
            <span
              className={`${compact ? "text-xs" : "text-sm"} font-mono w-8 text-right shrink-0 ${
                isWinner ? "font-bold" : "text-muted"
              }`}
            >
              {!isScheduled ? team.score : ""}
            </span>
          </div>
        );
      })}

      {/* Status bar */}
      <div className={`flex items-center justify-between ${compact ? "mt-1 pt-1" : "mt-1.5 pt-1.5"} border-t border-card-border/50`}>
        <div className="flex items-center gap-1.5 text-xs">
          {isLive && (
            <span className="flex items-center gap-1 text-accent font-medium">
              <Activity size={10} className="animate-pulse" />
              {game.statusDetail}
            </span>
          )}
          {isFinal && (
            <span className="text-muted">Final</span>
          )}
          {isScheduled && (
            <span className="flex items-center gap-1 text-muted">
              <Clock size={10} />
              {tipoff}
            </span>
          )}
          {game.broadcast && !isLive && (
            <span className="flex items-center gap-1 text-muted ml-1">
              <Tv size={9} />
              {game.broadcast}
            </span>
          )}
        </div>
        {pred?.resolved && (
          <span
            className={`text-xs font-medium ${
              pred.correct ? "text-green-400" : "text-red-400"
            }`}
          >
            {pred.correct ? "Correct" : "Wrong"}
          </span>
        )}
      </div>
    </Link>
  );
}

// ---------- Main component ----------

export default function Home() {
  const [gender] = useGender();
  const [accuracy, setAccuracy] = useState<AccuracyData | null>(null);
  const [games, setGames] = useState<Game[]>([]);
  const [gamesLoading, setGamesLoading] = useState(true);
  const [yesterdayGames, setYesterdayGames] = useState<Game[]>([]);
  const [tomorrowGames, setTomorrowGames] = useState<Game[]>([]);
  const [bracketStatus, setBracketStatus] = useState<BracketStatus | null>(null);
  const [topTeams, setTopTeams] = useState<RankedTeam[]>([]);

  // Fetch accuracy stats
  useEffect(() => {
    fetch(`${API_URL}/api/performance/homepage-stats`)
      .then((r) => r.json())
      .then(setAccuracy)
      .catch(() => {});
  }, []);

  // Fetch today's games
  const fetchGames = useCallback(
    (signal?: AbortSignal) => {
      const g = gender === "W" ? "W" : "M";
      setGamesLoading(true);
      fetch(`${API_URL}/api/scores?date=${todayStr()}&gender=${g}`, { signal })
        .then((r) => r.json())
        .then((data) => {
          setGames(data.games || []);
          setGamesLoading(false);
        })
        .catch((e) => {
          if (e.name !== "AbortError") setGamesLoading(false);
        });
    },
    [gender]
  );

  useEffect(() => {
    const ac = new AbortController();
    fetchGames(ac.signal);
    return () => ac.abort();
  }, [fetchGames]);

  // Fetch yesterday's games and tomorrow's games
  useEffect(() => {
    const ac = new AbortController();
    const g = gender === "W" ? "W" : "M";
    fetch(`${API_URL}/api/scores?date=${yesterdayStr()}&gender=${g}`, { signal: ac.signal })
      .then((r) => r.json())
      .then((data) => setYesterdayGames(data.games || []))
      .catch((e) => { if (e.name !== "AbortError") {} });
    fetch(`${API_URL}/api/scores?date=${tomorrowStr()}&gender=${g}`, { signal: ac.signal })
      .then((r) => r.json())
      .then((data) => setTomorrowGames(data.games || []))
      .catch((e) => { if (e.name !== "AbortError") {} });
    return () => ac.abort();
  }, [gender]);

  // Fetch bracket status
  useEffect(() => {
    const ac = new AbortController();
    const g = gender === "W" ? "women" : "men";
    fetch(`${API_URL}/api/bracket/full?gender=${g}&season=0`, { signal: ac.signal })
      .then((r) => r.json())
      .then((data) => {
        setBracketStatus({
          hasBracket: data.hasBracket,
          isComplete: data.isComplete,
          currentRound: data.currentRound,
          totalGamesPlayed: data.totalGamesPlayed,
          champion: data.champion,
        });
      })
      .catch((e) => { if (e.name !== "AbortError") {} });
    return () => ac.abort();
  }, [gender]);

  // Fetch top teams
  useEffect(() => {
    const ac = new AbortController();
    const g = gender === "W" ? "W" : "M";
    fetch(`${API_URL}/api/rankings/power?gender=${g}&limit=10`, { signal: ac.signal })
      .then((r) => r.json())
      .then((data) => setTopTeams(data.rankings || []))
      .catch((e) => { if (e.name !== "AbortError") {} });
    return () => ac.abort();
  }, [gender]);

  // Auto-refresh if live games
  useEffect(() => {
    const hasLive = games.some(
      (g) => g.status !== "STATUS_FINAL" && g.status !== "STATUS_SCHEDULED"
    );
    if (!hasLive) return;
    const interval = setInterval(() => fetchGames(), 30000);
    return () => clearInterval(interval);
  }, [games, fetchGames]);

  const liveGames = games.filter(
    (g) => g.status !== "STATUS_FINAL" && g.status !== "STATUS_SCHEDULED"
  );
  const finalGames = games.filter((g) => g.status === "STATUS_FINAL");
  const upcomingGames = games.filter((g) => g.status === "STATUS_SCHEDULED");
  const orderedGames = [...liveGames, ...upcomingGames, ...finalGames];

  const todayCorrect = finalGames.filter((g) => g.lockedPrediction?.correct === true).length;
  const todayResolved = finalGames.filter((g) => g.lockedPrediction?.resolved).length;

  const yesterdayFinals = yesterdayGames.filter((g) => g.status === "STATUS_FINAL");
  const tomorrowScheduled = tomorrowGames.filter((g) => g.status === "STATUS_SCHEDULED");

  const genderLabel = gender === "W" ? "Women's" : "Men's";

  return (
    <div className="min-h-screen">
      {/* Top ticker bar */}
      <div className="border-b border-card-border bg-card/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2 flex items-center justify-between text-sm">
          <div className="flex items-center gap-3 min-w-0">
            <span className="font-bold text-accent shrink-0">
              {genderLabel} Basketball
            </span>
            {bracketStatus?.hasBracket && (
              <span className="text-muted truncate hidden sm:inline">
                NCAA Tournament &middot; {bracketStatus.currentRound} &middot; {bracketStatus.totalGamesPlayed}/67 games
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {accuracy && (() => {
              const ctx = gender === "W" ? accuracy.women : accuracy.men;
              return ctx.accuracy ? (
                <span className="text-muted hidden sm:inline">
                  Model: <span className="text-foreground font-medium">{(ctx.accuracy * 100).toFixed(1)}%</span>
                  <span className="text-muted ml-1">({ctx.correct}/{ctx.total})</span>
                </span>
              ) : null;
            })()}
            {todayResolved > 0 && (
              <span className="text-muted">
                Today: <span className={`font-medium ${todayCorrect / todayResolved >= 0.7 ? "text-green-400" : "text-foreground"}`}>
                  {todayCorrect}/{todayResolved}
                </span>
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
        {/* Main grid: Content (left) + Sidebar (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-5">

          {/* ─── Left column ─── */}
          <div className="space-y-6">
            {/* Today's games */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h1 className="text-lg sm:text-xl font-bold">{genderLabel} Scores</h1>
                  <p className="text-xs sm:text-sm text-muted">{todayDisplay()}</p>
                </div>
                <div className="flex items-center gap-2">
                  {liveGames.length > 0 && (
                    <span className="flex items-center gap-1 text-xs text-accent font-medium">
                      <Activity size={12} className="animate-pulse" />
                      {liveGames.length} live
                    </span>
                  )}
                  <Link
                    href="/scores"
                    className="text-xs text-muted hover:text-accent transition-colors flex items-center gap-0.5"
                  >
                    All dates <ChevronRight size={12} />
                  </Link>
                </div>
              </div>

              {gamesLoading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[...Array(4)].map((_, i) => (
                    <div
                      key={i}
                      className="bg-card border border-card-border rounded-lg p-3 h-[110px] animate-pulse"
                    />
                  ))}
                </div>
              ) : games.length === 0 ? (
                <div className="bg-card border border-card-border rounded-lg p-8 text-center">
                  <Calendar size={24} className="text-muted mx-auto mb-2" />
                  <p className="text-sm text-muted mb-2">No {genderLabel.toLowerCase()} games today.</p>
                  <Link href="/scores" className="text-sm text-accent hover:underline">
                    Browse other dates
                  </Link>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {orderedGames.map((game) => (
                    <GameRow key={game.id} game={game} />
                  ))}
                </div>
              )}
            </div>

            {/* Bracket status - shown inline on left when there are few games */}
            {bracketStatus?.hasBracket && (
              <div className="bg-card border border-card-border rounded-lg overflow-hidden lg:hidden">
                <div className="px-4 py-3 border-b border-card-border flex items-center justify-between">
                  <h2 className="text-sm font-bold flex items-center gap-1.5">
                    <Trophy size={14} className="text-accent" />
                    {genderLabel} Tournament
                  </h2>
                  <Link href="/bracket" className="text-xs text-accent hover:underline">
                    Full Bracket
                  </Link>
                </div>
                <div className="p-4 flex items-center justify-between gap-4">
                  {bracketStatus.champion ? (
                    <div className="flex items-center gap-3">
                      {bracketStatus.champion.logo && (
                        <img src={bracketStatus.champion.logo} alt="" className="w-8 h-8 object-contain" />
                      )}
                      <div>
                        <div className="text-sm font-bold">{bracketStatus.champion.name}</div>
                        <div className="text-xs text-muted">National Champion</div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-6">
                      <div>
                        <div className="text-sm font-medium">{bracketStatus.currentRound}</div>
                        <div className="text-xs text-muted">{bracketStatus.totalGamesPlayed}/67 games</div>
                      </div>
                      <div className="w-24 h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-accent rounded-full"
                          style={{ width: `${(bracketStatus.totalGamesPlayed / 67) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                  <Link
                    href="/bracket"
                    className="px-3 py-2 bg-accent/10 text-accent rounded-lg text-sm font-medium hover:bg-accent/20 transition-colors shrink-0"
                  >
                    {bracketStatus.champion ? "View" : "Bracket"}
                  </Link>
                </div>
              </div>
            )}

            {/* Yesterday's results */}
            {yesterdayFinals.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold text-muted flex items-center gap-1.5">
                    <Calendar size={14} />
                    Yesterday &middot; {yesterdayDisplay()}
                  </h2>
                  <Link
                    href={`/scores`}
                    className="text-xs text-muted hover:text-accent transition-colors"
                  >
                    Full results
                  </Link>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {yesterdayFinals.slice(0, 6).map((game) => (
                    <GameRow key={game.id} game={game} compact />
                  ))}
                </div>
                {yesterdayFinals.length > 6 && (
                  <Link
                    href="/scores"
                    className="block text-center text-xs text-muted hover:text-accent mt-2 transition-colors"
                  >
                    +{yesterdayFinals.length - 6} more games
                  </Link>
                )}
              </div>
            )}

            {/* Tomorrow's upcoming games */}
            {tomorrowScheduled.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold text-muted flex items-center gap-1.5">
                    <Clock size={14} />
                    Upcoming &middot; {tomorrowDisplay()}
                  </h2>
                  <Link
                    href="/scores"
                    className="text-xs text-muted hover:text-accent transition-colors"
                  >
                    Full schedule
                  </Link>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {tomorrowScheduled.slice(0, 6).map((game) => (
                    <GameRow key={game.id} game={game} compact />
                  ))}
                </div>
                {tomorrowScheduled.length > 6 && (
                  <Link
                    href="/scores"
                    className="block text-center text-xs text-muted hover:text-accent mt-2 transition-colors"
                  >
                    +{tomorrowScheduled.length - 6} more games
                  </Link>
                )}
              </div>
            )}

            {/* Quick actions (mobile: 2x2 grid; desktop: 4 across) */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <Link
                href="/bracket"
                className="flex flex-col items-center gap-1.5 p-3 bg-card border border-card-border rounded-lg hover:border-accent/30 transition-colors text-center"
              >
                <Trophy size={18} className="text-accent" />
                <span className="text-sm font-medium">Bracket</span>
              </Link>
              <Link
                href="/compare"
                className="flex flex-col items-center gap-1.5 p-3 bg-card border border-card-border rounded-lg hover:border-accent/30 transition-colors text-center"
              >
                <GitCompareArrows size={18} className="text-blue-400" />
                <span className="text-sm font-medium">Compare</span>
              </Link>
              <Link
                href="/chat"
                className="flex flex-col items-center gap-1.5 p-3 bg-card border border-card-border rounded-lg hover:border-accent/30 transition-colors text-center"
              >
                <MessageSquare size={18} className="text-purple-400" />
                <span className="text-sm font-medium">Ask Agent</span>
              </Link>
              <Link
                href="/players"
                className="flex flex-col items-center gap-1.5 p-3 bg-card border border-card-border rounded-lg hover:border-accent/30 transition-colors text-center"
              >
                <Award size={18} className="text-green-400" />
                <span className="text-sm font-medium">Players</span>
              </Link>
            </div>
          </div>

          {/* ─── Right sidebar (desktop only content marked, mobile has inline versions) ─── */}
          <div className="space-y-4">
            {/* Bracket status card — desktop only (mobile version is inline above) */}
            {bracketStatus?.hasBracket && (
              <div className="hidden lg:block bg-card border border-card-border rounded-lg overflow-hidden">
                <div className="px-3 py-2.5 border-b border-card-border flex items-center justify-between">
                  <h2 className="text-sm font-bold flex items-center gap-1.5">
                    <Trophy size={13} className="text-accent" />
                    {genderLabel} Tournament
                  </h2>
                  <Link href="/bracket" className="text-xs text-accent hover:underline">
                    Bracket
                  </Link>
                </div>
                <div className="p-3">
                  {bracketStatus.champion ? (
                    <div className="flex items-center gap-3">
                      {bracketStatus.champion.logo && (
                        <img src={bracketStatus.champion.logo} alt="" className="w-8 h-8 object-contain" />
                      )}
                      <div>
                        <div className="text-sm font-bold">{bracketStatus.champion.name}</div>
                        <div className="text-xs text-muted">National Champion</div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted">Round</span>
                        <span className="font-medium">{bracketStatus.currentRound}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted">Games</span>
                        <span className="font-medium">{bracketStatus.totalGamesPlayed}/67</span>
                      </div>
                      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-accent rounded-full transition-all"
                          style={{ width: `${(bracketStatus.totalGamesPlayed / 67) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                  <Link
                    href="/bracket"
                    className="mt-2.5 block w-full text-center px-3 py-1.5 bg-accent/10 text-accent rounded-lg text-xs font-medium hover:bg-accent/20 transition-colors"
                  >
                    {bracketStatus.champion ? "View Bracket" : "Build Your Bracket"}
                  </Link>
                </div>
              </div>
            )}

            {/* Model accuracy card */}
            <div className="bg-card border border-card-border rounded-lg overflow-hidden">
              <div className="px-3 py-2.5 border-b border-card-border flex items-center justify-between">
                <h2 className="text-sm font-bold flex items-center gap-1.5">
                  <Target size={13} className="text-green-400" />
                  Model Accuracy
                </h2>
                <Link href="/performance" className="text-xs text-accent hover:underline">
                  Details
                </Link>
              </div>
              <div className="p-3 space-y-2.5">
                {accuracy ? (() => {
                  const current = gender === "W" ? accuracy.women : accuracy.men;
                  const other = gender === "W" ? accuracy.men : accuracy.women;
                  const currentLabel = gender === "W" ? "Women's" : "Men's";
                  const otherLabel = gender === "W" ? "Men's" : "Women's";
                  const currentColor = gender === "W" ? "text-pink-400" : "text-blue-400";
                  const otherColor = gender === "W" ? "text-blue-400" : "text-pink-400";
                  return (
                    <>
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-sm font-medium">{currentLabel}</span>
                          <span className="text-xs text-muted ml-1.5">{current.correct}/{current.total} games</span>
                        </div>
                        <span className={`text-lg font-bold ${currentColor}`}>
                          {current.accuracy
                            ? `${(current.accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between bg-white/[0.02] rounded-lg px-2.5 py-1.5">
                        <div>
                          <span className="text-xs text-muted">{otherLabel}</span>
                          <span className="text-xs text-muted ml-1.5">{other.correct}/{other.total}</span>
                        </div>
                        <span className={`text-sm font-bold ${otherColor}`}>
                          {other.accuracy
                            ? `${(other.accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between bg-white/[0.02] rounded-lg px-2.5 py-1.5">
                        <div>
                          <span className="text-xs text-muted">Overall</span>
                          <span className="text-xs text-muted ml-1.5">{accuracy.overall.correct}/{accuracy.overall.total}</span>
                        </div>
                        <span className="text-sm font-bold text-accent">
                          {accuracy.overall.accuracy
                            ? `${(accuracy.overall.accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </span>
                      </div>
                    </>
                  );
                })() : (
                  <div className="text-xs text-muted">Loading...</div>
                )}
              </div>
            </div>

            {/* Top 10 rankings */}
            <div className="bg-card border border-card-border rounded-lg overflow-hidden">
              <div className="px-3 py-2.5 border-b border-card-border flex items-center justify-between">
                <h2 className="text-sm font-bold flex items-center gap-1.5">
                  <BarChart3 size={13} className="text-blue-400" />
                  Power Rankings
                </h2>
                <Link href="/dashboard" className="text-xs text-accent hover:underline">
                  Full Rankings
                </Link>
              </div>
              <div>
                {topTeams.length > 0 ? (
                  topTeams.map((t, i) => (
                    <Link
                      key={t.team.id}
                      href={`/teams/${t.team.id}`}
                      className={`flex items-center gap-2 px-3 py-1.5 hover:bg-white/[0.03] transition-colors ${
                        i < topTeams.length - 1 ? "border-b border-card-border/50" : ""
                      }`}
                    >
                      <span className="text-xs font-mono text-muted w-4 text-right shrink-0">
                        {t.rank}
                      </span>
                      {t.team.logo ? (
                        <img src={t.team.logo} alt="" className="w-4 h-4 object-contain shrink-0" />
                      ) : (
                        <div className="w-4 h-4 rounded bg-card-border shrink-0" />
                      )}
                      <span className="text-sm font-medium truncate flex-1">{t.team.name}</span>
                      {t.team.seed && (
                        <span className="text-[10px] text-accent font-medium px-1 py-0.5 rounded bg-accent/10 shrink-0">
                          {t.team.seed}
                        </span>
                      )}
                      <span className="text-xs text-muted font-mono shrink-0">
                        {t.record}
                      </span>
                    </Link>
                  ))
                ) : (
                  <div className="p-3 text-xs text-muted">Loading...</div>
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
