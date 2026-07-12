"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

const CATEGORIES = ["model_access", "data_classification", "prompt_safety", "tool_usage", "rag_source", "memory_write", "cost_limit", "approval", "external_api", "logging", "retention"];
const MODES = ["monitor", "warn", "require_approval", "block"];
const RISKS = ["low", "medium", "high"];
const RULE_TYPES = ["no_secrets", "pii_external", "model_access", "require_citations", "approval_workflows", "cost_limit", "memory_write", "tool_usage", "logging"];

const modeColor = (m: string) => m === "block" ? "text-bad bg-bad/10" : m === "require_approval" ? "text-ind bg-ind/10" : m === "warn" ? "text-warn bg-warn/10" : "text-dim bg-white/5";
const riskColor = (r: string) => r === "high" ? "text-bad" : r === "medium" ? "text-warn" : "text-ok";
const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export default function Policies() {
  const [pols, setPols] = useState<any[]>([]);
  const [adding, setAdding] = useState(false);
  const load = () => api.policies().then(setPols).catch(() => {});
  useEffect(() => { load(); }, []);
  return (
    <div className="py-8">
      <div className="flex items-center justify-between">
        <div><h1 className="text-[22px] font-semibold">Policies</h1><p className="mt-1 text-[13px] text-dim">Define the rules AI actions must comply with. Each policy has an enforcement mode.</p></div>
        <button onClick={() => setAdding(true)} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">New policy</button>
      </div>
      <div className="mt-5 space-y-2">
        {pols.map((p) => (
          <Link key={p.id} href={`/policies/${p.id}`} className="flex items-center gap-3 rounded-xl border border-line bg-panel p-4 transition hover:border-vi/50">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-vi/10 text-[15px] text-vi">⛨</span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2"><span className="truncate text-[14px] font-medium text-ink">{p.name}</span><span className={`rounded-full px-2 py-0.5 text-[10px] ${riskColor(p.risk_level)} bg-white/5`}>{p.risk_level}</span></div>
              <div className="truncate text-[12px] text-dim">{p.description}</div>
            </div>
            <span className="rounded bg-white/5 px-2 py-0.5 text-[11px] text-faint">{p.category}</span>
            <span className="text-[11px] text-faint">{(p.rules || []).length} rule{(p.rules || []).length === 1 ? "" : "s"}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] ${modeColor(p.enforcement_mode)}`}>{p.enforcement_mode}</span>
          </Link>
        ))}
        {!pols.length && <div className="rounded-2xl border border-dashed border-line py-14 text-center text-[13px] text-faint">No policies yet. Create one to start governing AI actions.</div>}
      </div>
      {adding && <NewPolicy onClose={() => setAdding(false)} onAdded={() => { setAdding(false); load(); }} />}
    </div>
  );
}

function NewPolicy({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [f, setF] = useState({ name: "", description: "", category: "model_access", enforcement_mode: "warn", risk_level: "medium" });
  const [rules, setRules] = useState<any[]>([{ type: "no_secrets" }]);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const upd = (i: number, patch: any) => { const nr = [...rules]; nr[i] = { ...nr[i], ...patch }; setRules(nr); };
  async function add() {
    if (!f.name.trim()) return; setBusy(true); setErr("");
    const clean = rules.map((r) => {
      const o: any = { type: r.type };
      if (r.type === "model_access") { o.allowed = csv(r.allowed || ""); o.blocked = csv(r.blocked || ""); }
      if (r.type === "pii_external") o.approved_providers = csv(r.approved_providers || "");
      if (r.type === "approval_workflows") o.workflows = csv(r.workflows || "legal,medical,financial");
      if (r.type === "cost_limit") o.max_tokens = Number(r.max_tokens || 2000);
      if (r.type === "tool_usage") o.blocked_tools = csv(r.blocked_tools || "");
      return o;
    });
    try { await api.createPolicy({ ...f, rules: clean }); onAdded(); }
    catch (e: any) { setErr(e.status === 403 ? "Nyquest Pro required." : e.message); setBusy(false); }
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={onClose}>
      <div className="max-h-[88vh] w-full max-w-lg overflow-auto rounded-2xl border border-line bg-panel2 p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 text-[16px] font-semibold">New policy</h2>
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Policy name" className={inp + " mb-2"} />
        <input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="Description" className={inp + " mb-2"} />
        <div className="mb-3 grid grid-cols-3 gap-2">
          <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className={inp}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
          <select value={f.enforcement_mode} onChange={(e) => setF({ ...f, enforcement_mode: e.target.value })} className={inp}>{MODES.map((m) => <option key={m}>{m}</option>)}</select>
          <select value={f.risk_level} onChange={(e) => setF({ ...f, risk_level: e.target.value })} className={inp}>{RISKS.map((r) => <option key={r}>{r}</option>)}</select>
        </div>
        <div className="mb-2 text-[12px] font-medium text-dim">Rules</div>
        {rules.map((r, i) => (
          <div key={i} className="mb-2 space-y-1 rounded-lg border border-line bg-panel p-2">
            <div className="flex items-center gap-2">
              <select value={r.type} onChange={(e) => upd(i, { type: e.target.value })} className={inp}>{RULE_TYPES.map((t) => <option key={t}>{t}</option>)}</select>
              <button onClick={() => setRules(rules.filter((_, j) => j !== i))} className="text-faint hover:text-bad">✕</button>
            </div>
            {r.type === "model_access" && <div className="grid grid-cols-2 gap-1"><input value={r.allowed || ""} onChange={(e) => upd(i, { allowed: e.target.value })} placeholder="allowed (csv)" className={inp} /><input value={r.blocked || ""} onChange={(e) => upd(i, { blocked: e.target.value })} placeholder="blocked (csv)" className={inp} /></div>}
            {r.type === "pii_external" && <input value={r.approved_providers || ""} onChange={(e) => upd(i, { approved_providers: e.target.value })} placeholder="approved providers (csv)" className={inp} />}
            {r.type === "approval_workflows" && <input value={r.workflows ?? "legal,medical,financial"} onChange={(e) => upd(i, { workflows: e.target.value })} placeholder="workflows (csv)" className={inp} />}
            {r.type === "cost_limit" && <input type="number" value={r.max_tokens ?? 2000} onChange={(e) => upd(i, { max_tokens: e.target.value })} placeholder="max tokens" className={inp} />}
            {r.type === "tool_usage" && <input value={r.blocked_tools || ""} onChange={(e) => upd(i, { blocked_tools: e.target.value })} placeholder="blocked tools (csv)" className={inp} />}
          </div>
        ))}
        <button onClick={() => setRules([...rules, { type: "no_secrets" }])} className="mb-3 text-[12px] text-cy hover:underline">+ Add rule</button>
        {err && <p className="mb-2 text-[12px] text-bad">{err}</p>}
        <div className="flex justify-end gap-2"><button onClick={onClose} className="rounded-lg border border-line px-4 py-2 text-[13px] text-dim hover:text-ink">Cancel</button><button onClick={add} disabled={busy || !f.name.trim()} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Saving…" : "Create policy"}</button></div>
      </div>
    </div>
  );
}
const inp = "w-full rounded-lg border border-line bg-panel2 px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-vi/60";
