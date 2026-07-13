"""ZoidLab TrustGate API — Foundry Package 06, AI Policy Engine.

Every write + policy check requires Nyquest Pro (backend-enforced). The core question:
"Is this AI action allowed?" — answered by the deterministic policy engine.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Any, List

import database as db
import entitlements
import policy_engine
import exporter
import envelope
import seed_policies
from auth import session, owner_of, require_pro, entitlement


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    n = seed_policies.run()
    if n:
        print(f"[trustgate] seeded demo project + {n} policies")
    yield


app = FastAPI(title="ZoidLab TrustGate API", lifespan=lifespan)


def require_owner(request: Request):
    o = require_pro(request)
    s = session(request)
    db.upsert_user(o, s.get("email") if s else None, s.get("name") if s else None)
    return o


# ---- auth / meta --------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "service": "trustgate"}


@app.get("/api/auth/me")
def auth_me(request: Request):
    s = session(request)
    if not s:
        return {"authenticated": False}
    return {"authenticated": True, "user_id": s.get("sub"), "email": s.get("email"),
            "name": s.get("name"), "tier": s.get("tier")}


@app.get("/api/auth/entitlements")
def auth_entitlements(request: Request):
    return entitlement(request)


class MockLogin(BaseModel):
    tier: Optional[str] = "pro"


@app.post("/api/auth/mock-login")
def mock_login(body: MockLogin):
    return entitlements._mock()


@app.get("/api/stats")
def stats(request: Request, owner: str = Depends(require_owner)):
    return db.dashboard_stats(owner)


@app.get("/api/meta")
def meta():
    return {"categories": ["model_access", "data_classification", "prompt_safety", "tool_usage",
                           "rag_source", "memory_write", "cost_limit", "approval", "user_role",
                           "external_api", "logging", "retention"],
            "enforcement_modes": ["monitor", "warn", "require_approval", "block"],
            "rule_types": policy_engine.RULE_TYPES,
            "data_classifications": ["public", "internal", "confidential", "pii"]}


# ---- projects -----------------------------------------------------------
class ProjectBody(BaseModel):
    name: str
    description: Optional[str] = ""
    risk_level: Optional[str] = "low"


@app.get("/api/projects")
def projects(request: Request, owner: str = Depends(require_owner)):
    return {"projects": db.list_projects(owner)}


@app.post("/api/projects")
def create_project(body: ProjectBody, request: Request, owner: str = Depends(require_owner)):
    return {"ok": True, "project": db.create_project(body.model_dump(), owner)}


@app.get("/api/projects/{pid}")
def get_project(pid: str, request: Request, owner: str = Depends(require_owner)):
    p = db.get_project(pid, owner)
    if not p:
        raise HTTPException(404, "not_found")
    p["policies"] = db.list_policies(owner, project_id=pid)
    return p


# ---- policies -----------------------------------------------------------
class PolicyBody(BaseModel):
    name: str
    description: Optional[str] = ""
    category: Optional[str] = "model_access"
    status: Optional[str] = "active"
    risk_level: Optional[str] = "medium"
    rules: Optional[list] = []
    enforcement_mode: Optional[str] = "warn"
    applies_to: Optional[dict] = {}
    project_id: Optional[str] = None


@app.get("/api/policies")
def list_policies(request: Request, project_id: Optional[str] = None, category: Optional[str] = None,
                  status: Optional[str] = None, search: Optional[str] = None,
                  owner: str = Depends(require_owner)):
    return {"policies": db.list_policies(owner, project_id=project_id, category=category,
                                         status=status, search=search)}


@app.post("/api/policies")
def create_policy(body: PolicyBody, request: Request, owner: str = Depends(require_owner)):
    return {"ok": True, "policy": db.create_policy(body.model_dump(), owner)}


@app.get("/api/policies/{pid}")
def get_policy(pid: str, request: Request, owner: str = Depends(require_owner)):
    p = db.get_policy(pid, owner)
    if not p:
        raise HTTPException(404, "not_found")
    p["versions"] = db.list_versions(pid)
    return p


@app.put("/api/policies/{pid}")
def update_policy(pid: str, body: PolicyBody, request: Request, owner: str = Depends(require_owner)):
    p = db.update_policy(pid, body.model_dump(), owner)
    if not p:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True, "policy": p}


class SnapshotBody(BaseModel):
    changelog: Optional[str] = ""


@app.post("/api/policies/{pid}/versions")
def snapshot(pid: str, body: SnapshotBody, request: Request, owner: str = Depends(require_owner)):
    v = db.snapshot_policy(pid, body.changelog, owner)
    if v is None:
        raise HTTPException(404, "not_found")
    return {"ok": True, "versions": v}


# ---- the core policy check ----------------------------------------------
class ActionRequest(BaseModel):
    prompt: Optional[str] = ""
    model: Optional[str] = None
    provider: Optional[str] = None
    data_classification: Optional[str] = "public"
    workflow_type: Optional[str] = None
    context_type: Optional[str] = None       # e.g. "rag"
    rag_cited: Optional[bool] = False
    memory_write_risk: Optional[str] = None
    tools: Optional[list] = []
    max_tokens: Optional[int] = None


class TestBody(BaseModel):
    project_id: Optional[str] = None
    request: ActionRequest
    save: Optional[bool] = True
    correlation_id: Optional[str] = None    # ties the decision to a calling run/trace (§6.4)


@app.post("/api/test")
def run_test(body: TestBody, request: Request, owner: str = Depends(require_owner)):
    """Evaluate a proposed action against all active policies in a project."""
    policies = db.list_policies(owner_of(request), project_id=body.project_id, status="active")
    req = body.request.model_dump()
    result = policy_engine.evaluate(policies, req, correlation_id=body.correlation_id)
    if body.save:
        db.log_test(body.project_id, None, req, result, owner)
        if result["decision"] in ("blocked", "warn"):
            nm = result["matched_policies"][0] if result["matched_policies"] else "policy"
            db.log_violation(body.project_id, None, nm, result, req, owner)
        if result["decision"] == "require_approval":
            nm = result["matched_policies"][0] if result["matched_policies"] else "policy"
            result["approval_id"] = db.create_approval(body.project_id, None, nm, req,
                                                       "; ".join(result["reasons"])[:300], owner)
    return result


@app.post("/api/policies/{pid}/test")
def test_one_policy(pid: str, body: ActionRequest, request: Request, owner: str = Depends(require_owner)):
    p = db.get_policy(pid, owner_of(request))
    if not p:
        raise HTTPException(404, "not_found")
    result = policy_engine.evaluate([p], body.model_dump())
    db.log_test(p.get("project_id"), pid, body.model_dump(), result, owner)
    return result


class SubmitApprovalBody(BaseModel):
    request: ActionRequest
    reason: Optional[str] = ""


@app.post("/api/policies/{pid}/submit-approval")
def submit_approval(pid: str, body: SubmitApprovalBody, request: Request, owner: str = Depends(require_owner)):
    p = db.get_policy(pid, owner_of(request))
    if not p:
        raise HTTPException(404, "not_found")
    aid = db.create_approval(p.get("project_id"), pid, p["name"], body.request.model_dump(),
                             body.reason or "Manual submission", owner)
    return {"ok": True, "approval_id": aid}


# ---- violations / approvals ---------------------------------------------
@app.get("/api/violations")
def violations(request: Request, project_id: Optional[str] = None, owner: str = Depends(require_owner)):
    return {"violations": db.list_violations(owner, project_id=project_id)}


@app.get("/api/approvals")
def approvals(request: Request, status: Optional[str] = None, owner: str = Depends(require_owner)):
    return {"approvals": db.list_approvals(owner, status=status)}


class ReviewBody(BaseModel):
    notes: Optional[str] = ""


@app.post("/api/approvals/{aid}/approve")
def approve(aid: str, body: ReviewBody, request: Request, owner: str = Depends(require_owner)):
    a = db.resolve_approval(aid, "approved", owner, body.notes)
    if not a:
        raise HTTPException(404, "not_found")
    return {"ok": True, "approval": a}


@app.post("/api/approvals/{aid}/reject")
def reject(aid: str, body: ReviewBody, request: Request, owner: str = Depends(require_owner)):
    a = db.resolve_approval(aid, "rejected", owner, body.notes)
    if not a:
        raise HTTPException(404, "not_found")
    return {"ok": True, "approval": a}


# ---- analytics / audit / export -----------------------------------------
@app.get("/api/analytics")
def analytics(request: Request, owner: str = Depends(require_owner)):
    return db.analytics(owner)


@app.get("/api/projects/{pid}/audit")
def project_audit(pid: str, request: Request, owner: str = Depends(require_owner)):
    if not db.get_project(pid, owner):
        raise HTTPException(404, "not_found")
    return {"audit": db.audit_for(pid)}


def _wrapped(proj, policies, owner):
    payload = exporter.to_package(proj, policies)
    return envelope.wrap("trustgate", "policy_bundle", (proj or {}).get("id") or "all",
                         "1.0.0", payload, nyquest_user_id=owner)


@app.get("/api/export/json")
def export_json(request: Request, project_id: Optional[str] = None, owner: str = Depends(require_owner)):
    proj = db.get_project(project_id, owner) if project_id else None
    return _wrapped(proj, db.list_policies(owner, project_id=project_id), owner)


@app.get("/api/export/yaml")
def export_yaml(request: Request, project_id: Optional[str] = None, owner: str = Depends(require_owner)):
    proj = db.get_project(project_id, owner) if project_id else None
    return PlainTextResponse(exporter.to_yaml(_wrapped(proj, db.list_policies(owner, project_id=project_id), owner)))
