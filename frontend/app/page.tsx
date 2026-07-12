"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";

function Stat({ label, value, accent }: { label: string; value: any; accent?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-4">
      <div className="text-[11px] uppercase tracking-wider text-faint">{label}</div>
      <div className={`mt-1 text-[26px] font-semibold ${accent || "text-ink"}`}>{value ?? "—"}</div>
    </div>
  );
}

export default function Dashboard() {
  const [a, setA] = useState<any>(null);
  useEffect(() => { api.analytics().then(setA).catch(() => {}); }, []);
  return (
    <div className="py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-vi">Foundry Package 06 · Nyquest Pro</div>
          <h1 className="mt-1 text-[26px] font-semibold">TrustGate — AI Policy Engine</h1>
          <p className="mt-1 text-[13px] text-dim">The control point between user intent and AI execution. Define, test, enforce, and audit AI usage policies.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/policies" className="rounded-lg border border-line px-4 py-2 text-[13px] text-ink hover:bg-white/5">Manage policies</Link>
          <Link href="/test" className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">Test an action</Link>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Stat label="Active Policies" value={a?.active_policies} accent="text-cy" />
        <Stat label="Policy Checks" value={a?.policy_checks} />
        <Stat label="Violations" value={a?.violations} accent="text-warn" />
        <Stat label="Blocked" value={a?.blocked_requests} accent="text-bad" />
        <Stat label="High-Risk" value={a?.high_risk_actions} accent="text-warn" />
        <Stat label="Pending Approvals" value={a?.pending_approvals} accent="text-ind" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-line bg-panel p-5">
          <h2 className="text-[14px] font-semibold">Decisions</h2>
          <div className="mt-3 space-y-2">
            {(a?.by_decision || []).length === 0 && <p className="text-[12px] text-faint">No policy checks yet. Run a test to see decisions here.</p>}
            {(a?.by_decision || []).map((d: any) => (
              <div key={d.d} className="flex items-center justify-between text-[13px]">
                <span className={`rounded-full px-2 py-0.5 text-[11px] ${d.d === "blocked" ? "bg-bad/10 text-bad" : d.d === "require_approval" ? "bg-ind/10 text-ind" : d.d === "warn" ? "bg-warn/10 text-warn" : "bg-ok/10 text-ok"}`}>{d.d}</span>
                <span className="text-dim">{d.n}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-panel p-5">
          <h2 className="text-[14px] font-semibold">Most-triggered policies</h2>
          <div className="mt-3 space-y-2">
            {(a?.top_policies || []).length === 0 && <p className="text-[12px] text-faint">Nothing triggered yet.</p>}
            {(a?.top_policies || []).map((p: any) => (
              <div key={p.nm} className="flex items-center justify-between text-[13px]"><span className="truncate text-dim">{p.nm}</span><span className="text-faint">{p.n}</span></div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
