"use client";

import { useState, useEffect } from "react";
import { useGender } from "@/hooks/useGender";
import Link from "next/link";
import { Search } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TeamItem {
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

export default function TeamsPage() {
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [search, setSearch] = useState("");
  const [gender, setGender] = useGender();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/teams?gender=${gender}&limit=500`)
      .then((r) => r.json())
      .then((data) => setTeams(data.teams || []))
      .catch(() => setTeams([]))
      .finally(() => setLoading(false));
  }, [gender]);

  const filtered = teams.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      (t.conference || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen max-w-7xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold">Teams</h1>
          <p className="text-muted text-sm mt-1">
            Click a team to view their full profile and analytics
          </p>
        </div>
        <div className="flex items-center gap-3">
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
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Search teams..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 bg-card border border-card-border rounded-lg text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-accent/50 w-64"
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="text-center text-muted py-12">Loading teams...</div>
      ) : (
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filtered.map((team) => (
            <Link
              key={team.id}
              href={`/teams/${team.id}`}
              className="p-4 rounded-xl bg-card border border-card-border hover:border-accent/30 transition-colors group"
            >
              <div className="flex items-center gap-3 mb-3">
                {team.logo ? (
                  <img src={team.logo} alt="" className="w-10 h-10 object-contain shrink-0" />
                ) : (
                  <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center text-sm font-bold text-accent">
                    {team.name.slice(0, 2)}
                  </div>
                )}
                <div className="min-w-0">
                  <div className="font-medium text-sm group-hover:text-accent transition-colors truncate">
                    {team.name}
                  </div>
                  <div className="text-xs text-muted truncate">{team.conference || "—"}</div>
                </div>
              </div>
              <div className="flex items-center justify-between text-xs text-muted">
                <div className="flex items-center gap-2">
                  {team.seed && (
                    <span className="px-1.5 py-0.5 bg-accent/10 text-accent rounded text-[10px] font-medium">
                      #{team.seed}
                    </span>
                  )}
                  <span>
                    Elo: <span className="font-mono text-foreground">{team.elo || "—"}</span>
                  </span>
                </div>
                <span className="font-mono">{team.record || "—"}</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center text-muted py-12">No teams found matching &ldquo;{search}&rdquo;</div>
      )}
    </div>
  );
}
