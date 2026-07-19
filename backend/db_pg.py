"""Postgres data layer for ZoidLab TrustGate with per-tenant Row-Level Security (§3.2).

Tenant isolation is enforced by the database, not just the app: policy_projects and
policies carry owner_user_id, have FORCE ROW LEVEL SECURITY, and a policy exposing only
rows whose owner matches `app.current_owner` (set per transaction) or is NULL (shared
seed). Child tables (policy_versions, policy_tests, policy_violations, policy_approvals)
and audit_logs have no owner column — they are reached through an RLS-protected parent —
so they carry no policy. Public API mirrors the former sqlite database.py exactly.
"""
import os
import json
import uuid
import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# App connections use the RLS-enforced role (app_rls); DDL + cross-tenant admin use the
# superuser (foundry), which bypasses RLS by design.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://app_rls@127.0.0.1:5433/trustgate")
DATABASE_URL_ADMIN = os.environ.get("DATABASE_URL_ADMIN", "postgresql://foundry@127.0.0.1:5433/trustgate")
_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=True, kwargs={"autocommit": False})


def admin_conn():
    return psycopg.connect(DATABASE_URL_ADMIN, row_factory=dict_row)


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _j(v):
    return json.dumps(v)


def _pj(v, default=None):
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


def _slug(s):
    import re
    return (re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:50] or "item") + "-" + uuid.uuid4().hex[:5]


class _tx:
    """Transaction scoped to a tenant: sets app.current_owner so RLS applies."""
    def __init__(self, owner):
        self.owner = owner or ""

    def __enter__(self):
        self.conn = _pool.getconn()
        self.cur = self.conn.cursor(row_factory=dict_row)
        self.cur.execute("SELECT set_config('app.current_owner', %s, true)", (self.owner,))
        return self.cur

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.cur.close()
            _pool.putconn(self.conn)


_TENANT_TABLES = ["policy_projects", "policies"]


def init():
    with admin_conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT, name TEXT, role TEXT DEFAULT 'user',
            org_id TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY, name TEXT, slug TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS policy_projects (
            id TEXT PRIMARY KEY, org_id TEXT, owner_user_id TEXT, name TEXT NOT NULL, slug TEXT,
            description TEXT, status TEXT DEFAULT 'active', risk_level TEXT DEFAULT 'low',
            icon TEXT, accent TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY, project_id TEXT, org_id TEXT, owner_user_id TEXT, name TEXT NOT NULL,
            slug TEXT, description TEXT, category TEXT, status TEXT DEFAULT 'active', risk_level TEXT DEFAULT 'medium',
            rules TEXT, enforcement_mode TEXT DEFAULT 'warn', applies_to TEXT, version TEXT DEFAULT '1.0.0',
            created_at TEXT, updated_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pol_owner ON policies(owner_user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pol_project ON policies(project_id)")
        c.execute("""CREATE TABLE IF NOT EXISTS policy_versions (
            id TEXT PRIMARY KEY, policy_id TEXT, version TEXT, changelog TEXT, snapshot TEXT,
            created_by TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS policy_tests (
            id TEXT PRIMARY KEY, policy_id TEXT, project_id TEXT, input TEXT, decision TEXT, risk_level TEXT,
            matched_policies TEXT, reasons TEXT, created_by TEXT, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_test_project ON policy_tests(project_id, created_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS policy_violations (
            id TEXT PRIMARY KEY, project_id TEXT, policy_id TEXT, policy_name TEXT, decision TEXT,
            risk_level TEXT, reason TEXT, input TEXT, actor_user_id TEXT, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_viol_project ON policy_violations(project_id, created_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS policy_approvals (
            id TEXT PRIMARY KEY, project_id TEXT, policy_id TEXT, policy_name TEXT, input TEXT, reason TEXT,
            status TEXT DEFAULT 'pending', requested_by TEXT, reviewer_id TEXT, reviewer_notes TEXT,
            created_at TEXT, reviewed_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_appr_project ON policy_approvals(project_id, status)")
        c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, action TEXT, actor_user_id TEXT,
            details TEXT, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit ON audit_logs(entity_type, entity_id, created_at)")
        for t in _TENANT_TABLES:
            c.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            c.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            c.execute(f"DROP POLICY IF EXISTS {t}_isolation ON {t}")
            c.execute(f"""CREATE POLICY {t}_isolation ON {t}
                USING (owner_user_id IS NULL OR owner_user_id = current_setting('app.current_owner', true))
                WITH CHECK (owner_user_id IS NULL OR owner_user_id = current_setting('app.current_owner', true))""")
        c.execute("GRANT USAGE ON SCHEMA public TO app_rls")
        c.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_rls")


# --- users / admin / audit --------------------------------------------
def upsert_user(uid, email=None, name=None):
    if not uid:
        return
    now = now_iso()
    with _tx(uid) as cur:
        cur.execute("""INSERT INTO users (id,email,name,role,created_at,updated_at) VALUES (%s,%s,%s,'user',%s,%s)
                       ON CONFLICT (id) DO UPDATE SET email=COALESCE(EXCLUDED.email,users.email),
                         name=COALESCE(EXCLUDED.name,users.name), updated_at=EXCLUDED.updated_at""",
                    (uid, email, name, now, now))


def is_admin(uid):
    if not uid:
        return False
    admins = [a.strip() for a in os.environ.get("TRUSTGATE_ADMINS", "").split(",") if a.strip()]
    return uid in admins


def audit(entity_type, entity_id, action, actor, details=None):
    with _tx(None) as cur:
        cur.execute("INSERT INTO audit_logs (id,entity_type,entity_id,action,actor_user_id,details,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (new_id("aud"), entity_type, entity_id, action, actor, _j(details or {}), now_iso()))


def audit_for(entity_id, limit=80):
    with _tx(None) as cur:
        cur.execute("SELECT * FROM audit_logs WHERE entity_id=%s ORDER BY created_at DESC LIMIT %s", (entity_id, limit))
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r); d["details"] = _pj(d.get("details"), {}); out.append(d)
    return out


# --- projects ----------------------------------------------------------
def list_projects(viewer=None):
    with _tx(viewer) as cur:
        cur.execute("""SELECT p.*, (SELECT COUNT(*) FROM policies po WHERE po.project_id=p.id) AS policy_count
                       FROM policy_projects p ORDER BY p.updated_at DESC""")
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_project(pid, viewer=None):
    with _tx(viewer) as cur:
        cur.execute("SELECT * FROM policy_projects WHERE id=%s", (pid,))
        r = cur.fetchone()
    return dict(r) if r else None


def create_project(data, owner):
    pid = new_id("proj"); now = now_iso()
    with _tx(owner) as cur:
        cur.execute("""INSERT INTO policy_projects (id,owner_user_id,name,slug,description,status,risk_level,icon,accent,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (pid, owner, data["name"], _slug(data["name"]), data.get("description", ""), "active",
                     data.get("risk_level", "low"), data.get("icon", "⛨"), data.get("accent", "#7c5cfc"), now, now))
    audit("project", pid, "created", owner)
    return get_project(pid, owner)


# --- policies ----------------------------------------------------------
def _policy_out(r):
    if not r:
        return None
    d = dict(r)
    d["rules"] = _pj(d.get("rules"), [])
    d["applies_to"] = _pj(d.get("applies_to"), {})
    return d


def list_policies(viewer=None, project_id=None, category=None, status=None, search=None):
    q = "SELECT * FROM policies WHERE TRUE"
    args = []
    if project_id and project_id != "all":
        q += " AND project_id=%s"; args.append(project_id)
    if category and category != "all":
        q += " AND category=%s"; args.append(category)
    if status and status != "all":
        q += " AND status=%s"; args.append(status)
    if search:
        q += " AND lower(name) LIKE %s"; args.append(f"%{search.lower()}%")
    q += " ORDER BY updated_at DESC"
    with _tx(viewer) as cur:
        cur.execute(q, args)
        rows = cur.fetchall()
    return [_policy_out(r) for r in rows]


def get_policy(pid, viewer=None):
    with _tx(viewer) as cur:
        cur.execute("SELECT * FROM policies WHERE id=%s", (pid,))
        r = cur.fetchone()
    return _policy_out(r)


def get_policy_raw(pid):
    # Engine-internal read that bypasses tenant visibility (cross-app decision paths).
    with admin_conn() as c:
        r = c.execute("SELECT * FROM policies WHERE id=%s", (pid,)).fetchone()
    return _policy_out(r)


def create_policy(data, owner):
    pid = new_id("pol"); now = now_iso()
    with _tx(owner) as cur:
        cur.execute("""INSERT INTO policies (id,project_id,owner_user_id,name,slug,description,category,status,risk_level,
                       rules,enforcement_mode,applies_to,version,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (pid, data.get("project_id"), owner, data["name"], _slug(data["name"]), data.get("description", ""),
                     data.get("category", "model_access"), data.get("status", "active"), data.get("risk_level", "medium"),
                     _j(data.get("rules", [])), data.get("enforcement_mode", "warn"), _j(data.get("applies_to", {})),
                     "1.0.0", now, now))
    audit("policy", pid, "created", owner)
    return get_policy(pid, owner)


def update_policy(pid, data, owner):
    p = get_policy(pid, owner)
    if not p or (p.get("owner_user_id") and p["owner_user_id"] != owner and not is_admin(owner)):
        return None
    fields, args = [], []
    for k in ("name", "description", "category", "status", "risk_level", "enforcement_mode", "project_id"):
        if k in data and data[k] is not None:
            fields.append(f"{k}=%s"); args.append(data[k])
    if "rules" in data and data["rules"] is not None:
        fields.append("rules=%s"); args.append(_j(data["rules"]))
    if "applies_to" in data and data["applies_to"] is not None:
        fields.append("applies_to=%s"); args.append(_j(data["applies_to"]))
    fields.append("updated_at=%s"); args.append(now_iso())
    args.append(pid)
    with _tx(owner) as cur:
        cur.execute(f"UPDATE policies SET {','.join(fields)} WHERE id=%s", args)
    audit("policy", pid, "updated", owner)
    return get_policy(pid, owner)


def snapshot_policy(pid, changelog, owner):
    p = get_policy(pid, owner)
    if not p:
        return None
    vid = new_id("pv")
    with _tx(owner) as cur:
        cur.execute("INSERT INTO policy_versions (id,policy_id,version,changelog,snapshot,created_by,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (vid, pid, p.get("version", "1.0.0"), changelog or "", _j(p), owner, now_iso()))
    return list_versions(pid)


def list_versions(pid):
    with _tx(None) as cur:
        cur.execute("SELECT id,version,changelog,created_by,created_at FROM policy_versions WHERE policy_id=%s ORDER BY created_at DESC", (pid,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# --- tests / violations / approvals -----------------------------------
def log_test(project_id, policy_id, inp, result, owner):
    tid = new_id("test")
    with _tx(None) as cur:
        cur.execute("""INSERT INTO policy_tests (id,policy_id,project_id,input,decision,risk_level,matched_policies,reasons,created_by,created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (tid, policy_id, project_id, _j(inp), result["decision"], result["risk_level"],
                     _j(result["matched_policies"]), _j(result["reasons"]), owner, now_iso()))
    return tid


def log_violation(project_id, policy_id, policy_name, result, inp, actor):
    with _tx(None) as cur:
        cur.execute("""INSERT INTO policy_violations (id,project_id,policy_id,policy_name,decision,risk_level,reason,input,actor_user_id,created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (new_id("viol"), project_id, policy_id, policy_name, result["decision"], result["risk_level"],
                     "; ".join(result["reasons"])[:400], _j(inp), actor, now_iso()))


def list_violations(viewer=None, project_id=None, limit=100):
    # RLS on policy_projects scopes the join (inner join: a violation is visible only if
    # its project is — fail-closed vs the old LEFT JOIN owner filter).
    q = "SELECT v.* FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id WHERE TRUE"
    args = []
    if project_id and project_id != "all":
        q += " AND v.project_id=%s"; args.append(project_id)
    q += " ORDER BY v.created_at DESC LIMIT %s"; args.append(limit)
    with _tx(viewer) as cur:
        cur.execute(q, args)
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r); d["input"] = _pj(d.get("input"), {}); out.append(d)
    return out


def create_approval(project_id, policy_id, policy_name, inp, reason, requester):
    aid = new_id("appr")
    with _tx(None) as cur:
        cur.execute("""INSERT INTO policy_approvals (id,project_id,policy_id,policy_name,input,reason,status,requested_by,created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,'pending',%s,%s)""",
                    (aid, project_id, policy_id, policy_name, _j(inp), reason, requester, now_iso()))
    return aid


def list_approvals(viewer=None, status=None):
    q = "SELECT a.* FROM policy_approvals a JOIN policy_projects p ON p.id=a.project_id WHERE TRUE"
    args = []
    if status and status != "all":
        q += " AND a.status=%s"; args.append(status)
    q += " ORDER BY a.created_at DESC"
    with _tx(viewer) as cur:
        cur.execute(q, args)
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r); d["input"] = _pj(d.get("input"), {}); out.append(d)
    return out


def resolve_approval(aid, status, reviewer, notes=None):
    with _tx(None) as cur:
        cur.execute("SELECT id FROM policy_approvals WHERE id=%s", (aid,))
        r = cur.fetchone()
        if not r:
            return None
        cur.execute("UPDATE policy_approvals SET status=%s, reviewer_id=%s, reviewer_notes=%s, reviewed_at=%s WHERE id=%s",
                    (status, reviewer, notes, now_iso(), aid))
        cur.execute("SELECT * FROM policy_approvals WHERE id=%s", (aid,))
        row = cur.fetchone()
    d = dict(row); d["input"] = _pj(d.get("input"), {})
    return d


# --- analytics ---------------------------------------------------------
def dashboard_stats(viewer=None):
    """RLS scopes both the direct policy counts and every project join; COUNT comes back
    as int from psycopg but is wrapped anyway for JSON safety (template convention)."""
    with _tx(viewer) as cur:
        cur.execute("SELECT COUNT(*) n FROM policies WHERE status='active'")
        active = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM policy_tests t JOIN policy_projects p ON p.id=t.project_id")
        checks = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id")
        viol = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id WHERE v.decision='block'")
        blocked = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id WHERE v.risk_level='high'")
        high = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM policy_approvals a JOIN policy_projects p ON p.id=a.project_id WHERE a.status='pending'")
        pending = cur.fetchone()["n"]
    return {"active_policies": int(active), "policy_checks": int(checks), "violations": int(viol),
            "blocked_requests": int(blocked), "high_risk_actions": int(high), "pending_approvals": int(pending)}


def analytics(viewer=None):
    with _tx(viewer) as cur:
        cur.execute("""SELECT v.decision d, COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id
                       GROUP BY v.decision""")
        by_decision = cur.fetchall()
        cur.execute("""SELECT v.policy_name nm, COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id
                       GROUP BY v.policy_name ORDER BY n DESC LIMIT 8""")
        by_policy = cur.fetchall()
        cur.execute("SELECT category c, COUNT(*) n FROM policies GROUP BY category")
        by_cat = cur.fetchall()
    return {"by_decision": [{"d": r["d"], "n": int(r["n"])} for r in by_decision],
            "top_policies": [{"nm": r["nm"], "n": int(r["n"])} for r in by_policy],
            "by_category": [{"c": r["c"], "n": int(r["n"])} for r in by_cat], **dashboard_stats(viewer)}
