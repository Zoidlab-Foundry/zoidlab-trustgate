"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export default function Analytics() {
  const [a, setA] = useState<any>(null);
  useEffect(() => { api.analytics().then(setA).catch(() => {}); }, []);
  const total = (a?.by_decision || []).reduce((s: number, d: any) => s + d.n, 0) || 1;
  return (
    <div className="py-8">
      <h1 className="text-[22px] font-semibold">Analytics</h1>
      <p className="mt-1 text-[13px] text-dim">Governance posture across your policies and checks.</p>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-line bg-panel p-5">
          <h2 className="text-[14px] font-semibold">Decision mix</h2>
          <div className="mt-3 space-y-2">
            {(a?.by_decision || []).map((d: any) => (
              <div key={d.d}>
                <div className="flex justify-between text-[12px]"><span className="text-dim">{d.d}</span><span className="text-faint">{d.n}</span></div>
                <div className="mt-1 h-2 rounded bg-white/5"><div className={`h-2 rounded ${d.d === "blocked" ? "bg-bad" : d.d === "require_approval" ? "bg-ind" : d.d === "warn" ? "bg-warn" : "bg-ok"}`} style={{ width: `${Math.round((d.n / total) * 100)}%` }} /></div>
              </div>
            ))}
            {!(a?.by_decision || []).length && <p className="text-[12px] text-faint">No checks recorded yet.</p>}
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-panel p-5">
          <h2 className="text-[14px] font-semibold">Policies by category</h2>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {(a?.by_category || []).map((c: any) => <span key={c.c} className="rounded-full border border-line px-2.5 py-1 text-[11.5px] text-dim">{c.c} · <span className="text-ink">{c.n}</span></span>)}
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-panel2 p-3"><div className="text-[20px] font-semibold text-cy">{a?.active_policies ?? "—"}</div><div className="text-[10px] uppercase tracking-wider text-faint">active</div></div>
            <div className="rounded-lg bg-panel2 p-3"><div className="text-[20px] font-semibold text-bad">{a?.blocked_requests ?? "—"}</div><div className="text-[10px] uppercase tracking-wider text-faint">blocked</div></div>
            <div className="rounded-lg bg-panel2 p-3"><div className="text-[20px] font-semibold text-ind">{a?.pending_approvals ?? "—"}</div><div className="text-[10px] uppercase tracking-wider text-faint">pending</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}
