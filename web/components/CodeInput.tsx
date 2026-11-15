"use client";
import { useRef } from "react";

export default function CodeInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const set = (i: number, ch: string) => {
    const arr = value.padEnd(6, " ").split("");
    arr[i] = ch || " ";
    onChange(arr.join("").trimEnd());
    if (ch && i < 5) refs.current[i + 1]?.focus();
  };
  return (
    <div className="row" style={{ justifyContent: "center", gap: 10 }}
      onPaste={(e) => { const t = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6); if (t) { e.preventDefault(); onChange(t); refs.current[Math.min(t.length, 5)]?.focus(); } }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <input key={i} ref={(el) => { refs.current[i] = el; }} className="cb" inputMode="numeric" maxLength={1}
          aria-label={`Digit ${i + 1}`} value={(value[i] || "").trim()}
          onChange={(e) => set(i, e.target.value.replace(/\D/g, ""))}
          onKeyDown={(e) => { if (e.key === "Backspace" && !value[i] && i > 0) refs.current[i - 1]?.focus(); }} />
      ))}
    </div>
  );
}
