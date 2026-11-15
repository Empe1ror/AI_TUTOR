import Link from "next/link";
import Image from "next/image";

const FEATURES = [["Lessons in small steps", "One idea at a time, then a quick check."], ["Quizzes and review", "Spaced review brings back what fades."], ["Chat with your documents", "Upload notes and get cited answers."]];

export default function Landing() {
  return (
    <>
      <nav className="nav">
        <span className="row"><Image src="/logo.png" alt="Renewed AI Tutor logo" width={52} height={44} /><b className="h3 gt">Renewed AI Tutor</b></span>
        <div className="f" />
        <Link href="#features" className="m">Features</Link>
        <Link href="/signin" className="btn gh">Sign in</Link>
        <Link href="/signin?mode=signup" className="btn">Get started</Link>
      </nav>
      <section className="hero">
        <div className="col f" style={{ gap: 22 }}>
          <span className="pill" style={{ alignSelf: "flex-start" }}>Adaptive AI tutor</span>
          <h1 className="h1">Learn deeply.<br /><span className="gt">Grow confidently.</span></h1>
          <p className="m" style={{ fontSize: 18, maxWidth: 480 }}>Short guided lessons, quizzes that check what stuck, and a tutor that knows your notes.</p>
          <div className="row wrap"><Link href="/signin?mode=signup" className="btn">Start learning free</Link><Link href="/signin" className="btn gh">Sign in</Link></div>
        </div>
        <div className="c col f" style={{ boxShadow: "0 30px 80px rgba(124,58,237,.25)" }}>
          <div className="u">Explain photosynthesis simply</div>
          <div className="ai">Plants turn light into sugar. Think of a leaf as a tiny solar kitchen [1].</div>
          <div className="row wrap"><span className="pill">bio-notes.pdf p.2</span><span className="pill">Check my understanding</span></div>
        </div>
      </section>
      <section id="features" className="g3" style={{ padding: "24px clamp(16px,5vw,64px) 56px" }}>
        {FEATURES.map(([t, d]) => <div className="c" key={t}><h3 className="h3">{t}</h3><p className="m">{d}</p></div>)}
      </section>
    </>
  );
}
