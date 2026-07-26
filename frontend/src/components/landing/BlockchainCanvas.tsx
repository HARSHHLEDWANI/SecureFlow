"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useReducedMotion } from "framer-motion";
import { Boxes } from "lucide-react";

// The Three.js scene is code-split and never server-rendered; it only loads once
// the container scrolls into view, so the ~heavy 3D bundle never blocks first paint.
const BlockchainScene = dynamic(() => import("./BlockchainScene"), { ssr: false });

/** Static, no-motion fallback shown for reduced-motion users (progressive enhancement). */
function StaticFallback() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="glow-ring flex h-40 w-40 items-center justify-center rounded-2xl bg-[var(--surface)]">
        <Boxes className="h-16 w-16 text-[var(--accent-cyan)]" />
      </div>
    </div>
  );
}

export default function BlockchainCanvas({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          obs.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} className={className}>
      {reduceMotion ? <StaticFallback /> : inView ? <BlockchainScene /> : <StaticFallback />}
    </div>
  );
}
