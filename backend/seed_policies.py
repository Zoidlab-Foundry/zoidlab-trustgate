"""Seed a public demo policy project + policies (owner NULL = visible to everyone)."""
import database as db


def run():
    if db.list_projects(None):
        return 0
    now = db.now_iso()
    pid = db.new_id("proj")
    with db._conn() as c:
        c.execute("""INSERT INTO policy_projects (id,owner_user_id,name,slug,description,status,risk_level,icon,accent,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (pid, None, "Production Guardrails", db._slug("Production Guardrails"),
                   "Baseline governance for production AI: no secrets, approved models, PII handling, approvals.",
                   "active", "high", "⛨", "#7c5cfc", now, now))

    POLICIES = [
        ("No secrets in prompts", "prompt_safety", "block", "high",
         "Block any prompt containing API keys, passwords, tokens, or SSNs.",
         [{"type": "no_secrets"}], {"scope": ["prompt", "workflow", "agent"]}),
        ("PII stays on approved providers", "data_classification", "block", "high",
         "Confidential or PII data may only be sent to approved model providers.",
         [{"type": "pii_external", "approved_providers": ["nyquest-router", "anthropic", "openai"]}],
         {"data_types": ["pii", "confidential"]}),
        ("Approved production models only", "model_access", "warn", "medium",
         "Only approved models may be used in production workflows.",
         [{"type": "model_access", "allowed": ["anthropic", "openai", "google", "nyquest-router"],
           "blocked": ["deepseek", "qwen"]}], {"environment": ["production"]}),
        ("Human approval for high-stakes advice", "approval", "require_approval", "high",
         "Legal, medical, and financial advice workflows require human approval.",
         [{"type": "approval_workflows", "workflows": ["legal", "medical", "financial"]}],
         {"workflows": ["legal", "medical", "financial"]}),
        ("RAG answers must cite sources", "rag_source", "warn", "medium",
         "Retrieval-augmented answers must include citations.",
         [{"type": "require_citations"}], {"scope": ["rag"]}),
        ("High-risk memory writes need approval", "memory_write", "require_approval", "medium",
         "Writing high-sensitivity memories requires approval.",
         [{"type": "memory_write"}], {"scope": ["memory"]}),
        ("Token budget ceiling", "cost_limit", "warn", "low",
         "Cap generation length to control cost.",
         [{"type": "cost_limit", "max_tokens": 2000}], {"scope": ["prompt", "workflow"]}),
        ("Log all production calls", "logging", "monitor", "low",
         "Every production model/prompt call is logged for audit.",
         [{"type": "logging"}], {"environment": ["production"]}),
    ]
    with db._conn() as c:
        for name, cat, mode, risk, desc, rules, applies in POLICIES:
            c.execute("""INSERT INTO policies (id,project_id,owner_user_id,name,slug,description,category,status,risk_level,
                         rules,enforcement_mode,applies_to,version,created_at,updated_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (db.new_id("pol"), pid, None, name, db._slug(name), desc, cat, "active", risk,
                       db._j(rules), mode, db._j(applies), "1.0.0", now, now))
    return len(POLICIES)
