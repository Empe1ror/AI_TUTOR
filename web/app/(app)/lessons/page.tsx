"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Md from "@/components/Md";
import DictateButton from "@/components/DictateButton";

export default function Lessons() {
  const [v, setV] = useState<any>(null);
  const [due, setDue] = useState<any>({ count: 0 });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [topic, setTopic] = useState("");
  const [docs, setDocs] = useState(true);
  const [ans, setAns] = useState<any[]>([]);
  const setAnswer = (i: number, val: string) => setAns((prev) => { const a = [...prev]; a[i] = val; return a; });

  useEffect(() => { Promise.all([api("/lesson/active"), api("/lesson/due")]).then(([a, d]) => { setV(a); setDue(d); }).finally(() => setLoading(false)); }, []);
  async function act(path: string, body: any = {}) {
    setBusy(true); setErr("");
    try { setV(await api(path, { method: "POST", body })); setAns([]); } catch (e: any) { setErr(e.message); }
    setBusy(false);
  }
  const busyText = busy ? <p className="m" role="status">Working on it… this can take a few seconds.</p> : null;
  if (loading) return <p className="m">Loading…</p>;

  if (!v || (v.status !== "active" && v.phase !== "done")) return (
    <>
      <h2 className="h2">Lessons</h2>
      {due.count > 0 && <div className="c row wrap"><span className="f">📚 {due.count} topic(s) are due for review.</span><button className="btn" disabled={busy} onClick={() => act("/lesson/review")}>Review what's due</button></div>}
      <form className="c col" onSubmit={(e) => { e.preventDefault(); act("/lesson/start", { topic, use_docs: docs }); }}>
        <label className="col" style={{ gap: 6 }}><span className="m">What do you want to learn?</span><input className="in" required value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Cybernetics" /></label>
        <label className="row"><input type="checkbox" checked={docs} onChange={(e) => setDocs(e.target.checked)} /> Use my uploaded documents</label>
        <button className="btn" style={{ alignSelf: "flex-start" }} disabled={busy}>Start lesson</button>
      </form>
      {busyText}{err && <p className="err" role="alert">{err}</p>}
    </>
  );

  const pct = Math.min(100, ((v.segment_index + (v.phase === "done" ? 1 : 0)) / v.segment_total) * 100);
  const leave = async () => { await api(`/lesson/${v.lesson_id}/abandon`, { method: "POST" }); setV(null); };

  if (v.phase === "done") {
    const s = v.summary;
    return (
      <div className="c col"><span className="pill" style={{ alignSelf: "flex-start" }}>{v.mode === "review" ? "Review complete" : "Lesson complete"}</span>
        {s && <><p>{s.summary}</p><ul>{s.key_points.map((p: string) => <li key={p}>{p}</li>)}</ul>
          {!!s.review_topics.length && <p className="pill">Worth reviewing: {s.review_topics.join(", ")}</p>}
          {s.next_topic && <p className="m">Suggested next topic: {s.next_topic}</p>}</>}
        <button className="btn" style={{ alignSelf: "flex-start" }} onClick={() => setV(null)}>Start another lesson</button>
      </div>
    );
  }
  return (
    <>
      <div className="row wrap"><span className="pill">{v.topic}</span><span className="m f">Segment {v.segment_index + 1} of {v.segment_total} · {v.segment_title}</span><button className="btn gh" onClick={leave}>Leave lesson</button></div>
      <div className="bar"><b style={{ width: `${pct}%` }} /></div>
      <div className="row split" style={{ alignItems: "stretch", gap: 20 }}>
        <div className="c col f" style={{ padding: 28, gap: 16 }}>
          {v.phase === "teach" && <>
            <Md>{v.content}</Md>
            {!!v.sources?.length && <details><summary className="m">Sources ({v.sources.length})</summary>{v.sources.map((s: any) => <p key={s.n} className="m"><b>[{s.n}] {s.label}</b><br />{s.text}</p>)}</details>}
            <div className="row wrap"><button className="btn" disabled={busy} onClick={() => act(`/lesson/${v.lesson_id}/check`)}>Check my understanding</button>
              <button className="btn gh" disabled={busy} onClick={() => act(`/lesson/${v.lesson_id}/check`)}>I already know this</button></div></>}
          {v.phase === "check" && <>
            {v.content && <details><summary className="m">Re-read the explanation</summary><Md>{v.content}</Md></details>}
            {v.questions.map((q: any) => (
              <div className="col" key={q.index}><b>{q.prompt}</b>
                {q.kind === "mcq" ? q.options.map((o: string) => <button type="button" key={o} className={"o" + (ans[q.index] === o ? " s" : "")} onClick={() => { const a = [...ans]; a[q.index] = o; setAns(a); }}>{o}</button>)
                  : <div className="col">
                      <textarea className="in" value={ans[q.index] || ""} onChange={(e) => setAnswer(q.index, e.target.value)} />
                      <div className="row"><DictateButton key={q.index} value={ans[q.index] || ""} onChange={(val) => setAnswer(q.index, val)} /></div>
                    </div>}
              </div>))}
            <button className="btn" style={{ alignSelf: "flex-start" }} disabled={busy || v.questions.some((q: any) => !ans[q.index])} onClick={() => act(`/lesson/${v.lesson_id}/submit`, { answers: v.questions.map((q: any) => ans[q.index]) })}>Submit answers</button></>}
          {v.phase === "feedback" && <>
            <h3 className="h3">Score: {Math.round(v.result.score * 100)}% · {v.result.outcome}</h3>
            {v.result.questions.map((q: any) => <div key={q.index}><p>{q.correct ? "✅" : "❌"} {q.prompt}</p>{q.feedback && <p className="m">{q.feedback}</p>}{q.correct_answer && <p className="m">Answer: {q.correct_answer}</p>}</div>)}
            <button className="btn" style={{ alignSelf: "flex-start" }} disabled={busy} onClick={() => act(`/lesson/${v.lesson_id}/continue`)}>{v.result.outcome === "retry" ? "Try again with a new explanation" : "Continue"}</button></>}
          {busyText}{err && <p className="err" role="alert">{err}</p>}
        </div>
        <aside className="c col" style={{ width: 240, flex: "none" }}><h3 className="h3">Outline</h3>
          {v.outline.map((t: string, i: number) => <span key={t} className={i === v.segment_index ? "" : "m"} style={i === v.segment_index ? { color: "var(--pt)", fontWeight: 700 } : {}}>{i + 1}. {t}{i < v.segment_index ? " ✓" : ""}</span>)}</aside>
      </div>
    </>
  );
}
