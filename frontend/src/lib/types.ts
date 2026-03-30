/* ── ESPN scoreboard types (used by home, scores, game detail pages) ── */

export interface TeamScore {
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

export interface LockedPrediction {
  probAway: number;
  probHome: number;
  source: string;
  explanation: string | null;
  lockedAt: string | null;
  resolved: boolean;
  correct: boolean | null;
}

export interface Game {
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
