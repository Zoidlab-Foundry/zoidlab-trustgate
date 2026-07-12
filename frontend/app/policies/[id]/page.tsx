"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "../../../lib/api";

const MODES = ["monitor", "warn", "require_approval", "block"];
const STATUSES = ["active", "disabled"];

export default function PolicyDetail() {
  const { id } = useParams<{ id: string }>();
  const [p, setP] = useState<any>(null); const [saving, setSaving] = useState(false);
  const load = () => api.policy(id).then(setP).catch(() => {});
  useEffect(() => { load(); }, [id]);
  async function patch(patch: any) { setSaving(true); try { await api.updatePolicy(id, patch); await load(); } finally { setSaving(false); } }
  async function snap() { const c = prompt("Version note?") || ""; await api.snapshotPolicy(id, c); load(); }
  if (!p) return <div className="py-24 text-center text-faint">Loading…</div>;
  return (
    <div className="py-8">
      <Link href="/policies" className="text-[12px] text-faint hover:text-dim">← Policies</Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-[22px] font-semibold">{p.name}</h1><p className="mt-1 max-w-2xl text-[13px] text-dim">{p.description}</p></div>
        <button onClick={snap} className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-cy hover:bg-white/5">Snapshot version</button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-line bg-panel p-5">
            <h2 className="mb-3 text-[14px] font-semibold">Rules ({(p.rules || []).length})</h2>
            <div className="space-y-2">
              {(p.rules || []).map((r: any, i: number) => (
                <div key={i} className="rounded-lg border border-line bg-panel2 p-3 text-[12.5px]">
                  <div className="font-medium text-ink">{r.type}</div>
                  {Object.entries(r).filter(([k]) => k !== "type").map(([k, v]) => <div key={k} className="text-dim">{k}: <span className="text-faint">{Array.isArray(v) ? (v as any[]).join(", ") || "—" : String(v)}</span></div>)}
                </div>
              ))}
              {!(p.rules || []).length && <p className="text-[12px] text-faint">No rules on this policy.</p>}
            </div>
          </div>
          {(p.versions || []).length > 0 && (
            <div className="rounded-2xl border border-line bg-panel p-5">
              <h2 className="mb-2 text-[14px] font-semibold">Versions</h2>
              {p.versions.map((v: any) => <div key={v.id} className="flex justify-between border-b border-line py-1.5 text-[12px] last:border-0"><span className="text-dim">v{v.version} · {v.changelog || "snapshot"}</span><span className="text-faint">{(v.created_at || "").slice(0, 10)}</span></div>)}
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div className="rounded-2xl border border-line bg-panel p-4">
            <div className="mb-2 text-[11px] uppercase tracking-wider text-faint">Enforcement</div>
            <select value={p.enforcement_mode} onChange={(e) => patch({ enforcement_mode: e.target.value })} disabled={saving} className={inp}>{MODES.map((m) => <option key={m}>{m}</option>)}</select>
            <div className="mb-2 mt-3 text-[11px] uppercase tracking-wider text-faint">Status</div>
            <select value={p.status} onChange={(e) => patch({ status: e.target.value })} disabled={saving} className={inp}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
            <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded bg-white/5 px-2 py-0.5 text-dim">{p.category}</span>
              <span className={`rounded px-2 py-0.5 ${p.risk_level === "high" ? "bg-bad/10 text-bad" : p.risk_level === "medium" ? "bg-warn/10 text-warn" : "bg-ok/10 text-ok"}`}>{p.risk_level} risk</span>
              <span className="rounded bg-white/5 px-2 py-0.5 text-faint">v{p.version}</span>
            </div>
          </div>
          <Link href="/test" className="block rounded-2xl border border-line bg-panel p-4 text-[13px] text-cy hover:border-vi/50">Test an action against your policies →</Link>
        </div>
      </div>
    </div>
  );
}
const inp = "w-full rounded-lg border border-line bg-panel2 px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-vi/60";
