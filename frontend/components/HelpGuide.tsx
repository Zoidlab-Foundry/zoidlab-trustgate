"use client";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/* In-app guide: what TrustGate is and how to govern your first AI action.
   Auto-opens once per browser (localStorage) and lives behind the Guide nav button. */

const STORAGE_KEY = "tg_guide_v1";

const STEPS: { title: string; body: string }[] = [
  {
    title: "Create a policy",
    body: "On Policies, click New policy. Pick a category (model access, prompt safety, cost limits, RAG sources…), add rules like no_secrets, pii_external, model_access, or cost_limit, and choose an enforcement mode: monitor, warn, require_approval, or block.",
  },
  {
    title: "Test an AI action",
    body: "On Test, describe a proposed action — prompt, model, data classification, workflow type, tools — or grab a preset like \"Secret + PII to unapproved model\", then hit Check policy.",
  },
  {
    title: "Read the decision",
    body: "TrustGate answers ALLOWED, WARN, APPROVAL, or BLOCKED with a risk level, the matched policies, per-rule reasons, and a recommended action. Nothing is a black box.",
  },
  {
    title: "Review violations",
    body: "Every check that warned or blocked is logged on Violations for audit. Other Foundry apps — the Workflow Builder's TrustGate Policy node, RAG Builder, MemoryMaker, Prompter — call the same preflight endpoint, so their denials land here too.",
  },
  {
    title: "Handle approvals",
    body: "Actions that matched a require-approval policy queue on Approvals and wait for a human. Approve or Reject each one; the decision is recorded against the request.",
  },
  {
    title: "Export & enforce",
    body: "Export & Deploy packages your policy set as a portable Nyquest Policy Package (JSON or YAML) and shows where it's enforced across the Foundry — the Builder integration is live today.",
  },
];

export default function HelpGuide() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {}
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch {}
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") dismiss(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-dim transition hover:text-ink hover:bg-white/5"
        aria-label="Open the TrustGate guide"
      >
        Guide
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={dismiss} role="dialog" aria-modal="true" aria-label="TrustGate guide">
          <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-line bg-panel p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-1 flex items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-md bg-vi/15 text-[13px] text-vi">⛨</span>
              <h2 className="text-[16px] font-semibold">How TrustGate works</h2>
            </div>
            <p className="mb-5 text-[13px] text-dim">
              The policy gate for AI actions — define the rules, test any proposed action, and get an auditable allow/deny with reasons. Six steps from zero to governed:
            </p>
            <ol className="space-y-4">
              {STEPS.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-vi/15 text-[12px] font-semibold text-vi">{i + 1}</span>
                  <div>
                    <div className="text-[13.5px] font-medium">{s.title}</div>
                    <div className="text-[12.5px] leading-relaxed text-dim">{s.body}</div>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-6 flex items-center justify-between border-t border-line pt-4">
              <a href="https://foundry.zoidlab.ai" className="text-[12px] text-dim hover:text-ink">◈ All Foundry apps</a>
              <button onClick={dismiss} className="rounded-lg bg-vi px-4 py-1.5 text-[12.5px] font-semibold text-white hover:opacity-90">
                Got it
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
