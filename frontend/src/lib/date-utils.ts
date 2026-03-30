/** Format a Date as YYYYMMDD (local time). */
export function toDateStr(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
}

/** Today as YYYYMMDD. */
export function todayStr(): string {
  return toDateStr(new Date());
}

/** Yesterday as YYYYMMDD. */
export function yesterdayStr(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return toDateStr(d);
}

/** Tomorrow as YYYYMMDD. */
export function tomorrowStr(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return toDateStr(d);
}

/** Human-readable date, e.g. "Saturday, March 29". */
export function displayDateLong(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

/** Human-readable date with year, e.g. "Saturday, March 29, 2026". */
export function displayDateFull(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/** Short human-readable date, e.g. "Sat, Mar 29". */
export function displayDateShort(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}
