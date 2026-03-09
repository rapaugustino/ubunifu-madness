"use client";

import { Matchup } from "@/lib/types";
import WinProbBar from "./WinProbBar";
import { Sparkles } from "lucide-react";

interface MatchupCardProps {
  matchup: Matchup;
  onAnalyze?: () => void;
}

export default function MatchupCard({ matchup, onAnalyze }: MatchupCardProps) {
  const { teamA, teamB, winProbA, region } = matchup;

  return (
    <div className="p-4 rounded-xl bg-card border border-card-border hover:border-accent/20 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-muted font-medium uppercase tracking-wider">
          {region} Region
        </span>
        <span className="text-xs text-muted">Round {matchup.round}</span>
      </div>

      <WinProbBar
        teamA={teamA.name}
        teamB={teamB.name}
        probA={winProbA}
        seedA={teamA.seed}
        seedB={teamB.seed}
      />

      <div className="mt-3 flex items-center justify-between">
        <div className="flex gap-3 text-xs text-muted">
          <span>
            Elo: {teamA.elo} vs {teamB.elo}
          </span>
        </div>
        {onAnalyze && (
          <button
            onClick={onAnalyze}
            className="flex items-center gap-1 text-xs text-accent hover:text-accent-secondary transition-colors"
          >
            <Sparkles size={12} />
            AI Analysis
          </button>
        )}
      </div>
    </div>
  );
}
