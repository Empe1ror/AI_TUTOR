"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api("/dashboard").then(setD).catch(() => {}); }, []);
  if (!d) return <p className="m">Loading your dashboard…</p>;
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return (
    <>
      <div className="row wrap"><div className="f"><h2 className="h2">{greet}, {d.name.split(" ")[0]}</h2><span className="m">Here is your learning today</span></div><Link className="btn" href="/lessons">New lesson</Link></div>
      <div className="g3">
        <div className="c"><span className="m">Topics tracked</span><div className="big">{d.stats.topics}</div></div>
        <div className="c"><span className="m">Due for review</span><div className="big gt">{d.stats.due}</div></div>
        <div className="c"><span className="m">Quizzes completed</span><div className="big">{d.stats.quizzes}</div></div>
      </div>
      <div className="g2">
        <div className="c col"><span className="pill" style={{ alignSelf: "flex-start" }}>Continue</span>
          {d.active_lesson ? <><h3 className="h3">{d.active_lesson.topic} · segment {d.active_lesson.current} of {d.active_lesson.total}</h3>
            <div className="bar"><b style={{ width: `${(d.active_lesson.current - 1) / d.active_lesson.total * 100}%` }} /></div>
            <Link className="btn" style={{ alignSelf: "flex-start" }} href="/lessons">Resume lesson</Link></>
            : <><p className="m">No lesson in progress.</p><Link className="btn" style={{ alignSelf: "flex-start" }} href="/lessons">Start a lesson</Link></>}
        </div>
        <div className="c col"><span className="pill" style={{ alignSelf: "flex-start" }}>Review due</span>
          {d.due_topics.length ? <><h3 className="h3">{d.due_topics.join(", ")}</h3><Link className="btn gh" style={{ alignSelf: "flex-start" }} href="/lessons">Review what is due</Link></>
            : <p className="m">Nothing due right now. Nice work!</p>}
        </div>
      </div>
      <div className="c col"><h3 className="h3">Mastery</h3>
        {d.mastery.length ? d.mastery.map((m: any) => (
          <div className="row" key={m.topic}><span style={{ width: 160 }}>{m.topic}</span><div className="bar f"><b style={{ width: `${m.pct}%` }} /></div><span className="m">{m.pct}%</span></div>
        )) : <p className="m">Finish a lesson or quiz to see your mastery here.</p>}
      </div>
    </>
  );
}
