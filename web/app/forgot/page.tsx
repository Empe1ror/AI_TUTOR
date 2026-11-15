"use client";
import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import CodeInput from "@/components/CodeInput";

export default function Forgot() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (step === 1) { await api("/auth/forgot", { body: { email } }); setStep(2); }
      else { await api("/auth/reset", { body: { email, code, password } }); router.push("/signin"); }
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  }
  return (
    <div className="center">
      <form className="c card-c" onSubmit={go}>
        <Image src="/logo.png" alt="Renewed AI Tutor logo" width={72} height={61} />
        <h2 className="h2">{step === 1 ? "Reset your password" : "Enter your code"}</h2>
        {step === 1 ? (
          <><p className="m">Enter your email and we'll send you a code.</p>
            <input className="in" type="email" required placeholder="you@email.com" aria-label="Email" value={email} onChange={(e) => setEmail(e.target.value)} /></>
        ) : (
          <><p className="m">If that email has an account, a 6-digit code is on its way to <b>{email}</b>.</p>
            <CodeInput value={code} onChange={setCode} />
            <input className="in" type="password" required minLength={8} placeholder="New password (8+ characters)" aria-label="New password" value={password} onChange={(e) => setPassword(e.target.value)} /></>
        )}
        {err && <p className="err" role="alert">{err}</p>}
        <button className="btn" style={{ width: "100%" }} disabled={busy || (step === 2 && code.length < 6)}>{busy ? "Please wait…" : step === 1 ? "Send code" : "Set new password"}</button>
        <Link href="/signin" style={{ color: "var(--pt)" }}>Back to sign in</Link>
      </form>
    </div>
  );
}
