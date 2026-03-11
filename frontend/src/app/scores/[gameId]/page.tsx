"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Activity,
  Clock,
  Tv,
  Check,
  X,
  Lock,
  GitCompareArrows,
  RefreshCw,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ── Shared types (mirror scores page) ── */

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

interface LockedPrediction {
  probAway: number;
  probHome: number;
  source: string;
  lockedAt: string | null;
  resolved: boolean;
  correct: boolean | null;
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
  gameType: "regular" | "conf_tourney" | "tourney" | null;
  headline: string | null;
  winProb: { away: number; home: number } | null;
  lockedPrediction: LockedPrediction | null;
}

interface BoxTeam {
  name: string;
  abbreviation: string;
  logo: string;
  stats: Record<string, string>;
}

interface BoxPlayer {
  espnId: number | null;
  team: string;
  name: string;
  position: string;
  stats: Record<string, string>;
}

interface BoxScore {
  gameId: string;
  teams: BoxTeam[];
  players: BoxPlayer[];
}

/* ── Helper: find today's date string ── */
function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
}

/* ── Page component ── */

export default function GameDetailPage() {
  const params = useParams();
  const gameId = params.gameId as string;

  const [game, setGame] = useState<Game | null>(null);
  const [box, setBox] = useState<BoxScore | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Fetch the scoreboard for today (and nearby dates) to find this game,
     then fetch the box score separately. */
  const fetchGame = useCallback(
    async (background = false) => {
      if (!background) setLoading(true);
      else setRefreshing(true);

      try {
        // Try today and yesterday (game might span midnight)
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        let found: Game | null = null;
        let foundGender = "M";
        for (const d of [today, yesterday, tomorrow]) {
          const dateStr = formatDate(d);
          // Try both genders
          for (const g of ["M", "W"]) {
            const res = await fetch(
              `${API_URL}/api/scores?date=${dateStr}&gender=${g}`
            );
            if (!res.ok) continue;
            const data = await res.json();
            const match = (data.games || []).find(
              (gm: Game) => String(gm.id) === String(gameId)
            );
            if (match) {
              found = match;
              foundGender = g;
              break;
            }
          }
          if (found) break;
        }

        if (found) {
          setGame(found);
          setError(null);
        } else if (!background) {
          setError("Game not found");
        }

        // Always try box score (use detected gender)
        const boxRes = await fetch(`${API_URL}/api/scores/${gameId}?gender=${foundGender}`);
        if (boxRes.ok) {
          const boxData = await boxRes.json();
          setBox(boxData);
        }
      } catch {
        if (!background) setError("Failed to load game data");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [gameId]
  );

  useEffect(() => {
    fetchGame(false);
  }, [fetchGame]);

  // Auto-refresh every 15s if game is live
  useEffect(() => {
    if (!game) return;
    const isLive =
      game.status !== "STATUS_FINAL" && game.status !== "STATUS_SCHEDULED";
    if (!isLive) return;
    const interval = setInterval(() => fetchGame(true), 15000);
    return () => clearInterval(interval);
  }, [game, fetchGame]);

  /* ── Render states ── */

  if (loading) {
    return (
      <div className="min-h-screen max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <div className="text-center text-muted py-20">Loading game...</div>
      </div>
    );
  }

  if (error || !game) {
    return (
      <div className="min-h-screen max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <Link
          href="/scores"
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft size={14} />
          Back to Scores
        </Link>
        <div className="text-center text-muted py-20">
          {error || "Game not found"}
        </div>
      </div>
    );
  }

  const isFinal = game.status === "STATUS_FINAL";
  const isScheduled = game.status === "STATUS_SCHEDULED";
  const isLive = !isFinal && !isScheduled;

  const awayWon = isFinal && game.away.score > game.home.score;
  const homeWon = isFinal && game.home.score > game.away.score;

  const canCompare = game.away.kaggleId && game.home.kaggleId;
  const compareHref = canCompare
    ? `/compare?teamA=${game.away.kaggleId}&teamB=${game.home.kaggleId}`
    : null;

  const tipoff = isScheduled
    ? new Date(game.date).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  /* ── Prediction helpers ── */
  const wp = game.winProb;
  const confidence = wp ? Math.max(wp.away, wp.home) : 0;
  const isTossup = wp ? confidence < 0.55 : false;
  const modelPickedAway = wp ? wp.away > wp.home : false;
  const actualWinnerAway = game.away.score > game.home.score;
  const modelCorrect =
    isFinal && wp
      ? modelPickedAway === actualWinnerAway
      : null;

  /* ── Box score: group players by team ── */
  const playersByTeam: Record<string, BoxPlayer[]> = {};
  if (box?.players) {
    for (const p of box.players) {
      if (!playersByTeam[p.team]) playersByTeam[p.team] = [];
      playersByTeam[p.team].push(p);
    }
  }

  // Stat columns we want to display (common basketball stats)
  const statColumns = ["MIN", "FG", "3PT", "FT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF", "PTS"];

  return (
    <div className="min-h-screen max-w-4xl mx-auto px-4 sm:px-6 py-8">
      {/* Back link */}
      <div className="flex items-center justify-between mb-6">
        <Link
          href="/scores"
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground transition-colors"
        >
          <ArrowLeft size={14} />
          Back to Scores
        </Link>
        {refreshing && <RefreshCw size={14} className="text-accent animate-spin" />}
      </div>

      {/* ── Main scoreboard card ── */}
      <div className="bg-card border border-card-border rounded-xl p-6 mb-6">
        {/* Status */}
        <div className="flex items-center justify-center gap-3 mb-6 text-sm">
          {isLive && (
            <span className="flex items-center gap-1.5 text-accent font-semibold">
              <Activity size={14} className="animate-pulse" />
              LIVE &mdash; {game.statusDetail}
            </span>
          )}
          {isFinal && <span className="text-muted font-medium">Final</span>}
          {isScheduled && (
            <span className="flex items-center gap-1.5 text-muted">
              <Clock size={14} />
              {tipoff}
            </span>
          )}
          {game.broadcast && (
            <>
              <span className="text-card-border">|</span>
              <span className="flex items-center gap-1 text-muted text-xs">
                <Tv size={12} />
                {game.broadcast}
              </span>
            </>
          )}
        </div>

        {/* Tournament headline */}
        {game.headline && game.gameType !== "regular" && (
          <div className="text-center mb-4">
            <span className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full ${
              game.gameType === "tourney"
                ? "bg-accent/15 text-accent"
                : "bg-purple-500/15 text-purple-400"
            }`}>
              {game.headline}
            </span>
          </div>
        )}

        {/* Score display */}
        <div className="grid grid-cols-3 items-center gap-4 mb-4">
          {/* Away team */}
          <div className="text-center">
            <div className="flex justify-center mb-2">
              {game.away.logo ? (
                <img src={game.away.logo} alt="" className="w-16 h-16 object-contain" />
              ) : (
                <div className="w-16 h-16 rounded-lg bg-white/10" />
              )}
            </div>
            <div className="flex items-center justify-center gap-1.5 mb-0.5">
              {game.away.rank && game.away.rank <= 25 && (
                <span className="text-xs text-accent font-medium">#{game.away.rank}</span>
              )}
              <span className={`font-semibold ${awayWon ? "text-foreground" : isFinal ? "text-muted" : ""}`}>
                {game.away.name}
              </span>
            </div>
            <div className="text-xs text-muted">
              {game.away.record && <span>{game.away.record}</span>}
              {game.away.elo && <span className="ml-2">Elo {game.away.elo.toFixed(0)}</span>}
            </div>
          </div>

          {/* Score */}
          <div className="text-center">
            <div className="flex items-center justify-center gap-4">
              <span className={`text-4xl sm:text-5xl tabular-nums font-bold ${awayWon ? "" : isFinal ? "text-muted" : ""}`}>
                {game.away.score || (isScheduled ? "" : "0")}
              </span>
              <span className="text-2xl text-muted font-light">&ndash;</span>
              <span className={`text-4xl sm:text-5xl tabular-nums font-bold ${homeWon ? "" : isFinal ? "text-muted" : ""}`}>
                {game.home.score || (isScheduled ? "" : "0")}
              </span>
            </div>
            {isLive && game.clock && (
              <div className="text-xs text-muted mt-1">{game.clock}</div>
            )}
          </div>

          {/* Home team */}
          <div className="text-center">
            <div className="flex justify-center mb-2">
              {game.home.logo ? (
                <img src={game.home.logo} alt="" className="w-16 h-16 object-contain" />
              ) : (
                <div className="w-16 h-16 rounded-lg bg-white/10" />
              )}
            </div>
            <div className="flex items-center justify-center gap-1.5 mb-0.5">
              {game.home.rank && game.home.rank <= 25 && (
                <span className="text-xs text-accent font-medium">#{game.home.rank}</span>
              )}
              <span className={`font-semibold ${homeWon ? "text-foreground" : isFinal ? "text-muted" : ""}`}>
                {game.home.name}
              </span>
            </div>
            <div className="text-xs text-muted">
              {game.home.record && <span>{game.home.record}</span>}
              {game.home.elo && <span className="ml-2">Elo {game.home.elo.toFixed(0)}</span>}
            </div>
          </div>
        </div>

        {/* Venue */}
        {game.venue && (
          <div className="text-center text-xs text-muted mt-2">{game.venue}</div>
        )}
      </div>

      {/* ── Prediction card ── */}
      {wp && (
        <div className="bg-card border border-card-border rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold flex items-center gap-1.5">
              <Lock size={12} className="text-muted/60" />
              Locked Prediction
            </h2>
            {isFinal && modelCorrect !== null ? (
              <span
                className={`flex items-center gap-1 text-xs font-medium ${
                  modelCorrect ? "text-green-400" : "text-red-400"
                }`}
              >
                {modelCorrect ? <Check size={12} /> : <X size={12} />}
                {modelCorrect ? "MODEL CORRECT" : "MODEL MISSED"}
                {isTossup && <span className="text-yellow-400/80 ml-1">(TOSSUP)</span>}
              </span>
            ) : isTossup ? (
              <span className="text-xs text-yellow-400/80 font-medium">TOSSUP</span>
            ) : (
              <span className="text-xs text-muted">Pre-game lock</span>
            )}
          </div>

          {/* Probability bar */}
          <div className="flex items-center justify-between text-sm mb-2">
            <span className={modelPickedAway ? "font-semibold text-accent" : "text-muted"}>
              {game.away.abbreviation} {(wp.away * 100).toFixed(1)}%
            </span>
            <span className={!modelPickedAway ? "font-semibold text-accent" : "text-muted"}>
              {game.home.abbreviation} {(wp.home * 100).toFixed(1)}%
            </span>
          </div>
          <div className="h-3 bg-white/5 rounded-full overflow-hidden flex">
            <div
              className={`h-full rounded-l-full transition-all ${
                isFinal && modelCorrect !== null
                  ? modelCorrect
                    ? "bg-green-500/70"
                    : "bg-red-500/50"
                  : isTossup
                  ? "bg-yellow-500/40"
                  : "bg-accent/70"
              }`}
              style={{ width: `${wp.away * 100}%` }}
            />
            <div
              className={`h-full rounded-r-full ${isTossup && !isFinal ? "bg-yellow-500/20" : "bg-white/20"}`}
              style={{ width: `${wp.home * 100}%` }}
            />
          </div>

          {/* Prediction metadata */}
          {game.lockedPrediction && (
            <div className="flex items-center gap-3 mt-3 text-[10px] text-muted">
              <span>Source: {game.lockedPrediction.source}</span>
              {game.lockedPrediction.lockedAt && (
                <span>
                  Locked:{" "}
                  {new Date(game.lockedPrediction.lockedAt).toLocaleString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Compare Teams link ── */}
      {compareHref && (
        <Link
          href={compareHref}
          className="flex items-center justify-center gap-2 bg-card border border-card-border rounded-xl p-4 mb-6 text-sm text-muted hover:text-accent hover:border-accent/30 transition-colors"
        >
          <GitCompareArrows size={16} />
          Compare {game.away.abbreviation} vs {game.home.abbreviation}
        </Link>
      )}

      {/* ── Box Score ── */}
      {box && box.players.length > 0 && (
        <div className="space-y-6">
          {/* Team stats summary */}
          {box.teams.length === 2 && (
            <div className="bg-card border border-card-border rounded-xl p-5">
              <h2 className="text-sm font-semibold mb-4">Team Stats</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-card-border text-muted">
                      <th className="text-left py-2 pr-4 font-medium">Team</th>
                      {Object.keys(box.teams[0].stats).map((key) => (
                        <th key={key} className="text-center py-2 px-2 font-medium">
                          {key}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {box.teams.map((t) => (
                      <tr key={t.abbreviation} className="border-b border-card-border/50 last:border-0">
                        <td className="py-2 pr-4 font-medium flex items-center gap-2">
                          {t.logo && (
                            <img src={t.logo} alt="" className="w-4 h-4 object-contain" />
                          )}
                          {t.abbreviation}
                        </td>
                        {Object.values(t.stats).map((val, i) => (
                          <td key={i} className="text-center py-2 px-2 tabular-nums">
                            {val}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Player stats per team */}
          {Object.entries(playersByTeam).map(([teamAbbr, players]) => {
            // Figure out which stat columns are available
            const availableCols = statColumns.filter((col) =>
              players.some((p) => col in p.stats)
            );

            return (
              <div key={teamAbbr} className="bg-card border border-card-border rounded-xl p-5">
                <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                  {box.teams.find((t) => t.abbreviation === teamAbbr)?.logo && (
                    <img
                      src={box.teams.find((t) => t.abbreviation === teamAbbr)!.logo}
                      alt=""
                      className="w-5 h-5 object-contain"
                    />
                  )}
                  {teamAbbr} Players
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-card-border text-muted">
                        <th className="text-left py-2 pr-4 font-medium sticky left-0 bg-card">Player</th>
                        <th className="text-center py-2 px-1 font-medium">POS</th>
                        {availableCols.map((col) => (
                          <th key={col} className="text-center py-2 px-1.5 font-medium">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {players.map((p, idx) => (
                        <tr
                          key={p.espnId || idx}
                          className="border-b border-card-border/50 last:border-0 hover:bg-white/[0.02]"
                        >
                          <td className="py-1.5 pr-4 font-medium whitespace-nowrap sticky left-0 bg-card">
                            {p.name}
                          </td>
                          <td className="text-center py-1.5 px-1 text-muted">{p.position}</td>
                          {availableCols.map((col) => (
                            <td key={col} className="text-center py-1.5 px-1.5 tabular-nums">
                              {p.stats[col] ?? "-"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Box score loading or not available */}
      {box && box.players.length === 0 && !isScheduled && (
        <div className="bg-card border border-card-border rounded-xl p-5 text-center text-sm text-muted">
          {isLive ? "Box score updating..." : "Box score not available for this game."}
        </div>
      )}
    </div>
  );
}
