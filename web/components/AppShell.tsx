"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import ThemeToggle from "./ThemeToggle";

const Ctx = createContext<any>(null);
export const useUser = () => useContext(Ctx);
const NAV = [["Dashboard", "/dashboard"], ["Free chat", "/chat"], ["Lessons", "/lessons"], ["Quizzes", "/quizzes"], ["Library", "/library"], ["Settings", "/settings"]];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any>(null);
  const router = useRouter();
  const path = usePathname();
  useEffect(() => { api("/auth/me").then(setUser).catch(() => router.replace("/signin")); }, [router]);
  if (!user) return <div className="center m">Loading…</div>;
  return (
    <Ctx.Provider value={{ user, setUser }}>
      <div className="app">
        <aside className="sb">
          <div className="row lg"><Image src="/logo.png" alt="Renewed AI Tutor logo" width={40} height={34} /><b className="gt">Renewed</b></div>
          {NAV.map(([label, href]) => (
            <Link key={href} href={href} className={"n" + (path.startsWith(href) ? " a" : "")}><i /><span>{label}</span></Link>
          ))}
          <div className="f sp" />
          <div className="row user"><span className="av">{user.name[0]?.toUpperCase()}</span><span className="f">{user.name}</span><ThemeToggle /></div>
        </aside>
        <main className="main">{children}</main>
      </div>
    </Ctx.Provider>
  );
}
