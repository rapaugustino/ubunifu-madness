"use client";

import { useState, useEffect, useRef } from "react";
import { Sparkles, X, Trophy, CloudDownload } from "lucide-react";
import type { BracketTeam, Matchup, BracketData } from "./types";
import { API_URL, abbreviateTeam } from "./types";

// ─── TeamSlot ─────────────────────────────────────────────

export function TeamSlot({
  team,
  isWinner,
  isPicked,
  canPick,
  onClick,
  score,
  isEliminated,
  isCorrectPick,
}: {
  team: BracketTeam | null;
  isWinner: boolean;
  isPicked: boolean;
  canPick: boolean;
  onClick?: () => void;
  score?: number | null;
  isEliminated?: boolean;
  isCorrectPick?: boolean;
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
        isEliminated
          ? "bg-red-500/10 border border-red-500/30 border-l-2 border-l-red-500/60"
          : isCorrectPick
          ? "bg-green-500/15 border border-green-500/30 border-l-2 border-l-green-500/60"
          : isPicked
          ? "bg-accent/15 border border-accent/30"
          : isWinner
          ? "bg-green-500/10 border border-green-500/20"
          : canPick
          ? "bg-white/[0.03] border border-card-border hover:border-accent/30 cursor-pointer"
          : "bg-white/[0.02] border border-card-border opacity-60"
      }`}
    >
      {team.logo ? (
        <img src={team.logo} alt="" className={`w-4 h-4 object-contain shrink-0 ${isEliminated ? "grayscale" : ""}`} />
      ) : (
        <div className="w-4 h-4 rounded bg-white/10 shrink-0" />
      )}
      <div className="flex items-center gap-1 min-w-0 flex-1">
        {team.seed && (
          <span className="text-xs text-muted font-mono shrink-0">{team.seed}</span>
        )}
        <span className={`text-xs truncate ${isEliminated ? "line-through text-red-400/60" : isWinner || isPicked ? "font-semibold" : ""}`}>
          {team.name}
        </span>
      </div>
      {score != null && (
        <span className={`text-xs font-mono shrink-0 ${isWinner ? "font-bold text-green-400" : isEliminated ? "text-red-400/60" : "text-muted"}`}>
          {score}
        </span>
      )}
      {isEliminated && (
        <span className="text-red-400 text-xs font-bold shrink-0">X</span>
      )}
      {isCorrectPick && (
        <span className="text-green-400 text-xs font-bold shrink-0">&#10003;</span>
      )}
      {isWinner && score != null && !isEliminated && !isCorrectPick && (
        <span className="text-green-400 text-xs shrink-0">W</span>
      )}
    </button>
  );
}

// ─── MatchupCard ──────────────────────────────────────────

export function MatchupCard({
  matchup,
  isHistorical,
  picks,
  slotId,
  onPick,
  onAnalyze,
  eliminatedTeams,
}: {
  matchup: Matchup | null;
  isHistorical: boolean;
  picks: Record<string, number>;
  slotId: string;
  onPick: (slotId: string, teamId: number) => void;
  onAnalyze: (matchup: Matchup) => void;
  eliminatedTeams?: Set<number>;
}) {
  if (!matchup || (!matchup.teamA && !matchup.teamB)) {
    return (
      <div className="p-2 rounded-lg bg-card/50 border border-card-border border-dashed min-h-[76px] flex items-center justify-center">
        <span className="text-xs text-muted">TBD</span>
      </div>
    );
  }

  const { teamA, teamB, result, winProbA } = matchup;
  const userPick = picks[slotId];
  const hasResult = result != null;
  const aIsWinner = hasResult && teamA != null && result.winnerId === teamA.id;
  const bIsWinner = hasResult && teamB != null && result.winnerId === teamB.id;
  const canPick = !isHistorical && !hasResult;
  const aEliminated = eliminatedTeams && teamA?.id ? eliminatedTeams.has(teamA.id) : false;
  const bEliminated = eliminatedTeams && teamB?.id ? eliminatedTeams.has(teamB.id) : false;

  const wrongPickA = hasResult && eliminatedTeams && userPick === teamA?.id && !aIsWinner;
  const wrongPickB = hasResult && eliminatedTeams && userPick === teamB?.id && !bIsWinner;
  const correctPickA = hasResult && eliminatedTeams && userPick === teamA?.id && aIsWinner;
  const correctPickB = hasResult && eliminatedTeams && userPick === teamB?.id && bIsWinner;

  return (
    <div className={`p-2 rounded-lg bg-card border space-y-1 group relative ${
      wrongPickA || wrongPickB ? "border-red-500/20" :
      aEliminated && bEliminated ? "border-red-500/20" : "border-card-border"
    }`}>
      <TeamSlot
        team={teamA}
        isWinner={aIsWinner}
        isPicked={teamA != null && userPick === teamA.id && !wrongPickA}
        canPick={canPick && teamA != null && teamA.id != null}
        onClick={teamA?.id ? () => onPick(slotId, teamA.id) : undefined}
        score={hasResult ? (aIsWinner ? result.winnerScore : result.loserScore) : null}
        isEliminated={(aEliminated && !hasResult) || !!wrongPickA}
        isCorrectPick={!!correctPickA}
      />
      <TeamSlot
        team={teamB}
        isWinner={bIsWinner}
        isPicked={teamB != null && userPick === teamB.id && !wrongPickB}
        canPick={canPick && teamB != null && teamB.id != null}
        onClick={teamB?.id ? () => onPick(slotId, teamB.id) : undefined}
        score={hasResult ? (bIsWinner ? result.winnerScore : result.loserScore) : null}
        isEliminated={(bEliminated && !hasResult) || !!wrongPickB}
        isCorrectPick={!!correctPickB}
      />
      <div className="flex items-center gap-1 px-1">
        <div
          className="flex-1 h-0.5 bg-white/5 rounded-full overflow-hidden flex"
          title={`${teamA?.name ?? "Team A"}: ${(winProbA * 100).toFixed(0)}% — ${teamB?.name ?? "Team B"}: ${((1 - winProbA) * 100).toFixed(0)}%`}
        >
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

// ─── AnalysisPanel ────────────────────────────────────────

export function AnalysisPanel({
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
    const hasResult = matchup.result != null;
    const prompt = hasResult
      ? `Analyze this completed March Madness matchup: #${teamA.seed} ${teamA.name} (${teamA.record}, Elo ${teamA.elo}, ${teamA.conference}) vs #${teamB.seed} ${teamB.name} (${teamB.record}, Elo ${teamB.elo}, ${teamB.conference}). Our model gave ${teamA.name} a ${(matchup.winProbA * 100).toFixed(0)}% win probability. The winner was ${matchup.result!.winnerId === teamA.id ? teamA.name : teamB.name} (${matchup.result!.winnerScore}-${matchup.result!.loserScore}). Give a brief post-game analysis (3-4 sentences) covering what happened and whether the result was expected.`
      : `Analyze this upcoming March Madness matchup: #${teamA.seed} ${teamA.name} (${teamA.record}, Elo ${teamA.elo}, ${teamA.conference}) vs #${teamB.seed} ${teamB.name} (${teamB.record}, Elo ${teamB.elo}, ${teamB.conference}). Our model gives ${teamA.name} a ${(matchup.winProbA * 100).toFixed(0)}% win probability. Give a brief preview (3-4 sentences) covering key factors, upset potential, and which team has the edge.`;

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

// ─── EmailModal ───────────────────────────────────────────

export function EmailModal({
  mode,
  onSubmit,
  onClose,
}: {
  mode: "save" | "load";
  onSubmit: (email: string) => Promise<boolean>;
  onClose: () => void;
}) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError("");
    setSubmitting(true);
    const ok = await onSubmit(email.trim());
    setSubmitting(false);
    if (!ok) setError("Invalid email or server error. Try again.");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-background border border-card-border rounded-xl p-6 w-full max-w-sm mx-4">
        <h3 className="text-lg font-semibold mb-1">
          {mode === "save" ? "Save Your Bracket" : "Load Your Bracket"}
        </h3>
        <p className="text-sm text-muted mb-4">
          {mode === "save"
            ? "Enter your email to save picks across devices."
            : "Enter the email you used to save your bracket."}
        </p>
        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full px-3 py-2 rounded-lg bg-card border border-card-border text-sm focus:outline-none focus:border-accent mb-3"
          />
          {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={submitting || !email.trim()}
              className="flex-1 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors"
            >
              {submitting ? "..." : mode === "save" ? "Save" : "Load"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-white/5 text-muted rounded-lg text-sm hover:text-foreground transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── CopyFromMenu ─────────────────────────────────────────

export function CopyFromMenu({
  gender,
  season,
  onCopy,
}: {
  gender: string;
  season: number;
  onCopy: (picks: Record<string, number>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const copyFrom = async (bracketType: string) => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/bracket/official?gender=${gender}&bracket_type=${bracketType}&season=${season}`
      );
      const data = await res.json();
      if (data.exists && data.picks) {
        onCopy(data.picks);
        setOpen(false);
      }
    } catch {}
    setLoading(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-2 bg-accent/10 text-accent rounded-lg text-sm font-medium hover:bg-accent/20 transition-colors"
      >
        <CloudDownload size={14} />
        Start from...
      </button>
      {open && (
        <div className="absolute top-full mt-1 right-0 bg-card border border-card-border rounded-lg shadow-lg z-10 min-w-[160px]">
          {(["model", "agent", "consensus"] as const).map((type) => (
            <button
              key={type}
              onClick={() => copyFrom(type)}
              disabled={loading}
              className="block w-full text-left px-3 py-2 text-sm text-muted hover:text-foreground hover:bg-white/5 transition-colors first:rounded-t-lg last:rounded-b-lg"
            >
              {loading ? "Loading..." : type === "model" ? "Model (chalk)" : type === "agent" ? "Agent (upsets)" : "Consensus"}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── MiniSlot (compact for full bracket) ──────────────────

export function MiniSlot({
  team,
  isWinner,
  isEliminated,
  isCorrectPick,
  score,
}: {
  team: BracketTeam | null;
  isWinner: boolean;
  isEliminated?: boolean;
  isCorrectPick?: boolean;
  score?: number | null;
}) {
  if (!team) {
    return (
      <div className="flex items-center gap-1 px-1 py-0.5 min-h-[20px]">
        <span className="text-xs text-muted">TBD</span>
      </div>
    );
  }
  return (
    <div
      className={`flex items-center gap-1 px-1 py-0.5 min-h-[20px] rounded-sm ${
        isEliminated
          ? "bg-red-500/10"
          : isCorrectPick
          ? "bg-green-500/15"
          : isWinner
          ? "bg-green-500/10"
          : ""
      }`}
    >
      {team.logo && (
        <img src={team.logo} alt="" className={`w-3 h-3 object-contain shrink-0 ${isEliminated ? "grayscale" : ""}`} />
      )}
      <span className="text-xs text-muted font-mono shrink-0">{team.seed}</span>
      <span
        className={`text-xs truncate max-w-[72px] ${
          isEliminated ? "line-through text-red-400/60" : isWinner ? "font-semibold" : ""
        }`}
        title={team.name}
      >
        {abbreviateTeam(team.name)}
      </span>
      {score != null && (
        <span className={`text-xs font-mono ml-auto shrink-0 ${isWinner ? "text-green-400" : "text-muted"}`}>
          {score}
        </span>
      )}
      {isEliminated && <span className="text-red-400 text-[10px] font-bold shrink-0 ml-auto">X</span>}
      {isCorrectPick && <span className="text-green-400 text-[10px] font-bold shrink-0 ml-auto">&#10003;</span>}
    </div>
  );
}

// ─── MiniMatchupCard ──────────────────────────────────────

export function MiniMatchupCard({
  matchup,
  picks,
  slotId,
  eliminatedTeams,
  reverse,
}: {
  matchup: Matchup | null;
  picks: Record<string, number>;
  slotId: string;
  eliminatedTeams?: Set<number>;
  reverse?: boolean;
}) {
  if (!matchup || (!matchup.teamA && !matchup.teamB)) {
    return (
      <div className="rounded bg-card/50 border border-card-border border-dashed min-h-[42px] flex items-center justify-center">
        <span className="text-xs text-muted">TBD</span>
      </div>
    );
  }
  const { teamA, teamB, result } = matchup;
  const userPick = picks[slotId];
  const hasResult = result != null;
  const aIsWinner = hasResult && teamA != null && result.winnerId === teamA.id;
  const bIsWinner = hasResult && teamB != null && result.winnerId === teamB.id;
  const wrongPickA = hasResult && eliminatedTeams && userPick === teamA?.id && !aIsWinner;
  const wrongPickB = hasResult && eliminatedTeams && userPick === teamB?.id && !bIsWinner;
  const correctPickA = hasResult && eliminatedTeams && userPick === teamA?.id && aIsWinner;
  const correctPickB = hasResult && eliminatedTeams && userPick === teamB?.id && bIsWinner;
  const aEliminated = eliminatedTeams && teamA?.id ? eliminatedTeams.has(teamA.id) : false;
  const bEliminated = eliminatedTeams && teamB?.id ? eliminatedTeams.has(teamB.id) : false;

  const slotA = (
    <MiniSlot
      team={teamA}
      isWinner={aIsWinner}
      isEliminated={(aEliminated && !hasResult) || !!wrongPickA}
      isCorrectPick={!!correctPickA}
      score={hasResult ? (aIsWinner ? result.winnerScore : result.loserScore) : null}
    />
  );
  const slotB = (
    <MiniSlot
      team={teamB}
      isWinner={bIsWinner}
      isEliminated={(bEliminated && !hasResult) || !!wrongPickB}
      isCorrectPick={!!correctPickB}
      score={hasResult ? (bIsWinner ? result.winnerScore : result.loserScore) : null}
    />
  );

  return (
    <div className={`rounded bg-card border border-card-border overflow-hidden ${
      wrongPickA || wrongPickB ? "border-red-500/20" : ""
    }`}>
      {reverse ? <>{slotB}{slotA}</> : <>{slotA}{slotB}</>}
    </div>
  );
}

// ─── FullBracketView ──────────────────────────────────────

export function FullBracketView({
  bracket,
  displayPicks,
  eliminatedTeams,
  isOfficialMode,
  getMatchup,
}: {
  bracket: BracketData;
  displayPicks: Record<string, number>;
  eliminatedTeams: Set<number>;
  isOfficialMode: boolean;
  getMatchup: (m: Matchup | null, slotId: string) => Matchup | null;
}) {
  const regionNames = Object.keys(bracket.regions);
  const pairings = bracket.ffPairings;
  const topLeft = pairings[0]?.[0] ?? regionNames[0];
  const topRight = pairings[0]?.[1] ?? regionNames[1];
  const bottomLeft = pairings[1]?.[0] ?? regionNames[2];
  const bottomRight = pairings[1]?.[1] ?? regionNames[3];

  const elim = eliminatedTeams.size > 0 ? eliminatedTeams : undefined;

  const renderRegion = (regionName: string, reverse: boolean) => {
    const region = bracket.regions[regionName];
    if (!region) return null;
    const rounds = reverse ? [...region.rounds].reverse() : region.rounds;
    const roundNames = reverse
      ? [...bracket.roundNames].reverse()
      : bracket.roundNames;

    return (
      <div className="flex-1 min-w-0">
        <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-1.5 px-1">
          {regionName}
        </div>
        <div className={`flex gap-1.5 ${reverse ? "flex-row-reverse" : ""}`}>
          {rounds.map((round, displayIdx) => {
            const actualRoundIdx = reverse ? region.rounds.length - 1 - displayIdx : displayIdx;
            return (
              <div key={displayIdx} className="flex-1 min-w-0">
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1 truncate px-0.5">
                  {roundNames[displayIdx]?.replace("Round of ", "R")}
                </div>
                <div className="space-y-1" style={{ paddingTop: `${Math.pow(2, actualRoundIdx) * 4 - 4}px` }}>
                  {round.map((matchup, i) => {
                    const slotId = `${regionName}_r${actualRoundIdx}_${i}`;
                    return (
                      <div key={slotId} style={{ marginBottom: `${Math.pow(2, actualRoundIdx) * 8 - 8}px` }}>
                        <MiniMatchupCard
                          matchup={getMatchup(matchup, slotId)}
                          picks={displayPicks}
                          slotId={slotId}
                          eliminatedTeams={elim}
                          reverse={reverse}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[1100px]">
        {/* Top half */}
        <div className="flex gap-3 mb-4 items-start">
          {renderRegion(topLeft, false)}
          <div className="w-[140px] shrink-0 flex flex-col items-center justify-center pt-16">
            <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Semifinal 1</div>
            <MiniMatchupCard
              matchup={getMatchup(bracket.finalFour[0], "ff_0")}
              picks={displayPicks}
              slotId="ff_0"
              eliminatedTeams={elim}
            />
          </div>
          {renderRegion(topRight, true)}
        </div>

        {/* Championship */}
        <div className="flex justify-center my-3">
          <div className="w-[160px]">
            <div className="text-xs text-accent uppercase tracking-wider font-semibold mb-1 text-center">
              Championship
            </div>
            <MiniMatchupCard
              matchup={getMatchup(bracket.championship[0], "champ_0")}
              picks={displayPicks}
              slotId="champ_0"
              eliminatedTeams={elim}
            />
            {bracket.champion && (
              <div className="flex items-center gap-1 justify-center mt-1.5">
                <Trophy size={10} className="text-accent" />
                <span className="text-xs font-bold">{bracket.champion.name}</span>
              </div>
            )}
          </div>
        </div>

        {/* Bottom half */}
        <div className="flex gap-3 mt-4 items-start">
          {renderRegion(bottomLeft, false)}
          <div className="w-[140px] shrink-0 flex flex-col items-center justify-center pt-16">
            <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Semifinal 2</div>
            <MiniMatchupCard
              matchup={getMatchup(bracket.finalFour[1], "ff_1")}
              picks={displayPicks}
              slotId="ff_1"
              eliminatedTeams={elim}
            />
          </div>
          {renderRegion(bottomRight, true)}
        </div>
      </div>
    </div>
  );
}
