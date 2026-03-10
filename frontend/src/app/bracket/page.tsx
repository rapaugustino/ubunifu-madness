"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Sparkles, RefreshCw, Download, Trophy, X, ChevronDown } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface BracketTeam {
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

interface MatchupResult {
  winnerId: number;
  winnerScore: number;
  loserScore: number;
}

interface Matchup {
  teamA: BracketTeam | null;
  teamB: BracketTeam | null;
  winProbA: number;
  result: MatchupResult | null;
}

interface RegionData {
  regionCode: string;
  rounds: (Matchup | null)[][];
  winner: BracketTeam | null;
}

interface BracketData {
  season: number;
  gender: string;
  hasBracket: boolean;
  isComplete: boolean;
  regions: Record<string, RegionData>;
  finalFour: (Matchup | null)[];
  championship: (Matchup | null)[];
  champion: BracketTeam | null;
  roundNames: string[];
}

// localStorage key
function picksKey(season: number, gender: string) {
  return `bracket_picks_${season}_${gender}`;
}

function TeamSlot({
  team,
  isWinner,
  isPicked,
  canPick,
  onClick,
  score,
}: {
  team: BracketTeam | null;
  isWinner: boolean;
  isPicked: boolean;
  canPick: boolean;
  onClick?: () => void;
  score?: number | null;
}) {
  if (!team) {
    return (
      <div className="flex items-center gap-2 px-2 py-1.5 rounded bg-white/[0.02] border border-dashed border-card-border min-h-[32px]">
        <span className="text-xs text-muted">TBD</span>
      </div>
    );
  }

  return (
    <button
      onClick={canPick ? onClick : undefined}
      disabled={!canPick}
      className={`flex items-center gap-2 px-2 py-1.5 rounded text-left w-full min-h-[32px] transition-all ${
        isPicked
          ? "bg-accent/15 border border-accent/30"
          : isWinner
          ? "bg-green-500/10 border border-green-500/20"
          : canPick
          ? "bg-white/[0.03] border border-card-border hover:border-accent/30 cursor-pointer"
          : "bg-white/[0.02] border border-card-border opacity-60"
      }`}
    >
      {team.logo ? (
        <img src={team.logo} alt="" className="w-4 h-4 object-contain shrink-0" />
      ) : (
        <div className="w-4 h-4 rounded bg-white/10 shrink-0" />
      )}
      <div className="flex items-center gap-1 min-w-0 flex-1">
        {team.seed && (
          <span className="text-[10px] text-muted font-mono shrink-0">{team.seed}</span>
        )}
        <span className={`text-xs truncate ${isWinner || isPicked ? "font-semibold" : ""}`}>
          {team.name}
        </span>
      </div>
      {score != null && (
        <span className={`text-xs font-mono shrink-0 ${isWinner ? "font-bold" : "text-muted"}`}>
          {score}
        </span>
      )}
    </button>
  );
}

function MatchupCard({
  matchup,
  isHistorical,
  picks,
  slotId,
  onPick,
  onAnalyze,
}: {
  matchup: Matchup | null;
  isHistorical: boolean;
  picks: Record<string, number>;
  slotId: string;
  onPick: (slotId: string, teamId: number) => void;
  onAnalyze: (matchup: Matchup) => void;
}) {
  if (!matchup || !matchup.teamA || !matchup.teamB) {
    return (
      <div className="p-2 rounded-lg bg-card/50 border border-card-border border-dashed min-h-[76px] flex items-center justify-center">
        <span className="text-xs text-muted">TBD</span>
      </div>
    );
  }

  const { teamA, teamB, result, winProbA } = matchup;
  const userPick = picks[slotId];
  const hasResult = result != null;
  const aIsWinner = hasResult && result.winnerId === teamA.id;
  const bIsWinner = hasResult && result.winnerId === teamB.id;
  const canPick = !isHistorical;

  return (
    <div className="p-2 rounded-lg bg-card border border-card-border space-y-1 group relative">
      <TeamSlot
        team={teamA}
        isWinner={aIsWinner}
        isPicked={userPick === teamA.id}
        canPick={canPick}
        onClick={() => onPick(slotId, teamA.id)}
        score={hasResult ? (aIsWinner ? result.winnerScore : result.loserScore) : null}
      />
      <TeamSlot
        team={teamB}
        isWinner={bIsWinner}
        isPicked={userPick === teamB.id}
        canPick={canPick}
        onClick={() => onPick(slotId, teamB.id)}
        score={hasResult ? (bIsWinner ? result.winnerScore : result.loserScore) : null}
      />
      {/* Win prob indicator */}
      <div className="flex items-center gap-1 px-1">
        <div className="flex-1 h-0.5 bg-white/5 rounded-full overflow-hidden flex">
          <div className="h-full bg-accent/50 rounded-l-full" style={{ width: `${winProbA * 100}%` }} />
          <div className="h-full bg-blue-500/30 rounded-r-full" style={{ width: `${(1 - winProbA) * 100}%` }} />
        </div>
        <button
          onClick={() => onAnalyze(matchup)}
          className="opacity-0 group-hover:opacity-100 transition-opacity"
          title="AI Analysis"
        >
          <Sparkles size={10} className="text-accent" />
        </button>
      </div>
    </div>
  );
}

function AnalysisPanel({
  matchup,
  onClose,
}: {
  matchup: Matchup;
  onClose: () => void;
}) {
  const [analysis, setAnalysis] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!matchup.teamA || !matchup.teamB) return;

    const teamA = matchup.teamA;
    const teamB = matchup.teamB;
    const prompt = `Analyze this March Madness matchup: #${teamA.seed} ${teamA.name} (${teamA.record}, Elo ${teamA.elo}, ${teamA.conference}) vs #${teamB.seed} ${teamB.name} (${teamB.record}, Elo ${teamB.elo}, ${teamB.conference}). Our model gives ${teamA.name} a ${(matchup.winProbA * 100).toFixed(0)}% win probability. Give a brief analysis (3-4 sentences) covering key factors, upset potential, and your pick.`;

    setLoading(true);
    setAnalysis("");

    fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: prompt }],
        gender: teamA.gender === "W" ? "W" : "M",
      }),
    })
      .then(async (res) => {
        const reader = res.body?.getReader();
        if (!reader) return;
        const decoder = new TextDecoder();
        let text = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          for (const line of chunk.split("\n")) {
            if (line.startsWith("data: ") && !line.includes("[DONE]")) {
              try {
                const data = JSON.parse(line.slice(6));
                text += data.text;
                setAnalysis(text);
              } catch {}
            }
          }
        }
      })
      .catch(() => setAnalysis("Unable to generate analysis. Please try again."))
      .finally(() => setLoading(false));
  }, [matchup]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-md bg-background border-l border-card-border p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-accent" />
            <h2 className="text-lg font-semibold">Matchup Analysis</h2>
          </div>
          <button onClick={onClose} className="text-muted hover:text-foreground">
            <X size={18} />
          </button>
        </div>

        {matchup.teamA && matchup.teamB && (
          <div className="mb-4 p-3 rounded-lg bg-card border border-card-border">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {matchup.teamA.logo && <img src={matchup.teamA.logo} alt="" className="w-6 h-6" />}
                <span className="text-sm font-medium">
                  #{matchup.teamA.seed} {matchup.teamA.name}
                </span>
              </div>
              <span className="text-sm font-mono text-accent">
                {(matchup.winProbA * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden flex mb-2">
              <div className="h-full bg-accent/70 rounded-l-full" style={{ width: `${matchup.winProbA * 100}%` }} />
              <div className="h-full bg-blue-500/40 rounded-r-full" style={{ width: `${(1 - matchup.winProbA) * 100}%` }} />
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {matchup.teamB.logo && <img src={matchup.teamB.logo} alt="" className="w-6 h-6" />}
                <span className="text-sm font-medium">
                  #{matchup.teamB.seed} {matchup.teamB.name}
                </span>
              </div>
              <span className="text-sm font-mono text-blue-400">
                {((1 - matchup.winProbA) * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        )}

        <div className="p-4 rounded-lg bg-card border border-card-border">
          {loading && !analysis ? (
            <div className="flex items-center gap-2 text-sm text-muted">
              <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              Analyzing matchup...
            </div>
          ) : (
            <p className="text-sm text-muted leading-relaxed whitespace-pre-line">{analysis}</p>
          )}
        </div>

        {matchup.result && (
          <div className="mt-4 p-3 rounded-lg bg-green-500/5 border border-green-500/10">
            <div className="text-xs text-green-400 font-medium mb-1">Actual Result</div>
            <div className="text-sm">
              {matchup.teamA && matchup.teamB && (
                matchup.result.winnerId === matchup.teamA.id
                  ? `${matchup.teamA.name} ${matchup.result.winnerScore} - ${matchup.result.loserScore} ${matchup.teamB.name}`
                  : `${matchup.teamB.name} ${matchup.result.winnerScore} - ${matchup.result.loserScore} ${matchup.teamA.name}`
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function BracketPage() {
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [loading, setLoading] = useState(true);
  const [gender, setGender] = useState<"M" | "W">("M");
  const [activeRegion, setActiveRegion] = useState("East");
  const [picks, setPicks] = useState<Record<string, number>>({});
  const [analysisMatchup, setAnalysisMatchup] = useState<Matchup | null>(null);
  const [autoFilling, setAutoFilling] = useState(false);
  const [simResults, setSimResults] = useState<{
    championProbabilities: { teamId: number; teamName: string; probability: number }[];
    finalFourProbabilities: { teamId: number; teamName: string; probability: number }[];
  } | null>(null);

  const fetchBracket = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/bracket/full?gender=${gender}&season=0`);
      const data: BracketData = await res.json();
      setBracket(data);

      // Load picks from localStorage
      if (data.hasBracket) {
        const saved = localStorage.getItem(picksKey(data.season, gender));
        if (saved) {
          setPicks(JSON.parse(saved));
        } else {
          setPicks({});
        }
      }
    } catch {
      setBracket(null);
    } finally {
      setLoading(false);
    }
  }, [gender]);

  useEffect(() => {
    fetchBracket();
  }, [fetchBracket]);

  const handlePick = (slotId: string, teamId: number) => {
    if (!bracket) return;
    const newPicks = { ...picks, [slotId]: teamId };
    setPicks(newPicks);
    localStorage.setItem(picksKey(bracket.season, gender), JSON.stringify(newPicks));
  };

  const resetPicks = () => {
    if (!bracket) return;
    setPicks({});
    localStorage.removeItem(picksKey(bracket.season, gender));
  };

  const autoFill = async () => {
    if (!bracket) return;
    setAutoFilling(true);
    try {
      const res = await fetch(
        `${API_URL}/api/bracket/simulate?season=${bracket.season}&gender=${gender}&num_simulations=1000`,
        { method: "POST" }
      );
      const data = await res.json();
      setSimResults(data);
    } catch {}
    setAutoFilling(false);
  };

  const exportBracket = () => {
    if (!bracket) return;
    const data = {
      season: bracket.season,
      gender,
      picks,
      exportedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bracket_${bracket.season}_${gender}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted">Loading bracket...</div>
      </div>
    );
  }

  if (!bracket || !bracket.hasBracket) {
    return (
      <div className="min-h-screen max-w-5xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-2">Interactive Bracket</h1>
        <p className="text-muted">No bracket data available yet. Check back after Selection Sunday.</p>
      </div>
    );
  }

  const regionNames = Object.keys(bracket.regions);
  const currentRegion = bracket.regions[activeRegion];
  const isHistorical = bracket.isComplete;

  return (
    <div className="min-h-screen max-w-7xl mx-auto px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">
            {bracket.season} {gender === "W" ? "Women's" : "Men's"} Tournament
          </h1>
          <p className="text-muted text-sm mt-1">
            {isHistorical
              ? `Completed tournament. ${bracket.champion ? `Champion: ${bracket.champion.name}` : ""}`
              : "Click matchups to make your picks. Probabilities powered by our ML model."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!isHistorical && (
            <>
              <button
                onClick={autoFill}
                disabled={autoFilling}
                className="flex items-center gap-1.5 px-3 py-2 bg-accent/10 text-accent rounded-lg text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-50"
              >
                <Sparkles size={14} />
                {autoFilling ? "Simulating..." : "Simulate"}
              </button>
              <button
                onClick={resetPicks}
                className="flex items-center gap-1.5 px-3 py-2 bg-white/5 text-muted rounded-lg text-sm hover:text-foreground hover:bg-white/10 transition-colors"
              >
                <RefreshCw size={14} />
                Reset
              </button>
            </>
          )}
          <button
            onClick={exportBracket}
            className="flex items-center gap-1.5 px-3 py-2 bg-white/5 text-muted rounded-lg text-sm hover:text-foreground hover:bg-white/10 transition-colors"
          >
            <Download size={14} />
            Export
          </button>
        </div>
      </div>

      {/* Gender toggle */}
      <div className="flex items-center gap-2 mb-6">
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

      {/* Champion banner */}
      {bracket.champion && (
        <div className="mb-6 p-4 rounded-xl bg-gradient-to-r from-accent/10 to-accent/5 border border-accent/20 flex items-center gap-3">
          <Trophy size={20} className="text-accent shrink-0" />
          <div className="flex items-center gap-3">
            {bracket.champion.logo && (
              <img src={bracket.champion.logo} alt="" className="w-8 h-8 object-contain" />
            )}
            <div>
              <div className="text-sm font-bold">{bracket.champion.name}</div>
              <div className="text-xs text-muted">
                {bracket.season} {gender === "W" ? "Women's" : "Men's"} National Champion
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Simulation results */}
      {simResults && (
        <div className="mb-6 p-4 rounded-xl bg-card border border-card-border">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium">Monte Carlo Simulation (1,000 runs)</h3>
            <button onClick={() => setSimResults(null)} className="text-muted hover:text-foreground">
              <X size={14} />
            </button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider mb-2">Championship %</div>
              <div className="space-y-1">
                {simResults.championProbabilities.slice(0, 8).map((t) => (
                  <div key={t.teamId} className="flex items-center justify-between text-xs">
                    <span className="font-medium">{t.teamName}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1 bg-white/5 rounded-full overflow-hidden">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${t.probability * 100}%` }} />
                      </div>
                      <span className="font-mono text-accent w-10 text-right">{(t.probability * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted uppercase tracking-wider mb-2">Final Four %</div>
              <div className="space-y-1">
                {simResults.finalFourProbabilities.slice(0, 8).map((t) => (
                  <div key={t.teamId} className="flex items-center justify-between text-xs">
                    <span className="font-medium">{t.teamName}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1 bg-white/5 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${t.probability * 100}%` }} />
                      </div>
                      <span className="font-mono text-blue-400 w-10 text-right">{(t.probability * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Region tabs */}
      <div className="flex items-center gap-1 mb-6 p-1 bg-card rounded-lg border border-card-border w-fit flex-wrap">
        {regionNames.map((region) => (
          <button
            key={region}
            onClick={() => setActiveRegion(region)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeRegion === region
                ? "bg-accent/15 text-accent"
                : "text-muted hover:text-foreground"
            }`}
          >
            {region}
          </button>
        ))}
        <button
          onClick={() => setActiveRegion("Final Four")}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            activeRegion === "Final Four"
              ? "bg-accent/15 text-accent"
              : "text-muted hover:text-foreground"
          }`}
        >
          Final Four
        </button>
      </div>

      {/* Bracket view */}
      {activeRegion === "Final Four" ? (
        <div className="space-y-6">
          {/* Final Four */}
          <div>
            <h3 className="text-sm font-medium text-muted mb-3 uppercase tracking-wider">
              Final Four
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl">
              {bracket.finalFour.map((matchup, i) => (
                <MatchupCard
                  key={`ff_${i}`}
                  matchup={matchup}
                  isHistorical={isHistorical}
                  picks={picks}
                  slotId={`ff_${i}`}
                  onPick={handlePick}
                  onAnalyze={setAnalysisMatchup}
                />
              ))}
            </div>
          </div>

          {/* Championship */}
          {bracket.championship.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-accent mb-3 uppercase tracking-wider">
                Championship
              </h3>
              <div className="max-w-sm">
                {bracket.championship.map((matchup, i) => (
                  <MatchupCard
                    key={`champ_${i}`}
                    matchup={matchup}
                    isHistorical={isHistorical}
                    picks={picks}
                    slotId={`champ_${i}`}
                    onPick={handlePick}
                    onAnalyze={setAnalysisMatchup}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      ) : currentRegion ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {currentRegion.rounds.map((round, roundIdx) => (
            <div key={roundIdx}>
              <h3 className="text-xs font-medium text-muted mb-3 uppercase tracking-wider">
                {bracket.roundNames[roundIdx] || `Round ${roundIdx + 1}`}
              </h3>
              <div className="space-y-2">
                {round.map((matchup, i) => (
                  <MatchupCard
                    key={`${activeRegion}_r${roundIdx}_${i}`}
                    matchup={matchup}
                    isHistorical={isHistorical}
                    picks={picks}
                    slotId={`${activeRegion}_r${roundIdx}_${i}`}
                    onPick={handlePick}
                    onAnalyze={setAnalysisMatchup}
                  />
                ))}
              </div>
            </div>
          ))}

          {/* Region winner */}
          {currentRegion.winner && (
            <div className="sm:col-span-2 lg:col-span-4 mt-2">
              <div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-accent/5 border border-accent/10">
                <Trophy size={14} className="text-accent" />
                <span className="text-sm font-medium">
                  {activeRegion} Champion: {currentRegion.winner.name}
                </span>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {/* AI Analysis slide-over */}
      {analysisMatchup && (
        <AnalysisPanel matchup={analysisMatchup} onClose={() => setAnalysisMatchup(null)} />
      )}
    </div>
  );
}
