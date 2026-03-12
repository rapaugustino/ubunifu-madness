"use client";

import { useState, useEffect, useCallback } from "react";

type Gender = "M" | "W";

const STORAGE_KEY = "um-gender";
const EVENT_NAME = "um-gender-change";

/**
 * Shared gender state persisted in localStorage.
 * All instances stay in sync via a custom DOM event + storage event.
 */
function getStored(fallback: Gender): Gender {
  if (typeof window === "undefined") return fallback;
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "M" || v === "W" ? v : fallback;
}

export function useGender(defaultGender: Gender = "M") {
  // Always start with defaultGender to match SSR, then hydrate from localStorage
  const [gender, setGenderState] = useState<Gender>(defaultGender);

  // Hydrate from localStorage after mount (avoids SSR/client mismatch)
  useEffect(() => {
    const stored = getStored(defaultGender);
    if (stored !== defaultGender) {
      setGenderState(stored);
    }
  }, [defaultGender]);

  // Listen for changes from other components / tabs
  useEffect(() => {
    const handleCustom = (e: Event) => {
      const g = (e as CustomEvent<Gender>).detail;
      setGenderState(g);
    };
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && (e.newValue === "M" || e.newValue === "W")) {
        setGenderState(e.newValue);
      }
    };

    window.addEventListener(EVENT_NAME, handleCustom);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener(EVENT_NAME, handleCustom);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  const setGender = useCallback((g: Gender) => {
    setGenderState(g);
    localStorage.setItem(STORAGE_KEY, g);
    // Notify other hook instances in the same tab
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: g }));
  }, []);

  return [gender, setGender] as const;
}
