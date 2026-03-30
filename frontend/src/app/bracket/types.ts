export interface BracketTeam {
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
}

export interface MatchupResult {
  winnerId: number;
  winnerScore: number;
  loserScore: number;
}

export interface Matchup {
  teamA: BracketTeam | null;
  teamB: BracketTeam | null;
  winProbA: number;
  result: MatchupResult | null;
}

export interface RegionData {
  regionCode: string;
  rounds: (Matchup | null)[][];
  winner: BracketTeam | null;
}

export interface FirstFourMatchup extends Matchup {
  region: string;
  seed: number;
}

export interface BracketData {
  season: number;
  gender: string;
  hasBracket: boolean;
  isComplete: boolean;
  currentRound: string;
  totalGamesPlayed: number;
  firstFour: FirstFourMatchup[];
  regions: Record<string, RegionData>;
  finalFour: (Matchup | null)[];
  ffPairings: string[][];
  championship: (Matchup | null)[];
  champion: BracketTeam | null;
  roundNames: string[];
}

export type BracketMode = "my_bracket" | "model" | "agent" | "consensus" | "actual";

export const BRACKET_MODES: { key: BracketMode; label: string; description: string }[] = [
  { key: "my_bracket", label: "My Bracket", description: "Fill out your own picks" },
  { key: "model", label: "Model", description: "V6 ML ensemble picks (chalk)" },
  { key: "agent", label: "Agent", description: "AI agent picks (balanced upsets)" },
  { key: "consensus", label: "Consensus", description: "Model + Agent combined" },
  { key: "actual", label: "Actual", description: "Real tournament results" },
];

export { API_URL } from "@/lib/api";

export function picksKey(season: number, gender: string) {
  return `bracket_picks_${season}_${gender}`;
}

// Common NCAA team abbreviations for compact display
const TEAM_ABBREVS: Record<string, string> = {
  "Connecticut": "UConn", "North Carolina": "UNC", "South Carolina": "S. Carolina",
  "Michigan St": "Mich St", "Michigan State": "Mich St", "Ohio St": "Ohio St",
  "Oklahoma St": "Okla St", "Oregon St": "Ore St", "Florida St": "FSU",
  "Arizona St": "ASU", "Mississippi St": "Miss St", "Mississippi": "Ole Miss",
  "Colorado St": "Colo St", "San Diego St": "SDSU", "Boise St": "Boise St",
  "N Carolina": "UNC", "UT San Antonio": "UTSA", "UC San Diego": "UCSD",
  "W Illinois": "W Illinois", "S Dakota St": "SDSU", "F Dickinson": "FDU",
  "Murray St": "Murray St", "High Point": "High Pt", "Vanderbilt": "Vandy",
  "Georgetown": "G'town", "Northwestern": "N'western", "Northeastern": "N'eastern",
  "Southeastern": "SE LA",
};

export function abbreviateTeam(name: string): string {
  if (TEAM_ABBREVS[name]) return TEAM_ABBREVS[name];
  if (name.length <= 10) return name;
  if (name.startsWith("UT ")) return "UT" + name.slice(3, 7);
  if (name.startsWith("UC ")) return "UC" + name.slice(3, 7);
  return name.slice(0, 10);
}
