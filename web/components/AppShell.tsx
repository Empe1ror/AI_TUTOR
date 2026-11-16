"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import ThemeToggle from "./ThemeToggle";

const Ctx = createContext<any>(null);
export const useUser = () => useContext(Ctx);
const ICONS: Record<string, React.ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></>,
  chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  lessons: <><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></>,
  quizzes: <><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><path d="M12 17h.01" /></>,
  library: <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2z" />,
  settings: <><line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" /><line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" /><line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" /><line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" /><line x1="17" y1="16" x2="23" y2="16" /></>,
};
function Icon({ name }: { name: string }) {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONS[name]}</svg>;
}
const NAV = [["Dashboard", "/dashboard", "dashboard"], ["Free chat", "/chat", "chat"], ["Lessons", "/lessons", "lessons"], ["Quizzes", "/quizzes", "quizzes"], ["Library", "/library", "library"], ["Settings", "/settings", "settings"]];

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
          {NAV.map(([label, href, icon]) => (
            <Link key={href} href={href} title={label} className={"n" + (path.startsWith(href) ? " a" : "")}>
              <Icon name={icon} /><span>{label}</span>
            </Link>
          ))}
          <div className="f sp" />
          <div className="row user"><span className="av">{user.name[0]?.toUpperCase()}</span><span className="f">{user.name}</span><ThemeToggle /></div>
        </aside>
        <main className="main">{children}</main>
      </div>
    </Ctx.Provider>
  );
}
