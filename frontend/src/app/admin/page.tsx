"use client";

import { useState, useEffect, useCallback } from "react";
import { API_URL } from "@/lib/api";

type ActionStatus = {
  loading: boolean;
  message: string | null;
  error: boolean;
};

function useActionStatus(): [ActionStatus, (fn: () => Promise<unknown>) => Promise<void>] {
  const [status, setStatus] = useState<ActionStatus>({ loading: false, message: null, error: false });

  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setStatus({ loading: true, message: null, error: false });
    try {
      const result = await fn();
      const msg = typeof result === "object" && result !== null
        ? JSON.stringify(result, null, 2)
        : String(result);
      setStatus({ loading: false, message: msg, error: false });
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      setStatus({ loading: false, message: errMsg, error: true });
    }
  }, []);

  return [status, run];
}

async function apiPost(path: string, email: string, params?: Record<string, string>) {
  const url = new URL(`${API_URL}${path}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

function ActionButton({
  label,
  onClick,
  status,
  variant = "default",
}: {
  label: string;
  onClick: () => void;
  status: ActionStatus;
  variant?: "default" | "accent" | "danger";
}) {
  const baseClasses = "px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50";
  const variantClasses = {
    default: "bg-card border border-card-border hover:border-accent/40 text-foreground",
    accent: "bg-accent/20 border border-accent/30 hover:bg-accent/30 text-accent",
    danger: "bg-red-500/20 border border-red-500/30 hover:bg-red-500/30 text-red-400",
  };

  return (
    <div className="space-y-1">
      <button
        onClick={onClick}
        disabled={status.loading}
        className={`${baseClasses} ${variantClasses[variant]}`}
      >
        {status.loading ? "Running..." : label}
      </button>
      {status.message && (
        <pre
          className={`text-xs p-2 rounded max-h-32 overflow-auto whitespace-pre-wrap ${
            status.error ? "bg-red-500/10 text-red-400" : "bg-green-500/10 text-green-400"
          }`}
        >
          {status.message}
        </pre>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [email, setEmail] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [authError, setAuthError] = useState(false);

  // Action statuses
  const [seedsM, runSeedsM] = useActionStatus();
  const [seedsW, runSeedsW] = useActionStatus();
  const [modelM, runModelM] = useActionStatus();
  const [modelW, runModelW] = useActionStatus();
  const [agentM, runAgentM] = useActionStatus();
  const [agentW, runAgentW] = useActionStatus();
  const [consensusM, runConsensusM] = useActionStatus();
  const [consensusW, runConsensusW] = useActionStatus();
  const [resetModelM, runResetModelM] = useActionStatus();
  const [resetModelW, runResetModelW] = useActionStatus();
  const [resetAgentM, runResetAgentM] = useActionStatus();
  const [resetAgentW, runResetAgentW] = useActionStatus();
  const [resetConsensusM, runResetConsensusM] = useActionStatus();
  const [resetConsensusW, runResetConsensusW] = useActionStatus();
  const [cron, runCron] = useActionStatus();

  const tryLogin = useCallback(async (loginEmail: string) => {
    setAuthError(false);
    try {
      const res = await fetch(`${API_URL}/api/admin/auth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail }),
      });
      const data = await res.json();
      if (data.authorized) {
        setAuthorized(true);
        setEmail(loginEmail);
        localStorage.setItem("admin_email", loginEmail);
      } else {
        setAuthError(true);
      }
    } catch {
      setAuthError(true);
    }
  }, []);

  // Auto-login from saved email
  useEffect(() => {
    const saved = localStorage.getItem("admin_email");
    if (saved) {
      setEmail(saved);
      tryLogin(saved);
    }
  }, [tryLogin]);

  const handleLogin = () => tryLogin(email);

  if (!authorized) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="bg-card border border-card-border rounded-xl p-8 w-full max-w-sm space-y-4">
          <h1 className="text-xl font-bold text-center">Admin Access</h1>
          <p className="text-sm text-muted text-center">Enter your admin email to continue.</p>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            placeholder="Email address"
            className="w-full px-3 py-2 rounded-lg bg-background border border-card-border text-foreground text-sm focus:outline-none focus:border-accent/50"
          />
          {authError && (
            <p className="text-xs text-red-400 text-center">Unauthorized email address.</p>
          )}
          <button
            onClick={handleLogin}
            className="w-full px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/80 transition-colors"
          >
            Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-sm text-muted">Logged in as {email}</p>
      </div>

      <div className="space-y-8">
        {/* Refresh Seeds */}
        <section className="bg-card border border-card-border rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-1">Refresh Seeds</h2>
          <p className="text-xs text-muted mb-4">Fetch tournament seeds from ESPN and update the database.</p>
          <div className="flex flex-wrap gap-3">
            <ActionButton
              label="Men's Seeds"
              status={seedsM}
              onClick={() => runSeedsM(() => apiPost("/api/admin/seeds/refresh", email, { gender: "M" }))}
            />
            <ActionButton
              label="Women's Seeds"
              status={seedsW}
              onClick={() => runSeedsW(() => apiPost("/api/admin/seeds/refresh", email, { gender: "W" }))}
            />
          </div>
        </section>

        {/* Generate Model Bracket */}
        <section className="bg-card border border-card-border rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-1">Model Bracket</h2>
          <p className="text-xs text-muted mb-4">Generate the chalk (model-favorite) bracket. Locked once created.</p>
          <div className="flex flex-wrap gap-3">
            <ActionButton
              label="Generate Men's"
              status={modelM}
              variant="accent"
              onClick={() => runModelM(() => apiPost("/api/admin/bracket/generate", email, { gender: "M", bracket_type: "model" }))}
            />
            <ActionButton
              label="Generate Women's"
              status={modelW}
              variant="accent"
              onClick={() => runModelW(() => apiPost("/api/admin/bracket/generate", email, { gender: "W", bracket_type: "model" }))}
            />
            <ActionButton
              label="Reset Men's"
              status={resetModelM}
              variant="danger"
              onClick={() => runResetModelM(() => apiPost("/api/admin/bracket/reset", email, { gender: "M", bracket_type: "model" }))}
            />
            <ActionButton
              label="Reset Women's"
              status={resetModelW}
              variant="danger"
              onClick={() => runResetModelW(() => apiPost("/api/admin/bracket/reset", email, { gender: "W", bracket_type: "model" }))}
            />
          </div>
        </section>

        {/* Generate Agent Bracket */}
        <section className="bg-card border border-card-border rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-1">Agent Bracket</h2>
          <p className="text-xs text-muted mb-4">Generate the balanced (agent-style, slight upset variance) bracket.</p>
          <div className="flex flex-wrap gap-3">
            <ActionButton
              label="Generate Men's"
              status={agentM}
              variant="accent"
              onClick={() => runAgentM(() => apiPost("/api/admin/bracket/generate", email, { gender: "M", bracket_type: "agent" }))}
            />
            <ActionButton
              label="Generate Women's"
              status={agentW}
              variant="accent"
              onClick={() => runAgentW(() => apiPost("/api/admin/bracket/generate", email, { gender: "W", bracket_type: "agent" }))}
            />
            <ActionButton
              label="Reset Men's"
              status={resetAgentM}
              variant="danger"
              onClick={() => runResetAgentM(() => apiPost("/api/admin/bracket/reset", email, { gender: "M", bracket_type: "agent" }))}
            />
            <ActionButton
              label="Reset Women's"
              status={resetAgentW}
              variant="danger"
              onClick={() => runResetAgentW(() => apiPost("/api/admin/bracket/reset", email, { gender: "W", bracket_type: "agent" }))}
            />
          </div>
        </section>

        {/* Generate Consensus Bracket */}
        <section className="bg-card border border-card-border rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-1">Consensus Bracket</h2>
          <p className="text-xs text-muted mb-4">Combine model + agent brackets. Both must exist first.</p>
          <div className="flex flex-wrap gap-3">
            <ActionButton
              label="Generate Men's"
              status={consensusM}
              variant="accent"
              onClick={() => runConsensusM(() => apiPost("/api/admin/bracket/consensus", email, { gender: "M" }))}
            />
            <ActionButton
              label="Generate Women's"
              status={consensusW}
              variant="accent"
              onClick={() => runConsensusW(() => apiPost("/api/admin/bracket/consensus", email, { gender: "W" }))}
            />
            <ActionButton
              label="Reset Men's"
              status={resetConsensusM}
              variant="danger"
              onClick={() => runResetConsensusM(() => apiPost("/api/admin/bracket/reset", email, { gender: "M", bracket_type: "consensus" }))}
            />
            <ActionButton
              label="Reset Women's"
              status={resetConsensusW}
              variant="danger"
              onClick={() => runResetConsensusW(() => apiPost("/api/admin/bracket/reset", email, { gender: "W", bracket_type: "consensus" }))}
            />
          </div>
        </section>

        {/* Run Cron Pipeline */}
        <section className="bg-card border border-card-border rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-1">Run Cron Pipeline</h2>
          <p className="text-xs text-muted mb-4">
            Full daily update: Elo, player stats, SOS, advanced stats, records, power ratings, predictions. May take several minutes.
          </p>
          <ActionButton
            label="Run Full Pipeline"
            status={cron}
            variant="danger"
            onClick={() => runCron(() => apiPost("/api/admin/cron/run", email))}
          />
        </section>
      </div>
    </div>
  );
}
