"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const TYPES: any = { mcq: "Multiple choice (10)", short: "Short answer (10)", mixed: "Mixed (15)" };

export default function Quizzes() {
  const [v, setV] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [f, setF] = useState({ topic: "", quiz_type: "mcq", source: "knowledge", difficulty: "medium" });
  const [ans, setAns] = useState<any[]>([]);
  const [i, setI] = useState(0);
  useEffect(() => { api("/quiz/active").then(setV).finally(() => setLoading(false)); }, []);
  async function act(path: string, body: any) {
    setBusy(true); setErr("");
    try { setV(await api(path, { method: "POST", body })); setAns([]); setI(0); } catch (e: any) { setErr(e.message); }
    setBusy(false);
  }
  if (loading) return <p className="m">Loading…</p>;
  const status = busy ? <p className="m" role="status">Working on it… a full quiz can take up to a minute.</p> : null;

  if (!v || (v.status !== "active" && v.phase !== "done")) return (
    <>
      <h2 className="h2">Quizzes</h2>
      <form className="c col" onSubmit={(e) => { e.preventDefault(); act("/quiz/start", f); }}>
        <label className="col" style={{ gap: 6 }}><span className="m">Quiz topic</span><input className="in" required value={f.topic} onChange={(e) => setF({ ...f, topic: e.target.value })} /></label>
        <div className="g2">
          <label className="col" style={{ gap: 6 }}><span className="m">Quiz type</span><select className="in" value={f.quiz_type} onChange={(e) => setF({ ...f, quiz_type: e.target.value })}>{Object.keys(TYPES).map((k) => <option key={k} value={k}>{TYPES[k]}</option>)}</select></label>
          <label className="col" style={{ gap: 6 }}><span className="m">Questions come from</span><select className="in" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}><option value="knowledge">Tutor's knowledge</option><option value="documents">My uploaded documents</option></select></label>
        </div>
        <label className="col" style={{ gap: 6 }}><span className="m">Difficulty</span><select className="in" value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })}><option>easy</option><option>medium</option><option>hard</option></select></label>
        <button className="btn" style={{ alignSelf: "flex-start" }} disabled={busy}>Create quiz</button>
      </form>{status}{err && <p className="err" role="alert">{err}</p>}
    </>
  );

  if (v.phase === "answering") {
    const q = v.questions[i];
    const set = (val: string) => { const a = [...ans]; a[q.index] = val; setAns(a); };
    return (
      <>
        <div className="row wrap"><span className="pill">{v.topic} · {TYPES[v.quiz_type]} · {v.difficulty}</span><span className="m f">Question {i + 1} of {v.total}</span>
          <button className="btn gh" onClick={async () => { await api(`/quiz/${v.quiz_id}/abandon`, { method: "POST" }); setV(null); }}>Discard</button></div>
        <div className="bar"><b style={{ width: `${((i + 1) / v.total) * 100}%` }} /></div>
        {v.total < v.requested_total && <p className="pill">Only {v.total} good questions could be written (requested {v.requested_total}).</p>}
        <div className="c col" style={{ padding: 28 }}>
          <h2 className="h2">{q.prompt}</h2>
          {q.kind === "mcq" ? q.options.map((o: string) => <button key={o} className={"o" + (ans[q.index] === o ? " s" : "")} onClick={() => set(o)}>{o}</button>)
            : <textarea className="in" value={ans[q.index] || ""} onChange={(e) => set(e.target.value)} placeholder="Your answer (leave blank to skip)" />}
          <div className="row"><button className="btn gh" disabled={i === 0} onClick={() => setI(i - 1)}>Back</button><div className="f" />
            {i < v.total - 1 ? <button className="btn" onClick={() => setI(i + 1)}>{ans[q.index] ? "Next question" : "Skip"}</button>
              : <button className="btn" disabled={busy} onClick={() => act(`/quiz/${v.quiz_id}/submit`, { answers: v.questions.map((x: any) => ans[x.index] ?? null) })}>Submit quiz</button>}</div>
        </div>{status}{err && <p className="err" role="alert">{err}</p>}
      </>
    );
  }
  const r = v.result;
  return (
    <>
      <div className="row wrap"><h2 className="h2 f">Quiz complete</h2><button className="btn" onClick={() => setV(null)}>New quiz</button></div>
      <div className="c row wrap" style={{ gap: 28 }}>
        <div className="ring" style={{ background: `conic-gradient(var(--p) 0 ${r.percent}%,var(--q) 0)` }}><span>{r.percent}%</span></div>
        <div className="col"><b>{r.correct_count} of {r.total} correct{r.skipped ? ` · ${r.skipped} skipped` : ""}</b>
          {Object.entries(r.by_kind).map(([k, s]: any) => <span className="m" key={k}>{k === "mcq" ? "Multiple choice" : "Short answer"} {s.correct}/{s.total}</span>)}</div>
      </div>
      <div className="c col">{r.items.map((it: any) => (
        <details key={it.index}><summary>{it.correct ? "✅" : "❌"} {it.index + 1}. {it.prompt}</summary>
          <p><b>Your answer:</b> {it.your_answer || "(skipped)"}</p><p><b>Correct answer:</b> {it.correct_answer}</p>{it.feedback && <p className="m">{it.feedback}</p>}</details>))}</div>
    </>
  );
}
