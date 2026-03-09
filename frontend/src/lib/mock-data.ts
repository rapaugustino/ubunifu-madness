import { Team, PowerRanking, Matchup } from "./types";

export const menTeams: Team[] = [
  { id: 1112, name: "Duke", seed: 1, conference: "ACC", elo: 2021, record: "29-4", winPct: 0.879, gender: "M" },
  { id: 1211, name: "Houston", seed: 1, conference: "Big 12", elo: 2013, record: "30-3", winPct: 0.909, gender: "M" },
  { id: 1104, name: "Auburn", seed: 1, conference: "SEC", elo: 1993, record: "28-5", winPct: 0.848, gender: "M" },
  { id: 1181, name: "Florida", seed: 1, conference: "SEC", elo: 1970, record: "27-6", winPct: 0.818, gender: "M" },
  { id: 1388, name: "Tennessee", seed: 2, conference: "SEC", elo: 1954, record: "26-7", winPct: 0.788, gender: "M" },
  { id: 1243, name: "Kansas", seed: 2, conference: "Big 12", elo: 1947, record: "25-8", winPct: 0.758, gender: "M" },
  { id: 1276, name: "Marquette", seed: 2, conference: "Big East", elo: 1940, record: "26-7", winPct: 0.788, gender: "M" },
  { id: 1100, name: "Arizona", seed: 2, conference: "Big 12", elo: 1937, record: "25-8", winPct: 0.758, gender: "M" },
  { id: 1314, name: "Purdue", seed: 3, conference: "Big Ten", elo: 1919, record: "24-9", winPct: 0.727, gender: "M" },
  { id: 1228, name: "Iowa St", seed: 3, conference: "Big 12", elo: 1931, record: "25-7", winPct: 0.781, gender: "M" },
  { id: 1397, name: "Wisconsin", seed: 3, conference: "Big Ten", elo: 1905, record: "24-9", winPct: 0.727, gender: "M" },
  { id: 1382, name: "Texas Tech", seed: 3, conference: "Big 12", elo: 1898, record: "23-9", winPct: 0.719, gender: "M" },
  { id: 1168, name: "UConn", seed: 4, conference: "Big East", elo: 1890, record: "22-10", winPct: 0.688, gender: "M" },
  { id: 1196, name: "Gonzaga", seed: 4, conference: "WCC", elo: 1885, record: "26-6", winPct: 0.813, gender: "M" },
  { id: 1153, name: "Clemson", seed: 4, conference: "ACC", elo: 1880, record: "24-9", winPct: 0.727, gender: "M" },
  { id: 1301, name: "Oregon", seed: 4, conference: "Big Ten", elo: 1875, record: "23-10", winPct: 0.697, gender: "M" },
  { id: 1280, name: "Michigan St", seed: 5, conference: "Big Ten", elo: 1862, record: "22-11", winPct: 0.667, gender: "M" },
  { id: 1374, name: "Texas A&M", seed: 5, conference: "SEC", elo: 1855, record: "22-11", winPct: 0.667, gender: "M" },
  { id: 1339, name: "St. John's", seed: 5, conference: "Big East", elo: 1850, record: "23-9", winPct: 0.719, gender: "M" },
  { id: 1281, name: "Michigan", seed: 5, conference: "Big Ten", elo: 1845, record: "21-12", winPct: 0.636, gender: "M" },
  { id: 1232, name: "Kentucky", seed: 6, conference: "SEC", elo: 1835, record: "21-12", winPct: 0.636, gender: "M" },
  { id: 1139, name: "BYU", seed: 6, conference: "Big 12", elo: 1830, record: "22-11", winPct: 0.667, gender: "M" },
  { id: 1222, name: "Illinois", seed: 6, conference: "Big Ten", elo: 1825, record: "20-13", winPct: 0.606, gender: "M" },
  { id: 1285, name: "Mississippi St", seed: 6, conference: "SEC", elo: 1820, record: "21-12", winPct: 0.636, gender: "M" },
];

export const womenTeams: Team[] = [
  { id: 3163, name: "UConn", seed: 1, conference: "Big East", elo: 2346, record: "31-2", winPct: 0.939, gender: "W" },
  { id: 3392, name: "UCLA", seed: 1, conference: "Big Ten", elo: 2263, record: "30-3", winPct: 0.909, gender: "W" },
  { id: 3345, name: "South Carolina", seed: 1, conference: "SEC", elo: 2199, record: "29-4", winPct: 0.879, gender: "W" },
  { id: 3375, name: "Texas", seed: 1, conference: "SEC", elo: 2197, record: "28-5", winPct: 0.848, gender: "W" },
  { id: 3261, name: "LSU", seed: 2, conference: "SEC", elo: 2154, record: "27-6", winPct: 0.818, gender: "W" },
  { id: 3258, name: "Louisville", seed: 2, conference: "ACC", elo: 2124, record: "26-7", winPct: 0.788, gender: "W" },
];

export const mockBracketMatchups: Matchup[] = [
  { teamA: menTeams[0], teamB: { ...menTeams[23], seed: 16, name: "Robert Morris", elo: 1420, record: "20-14" }, winProbA: 0.97, round: 1, region: "East" },
  { teamA: { ...menTeams[7], seed: 8, name: "San Diego St", elo: 1720, record: "22-11" }, teamB: { ...menTeams[8], seed: 9, name: "Creighton", elo: 1715, record: "21-12" }, winProbA: 0.52, round: 1, region: "East" },
  { teamA: menTeams[8], teamB: { ...menTeams[20], seed: 14, name: "Colgate", elo: 1510, record: "24-9" }, winProbA: 0.89, round: 1, region: "East" },
  { teamA: menTeams[4], teamB: { ...menTeams[22], seed: 15, name: "Vermont", elo: 1480, record: "25-8" }, winProbA: 0.93, round: 1, region: "East" },
  { teamA: menTeams[16], teamB: { ...menTeams[21], seed: 12, name: "McNeese", elo: 1610, record: "27-6" }, winProbA: 0.72, round: 1, region: "East" },
  { teamA: menTeams[12], teamB: { ...menTeams[19], seed: 13, name: "Yale", elo: 1560, record: "23-7" }, winProbA: 0.81, round: 1, region: "East" },
  { teamA: menTeams[20], teamB: { ...menTeams[18], seed: 11, name: "Drake", elo: 1650, record: "24-9" }, winProbA: 0.62, round: 1, region: "East" },
  { teamA: menTeams[10], teamB: { ...menTeams[17], seed: 7, name: "Nevada", elo: 1730, record: "25-8" }, winProbA: 0.58, round: 1, region: "East" },

  { teamA: menTeams[1], teamB: { ...menTeams[23], seed: 16, name: "Norfolk St", elo: 1380, record: "19-15" }, winProbA: 0.98, round: 1, region: "South" },
  { teamA: menTeams[5], teamB: { ...menTeams[22], seed: 15, name: "UNC Asheville", elo: 1460, record: "24-9" }, winProbA: 0.94, round: 1, region: "South" },
  { teamA: menTeams[9], teamB: { ...menTeams[21], seed: 14, name: "Lipscomb", elo: 1530, record: "26-7" }, winProbA: 0.87, round: 1, region: "South" },
  { teamA: menTeams[13], teamB: { ...menTeams[20], seed: 13, name: "High Point", elo: 1545, record: "25-8" }, winProbA: 0.82, round: 1, region: "South" },
];

export const mockPowerRankings: PowerRanking[] = menTeams.slice(0, 24).map((team, i) => ({
  rank: i + 1,
  team,
  elo: team.elo,
  record: team.record,
  conference: team.conference,
  confStrength: [0.92, 0.95, 0.89, 0.89, 0.89, 0.95, 0.85, 0.95, 0.88, 0.95, 0.88, 0.95, 0.85, 0.72, 0.78, 0.88, 0.88, 0.89, 0.85, 0.88, 0.89, 0.95, 0.88, 0.89][i],
  trend: (["up", "down", "same"] as const)[i % 3],
  trendAmount: [2, 1, 0, 3, 1, 0, 2, 1, 0, 4, 2, 0, 1, 3, 0, 2, 1, 0, 3, 2, 0, 1, 2, 0][i],
}));

export const conferences = [
  { name: "SEC", avgElo: 1892, depth: 0.89, ncWinRate: 0.623, teams: 16, tourneyBids: 6 },
  { name: "Big 12", avgElo: 1878, depth: 0.95, ncWinRate: 0.611, teams: 16, tourneyBids: 7 },
  { name: "Big Ten", avgElo: 1845, depth: 0.88, ncWinRate: 0.595, teams: 18, tourneyBids: 5 },
  { name: "Big East", avgElo: 1812, depth: 0.85, ncWinRate: 0.572, teams: 11, tourneyBids: 4 },
  { name: "ACC", avgElo: 1795, depth: 0.78, ncWinRate: 0.558, teams: 18, tourneyBids: 3 },
  { name: "WCC", avgElo: 1710, depth: 0.72, ncWinRate: 0.489, teams: 13, tourneyBids: 1 },
  { name: "Mountain West", avgElo: 1695, depth: 0.70, ncWinRate: 0.478, teams: 12, tourneyBids: 2 },
  { name: "American", avgElo: 1665, depth: 0.68, ncWinRate: 0.452, teams: 14, tourneyBids: 1 },
];
