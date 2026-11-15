"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import GoogleButton from "@/components/GoogleButton";

function Form() {
  const router = useRouter();
  const [mode, setMode] = useState(useSearchParams().get("mode") === "signup" ? "signup" : "signin");
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });

  async function google(credential: string) {
    setErr("");
    try { await api("/auth/google", { body: { credential } }); router.push("/dashboard"); }
    catch (e: any) { setErr(e.message); }
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (mode === "signup") {
        await api("/auth/signup", { body: f });
        router.push(`/verify?email=${encodeURIComponent(f.email)}`);
      } else {
        await api("/auth/login", { body: { email: f.email, password: f.password } });
        router.push("/dashboard");
      }
    } catch (e: any) {
      if (e.message === "UNVERIFIED") router.push(`/verify?email=${encodeURIComponent(f.email)}`);
      else setErr(e.message);
    }
    setBusy(false);
  }
  return (
    <form className="glass" onSubmit={submit}>
      <span className="row"><Image src="/logo.png" alt="Renewed AI Tutor logo" width={52} height={44} /><b className="h3 gt">Renewed AI Tutor</b></span>
      <div className="row">
        <button type="button" className={mode === "signin" ? "pill" : "m"} style={{ background: mode === "signin" ? undefined : "none", border: 0 }} onClick={() => setMode("signin")}>Sign in</button>
        <button type="button" className={mode === "signup" ? "pill" : "m"} style={{ background: mode === "signup" ? undefined : "none", border: 0 }} onClick={() => setMode("signup")}>Create account</button>
      </div>
      <h2 className="h2">{mode === "signup" ? "Create your account" : "Welcome back"}</h2>
      {mode === "signup" && <label className="col" style={{ gap: 6 }}><span className="m">Name</span><input className="in" required value={f.name} onChange={set("name")} autoComplete="name" /></label>}
      <label className="col" style={{ gap: 6 }}><span className="m">Email</span><input className="in" type="email" required value={f.email} onChange={set("email")} autoComplete="email" placeholder="you@email.com" /></label>
      <label className="col" style={{ gap: 6 }}><span className="m">Password</span><input className="in" type="password" required minLength={8} value={f.password} onChange={set("password")} autoComplete={mode === "signup" ? "new-password" : "current-password"} placeholder="At least 8 characters" /></label>
      {mode === "signin" && <div className="row"><span className="f" /><Link href="/forgot" style={{ color: "var(--pt)" }}>Forgot password?</Link></div>}
      {err && <p className="err" role="alert">{err}</p>}
      <button className="btn" disabled={busy}>{busy ? "Please wait…" : mode === "signup" ? "Create account" : "Sign in"}</button>
      <GoogleButton onCredential={google} />
    </form>
  );
}

export default function SignIn() {
  return (
    <div className="auth dk">
      <Image src="/hero.jpg" alt="" fill priority sizes="100vw" style={{ objectFit: "cover", objectPosition: "100% center" }} />
      <div className="shade" />
      <Suspense><Form /></Suspense>
    </div>
  );
}
