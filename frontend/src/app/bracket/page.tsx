"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useGender } from "@/hooks/useGender";
import { useBracketSync } from "@/hooks/useBracketSync";
import { Sparkles, RefreshCw, Download, Trophy, X, Save, Check, CloudDownload } from "lucide-react";

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

interface FirstFourMatchup extends Matchup {
  region: string;
  seed: number;
}

interface BracketData {
  season: number;
  gender: string;
  hasBracket: boolean;
  isComplete: boolean;
  firstFour: FirstFourMatchup[];
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
        <span className={`text-xs font-mono shrink-0 ${isWinner ? "font-bold text-green-400" : "text-muted"}`}>
          {score}
        </span>
      )}
      {isWinner && score != null && (
        <span className="text-green-400 text-[10px] shrink-0">W</span>
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
  const canPick = !isHistorical;

  return (
    <div className="p-2 rounded-lg bg-card border border-card-border space-y-1 group relative">
      <TeamSlot
        team={teamA}
        isWinner={aIsWinner}
        isPicked={teamA != null && userPick === teamA.id}
        canPick={canPick && teamA != null && teamA.id != null}
        onClick={teamA?.id ? () => onPick(slotId, teamA.id) : undefined}
        score={hasResult ? (aIsWinner ? result.winnerScore : result.loserScore) : null}
      />
      <TeamSlot
        team={teamB}
        isWinner={bIsWinner}
        isPicked={teamB != null && userPick === teamB.id}
        canPick={canPick && teamB != null && teamB.id != null}
        onClick={teamB?.id ? () => onPick(slotId, teamB.id) : undefined}
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

function EmailModal({
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

function CopyFromMenu({
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

type BracketMode = "my_bracket" | "model" | "agent" | "consensus";

const BRACKET_MODES: { key: BracketMode; label: string; description: string }[] = [
  { key: "my_bracket", label: "My Bracket", description: "Fill out your own picks" },
  { key: "model", label: "Model", description: "V6 ML ensemble picks (chalk)" },
  { key: "agent", label: "Agent", description: "AI agent picks (balanced upsets)" },
  { key: "consensus", label: "Consensus", description: "Model + Agent combined" },
];

export default function BracketPage() {
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [loading, setLoading] = useState(true);
  const [gender, setGender] = useGender();
  const [activeRegion, setActiveRegion] = useState("East");
  const [picks, setPicks] = useState<Record<string, number>>({});
  const [analysisMatchup, setAnalysisMatchup] = useState<Matchup | null>(null);
  const [autoFilling, setAutoFilling] = useState(false);
  const [bracketMode, setBracketMode] = useState<BracketMode>("my_bracket");
  const [officialPicks, setOfficialPicks] = useState<Record<string, number> | null>(null);
  const [officialMeta, setOfficialMeta] = useState<Record<string, unknown> | null>(null);
  const [officialLoading, setOfficialLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [simResults, setSimResults] = useState<{
    championProbabilities: { teamId: number; teamName: string; probability: number }[];
    finalFourProbabilities: { teamId: number; teamName: string; probability: number }[];
  } | null>(null);

  const sync = useBracketSync(
    bracket?.season ?? 0,
    gender,
    picks,
    (loadedPicks) => {
      setPicks(loadedPicks);
      if (bracket) {
        localStorage.setItem(picksKey(bracket.season, gender), JSON.stringify(loadedPicks));
      }
    },
  );

  // Load official bracket when mode changes
  useEffect(() => {
    if (bracketMode === "my_bracket") {
      setOfficialPicks(null);
      setOfficialMeta(null);
      return;
    }
    setOfficialLoading(true);
    fetch(`${API_URL}/api/bracket/official?gender=${gender}&bracket_type=${bracketMode}&season=0`)
      .then((res) => res.json())
      .then((data) => {
        if (data.exists) {
          setOfficialPicks(data.picks);
          setOfficialMeta(data.metadata);
        } else {
          setOfficialPicks(null);
          setOfficialMeta(null);
        }
      })
      .catch(() => {
        setOfficialPicks(null);
        setOfficialMeta(null);
      })
      .finally(() => setOfficialLoading(false));
  }, [bracketMode, gender]);

  const generateOfficial = async () => {
    if (!bracket || generating) return;
    setGenerating(true);
    try {
      const endpoint =
        bracketMode === "consensus"
          ? `${API_URL}/api/bracket/official/consensus?gender=${gender}&season=${bracket.season}`
          : `${API_URL}/api/bracket/official/generate?gender=${gender}&bracket_type=${bracketMode}&season=${bracket.season}`;
      const res = await fetch(endpoint, { method: "POST" });
      const data = await res.json();
      if (data.exists && data.picks) {
        setOfficialPicks(data.picks);
        setOfficialMeta(data.metadata);
      }
    } catch {}
    setGenerating(false);
  };

  // Which picks to display based on mode
  const displayPicks = bracketMode === "my_bracket" ? picks : (officialPicks ?? {});
  const isReadOnly = bracketMode !== "my_bracket" && officialPicks !== null;

  const fetchBracket = useCallback(async () => {
    setLoading(true);
    setBracket(null);
    setPicks({});
    setLiveProbCache({});
    setSimResults(null);
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

  // Build a team lookup from all bracket data for dynamic matchup building
  const teamLookup = useMemo(() => {
    if (!bracket) return {} as Record<number, BracketTeam>;
    const lookup: Record<number, BracketTeam> = {};
    for (const region of Object.values(bracket.regions)) {
      for (const round of region.rounds) {
        for (const m of round) {
          if (m?.teamA?.id) lookup[m.teamA.id] = m.teamA;
          if (m?.teamB?.id) lookup[m.teamB.id] = m.teamB;
        }
      }
    }
    for (const m of bracket.firstFour) {
      if (m?.teamA?.id) lookup[m.teamA.id] = m.teamA;
      if (m?.teamB?.id) lookup[m.teamB.id] = m.teamB;
    }
    for (const m of bracket.finalFour) {
      if (m?.teamA?.id) lookup[m.teamA.id] = m.teamA;
      if (m?.teamB?.id) lookup[m.teamB.id] = m.teamB;
    }
    return lookup;
  }, [bracket]);

  // Build dynamic matchups for later rounds based on user picks.
  // When both feeder slots have picks, create a matchup for the next round.
  // Cache of fetched live predictions: "teamAId_teamBId" -> winProbA
  const [liveProbCache, setLiveProbCache] = useState<Record<string, number>>({});

  // Fetch live prediction for a pair of teams
  const fetchLiveProb = useCallback((teamAId: number, teamBId: number) => {
    const key = `${Math.min(teamAId, teamBId)}_${Math.max(teamAId, teamBId)}`;
    if (liveProbCache[key] !== undefined) return;
    // Mark as pending to avoid duplicate fetches
    setLiveProbCache((prev) => ({ ...prev, [key]: -1 }));
    fetch(`${API_URL}/api/predictions/${Math.min(teamAId, teamBId)}/${Math.max(teamAId, teamBId)}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.win_prob_a !== undefined) {
          setLiveProbCache((prev) => ({ ...prev, [key]: data.win_prob_a }));
        }
      })
      .catch(() => {});
  }, [liveProbCache]);

  const getLiveProb = (teamAId: number | null, teamBId: number | null): number => {
    if (!teamAId || !teamBId) return 0.5;
    const key = `${Math.min(teamAId, teamBId)}_${Math.max(teamAId, teamBId)}`;
    const cached = liveProbCache[key];
    if (cached !== undefined && cached >= 0) {
      return teamAId === Math.min(teamAId, teamBId) ? cached : 1 - cached;
    }
    // Trigger fetch if not cached
    fetchLiveProb(teamAId, teamBId);
    // Fallback to Elo while loading
    const tA = teamLookup[teamAId];
    const tB = teamLookup[teamBId];
    if (tA?.elo && tB?.elo) {
      return 1 / (1 + Math.pow(10, (tB.elo - tA.elo) / 400));
    }
    return 0.5;
  };

  const dynamicMatchups = useMemo(() => {
    if (!bracket) return {} as Record<string, Matchup>;
    const activePicks = bracketMode === "my_bracket" ? picks : (officialPicks ?? {});
    const dynamic: Record<string, Matchup> = {};

    // First: resolve First Four picks into R64 TBD slots.
    // A First Four pick fills the null-id team in the R64 matchup for that region+seed.
    // Resolve First Four winners into R64 TBD slots
    if (bracket.firstFour) {
      for (let fi = 0; fi < bracket.firstFour.length; fi++) {
        const ffSlot = `first_four_${fi}`;
        const ffPick = activePicks[ffSlot];
        const ffResult = bracket.firstFour[fi]?.result;
        const winnerId = ffResult ? ffResult.winnerId : ffPick;
        if (!winnerId) continue;

        const ff = bracket.firstFour[fi];
        const ffRegion = ff.region; // e.g. "Midwest"
        const ffSeed = ff.seed;

        // Find the R64 slot in this region that has a TBD team with this seed
        const region = bracket.regions[ffRegion];
        if (!region) continue;
        const r64 = region.rounds[0];
        for (let mi = 0; mi < r64.length; mi++) {
          const m = r64[mi];
          if (!m) continue;
          const aNeedsFill = m.teamA && m.teamA.id === null && m.teamA.seed === ffSeed;
          const bNeedsFill = m.teamB && m.teamB.id === null && m.teamB.seed === ffSeed;
          if (aNeedsFill || bNeedsFill) {
            const slotId = `${ffRegion}_r0_${mi}`;
            const winnerTeam = teamLookup[winnerId];
            if (winnerTeam) {
              const existingMatchup = m;
              const resolvedA = aNeedsFill ? winnerTeam : existingMatchup.teamA;
              const resolvedB = bNeedsFill ? winnerTeam : existingMatchup.teamB;
              dynamic[slotId] = {
                teamA: resolvedA,
                teamB: resolvedB,
                winProbA: getLiveProb(resolvedA?.id ?? null, resolvedB?.id ?? null),
                result: existingMatchup.result,
              };
            }
            break;
          }
        }
      }
    }

    // Within a region: r0_0 + r0_1 -> r1_0, r0_2 + r0_3 -> r1_1, etc.
    for (const regionName of Object.keys(bracket.regions)) {
      const region = bracket.regions[regionName];
      for (let roundIdx = 1; roundIdx < region.rounds.length; roundIdx++) {
        const prevRound = region.rounds[roundIdx - 1];
        for (let i = 0; i < prevRound.length; i += 2) {
          const nextIdx = Math.floor(i / 2);
          const nextSlot = `${regionName}_r${roundIdx}_${nextIdx}`;

          // If backend already has a real matchup with real teams, skip
          const existing = region.rounds[roundIdx]?.[nextIdx];
          if (existing?.teamA?.id && existing?.teamB?.id) continue;

          const slotA = `${regionName}_r${roundIdx - 1}_${i}`;
          const slotB = `${regionName}_r${roundIdx - 1}_${i + 1}`;

          // Check picks or game results for feeder slots
          let winnerA = activePicks[slotA];
          let winnerB = activePicks[slotB];

          // Also check game results from the backend
          if (!winnerA) {
            const prevMatchA = region.rounds[roundIdx - 1]?.[i];
            if (prevMatchA?.result) winnerA = prevMatchA.result.winnerId;
          }
          if (!winnerB) {
            const prevMatchB = region.rounds[roundIdx - 1]?.[i + 1];
            if (prevMatchB?.result) winnerB = prevMatchB.result.winnerId;
          }

          // Also check dynamic matchup results
          const dynA = dynamic[slotA];
          const dynB = dynamic[slotB];
          if (!winnerA && dynA?.result) winnerA = dynA.result.winnerId;
          if (!winnerB && dynB?.result) winnerB = dynB.result.winnerId;

          const teamA = winnerA ? teamLookup[winnerA] : null;
          const teamB = winnerB ? teamLookup[winnerB] : null;

          if (teamA || teamB) {
            dynamic[nextSlot] = {
              teamA: teamA ?? null,
              teamB: teamB ?? null,
              winProbA: getLiveProb(teamA?.id ?? null, teamB?.id ?? null),
              result: null,
            };
          }
        }
      }
    }

    // Final Four: region winners feed into ff_0, ff_1
    const regionNames = Object.keys(bracket.regions);
    const regionWinnerSlots = regionNames.map((rn) => {
      const region = bracket.regions[rn];
      const lastRound = region.rounds.length - 1;
      return `${rn}_r${lastRound}_0`;
    });

    // ff_0 = region 0 winner vs region 1 winner
    // ff_1 = region 2 winner vs region 3 winner
    for (let ffIdx = 0; ffIdx < 2; ffIdx++) {
      const slotA = regionWinnerSlots[ffIdx * 2];
      const slotB = regionWinnerSlots[ffIdx * 2 + 1];
      if (!slotA || !slotB) continue;

      let winnerA = activePicks[slotA];
      let winnerB = activePicks[slotB];
      if (!winnerA && dynamic[slotA]?.result) winnerA = dynamic[slotA].result!.winnerId;
      if (!winnerB && dynamic[slotB]?.result) winnerB = dynamic[slotB].result!.winnerId;

      // Also check backend region winners
      if (!winnerA) {
        const rw = bracket.regions[regionNames[ffIdx * 2]]?.winner;
        if (rw?.id) winnerA = rw.id;
      }
      if (!winnerB) {
        const rw = bracket.regions[regionNames[ffIdx * 2 + 1]]?.winner;
        if (rw?.id) winnerB = rw.id;
      }

      const teamA = winnerA ? teamLookup[winnerA] : null;
      const teamB = winnerB ? teamLookup[winnerB] : null;
      if (teamA || teamB) {
        dynamic[`ff_${ffIdx}`] = {
          teamA: teamA ?? null,
          teamB: teamB ?? null,
          winProbA: 0.5,
          result: null,
        };
      }
    }

    // Championship: ff_0 winner vs ff_1 winner
    const ffWinnerA = activePicks["ff_0"];
    const ffWinnerB = activePicks["ff_1"];
    const champA = ffWinnerA ? teamLookup[ffWinnerA] : null;
    const champB = ffWinnerB ? teamLookup[ffWinnerB] : null;
    if (champA || champB) {
      dynamic["champ_0"] = {
        teamA: champA ?? null,
        teamB: champB ?? null,
        winProbA: 0.5,
        result: null,
      };
    }

    return dynamic;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bracket, picks, officialPicks, bracketMode, teamLookup, liveProbCache]);

  // Get the effective matchup for a slot (backend data or dynamic)
  const getMatchup = useCallback(
    (backendMatchup: Matchup | null, slotId: string): Matchup | null => {
      // If backend has a full matchup with both teams, use it
      if (backendMatchup?.teamA?.id && backendMatchup?.teamB?.id) return backendMatchup;
      // Otherwise check dynamic
      return dynamicMatchups[slotId] ?? backendMatchup;
    },
    [dynamicMatchups]
  );

  const handlePick = (slotId: string, teamId: number) => {
    if (!bracket) return;
    // When changing a pick, cascade-clear downstream picks that depended on the old pick
    const newPicks = { ...picks, [slotId]: teamId };
    const oldPick = picks[slotId];
    if (oldPick && oldPick !== teamId) {
      // Clear all downstream slots that had the old team picked
      const clearDownstream = (oldTeamId: number) => {
        for (const [key, val] of Object.entries(newPicks)) {
          if (key !== slotId && val === oldTeamId) {
            delete newPicks[key];
            // Recursively clear further downstream
            clearDownstream(oldTeamId);
          }
        }
      };
      clearDownstream(oldPick);
    }
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

    const activePicks = displayPicks;
    const genderLabel = gender === "W" ? "Women's" : "Men's";
    const modeLabel = BRACKET_MODES.find((m) => m.key === bracketMode)?.label ?? "My Bracket";
    const title = `${bracket.season} ${genderLabel} NCAA Tournament Bracket`;
    const date = new Date().toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });

    // Build a team name lookup from bracket data
    const teamNames: Record<number, string> = {};
    const teamSeeds: Record<number, number | null> = {};
    for (const region of Object.values(bracket.regions)) {
      for (const round of region.rounds) {
        for (const m of round) {
          if (m?.teamA) { teamNames[m.teamA.id] = m.teamA.name; teamSeeds[m.teamA.id] = m.teamA.seed; }
          if (m?.teamB) { teamNames[m.teamB.id] = m.teamB.name; teamSeeds[m.teamB.id] = m.teamB.seed; }
        }
      }
    }

    const pickTag = bracketMode === "my_bracket" ? "YOUR PICK" : modeLabel.toUpperCase();

    const matchupLine = (m: Matchup | null, slotId: string) => {
      if (!m || !m.teamA || !m.teamB) return "  TBD vs TBD";
      const a = m.teamA;
      const b = m.teamB;
      const seedA = a.seed ? `(${a.seed})` : "";
      const seedB = b.seed ? `(${b.seed})` : "";
      const probA = (m.winProbA * 100).toFixed(0);
      const probB = ((1 - m.winProbA) * 100).toFixed(0);
      const pick = activePicks[slotId];
      const markA = pick === a.id ? ` << ${pickTag}` : "";
      const markB = pick === b.id ? ` << ${pickTag}` : "";

      let result = "";
      if (m.result) {
        const winner = m.result.winnerId === a.id ? a.name : b.name;
        result = `  Result: ${winner} ${m.result.winnerScore}-${m.result.loserScore}`;
      }

      return [
        `  ${seedA} ${a.name} (${probA}%)${markA}`,
        `  ${seedB} ${b.name} (${probB}%)${markB}`,
        result,
      ]
        .filter(Boolean)
        .join("\n");
    };

    let text = `${"=".repeat(60)}\n`;
    text += `  ${title}\n`;
    text += `  ${modeLabel} Bracket | Generated by Ubunifu Madness\n`;
    text += `  ${date} | madness.ubunifutech.com\n`;
    text += `${"=".repeat(60)}\n\n`;

    for (const [regionName, region] of Object.entries(bracket.regions)) {
      text += `--- ${regionName.toUpperCase()} REGION ${"─".repeat(Math.max(0, 42 - regionName.length))}\n\n`;

      region.rounds.forEach((round, roundIdx) => {
        const roundLabel = bracket.roundNames[roundIdx] || `Round ${roundIdx + 1}`;
        text += `  ${roundLabel}\n  ${"─".repeat(roundLabel.length)}\n`;
        round.forEach((matchup, i) => {
          text += matchupLine(matchup, `${regionName}_r${roundIdx}_${i}`) + "\n\n";
        });
      });

      // Show who advances from this region based on picks
      const e8Slot = `${regionName}_r3_0`;
      const e8Pick = activePicks[e8Slot];
      if (e8Pick && teamNames[e8Pick]) {
        const seed = teamSeeds[e8Pick];
        text += `  >> ${regionName} to Final Four: ${seed ? `(${seed}) ` : ""}${teamNames[e8Pick]}\n\n`;
      } else if (region.winner) {
        text += `  >> ${regionName} to Final Four: ${region.winner.name}\n\n`;
      }
    }

    text += `--- FINAL FOUR ${"─".repeat(43)}\n\n`;
    bracket.finalFour.forEach((matchup, i) => {
      text += matchupLine(matchup, `ff_${i}`) + "\n\n";
    });

    if (bracket.championship.length > 0) {
      text += `--- CHAMPIONSHIP ${"─".repeat(41)}\n\n`;
      bracket.championship.forEach((matchup, i) => {
        text += matchupLine(matchup, `champ_${i}`) + "\n\n";
      });
    }

    // Show champion from picks
    const champPick = activePicks["champ_0"];
    if (champPick && teamNames[champPick]) {
      const seed = teamSeeds[champPick];
      text += `${"=".repeat(60)}\n`;
      text += `  NATIONAL CHAMPION: ${seed ? `(${seed}) ` : ""}${teamNames[champPick]}\n`;
      text += `${"=".repeat(60)}\n`;
    } else if (bracket.champion) {
      text += `${"=".repeat(60)}\n`;
      text += `  NATIONAL CHAMPION: ${bracket.champion.name}\n`;
      text += `${"=".repeat(60)}\n`;
    }

    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.write(`<!DOCTYPE html>
<html>
<head>
  <title>${title} - ${modeLabel}</title>
  <style>
    body {
      font-family: "Courier New", Courier, monospace;
      font-size: 11px;
      line-height: 1.5;
      padding: 24px;
      white-space: pre;
      color: #111;
      background: #fff;
    }
    @media print {
      body { padding: 12px; font-size: 10px; }
      @page { margin: 0.5in; }
    }
  </style>
</head>
<body>${text.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</body>
</html>`);
    printWindow.document.close();
    printWindow.print();
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
  const isOfficialMode = bracketMode !== "my_bracket";
  const canInteract = !isHistorical && !isReadOnly;

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
              : isOfficialMode
              ? BRACKET_MODES.find((m) => m.key === bracketMode)?.description ?? ""
              : "Click matchups to make your picks. Probabilities powered by our ML model."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canInteract && (
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
              <CopyFromMenu
                gender={gender}
                season={bracket.season}
                onCopy={(copiedPicks) => {
                  setPicks(copiedPicks);
                  localStorage.setItem(picksKey(bracket.season, gender), JSON.stringify(copiedPicks));
                }}
              />
            </>
          )}
          <button
            onClick={exportBracket}
            className="flex items-center gap-1.5 px-3 py-2 bg-white/5 text-muted rounded-lg text-sm hover:text-foreground hover:bg-white/10 transition-colors"
          >
            <Download size={14} />
            Export
          </button>
          {canInteract && (
            sync.isConnected ? (
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-xs text-green-400">
                  <Check size={12} />
                  {sync.saving ? "Saving..." : "Saved"}
                </span>
                <button
                  onClick={sync.disconnect}
                  className="text-xs text-muted hover:text-foreground transition-colors"
                  title="Disconnect account"
                >
                  {sync.email}
                </button>
              </div>
            ) : (
              <>
                <button
                  onClick={sync.openSaveModal}
                  className="flex items-center gap-1.5 px-3 py-2 bg-accent/10 text-accent rounded-lg text-sm font-medium hover:bg-accent/20 transition-colors"
                >
                  <Save size={14} />
                  Save
                </button>
                <button
                  onClick={sync.openLoadModal}
                  className="flex items-center gap-1.5 px-3 py-2 bg-white/5 text-muted rounded-lg text-sm hover:text-foreground hover:bg-white/10 transition-colors"
                >
                  <CloudDownload size={14} />
                  Load
                </button>
              </>
            )
          )}
        </div>
      </div>

      {/* Gender toggle + Bracket mode selector */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-6">
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
        <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
          {BRACKET_MODES.map((mode) => (
            <button
              key={mode.key}
              onClick={() => setBracketMode(mode.key)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                bracketMode === mode.key
                  ? "bg-accent text-white"
                  : "text-muted hover:text-foreground"
              }`}
              title={mode.description}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Official bracket status banner */}
      {isOfficialMode && !officialLoading && !officialPicks && !isHistorical && (
        <div className="mb-6 p-4 rounded-xl bg-card border border-card-border text-center">
          <p className="text-sm text-muted">
            {bracketMode === "consensus"
              ? "Consensus bracket will be available after Model and Agent brackets are generated."
              : `${BRACKET_MODES.find((m) => m.key === bracketMode)?.label} bracket has not been generated yet. Check back soon.`}
          </p>
        </div>
      )}

      {/* Official bracket locked banner */}
      {isOfficialMode && officialPicks && (
        <div className="mb-6 p-3 rounded-lg bg-green-500/5 border border-green-500/10 flex items-center gap-2">
          <Check size={14} className="text-green-400 shrink-0" />
          <span className="text-xs text-green-400">
            {BRACKET_MODES.find((m) => m.key === bracketMode)?.label} bracket locked.
            {officialMeta && bracketMode === "consensus" && (
              <> Agreement: {String(officialMeta.agreement_pct)}% ({String(officialMeta.contested_slots)} contested picks).</>
            )}
          </span>
        </div>
      )}

      {officialLoading && (
        <div className="mb-6 flex items-center gap-2 text-sm text-muted">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          Loading bracket...
        </div>
      )}

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
        {bracket.firstFour && bracket.firstFour.length > 0 && (
          <button
            onClick={() => setActiveRegion("First Four")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeRegion === "First Four"
                ? "bg-accent/15 text-accent"
                : "text-muted hover:text-foreground"
            }`}
          >
            First Four
          </button>
        )}
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
      {activeRegion === "First Four" ? (
        <div>
          <h3 className="text-sm font-medium text-muted mb-3 uppercase tracking-wider">
            First Four — Play-In Games
          </h3>
          <p className="text-xs text-muted mb-4">
            Winners advance to the Round of 64 in their respective regions.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl">
            {bracket.firstFour.map((matchup, i) => (
              <div key={`ff4_${i}`}>
                <div className="text-[10px] text-muted mb-1 uppercase tracking-wider">
                  {matchup.region} Region — {matchup.seed} Seed
                </div>
                <MatchupCard
                  matchup={matchup}
                  isHistorical={isHistorical || isReadOnly || matchup.result != null}
                  picks={displayPicks}
                  slotId={`first_four_${i}`}
                  onPick={handlePick}
                  onAnalyze={setAnalysisMatchup}
                />
              </div>
            ))}
          </div>
        </div>
      ) : activeRegion === "Final Four" ? (
        <div className="space-y-6">
          {/* Final Four */}
          <div>
            <h3 className="text-sm font-medium text-muted mb-3 uppercase tracking-wider">
              Final Four
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl">
              {bracket.finalFour.map((matchup, i) => {
                const slotId = `ff_${i}`;
                return (
                  <MatchupCard
                    key={slotId}
                    matchup={getMatchup(matchup, slotId)}
                    isHistorical={isHistorical || isReadOnly}
                    picks={displayPicks}
                    slotId={slotId}
                    onPick={handlePick}
                    onAnalyze={setAnalysisMatchup}
                  />
                );
              })}
            </div>
          </div>

          {/* Championship */}
          {bracket.championship.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-accent mb-3 uppercase tracking-wider">
                Championship
              </h3>
              <div className="max-w-sm">
                {bracket.championship.map((matchup, i) => {
                  const slotId = `champ_${i}`;
                  return (
                    <MatchupCard
                      key={slotId}
                      matchup={getMatchup(matchup, slotId)}
                      isHistorical={isHistorical}
                      picks={displayPicks}
                      slotId={slotId}
                      onPick={handlePick}
                      onAnalyze={setAnalysisMatchup}
                    />
                  );
                })}
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
                {round.map((matchup, i) => {
                  const slotId = `${activeRegion}_r${roundIdx}_${i}`;
                  const effectiveMatchup = getMatchup(matchup, slotId);
                  return (
                    <MatchupCard
                      key={slotId}
                      matchup={effectiveMatchup}
                      isHistorical={isHistorical}
                      picks={displayPicks}
                      slotId={slotId}
                      onPick={handlePick}
                      onAnalyze={setAnalysisMatchup}
                    />
                  );
                })}
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

      {/* Email modal for save/load */}
      {sync.showModal && (
        <EmailModal
          mode={sync.modalMode}
          onSubmit={sync.identify}
          onClose={() => sync.setShowModal(false)}
        />
      )}
    </div>
  );
}
