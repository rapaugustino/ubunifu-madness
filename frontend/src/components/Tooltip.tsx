"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Info } from "lucide-react";

export function Tooltip({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  const [show, setShow] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const [position, setPosition] = useState<"top" | "bottom">("top");
  const triggerRef = useRef<HTMLSpanElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (show && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const above = rect.top > 80;
      setPosition(above ? "top" : "bottom");

      // position: fixed is viewport-relative, so do NOT add scrollY
      const top = above ? rect.top - 8 : rect.bottom + 8;
      // Clamp left so tooltip doesn't overflow horizontally
      const centerX = rect.left + rect.width / 2;
      const clampedLeft = Math.max(120, Math.min(centerX, window.innerWidth - 120));

      setCoords({ top, left: clampedLeft });
    }
  }, [show]);

  return (
    <span
      ref={triggerRef}
      className="inline-flex items-center"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && mounted && createPortal(
        <span
          className="fixed px-2.5 py-1.5 text-xs text-foreground bg-[#1a1a2e] border border-card-border rounded-lg shadow-lg whitespace-normal max-w-[220px] text-center leading-relaxed pointer-events-none"
          style={{
            zIndex: 99999,
            top: coords.top,
            left: coords.left,
            transform: position === "top"
              ? "translate(-50%, -100%)"
              : "translate(-50%, 0)",
          }}
        >
          {text}
        </span>,
        document.body
      )}
    </span>
  );
}

export function MetricLabel({
  label,
  tooltip,
  className = "",
}: {
  label: string;
  tooltip: string;
  className?: string;
}) {
  return (
    <Tooltip text={tooltip}>
      <span className={`inline-flex items-center gap-1 ${className}`}>
        {label}
        <Info size={10} className="text-muted/50 shrink-0" />
      </span>
    </Tooltip>
  );
}

// Centralized metric definitions
export const METRIC_TOOLTIPS: Record<string, string> = {
  elo: "Elo rating measures team strength. Higher is better. Average D1 team is ~1500.",
  offEfficiency: "Points scored per 100 possessions. Measures how efficient the offense is.",
  defEfficiency: "Points allowed per 100 possessions. Lower is better defense.",
  tempo: "Average possessions per game. Higher means faster pace of play.",
  efgPct: "Effective field goal %. Adjusts for 3-pointers being worth more. Above 52% is strong.",
  toPct: "Turnover rate — % of possessions ending in a turnover. Lower is better.",
  orPct: "Offensive rebound rate — % of missed shots recovered. Higher means more second chances.",
  ftRate: "Free throw rate — free throw attempts relative to field goal attempts.",
  oppEfgPct: "Opponent eFG%. Measures defensive ability to contest shots. Lower is better.",
  oppToPct: "Forced turnover rate — how often the defense forces turnovers. Higher is better.",
  winProb: "Win probability from our ML model (LightGBM + Logistic Regression ensemble).",
  seed: "NCAA tournament seed. #1 is strongest, #16 is weakest in each region.",
  confAvgElo: "Average Elo of all teams in the conference. Higher means stronger conference.",
  confNcWinRate: "Conference's win rate against other conferences this season. The best measure of overall conference strength.",
  confDepth: "How evenly matched teams are within the conference. Higher means more parity — no weak links.",
  confTop5Elo: "Average Elo of the top 5 teams. Measures elite talent at the top of the conference.",
  ncWinrate: "Conference's win rate in non-conference games. Shows overall conference strength.",
  tourneyWinRate: "Conference's historical tournament win rate across all March Madness games.",
  trend: "Compares last 10 games win% vs season average. >5% difference triggers hot/cold indicator.",
  masseyRank: "Composite ranking from Massey Ratings, aggregating 100+ ranking systems.",
  momentum: "Recent form based on last 10 games — win percentage and margin of victory.",
  lastNMov: "Average margin of victory/loss in the last 10 games.",
  brier: "Brier score measures prediction accuracy. 0 is perfect, 0.25 is random. Lower is better.",
  sos: "Strength of schedule — average Elo of all opponents faced. Higher means tougher schedule.",
  adjEM: "Adjusted Efficiency Margin — opponent-adjusted net points per 100 possessions. The single best measure of team quality.",
  adjOE: "Adjusted Offensive Efficiency — points scored per 100 possessions, adjusted for opponent defensive strength.",
  adjDE: "Adjusted Defensive Efficiency — points allowed per 100 possessions, adjusted for opponent offensive strength. Lower is better.",
  barthag: "Probability of beating an average D1 team on a neutral court. Derived from adjusted efficiency using a Pythagorean formula.",
  luck: "Actual win% minus expected win% from point differential. Positive = overperforming (likely to regress). Negative = unlucky.",
  trueShooting: "True Shooting % — overall scoring efficiency accounting for 2-pointers, 3-pointers, and free throws in one number.",
  oppTrueShooting: "Opponent True Shooting % — how efficiently opponents score against this team's defense. Lower is better.",
  threePtRate: "Three-Point Attempt Rate — fraction of field goal attempts that are three-pointers. Higher = more perimeter-oriented offense.",
  astToRatio: "Assist-to-Turnover Ratio — measures ball movement quality and offensive discipline. Higher means fewer wasted possessions.",
  drbPct: "Defensive Rebound % — rate of securing defensive rebounds, denying opponents second-chance points.",
  stlPct: "Steal % — steals per opponent possession. Measures perimeter defensive pressure and ball hawking.",
  blkPct: "Block % — blocks per opponent two-point attempt. Measures rim protection and interior defense.",
  closeRecord: "Record in games decided by 5 or fewer points. Shows clutch performance and ability to win tight games.",
  marginStdev: "Standard deviation of scoring margin across all games. Lower = more consistent; higher = more volatile/unpredictable.",
  floorCeiling: "10th / 90th percentile net efficiency. Floor = worst games, Ceiling = best games. Wide gap = high variance team.",
  upsetVulnerability: "Composite upset risk score (0-100). Factors in volatility, luck, 3-point reliance, and free throw shooting. Higher = more upset-prone.",
  pythWinPct: "Pythagorean Win % — expected winning percentage based purely on points scored vs. points allowed. Removes close-game variance.",
  // Player stats
  ppg: "Points Per Game — average points scored per game played.",
  rpg: "Rebounds Per Game — average total rebounds (offensive + defensive) per game.",
  apg: "Assists Per Game — average assists per game. Measures playmaking ability.",
  spg: "Steals Per Game — average steals per game. Measures perimeter defense and anticipation.",
  bpg: "Blocks Per Game — average blocks per game. Measures rim protection.",
  fgPct: "Field Goal % — overall shooting percentage on all two-point and three-point attempts.",
  fg3Pct: "Three-Point % — shooting percentage on three-point attempts only.",
  ftPct: "Free Throw % — shooting percentage from the free throw line.",
  mpg: "Minutes Per Game — average minutes played per game.",
  gp: "Games Played — total number of games with recorded stats this season.",
  // Conference advanced
  avgAdjEM: "Conference average Adjusted Efficiency Margin — mean opponent-adjusted net points per 100 possessions across all teams.",
  avgBarthag: "Conference average Barthag — mean probability of beating an average D1 team across all teams.",
};
