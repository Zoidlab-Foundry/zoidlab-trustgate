"""TrustGate assistant manifest — what the in-app assistant knows and may do.

This file is the assistant's security boundary: only the capabilities declared here exist
for it, and they execute through this app's own session-authed API (require_pro + RLS apply).
Delete-class operations are intentionally not declared, and approval resolve/reject stay
manual — human-judgment actions are not assistant capabilities.
"""
from foundry_common.assistant import cap, page

MANIFEST = {
    "app": "TrustGate",
    "description": (
        "TrustGate is the Foundry's deterministic AI usage policy engine. Users define "
        "policies made of rules (no_secrets, pii_external, model_access, require_citations, "
        "approval_workflows, cost_limit, memory_write, tool_usage, logging) with an "
        "enforcement mode (monitor / warn / require_approval / block). Other Foundry apps "
        "call TrustGate's preflight check before running AI actions; blocked or warned "
        "actions land in the violations log and require_approval actions queue for a human "
        "reviewer. Nothing is probabilistic — the same request always yields the same decision."
    ),
    "base_url": "http://127.0.0.1:8700",
    "pages": [
        page("/", "Dashboard", "Overview: policy/violation/approval stats and recent activity."),
        page("/policies", "Policies", "Create and manage policies, their rules and enforcement modes.",
             assists={"new-policy": "the New policy button"}),
        page("/test", "Test Console", "Simulate an AI action and see which policies fire and the decision.",
             assists={"run-test": "the Check policy button"}),
        page("/violations", "Violations", "Log of blocked and warned actions with matched policies."),
        page("/approvals", "Approvals", "Pending require_approval requests awaiting a human decision."),
        page("/analytics", "Analytics", "Decision trends, top-firing policies, category breakdowns."),
        page("/deploy", "Deploy", "Deploy TrustGate as a token-authed preflight API for other apps."),
    ],
    "capabilities": [
        cap("list_policies", "GET", "/api/policies", risk="read",
            desc="The user's policies. Optional filters: project_id, category, status, search.",
            params={"project_id": "filter by project id", "category": "filter by category",
                    "status": "filter by status (active/draft/archived)", "search": "text search"}),
        cap("get_policy", "GET", "/api/policies/{pid}", risk="read",
            desc="One policy with its rules, enforcement mode, and version history.",
            params={"pid": "policy id"}),
        cap("list_violations", "GET", "/api/violations", risk="read",
            desc="Blocked/warned actions, newest first. Optional project_id filter.",
            params={"project_id": "filter by project id"}),
        cap("list_approvals", "GET", "/api/approvals", risk="read",
            desc="Approval queue entries. Optional status filter (pending/approved/rejected). "
                 "Approving or rejecting is a human action done in the UI, not via the assistant.",
            params={"status": "filter by status"}),
        cap("stats", "GET", "/api/stats", risk="read",
            desc="Dashboard counts: policies, violations, approvals, recent decisions."),
        cap("meta", "GET", "/api/meta", risk="read",
            desc="Valid categories, enforcement modes, rule types, and data classifications."),
        cap("create_policy", "POST", "/api/policies", risk="write",
            desc="Create a policy. rules is a list of objects like {'type': <rule type>, ...} "
                 "using rule types from meta; enforcement_mode is one of "
                 "monitor/warn/require_approval/block.",
            params={"name": "policy name", "description": "short description",
                    "category": "category label (default model_access)",
                    "status": "active or draft (default active)",
                    "risk_level": "low/medium/high (default medium)",
                    "rules": "list of rule objects", "enforcement_mode": "enforcement mode (default warn)",
                    "project_id": "optional project id"}),
        cap("run_test", "POST", "/api/test", risk="write",
            desc="Evaluate a simulated AI action against all active policies and return the "
                 "decision with matched policies and reasons. request is an object like "
                 "{'prompt': str, 'model': str, 'provider': str, 'data_classification': "
                 "'public|internal|confidential|pii', 'tools': [str], 'max_tokens': int, "
                 "'context_type': str, 'rag_cited': bool}. Saved tests log violations and "
                 "may queue an approval; set save false for a dry run.",
            params={"project_id": "optional project id to scope policies",
                    "request": "the simulated action object",
                    "save": "true to log the test (default true)",
                    "correlation_id": "optional id tying the decision to a calling run"}),
    ],
}
