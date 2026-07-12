"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export default function Violations() {
  const [v, setV] = useState<any[]>([]);
  useEffect(() => { api.violations().then(setV).catch(() => {}); }, []);
  return (
    <div className="py-8">
      <h1 className="text-[22px] font-semibold">Violations</h1>
      <p className="mt-1 text-[13px] text-dim">Every policy check that warned or blocked is logged here for audit.</p>
      <div className="mt-5 overflow-x-auto rounded-2xl border border-line">
        <table className="w-full text-[12.5px]">
          <thead className="bg-panel2 text-faint"><tr className="text-left"><th className="p-3 font-medium">When</th><th className="p-3 font-medium">Policy</th><th className="p-3 font-medium">Decision</th><th className="p-3 font-medium">Risk</th><th className="p-3 font-medium">Reason</th></tr></thead>
          <tbody>
            {v.map((x) => (
              <tr key={x.id} className="border-t border-line">
                <td className="whitespace-nowrap p-3 text-faint">{(x.created_at || "").slice(0, 16).replace("T", " ")}</td>
                <td className="p-3 text-ink">{x.policy_name}</td>
                <td className="p-3"><span className={`rounded-full px-2 py-0.5 text-[11px] ${x.decision === "blocked" ? "bg-bad/10 text-bad" : x.decision === "require_approval" ? "bg-ind/10 text-ind" : "bg-warn/10 text-warn"}`}>{x.decision}</span></td>
                <td className={`p-3 ${x.risk_level === "high" ? "text-bad" : x.risk_level === "medium" ? "text-warn" : "text-ok"}`}>{x.risk_level}</td>
                <td className="max-w-md p-3 text-dim">{x.reason}</td>
              </tr>
            ))}
            {!v.length && <tr><td colSpan={5} className="p-10 text-center text-faint">No violations yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
