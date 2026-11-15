"use client";
import { useEffect, useRef } from "react";

declare global { interface Window { google?: any } }

export default function GoogleButton({ onCredential }: { onCredential: (credential: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const cb = useRef(onCredential);
  cb.current = onCredential;
  const id = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  useEffect(() => {
    if (!id) return;
    const init = () => {
      if (!window.google || !box.current) return;
      window.google.accounts.id.initialize({ client_id: id, callback: (r: any) => cb.current(r.credential) });
      window.google.accounts.id.renderButton(box.current, { theme: "filled_black", size: "large", shape: "pill", text: "continue_with", width: Math.min(400, box.current.offsetWidth || 360) });
    };
    if (window.google) return init();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client"; s.async = true; s.onload = init;
    document.head.appendChild(s);
  }, [id]);
  if (!id) return null;
  return <><div className="row m" style={{ fontSize: 13 }}><hr className="f" style={{ borderColor: "var(--b)" }} />or<hr className="f" style={{ borderColor: "var(--b)" }} /></div><div ref={box} style={{ minHeight: 44, display: "flex", justifyContent: "center" }} /></>;
}
