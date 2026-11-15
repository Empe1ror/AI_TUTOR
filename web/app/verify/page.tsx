"use client";
import { Suspense, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import CodeInput from "@/components/CodeInput";

function Verify() {
  const router = useRouter();
  const email = useSearchParams().get("email") || "";
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(45);
  useEffect(() => { if (wait > 0) { const t = setTimeout(() => setWait(wait - 1), 1000); return () => clearTimeout(t); } }, [wait]);

  async function verify() {
    setErr(""); setBusy(true);
    try { await api("/auth/verify", { body: { email, code } }); router.push("/dashboard"); }
    catch (e: any) { setErr(e.message); }
    setBusy(false);
  }
  async function resend() {
    setErr("");
    try { await api("/auth/resend", { body: { email } }); setWait(45); } catch (e: any) { setErr(e.message); }
  }
  return (
    <div className="center" style={{ background: "radial-gradient(500px 360px at 50% 40%,rgba(124,58,237,.14),transparent)" }}>
      <div className="c card-c">
        <Image src="/logo.png" alt="Renewed AI Tutor logo" width={72} height={61} />
        <h2 className="h2">Check your email</h2>
        <p className="m">We sent a 6-digit code to <b>{email}</b>. It expires in 10 minutes.</p>
        <CodeInput value={code} onChange={setCode} />
        {err && <p className="err" role="alert">{err}</p>}
        <button className="btn" style={{ width: "100%" }} disabled={busy || code.length < 6} onClick={verify}>{busy ? "Verifying…" : "Verify and continue"}</button>
        {wait > 0 ? <span className="m">Resend code in 0:{String(wait).padStart(2, "0")}</span> : <button className="pill" onClick={resend}>Resend code</button>}
        <Link href="/signin?mode=signup" style={{ color: "var(--pt)" }}>Use a different email</Link>
      </div>
    </div>
  );
}
export default function Page() { return <Suspense><Verify /></Suspense>; }
