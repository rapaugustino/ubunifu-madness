"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useGender } from "@/hooks/useGender";
import { useBracketSync } from "@/hooks/useBracketSync";
import { RefreshCw, Download, Trophy, Save, Check, CloudDownload } from "lucide-react";

import type { BracketData, BracketTeam, Matchup, RegionData, BracketMode } from "./types";
import { API_URL, BRACKET_MODES, picksKey } from "./types";
import {
  TeamSlot,
  MatchupCard,
  AnalysisPanel,
  EmailModal,
  CopyFromMenu,
  FullBracketView,
} from "./components";

export default function BracketPage() {
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [loading, setLoading] = useState(true);
  const [gender, setGender] = useGender();
  const [activeRegion, setActiveRegion] = useState("East");
  const [picks, setPicks] = useState<Record<string, number>>({});
  const [analysisMatchup, setAnalysisMatchup] = useState<Matchup | null>(null);
  const [bracketMode, setBracketMode] = useState<BracketMode>("my_bracket");
  const [officialPicks, setOfficialPicks] = useState<Record<string, number> | null>(null);
  const [officialMeta, setOfficialMeta] = useState<Record<string, unknown> | null>(null);
  const [officialLoading, setOfficialLoading] = useState(false);

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
    if (bracketMode === "my_bracket" || bracketMode === "actual") {
      setOfficialPicks(null);
      setOfficialMeta(null);
      return;
    }
    setOfficialLoading(true);
    setOfficialPicks(null);
    setOfficialMeta(null);
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

  const displayPicks = bracketMode === "my_bracket" ? picks : bracketMode === "actual" ? {} : (officialPicks ?? {});
  const isReadOnly = bracketMode !== "my_bracket";

  const fetchBracket = useCallback(async () => {
    setLoading(true);
    setBracket(null);
    setPicks({});
    setLiveProbCache({});
    try {
      const res = await fetch(`${API_URL}/api/bracket/full?gender=${gender}&season=0`);
      const data: BracketData = await res.json();
      setBracket(data);

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

  // Build a team lookup from all bracket data
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

  // Live prediction cache
  const [liveProbCache, setLiveProbCache] = useState<Record<string, number>>({});

  const fetchLiveProb = useCallback((teamAId: number, teamBId: number) => {
    const key = `${Math.min(teamAId, teamBId)}_${Math.max(teamAId, teamBId)}`;
    if (liveProbCache[key] !== undefined) return;
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
    fetchLiveProb(teamAId, teamBId);
    const tA = teamLookup[teamAId];
    const tB = teamLookup[teamBId];
    if (tA?.elo && tB?.elo) {
      return 1 / (1 + Math.pow(10, (tB.elo - tA.elo) / 400));
    }
    return 0.5;
  };

  // Build dynamic matchups for later rounds based on picks
  const dynamicMatchups = useMemo(() => {
    if (!bracket) return {} as Record<string, Matchup>;
    const activePicks = bracketMode === "my_bracket" ? picks : (officialPicks ?? {});
    const dynamic: Record<string, Matchup> = {};

    // Resolve First Four picks into R64 TBD slots
    if (bracket.firstFour) {
      for (let fi = 0; fi < bracket.firstFour.length; fi++) {
        const ffSlot = `first_four_${fi}`;
        const ffPick = activePicks[ffSlot];
        const ffResult = bracket.firstFour[fi]?.result;
        const winnerId = ffResult ? ffResult.winnerId : ffPick;
        if (!winnerId) continue;

        const ff = bracket.firstFour[fi];
        const ffRegion = ff.region;
        const ffSeed = ff.seed;

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

    // Within a region: r0_0 + r0_1 -> r1_0, etc.
    for (const regionName of Object.keys(bracket.regions)) {
      const region = bracket.regions[regionName];
      for (let roundIdx = 1; roundIdx < region.rounds.length; roundIdx++) {
        const prevRound = region.rounds[roundIdx - 1];
        for (let i = 0; i < prevRound.length; i += 2) {
          const nextIdx = Math.floor(i / 2);
          const nextSlot = `${regionName}_r${roundIdx}_${nextIdx}`;

          const existing = region.rounds[roundIdx]?.[nextIdx];
          if (existing?.teamA?.id && existing?.teamB?.id) continue;

          const slotA = `${regionName}_r${roundIdx - 1}_${i}`;
          const slotB = `${regionName}_r${roundIdx - 1}_${i + 1}`;

          let winnerA = activePicks[slotA];
          let winnerB = activePicks[slotB];

          if (!winnerA) {
            const prevMatchA = region.rounds[roundIdx - 1]?.[i];
            if (prevMatchA?.result) winnerA = prevMatchA.result.winnerId;
          }
          if (!winnerB) {
            const prevMatchB = region.rounds[roundIdx - 1]?.[i + 1];
            if (prevMatchB?.result) winnerB = prevMatchB.result.winnerId;
          }

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

    // Final Four
    const ffPairings: string[][] = bracket.ffPairings || [];
    for (let ffIdx = 0; ffIdx < ffPairings.length; ffIdx++) {
      const [regionA, regionB] = ffPairings[ffIdx];
      const regA: RegionData | undefined = bracket.regions[regionA];
      const regB: RegionData | undefined = bracket.regions[regionB];
      if (!regA || !regB) continue;

      const slotA = `${regionA}_r${regA.rounds.length - 1}_0`;
      const slotB = `${regionB}_r${regB.rounds.length - 1}_0`;

      let winnerA = activePicks[slotA];
      let winnerB = activePicks[slotB];
      if (!winnerA && dynamic[slotA]?.result) winnerA = dynamic[slotA].result!.winnerId;
      if (!winnerB && dynamic[slotB]?.result) winnerB = dynamic[slotB].result!.winnerId;

      if (!winnerA) {
        const rw = regA.winner;
        if (rw?.id) winnerA = rw.id;
      }
      if (!winnerB) {
        const rw = regB.winner;
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

    // Championship
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

  // Get the effective matchup for a slot
  const isOfficialMode = bracketMode !== "my_bracket" && bracketMode !== "actual";
  const getMatchup = useCallback(
    (backendMatchup: Matchup | null, slotId: string): Matchup | null => {
      if (bracketMode === "actual") {
        if (slotId.startsWith("champ_")) {
          const anyFfResult = bracket?.finalFour?.some((m: Matchup | null) => m?.result);
          if (!anyFfResult) return null;
        }
        if (slotId.startsWith("ff_")) {
          if (!backendMatchup?.teamA || !backendMatchup?.teamB) return null;
        }
        return backendMatchup;
      }
      const isFfOrChamp = slotId.startsWith("ff_") || slotId.startsWith("champ_");
      if (isFfOrChamp && isOfficialMode && dynamicMatchups[slotId]) {
        return dynamicMatchups[slotId];
      }
      if (backendMatchup?.teamA?.id && backendMatchup?.teamB?.id) return backendMatchup;
      return dynamicMatchups[slotId] ?? backendMatchup;
    },
    [dynamicMatchups, isOfficialMode, bracketMode, bracket]
  );

  // Compute eliminated teams
  const eliminatedTeams = useMemo(() => {
    if (!bracket || bracketMode === "actual") return new Set<number>();
    const activePicks = bracketMode === "my_bracket" ? picks : (officialPicks ?? {});
    const eliminated = new Set<number>();

    const checkSlot = (slotId: string, matchup: Matchup | null) => {
      if (!matchup?.result) return;
      const pick = activePicks[slotId];
      if (pick && pick !== matchup.result.winnerId) {
        eliminated.add(pick);
      }
    };

    if (bracket.firstFour) {
      bracket.firstFour.forEach((m, i) => checkSlot(`first_four_${i}`, m));
    }
    for (const regionName of Object.keys(bracket.regions)) {
      const region = bracket.regions[regionName];
      for (let roundIdx = 0; roundIdx < region.rounds.length; roundIdx++) {
        region.rounds[roundIdx].forEach((m, matchIdx) => {
          checkSlot(`${regionName}_r${roundIdx}_${matchIdx}`, m);
        });
      }
    }
    bracket.finalFour.forEach((m, i) => checkSlot(`ff_${i}`, m));
    bracket.championship.forEach((m, i) => checkSlot(`champ_${i}`, m));

    return eliminated;
  }, [bracket, picks, officialPicks, bracketMode]);

  // Bracket score
  const bracketScore = useMemo(() => {
    if (!bracket || bracketMode === "actual") return null;
    const activePicks = bracketMode === "my_bracket" ? picks : (officialPicks ?? {});
    let correct = 0;
    let total = 0;

    const checkSlot = (slotId: string, matchup: Matchup | null) => {
      if (!matchup?.result) return;
      const pick = activePicks[slotId];
      if (pick) {
        total++;
        if (pick === matchup.result.winnerId) correct++;
      }
    };

    if (bracket.firstFour) {
      bracket.firstFour.forEach((m, i) => checkSlot(`first_four_${i}`, m));
    }
    for (const regionName of Object.keys(bracket.regions)) {
      const region = bracket.regions[regionName];
      for (let roundIdx = 0; roundIdx < region.rounds.length; roundIdx++) {
        region.rounds[roundIdx].forEach((m, matchIdx) => {
          checkSlot(`${regionName}_r${roundIdx}_${matchIdx}`, m);
        });
      }
    }
    bracket.finalFour.forEach((m, i) => checkSlot(`ff_${i}`, m));
    bracket.championship.forEach((m, i) => checkSlot(`champ_${i}`, m));

    return { correct, total };
  }, [bracket, picks, officialPicks, bracketMode]);

  const handlePick = (slotId: string, teamId: number) => {
    if (!bracket) return;
    const newPicks = { ...picks, [slotId]: teamId };
    const oldPick = picks[slotId];
    if (oldPick && oldPick !== teamId) {
      const clearDownstream = (oldTeamId: number) => {
        for (const [key, val] of Object.entries(newPicks)) {
          if (key !== slotId && val === oldTeamId) {
            delete newPicks[key];
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

  // ─── Render ─────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted">Loading bracket...</div>
      </div>
    );
  }

  if (!bracket || !bracket.hasBracket) {
    return (
      <div className="min-h-screen max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-2">Interactive Bracket</h1>
        <p className="text-muted">No bracket data available yet. Check back after Selection Sunday.</p>
      </div>
    );
  }

  const regionNames = Object.keys(bracket.regions);
  const currentRegion = bracket.regions[activeRegion];
  const isHistorical = bracket.isComplete;
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
              ? `Champion: ${bracket.champion?.name ?? "TBD"}`
              : bracket.currentRound
              ? `${bracket.currentRound} — ${bracket.totalGamesPlayed} of 67 games played`
              : isOfficialMode
              ? BRACKET_MODES.find((m) => m.key === bracketMode)?.description ?? ""
              : "Click matchups to make your picks. Probabilities powered by our ML model."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canInteract && (
            <>
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
                <button
                  onClick={sync.manualSave}
                  disabled={sync.saving}
                  className="flex items-center gap-1.5 px-3 py-2 bg-accent/10 text-accent rounded-lg text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-50"
                >
                  <Save size={14} />
                  {sync.saving ? "Saving..." : "Save"}
                </button>
                <span className="text-xs text-muted">{sync.email}</span>
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

      {/* Official bracket not generated banner */}
      {isOfficialMode && !officialLoading && !officialPicks && !isHistorical && (
        <div className="mb-6 p-4 rounded-xl bg-card border border-card-border text-center">
          <p className="text-sm text-muted">
            {bracketMode === "consensus"
              ? "Consensus bracket will be available after Model and Agent brackets are generated."
              : `${BRACKET_MODES.find((m) => m.key === bracketMode)?.label} bracket has not been generated yet. Check back soon.`}
          </p>
        </div>
      )}

      {/* Score banner */}
      {bracketMode !== "actual" && bracketScore && bracketScore.total > 0 && (
        <div className="mb-6 p-3 rounded-lg bg-white/[0.02] border border-card-border flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {isOfficialMode && officialPicks && (
              <>
                <Check size={14} className="text-green-400 shrink-0" />
                <span className="text-xs text-green-400">
                  {BRACKET_MODES.find((m) => m.key === bracketMode)?.label} bracket locked.
                  {officialMeta && bracketMode === "consensus" && (
                    <> Agreement: {String(officialMeta.agreement_pct)}% ({String(officialMeta.contested_slots)} contested picks).</>
                  )}
                </span>
              </>
            )}
            {bracketMode === "my_bracket" && (
              <span className="text-xs text-muted">Your picks vs actual results</span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className="flex items-center gap-1.5">
              <span className={`text-sm font-bold ${
                bracketScore.correct / bracketScore.total >= 0.7 ? "text-green-400" :
                bracketScore.correct / bracketScore.total >= 0.5 ? "text-accent" :
                "text-red-400"
              }`}>
                {bracketScore.correct}/{bracketScore.total}
              </span>
              <span className="text-xs text-muted">correct</span>
              <span className={`text-xs font-mono ${
                bracketScore.correct / bracketScore.total >= 0.7 ? "text-green-400" :
                bracketScore.correct / bracketScore.total >= 0.5 ? "text-accent" :
                "text-red-400"
              }`}>
                ({(bracketScore.correct / bracketScore.total * 100).toFixed(1)}%)
              </span>
            </div>
            <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  bracketScore.correct / bracketScore.total >= 0.7 ? "bg-green-400" :
                  bracketScore.correct / bracketScore.total >= 0.5 ? "bg-accent" :
                  "bg-red-400"
                }`}
                style={{ width: `${(bracketScore.correct / bracketScore.total) * 100}%` }}
              />
            </div>
          </div>
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

      {/* Region tabs */}
      <div className="flex items-center gap-1 mb-6 p-1 bg-card rounded-lg border border-card-border w-fit flex-wrap">
        <button
          onClick={() => setActiveRegion("Full Bracket")}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            activeRegion === "Full Bracket"
              ? "bg-accent/15 text-accent"
              : "text-muted hover:text-foreground"
          }`}
        >
          Full Bracket
        </button>
        <div className="w-px h-4 bg-card-border mx-0.5" />
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
      {activeRegion === "Full Bracket" ? (
        <FullBracketView
          bracket={bracket}
          displayPicks={displayPicks}
          eliminatedTeams={eliminatedTeams}
          isOfficialMode={isOfficialMode}
          getMatchup={getMatchup}
        />
      ) : activeRegion === "First Four" ? (
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
                <div className="text-xs text-muted mb-1 uppercase tracking-wider">
                  {matchup.region} Region — {matchup.seed} Seed
                </div>
                <MatchupCard
                  matchup={matchup}
                  isHistorical={isHistorical || isReadOnly || matchup.result != null}
                  picks={displayPicks}
                  slotId={`first_four_${i}`}
                  onPick={handlePick}
                  onAnalyze={setAnalysisMatchup}
                  eliminatedTeams={bracketMode !== "actual" ? eliminatedTeams : undefined}
                />
              </div>
            ))}
          </div>
        </div>
      ) : activeRegion === "Final Four" ? (
        <div className="space-y-6">
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
                    eliminatedTeams={bracketMode !== "actual" ? eliminatedTeams : undefined}
                  />
                );
              })}
            </div>
          </div>

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
                      eliminatedTeams={bracketMode !== "actual" ? eliminatedTeams : undefined}
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
                      eliminatedTeams={bracketMode !== "actual" ? eliminatedTeams : undefined}
                    />
                  );
                })}
              </div>
            </div>
          ))}

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

      {/* Email modal */}
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
