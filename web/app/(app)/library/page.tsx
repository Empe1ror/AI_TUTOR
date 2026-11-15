"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Library() {
  const [docs, setDocs] = useState<any[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<any[]>([]);
  const load = () => api("/library").then(setDocs).catch(() => {});
  useEffect(() => { load(); }, []);
  async function upload() {
    setBusy(true); setMsgs([]);
    const form = new FormData(); files.forEach((f) => form.append("files", f));
    try { setMsgs(await api("/library", { form })); setFiles([]); load(); } catch (e: any) { setMsgs([{ ok: false, filename: "Upload", error: e.message }]); }
    setBusy(false);
  }
  return (
    <>
      <h2 className="h2">My study library</h2>
      <div className="c col" style={{ alignItems: "center", borderStyle: "dashed", padding: 36 }}>
        <b>Choose PDF, DOCX, TXT or MD files</b><span className="m">Up to 10 MB each</span>
        <input type="file" multiple accept=".pdf,.txt,.md,.docx" aria-label="Choose files" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
        <button className="btn" disabled={!files.length || busy} onClick={upload}>{busy ? "Reading your files…" : "Add to my library"}</button>
      </div>
      {msgs.map((m, i) => <p key={i} className={m.ok ? "ok" : "err"}>{m.ok ? (m.duplicate ? `${m.filename} is already in your library.` : `Added ${m.filename} (${m.n_chunks} sections)${m.skipped ? `, ${m.skipped} skipped by the content filter` : ""}.`) : `${m.filename}: ${m.error}`}</p>)}
      <div className="c col">
        {!docs.length && <p className="m">No documents yet.</p>}
        {docs.map((d) => <div className="row" key={d.doc_id}><b className="f">{d.filename}</b><span className="m">{d.n_chunks} sections</span>
          <button className="btn gh" onClick={async () => { await api(`/library/${d.doc_id}`, { method: "DELETE" }); load(); }}>Remove</button></div>)}
      </div>
    </>
  );
}
