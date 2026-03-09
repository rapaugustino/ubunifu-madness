export interface Team {
  id: number;
  name: string;
  seed: number;
  conference: string;
  elo: number;
  record: string;
  winPct: number;
  logo?: string;
  gender: "M" | "W";
}

export interface Matchup {
  teamA: Team;
  teamB: Team;
  winProbA: number;
  round: number;
  region: string;
}

export interface TeamStats {
  elo: number;
  seed: number;
  confStrength: number;
  offEfficiency: number;
  defEfficiency: number;
  tempo: number;
  sosRank: number;
  momentum: number;
  record: string;
  conference: string;
}

export interface PowerRanking {
  rank: number;
  team: Team;
  elo: number;
  record: string;
  conference: string;
  confStrength: number;
  trend: "up" | "down" | "same";
  trendAmount: number;
}
