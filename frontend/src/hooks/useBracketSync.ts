"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface BracketSyncState {
  email: string | null;
  userId: number | null;
  saving: boolean;
  lastSaved: Date | null;
}

/**
 * Hook for bracket persistence via email-only accounts.
 * - Handles identify (upsert user by email), save, and load
 * - Debounces saves (800ms) so every pick change auto-saves
 * - Stores email/userId in localStorage for session persistence
 */
export function useBracketSync(
  season: number,
  gender: string,
  picks: Record<string, number>,
  onLoadPicks: (picks: Record<string, number>) => void,
) {
  const [state, setState] = useState<BracketSyncState>({
    email: null,
    userId: null,
    saving: false,
    lastSaved: null,
  });
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState<"save" | "load">("save");

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const picksRef = useRef(picks);
  picksRef.current = picks;

  // Restore email/userId from localStorage on mount, and auto-load picks from server
  useEffect(() => {
    const email = localStorage.getItem("bracket_user_email");
    const userId = localStorage.getItem("bracket_user_id");
    if (email && userId) {
      setState((s) => ({ ...s, email, userId: Number(userId) }));
      // Auto-load saved picks from server
      fetch(
        `${API_URL}/api/users/brackets?email=${encodeURIComponent(email)}&season=${season}&gender=${gender}`
      )
        .then((res) => res.json())
        .then((data) => {
          if (data.found && data.picks && Object.keys(data.picks).length > 0) {
            onLoadPicks(data.picks);
          }
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season, gender]);

  // Auto-save picks when they change (debounced), only if user is identified
  useEffect(() => {
    if (!state.userId || !season || Object.keys(picks).length === 0) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      savePicks(state.userId!, picksRef.current);
    }, 800);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picks, state.userId, season, gender]);

  const savePicks = async (userId: number, picksToSave: Record<string, number>) => {
    setState((s) => ({ ...s, saving: true }));
    try {
      await fetch(`${API_URL}/api/users/${userId}/brackets/${season}/${gender}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ picks: picksToSave }),
      });
      setState((s) => ({ ...s, saving: false, lastSaved: new Date() }));
    } catch {
      setState((s) => ({ ...s, saving: false }));
    }
  };

  const identify = useCallback(
    async (email: string): Promise<boolean> => {
      try {
        const res = await fetch(`${API_URL}/api/users/identify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        if (!res.ok) return false;
        const data = await res.json();

        localStorage.setItem("bracket_user_email", data.email);
        localStorage.setItem("bracket_user_id", String(data.userId));
        setState((s) => ({
          ...s,
          email: data.email,
          userId: data.userId,
        }));

        // If saving mode, save current picks immediately
        if (modalMode === "save" && Object.keys(picksRef.current).length > 0) {
          await savePicks(data.userId, picksRef.current);
        }

        // If loading mode, try to load picks from server
        if (modalMode === "load") {
          const loadRes = await fetch(
            `${API_URL}/api/users/brackets?email=${encodeURIComponent(email)}&season=${season}&gender=${gender}`
          );
          const loadData = await loadRes.json();
          if (loadData.found && loadData.picks) {
            onLoadPicks(loadData.picks);
          }
        }

        setShowModal(false);
        return true;
      } catch {
        return false;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [season, gender, modalMode]
  );

  const openSaveModal = () => {
    setModalMode("save");
    setShowModal(true);
  };

  const openLoadModal = () => {
    setModalMode("load");
    setShowModal(true);
  };

  const disconnect = () => {
    localStorage.removeItem("bracket_user_email");
    localStorage.removeItem("bracket_user_id");
    setState({ email: null, userId: null, saving: false, lastSaved: null });
  };

  return {
    ...state,
    showModal,
    modalMode,
    setShowModal,
    identify,
    openSaveModal,
    openLoadModal,
    disconnect,
    isConnected: !!state.userId,
  };
}
