"use client";
import { useEffect, useRef, useState } from "react";

export default function DictateButton({ value, onChange, disabled }: {
  value: string; onChange: (v: string) => void; disabled?: boolean;
}) {
  const [on, setOn] = useState(false);
  const [ok, setOk] = useState(true);
  const [err, setErr] = useState("");
  const rec = useRef<any>(null);
  const base = useRef("");
  const cb = useRef(onChange);
  cb.current = onChange;

  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setOk(false); return; }
    const r = new SR();
    r.continuous = true;
    r.interimResults = true;
    r.lang = navigator.language || "en-US";
    r.onresult = (e: any) => {
      let t = "";
      for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
      cb.current((base.current + " " + t).trim());
    };
    r.onerror = (e: any) => {
      setErr(e.error === "not-allowed" ? "Microphone access was blocked." : "Dictation stopped. Try again.");
      setOn(false);
    };
    r.onend = () => setOn(false);
    rec.current = r;
    return () => { try { r.abort(); } catch {} };
  }, []);

  function toggle() {
    if (!rec.current) return;
    setErr("");
    if (on) { rec.current.stop(); return; }
    base.current = value;
    try { rec.current.start(); setOn(true); } catch {}
  }

  if (!ok) return null;
  return (
    <>
      <button type="button" className={"btn " + (on ? "" : "gh")} onClick={toggle} disabled={disabled}
        aria-pressed={on} aria-label={on ? "Stop dictation" : "Start dictation"}>
        {on ? "● Stop" : "🎤 Dictate"}
      </button>
      {err && <span className="err" role="alert">{err}</span>}
    </>
  );
}