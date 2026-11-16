"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import Md from "@/components/Md";
import DictateButton from "@/components/DictateButton";

type Msg = { role: string; content: string; sources?: any[] };

export default function Chat() {
  const [sid, setSid] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [list, setList] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [docs, setDocs] = useState(true);
  const [err, setErr] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const refresh = () => api("/chat/sessions").then(setList).catch(() => {});
  useEffect(() => { setSid(crypto.randomUUID()); refresh(); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  async function open(id: string) { setSid(id); setMsgs(await api("/chat/history?session_id=" + id)); }
  async function send(e: React.FormEvent, preset?: string) {
    e.preventDefault();
    const message = (preset ?? text).trim();
    if (!message || busy) return;
    setText(""); setErr(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: message }]);
    try {
      const r = await api("/chat", { body: { message, session_id: sid, use_docs: docs } });
      setMsgs((m) => [...m, { role: "assistant", content: r.reply, sources: r.sources }]);
      refresh();
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  }
  return (
    <div className="row split" style={{ alignItems: "stretch", gap: 20, flex: 1 }}>
      <aside className="c col" style={{ width: 240, flex: "none", maxHeight: "80vh", overflow: "auto" }}>
        <button className="btn" onClick={() => { setSid(crypto.randomUUID()); setMsgs([]); }}>＋ New chat</button>
        {list.map((s) => <button key={s.session_id} className={"o" + (s.session_id === sid ? " s" : "")} onClick={() => open(s.session_id)}>{s.title || "Chat"}</button>)}
      </aside>
      <section className="col f" style={{ minHeight: "70vh" }}>
        <div className="row wrap"><h2 className="h2 f">Your tutor</h2>
          <label className="pill row" style={{ cursor: "pointer" }}><input type="checkbox" checked={docs} onChange={(e) => setDocs(e.target.checked)} /> Using my documents</label></div>
        <div className="col f" style={{ overflow: "auto", gap: 14 }}>
          {!msgs.length && <div className="c col"><p className="m">Ask a question, name a topic, or share code.</p>
            <div className="row wrap">{["Teach me a topic from the basics", "Help me solve a problem step by step", "Help me debug my code"].map((s) => <button key={s} className="pill" onClick={(e) => send(e, s)}>{s}</button>)}</div></div>}
          {msgs.map((m, i) => m.role === "user" ? <div className="u" key={i}>{m.content}</div> : (
            <div className="ai" key={i}><Md>{m.content}</Md>
              {!!m.sources?.length && <div className="row wrap" style={{ marginTop: 8 }}>{m.sources.map((s: any) => <span className="pill" key={s.n} title={s.text}>[{s.n}] {s.label}</span>)}</div>}</div>))}
          {busy && <div className="ai m">Thinking through the best way to teach this…</div>}
          <div ref={end} />
        </div>
        {err && <p className="err" role="alert">{err}</p>}
        <form className="row" onSubmit={send}>
          <input className="in f" placeholder="What would you like to learn today?" aria-label="Message" value={text} onChange={(e) => setText(e.target.value)} />
          <DictateButton value={text} onChange={setText} disabled={busy} />
          <button className="btn" disabled={busy}>Send</button>
        </form> 
      </section>
    </div>
  );
}
