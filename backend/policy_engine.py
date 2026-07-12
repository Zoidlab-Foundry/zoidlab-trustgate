"""ZoidLab TrustGate policy engine — deterministic, real.

Evaluates a proposed AI action (prompt, model, data classification, workflow type,
tools, RAG/memory context) against a set of active policies and their rules, and returns
a clear decision with reasons and a recommended action. Rule checks are concrete
(regex secret/PII detection via risk_scanner, model allow/deny lists, approval triggers,
citation requirements, cost limits) — no fabricated scoring.
"""
import risk_scanner

_ENFORCE_ORDER = {"monitor": 0, "warn": 1, "require_approval": 2, "block": 3}
_DECISION = {"monitor": "allow", "warn": "warn", "require_approval": "require_approval", "block": "blocked"}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

RULE_TYPES = [
    "no_secrets", "pii_external", "model_access", "require_citations",
    "approval_workflows", "cost_limit", "memory_write", "tool_usage", "logging",
]


def _provider_of(req):
    m = (req.get("model") or "").lower()
    p = (req.get("provider") or "").lower()
    if p:
        return p
    return m.split("/")[0] if "/" in m else m


def _check_rule(rule, req):
    """Return a reason string if this rule is violated by the request, else None."""
    t = rule.get("type")
    prompt = req.get("prompt") or ""
    provider = _provider_of(req)
    model = (req.get("model") or "").lower()
    dc = (req.get("data_classification") or "public").lower()

    if t == "no_secrets":
        scan = risk_scanner.scan(prompt)
        if scan["has_secret"]:
            return f"Prompt contains what looks like a secret ({', '.join(scan['secrets'] + scan['patterns']) or 'sensitive value'})."
    elif t == "pii_external":
        approved = [p.lower() for p in (rule.get("approved_providers") or [])]
        if dc in ("pii", "confidential") and provider and provider not in approved:
            return f"{dc.upper()} data cannot be sent to provider '{provider}' (not on the approved list)."
    elif t == "model_access":
        blocked = [b.lower() for b in (rule.get("blocked") or [])]
        allowed = [a.lower() for a in (rule.get("allowed") or [])]
        tag = model or provider
        if any(b in tag for b in blocked):
            return f"Model/provider '{tag}' is on the blocked list."
        if allowed and not any(a in tag for a in allowed):
            return f"Model/provider '{tag}' is not on the approved list for this policy."
    elif t == "require_citations":
        if req.get("context_type") == "rag" and not req.get("rag_cited", False):
            return "RAG answer is missing required citations."
    elif t == "approval_workflows":
        wfs = [w.lower() for w in (rule.get("workflows") or ["legal", "medical", "financial"])]
        wt = (req.get("workflow_type") or "").lower()
        if wt and wt in wfs:
            return f"'{wt}' workflows require human approval before AI execution."
    elif t == "cost_limit":
        mx = int(rule.get("max_tokens") or 0)
        if mx and int(req.get("max_tokens") or 0) > mx:
            return f"Requested max_tokens ({req.get('max_tokens')}) exceeds the policy limit ({mx})."
    elif t == "memory_write":
        if (req.get("memory_write_risk") or "").lower() == "high":
            return "High-risk memory write requires approval."
    elif t == "tool_usage":
        blocked = [b.lower() for b in (rule.get("blocked_tools") or [])]
        used = [str(x).lower() for x in (req.get("tools") or [])]
        hit = [u for u in used if u in blocked]
        if hit:
            return f"Tool(s) not permitted by policy: {', '.join(hit)}."
    elif t == "logging":
        return None  # informational only — never a violation
    return None


def _check_policy(policy, req):
    reasons = []
    for rule in policy.get("rules") or []:
        r = _check_rule(rule, req)
        if r:
            reasons.append(r)
    return reasons


def _recommend(decision, matched, req):
    if decision == "allow":
        return "None. This action complies with your active policies."
    first = matched[0]["reasons"][0] if matched and matched[0]["reasons"] else ""
    if "secret" in first.lower():
        return "Remove the secret from the prompt and use an approved internal model or the secrets vault."
    if "provider" in first.lower() or "approved list" in first.lower():
        return "Switch to an approved model/provider for this data classification."
    if "citation" in first.lower():
        return "Enable citations on the RAG answer before proceeding."
    if "approval" in first.lower() or "workflow" in first.lower():
        return "Submit this action for human approval before executing."
    if "max_tokens" in first.lower():
        return "Lower max_tokens to the policy limit, or request an exception."
    if "tool" in first.lower():
        return "Remove the disallowed tool(s) from this action."
    return "Review the matched policies and adjust the request to comply."


def evaluate(policies, req):
    """policies: list of active policy dicts. req: the proposed action. Returns a decision."""
    matched = []
    for pol in policies:
        if pol.get("status") not in (None, "active"):
            continue
        reasons = _check_policy(pol, req)
        if reasons:
            matched.append({"policy": pol, "reasons": reasons})

    if not matched:
        return {"decision": "allow", "risk_level": "low", "matched_policies": [],
                "reasons": ["No policy matched — this action is allowed."],
                "recommended_action": "None. This action complies with your active policies.",
                "rule_hits": []}

    strongest = max(matched, key=lambda m: _ENFORCE_ORDER.get(m["policy"].get("enforcement_mode", "warn"), 1))
    mode = strongest["policy"].get("enforcement_mode", "warn")
    decision = _DECISION.get(mode, "warn")
    risk = max((m["policy"].get("risk_level", "medium") for m in matched),
               key=lambda r: _RISK_ORDER.get(r, 1))
    reasons = [r for m in matched for r in m["reasons"]]
    names = [m["policy"]["name"] for m in matched]
    return {"decision": decision, "risk_level": risk, "matched_policies": names, "reasons": reasons,
            "recommended_action": _recommend(decision, matched, req),
            "rule_hits": [{"policy": m["policy"]["name"], "enforcement": m["policy"].get("enforcement_mode"),
                           "reasons": m["reasons"]} for m in matched]}
