"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

const DC = ["public", "internal", "confidential", "pii"];
const PRESETS: Record<string, any> = {
  "Clean FAQ answer": { prompt: "Summarize our refund policy for a customer.", model: "anthropic/claude-sonnet-5", provider: "anthropic", data_classification: "public", workflow_type: "faq", max_tokens: 600 },
  "Secret + PII to unapproved model": { prompt: "Use API key sk-live-abc123456789 to process this SSN 123-45-6789.", model: "deepseek/chat", provider: "deepseek", data_classification: "pii", workflow_type: "support", max_tokens: 800 },
  "Legal advice workflow": { prompt: "Draft a binding contract clause.", model: "openai/gpt-5", provider: "openai", data_classification: "confidential", workflow_type: "legal", max_tokens: 1500 },
  "Uncited RAG answer": { prompt: "What is our SLA?", model: "anthropic/claude-sonnet-5", provider: "anthropic", data_classification: "internal", context_type: "rag", rag_cited: false, max_tokens: 500 },
};

export default function TestPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [pid, setPid] = useState("");
  const [f, setF] = useState<any>(PRESETS["Secret + PII to unapproved model"]);
  const [res, setRes] = useState<any>(null); const [busy, setBusy] = useState(false);
  useEffect(() => { api.projects().then((p) => { setProjects(p); if (p[0]) setPid(p[0].id); }).catch(() => {}); }, []);
  async function run() {
    setBusy(true); setRes(null);
    try { setRes(await api.test({ project_id: pid || undefined, request: f, save: true })); } finally { setBusy(false); }
  }
  const dec = res?.decision;
  const decColor = dec === "blocked" ? "border-bad/50 bg-bad/10 text-bad" : dec === "require_approval" ? "border-ind/50 bg-ind/10 text-ind" : dec === "warn" ? "border-warn/50 bg-warn/10 text-warn" : "border-ok/50 bg-ok/10 text-ok";
  return (
    <div className="py-8">
      <h1 className="text-[22px] font-semibold">Test an AI action</h1>
      <p className="mt-1 text-[13px] text-dim">Describe a proposed AI action; TrustGate evaluates it against your active policies and answers: <b className="text-ink">is this allowed?</b></p>
      <div className="mt-3 flex flex-wrap gap-1.5">{Object.keys(PRESETS).map((k) => <button key={k} onClick={() => { setF(PRESETS[k]); setRes(null); }} className="rounded-full border border-line px-2.5 py-1 text-[11px] text-dim hover:text-ink hover:border-vi/50">{k}</button>)}</div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[380px_1fr]">
        <div className="space-y-2 rounded-xl border border-line bg-panel p-4">
          {projects.length > 0 && <label className="block"><span className="mb-1 block text-[11px] text-faint">Policy project</span><select value={pid} onChange={(e) => setPid(e.target.value)} className={inp}>{projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>}
          <label className="block"><span className="mb-1 block text-[11px] text-faint">Prompt / input</span><textarea value={f.prompt || ""} onChange={(e) => setF({ ...f, prompt: e.target.value })} rows={3} className={inp} /></label>
          <div className="grid grid-cols-2 gap-2">
            <label><span className="mb-1 block text-[11px] text-faint">Model</span><input value={f.model || ""} onChange={(e) => setF({ ...f, model: e.target.value, provider: (e.target.value.split("/")[0]) })} className={inp} /></label>
            <label><span className="mb-1 block text-[11px] text-faint">Data class</span><select value={f.data_classification || "public"} onChange={(e) => setF({ ...f, data_classification: e.target.value })} className={inp}>{DC.map((d) => <option key={d}>{d}</option>)}</select></label>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label><span className="mb-1 block text-[11px] text-faint">Workflow type</span><input value={f.workflow_type || ""} onChange={(e) => setF({ ...f, workflow_type: e.target.value })} placeholder="faq / legal / medical…" className={inp} /></label>
            <label><span className="mb-1 block text-[11px] text-faint">Max tokens</span><input type="number" value={f.max_tokens || ""} onChange={(e) => setF({ ...f, max_tokens: Number(e.target.value) })} className={inp} /></label>
          </div>
          <label><span className="mb-1 block text-[11px] text-faint">Tools (csv)</span><input value={(f.tools || []).join(",")} onChange={(e) => setF({ ...f, tools: e.target.value.split(",").map((x: string) => x.trim()).filter(Boolean) })} className={inp} /></label>
          <div className="flex items-center gap-4 pt-1">
            <label className="flex items-center gap-2 text-[12px] text-dim"><input type="checkbox" checked={f.context_type === "rag"} onChange={(e) => setF({ ...f, context_type: e.target.checked ? "rag" : undefined })} /> RAG context</label>
            {f.context_type === "rag" && <label className="flex items-center gap-2 text-[12px] text-dim"><input type="checkbox" checked={!!f.rag_cited} onChange={(e) => setF({ ...f, rag_cited: e.target.checked })} /> cited</label>}
            <label className="flex items-center gap-2 text-[12px] text-dim"><input type="checkbox" checked={f.memory_write_risk === "high"} onChange={(e) => setF({ ...f, memory_write_risk: e.target.checked ? "high" : undefined })} /> high-risk memory write</label>
          </div>
          <button onClick={run} disabled={busy} className="mt-2 w-full rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Checking…" : "Check policy"}</button>
        </div>

        <div>
          {!res ? <div className="rounded-2xl border border-dashed border-line py-20 text-center text-[13px] text-faint">Run a check to see the policy decision.</div> : (
            <div className={`rounded-2xl border p-5 ${decColor}`}>
              <div className="flex items-center gap-3">
                <span className="text-[26px] font-bold uppercase">{dec === "blocked" ? "BLOCKED" : dec === "require_approval" ? "APPROVAL" : dec === "warn" ? "WARN" : "ALLOWED"}</span>
                <span className="rounded-full border border-current/40 px-2 py-0.5 text-[11px]">risk: {res.risk_level}</span>
                {res.approval_id && <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px]">approval queued</span>}
              </div>
              {res.matched_policies?.length > 0 && <div className="mt-3 text-[12px]"><span className="uppercase tracking-wider opacity-70">matched policies:</span> {res.matched_policies.join(", ")}</div>}
              <ul className="mt-3 space-y-1.5 text-[13px] text-ink">
                {res.reasons.map((r: string, i: number) => <li key={i} className="flex gap-2"><span className="opacity-60">›</span>{r}</li>)}
              </ul>
              <div className="mt-4 rounded-lg border border-line bg-panel2 p-3 text-[12.5px] text-dim"><span className="font-medium text-ink">Recommended action:</span> {res.recommended_action}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
const inp = "w-full rounded-lg border border-line bg-panel2 px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-vi/60";
