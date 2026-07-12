"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export default function Approvals() {
  const [a, setA] = useState<any[]>([]); const [tab, setTab] = useState("pending"); const [busy, setBusy] = useState("");
  const load = () => api.approvals({ status: tab === "all" ? "" : tab }).then(setA).catch(() => {});
  useEffect(() => { load(); }, [tab]);
  async function act(id: string, kind: "approve" | "reject") { setBusy(id); try { await (kind === "approve" ? api.approve(id) : api.reject(id)); load(); } finally { setBusy(""); } }
  return (
    <div className="py-8">
      <h1 className="text-[22px] font-semibold">Approvals</h1>
      <p className="mt-1 text-[13px] text-dim">Actions that matched a require-approval policy wait here for a human decision.</p>
      <div className="mt-4 flex gap-1 border-b border-line">
        {["pending", "approved", "rejected", "all"].map((t) => <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 text-[13px] capitalize ${tab === t ? "border-b-2 border-vi text-ink" : "text-dim hover:text-ink"}`}>{t}</button>)}
      </div>
      <div className="mt-4 space-y-2">
        {a.map((x) => (
          <div key={x.id} className="rounded-xl border border-line bg-panel p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[13.5px] font-medium text-ink">{x.policy_name}</div>
                <div className="mt-0.5 text-[12px] text-dim">{x.reason}</div>
                {x.input?.prompt && <div className="mt-1 truncate text-[11px] text-faint">action: "{x.input.prompt}"</div>}
              </div>
              {x.status === "pending" ? (
                <div className="flex shrink-0 gap-2">
                  <button onClick={() => act(x.id, "approve")} disabled={!!busy} className="rounded-md border border-ok/40 px-3 py-1.5 text-[12px] text-ok hover:bg-ok/10 disabled:opacity-50">Approve</button>
                  <button onClick={() => act(x.id, "reject")} disabled={!!busy} className="rounded-md border border-bad/40 px-3 py-1.5 text-[12px] text-bad hover:bg-bad/10 disabled:opacity-50">Reject</button>
                </div>
              ) : <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${x.status === "approved" ? "bg-ok/10 text-ok" : "bg-bad/10 text-bad"}`}>{x.status}</span>}
            </div>
          </div>
        ))}
        {!a.length && <div className="rounded-2xl border border-dashed border-line py-14 text-center text-[13px] text-faint">Nothing here.</div>}
      </div>
    </div>
  );
}
