"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useUser } from "@/components/AppShell";
import ThemeToggle from "@/components/ThemeToggle";

export default function Settings() {
  const { user, setUser } = useUser();
  const router = useRouter();
  const [name, setName] = useState(user.name);
  const [msg, setMsg] = useState("");
  async function save(patch: any) {
    await api("/settings", { method: "PATCH", body: patch });
    setUser({ ...user, ...patch }); setMsg("Saved.");
  }
  return (
    <>
      <h2 className="h2">Settings</h2>
      <div className="g2">
        <div className="c col">
          <label className="col" style={{ gap: 6 }}><span className="m">Name</span><input className="in" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="col" style={{ gap: 6 }}><span className="m">Email</span><input className="in" value={user.email} disabled /></label>
          <button className="btn" style={{ alignSelf: "flex-start" }} onClick={() => save({ name })}>Save</button>{msg && <p className="ok" role="status">{msg}</p>}
        </div>
        <div className="c col">
          <h3 className="h3">Appearance</h3><div><ThemeToggle /></div>
          <h3 className="h3">Email reminders</h3>
          <label className="row"><input type="checkbox" checked={user.reminders_enabled} onChange={(e) => save({ reminders_enabled: e.target.checked })} /> Email me about weak topics after 1 and 2 days</label>
          <button className="btn gh" style={{ alignSelf: "flex-start" }} onClick={async () => { await api("/auth/logout", { method: "POST" }); router.push("/signin"); }}>Sign out</button>
        </div>
      </div>
    </>
  );
}
