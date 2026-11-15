"use client";
import { useEffect, useState } from "react";

export function setTheme(t: string) {
  document.documentElement.dataset.theme = t;
  try { localStorage.theme = t; } catch {}
}
export default function ThemeToggle() {
  const [t, setT] = useState("light");
  useEffect(() => setT(document.documentElement.dataset.theme || "light"), []);
  return (
    <button className="btn gh" style={{ minHeight: 38, padding: "0 14px" }}
      onClick={() => { const n = t === "dark" ? "light" : "dark"; setTheme(n); setT(n); }}
      aria-label="Toggle light and dark mode">{t === "dark" ? "☀ Light" : "☾ Dark"}</button>
  );
}
