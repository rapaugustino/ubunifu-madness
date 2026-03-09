"use client";

interface WinProbBarProps {
  teamA: string;
  teamB: string;
  probA: number;
  seedA?: number;
  seedB?: number;
}

export default function WinProbBar({ teamA, teamB, probA, seedA, seedB }: WinProbBarProps) {
  const probB = 1 - probA;
  const pctA = Math.round(probA * 100);
  const pctB = Math.round(probB * 100);
  const isUpset = seedA && seedB && seedA > seedB && probA > 0.5;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between text-sm mb-1.5">
        <div className="flex items-center gap-2">
          {seedA && (
            <span className="text-xs bg-white/10 px-1.5 py-0.5 rounded font-mono">
              {seedA}
            </span>
          )}
          <span className={`font-medium ${probA > 0.5 ? "text-foreground" : "text-muted"}`}>
            {teamA}
          </span>
        </div>
        <span className={`font-mono text-sm ${probA > 0.5 ? "text-accent font-semibold" : "text-muted"}`}>
          {pctA}%
        </span>
      </div>

      <div className="relative h-2.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`absolute left-0 top-0 h-full rounded-full prob-bar transition-all ${
            isUpset ? "bg-red-500" : "bg-accent"
          }`}
          style={{ width: `${pctA}%` }}
        />
        <div
          className="absolute right-0 top-0 h-full rounded-full prob-bar bg-blue-500/60"
          style={{ width: `${pctB}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-sm mt-1.5">
        <div className="flex items-center gap-2">
          {seedB && (
            <span className="text-xs bg-white/10 px-1.5 py-0.5 rounded font-mono">
              {seedB}
            </span>
          )}
          <span className={`font-medium ${probB > 0.5 ? "text-foreground" : "text-muted"}`}>
            {teamB}
          </span>
        </div>
        <span className={`font-mono text-sm ${probB > 0.5 ? "text-blue-400 font-semibold" : "text-muted"}`}>
          {pctB}%
        </span>
      </div>

      {isUpset && (
        <div className="mt-1 text-xs text-red-400 font-medium">
          Upset Alert
        </div>
      )}
    </div>
  );
}
