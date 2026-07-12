"""SQLite persistence for ZoidLab TrustGate (Foundry Package 06).

Postgres-portable: JSONB columns are JSON-encoded TEXT; all access goes through these
helpers so a swap to Postgres/SQLModel touches only this file. Ownership = Nyquest user
id; seed content (owner NULL) is visible to everyone.
"""
import os
import json
import uuid
import sqlite3
import datetime

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "trustgate.db")


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


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


def init():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT, name TEXT, role TEXT DEFAULT 'user',
                org_id TEXT, created_at TEXT, updated_at TEXT );
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY, name TEXT, slug TEXT, created_at TEXT, updated_at TEXT );
            CREATE TABLE IF NOT EXISTS policy_projects (
                id TEXT PRIMARY KEY, org_id TEXT, owner_user_id TEXT, name TEXT NOT NULL, slug TEXT,
                description TEXT, status TEXT DEFAULT 'active', risk_level TEXT DEFAULT 'low',
                icon TEXT, accent TEXT, created_at TEXT, updated_at TEXT );
            CREATE TABLE IF NOT EXISTS policies (
                id TEXT PRIMARY KEY, project_id TEXT, org_id TEXT, owner_user_id TEXT, name TEXT NOT NULL,
                slug TEXT, description TEXT, category TEXT, status TEXT DEFAULT 'active', risk_level TEXT DEFAULT 'medium',
                rules TEXT, enforcement_mode TEXT DEFAULT 'warn', applies_to TEXT, version TEXT DEFAULT '1.0.0',
                created_at TEXT, updated_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_pol_owner ON policies(owner_user_id);
            CREATE INDEX IF NOT EXISTS idx_pol_project ON policies(project_id);
            CREATE TABLE IF NOT EXISTS policy_versions (
                id TEXT PRIMARY KEY, policy_id TEXT, version TEXT, changelog TEXT, snapshot TEXT,
                created_by TEXT, created_at TEXT );
            CREATE TABLE IF NOT EXISTS policy_tests (
                id TEXT PRIMARY KEY, policy_id TEXT, project_id TEXT, input TEXT, decision TEXT, risk_level TEXT,
                matched_policies TEXT, reasons TEXT, created_by TEXT, created_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_test_project ON policy_tests(project_id, created_at);
            CREATE TABLE IF NOT EXISTS policy_violations (
                id TEXT PRIMARY KEY, project_id TEXT, policy_id TEXT, policy_name TEXT, decision TEXT,
                risk_level TEXT, reason TEXT, input TEXT, actor_user_id TEXT, created_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_viol_project ON policy_violations(project_id, created_at);
            CREATE TABLE IF NOT EXISTS policy_approvals (
                id TEXT PRIMARY KEY, project_id TEXT, policy_id TEXT, policy_name TEXT, input TEXT, reason TEXT,
                status TEXT DEFAULT 'pending', requested_by TEXT, reviewer_id TEXT, reviewer_notes TEXT,
                created_at TEXT, reviewed_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_appr_project ON policy_approvals(project_id, status);
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, action TEXT, actor_user_id TEXT,
                details TEXT, created_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_audit ON audit_logs(entity_type, entity_id, created_at);
            """
        )


def _visible(col="owner_user_id"):
    return f"({col} IS NULL OR {col}=?)"


# --- users / admin / audit --------------------------------------------
def upsert_user(uid, email=None, name=None):
    if not uid:
        return
    now = now_iso()
    with _conn() as c:
        c.execute("""INSERT INTO users (id,email,name,role,created_at,updated_at) VALUES (?,?,?,'user',?,?)
                     ON CONFLICT(id) DO UPDATE SET email=COALESCE(excluded.email,users.email),
                       name=COALESCE(excluded.name,users.name), updated_at=excluded.updated_at""",
                  (uid, email, name, now, now))


def is_admin(uid):
    if not uid:
        return False
    admins = [a.strip() for a in os.environ.get("TRUSTGATE_ADMINS", "").split(",") if a.strip()]
    return uid in admins


def audit(entity_type, entity_id, action, actor, details=None):
    with _conn() as c:
        c.execute("INSERT INTO audit_logs (id,entity_type,entity_id,action,actor_user_id,details,created_at) VALUES (?,?,?,?,?,?,?)",
                  (new_id("aud"), entity_type, entity_id, action, actor, _j(details or {}), now_iso()))


def audit_for(entity_id, limit=80):
    with _conn() as c:
        rows = c.execute("SELECT * FROM audit_logs WHERE entity_id=? ORDER BY created_at DESC LIMIT ?", (entity_id, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["details"] = _pj(d.get("details"), {}); out.append(d)
    return out


# --- projects ----------------------------------------------------------
def list_projects(viewer=None):
    with _conn() as c:
        rows = c.execute(f"""SELECT p.*, (SELECT COUNT(*) FROM policies po WHERE po.project_id=p.id) AS policy_count
                             FROM policy_projects p WHERE {_visible()} ORDER BY p.updated_at DESC""", (viewer,)).fetchall()
    return [dict(r) for r in rows]


def get_project(pid, viewer=None):
    with _conn() as c:
        r = c.execute(f"SELECT * FROM policy_projects WHERE id=? AND {_visible()}", (pid, viewer)).fetchone()
    return dict(r) if r else None


def create_project(data, owner):
    pid = new_id("proj"); now = now_iso()
    with _conn() as c:
        c.execute("""INSERT INTO policy_projects (id,owner_user_id,name,slug,description,status,risk_level,icon,accent,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
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
    q = f"SELECT * FROM policies WHERE {_visible()}"
    args = [viewer]
    if project_id and project_id != "all":
        q += " AND project_id=?"; args.append(project_id)
    if category and category != "all":
        q += " AND category=?"; args.append(category)
    if status and status != "all":
        q += " AND status=?"; args.append(status)
    if search:
        q += " AND lower(name) LIKE ?"; args.append(f"%{search.lower()}%")
    q += " ORDER BY updated_at DESC"
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    return [_policy_out(r) for r in rows]


def get_policy(pid, viewer=None):
    with _conn() as c:
        r = c.execute(f"SELECT * FROM policies WHERE id=? AND {_visible()}", (pid, viewer)).fetchone()
    return _policy_out(r)


def get_policy_raw(pid):
    with _conn() as c:
        r = c.execute("SELECT * FROM policies WHERE id=?", (pid,)).fetchone()
    return _policy_out(r)


def create_policy(data, owner):
    pid = new_id("pol"); now = now_iso()
    with _conn() as c:
        c.execute("""INSERT INTO policies (id,project_id,owner_user_id,name,slug,description,category,status,risk_level,
                     rules,enforcement_mode,applies_to,version,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            fields.append(f"{k}=?"); args.append(data[k])
    if "rules" in data and data["rules"] is not None:
        fields.append("rules=?"); args.append(_j(data["rules"]))
    if "applies_to" in data and data["applies_to"] is not None:
        fields.append("applies_to=?"); args.append(_j(data["applies_to"]))
    fields.append("updated_at=?"); args.append(now_iso())
    args.append(pid)
    with _conn() as c:
        c.execute(f"UPDATE policies SET {','.join(fields)} WHERE id=?", args)
    audit("policy", pid, "updated", owner)
    return get_policy(pid, owner)


def snapshot_policy(pid, changelog, owner):
    p = get_policy(pid, owner)
    if not p:
        return None
    vid = new_id("pv")
    with _conn() as c:
        c.execute("INSERT INTO policy_versions (id,policy_id,version,changelog,snapshot,created_by,created_at) VALUES (?,?,?,?,?,?,?)",
                  (vid, pid, p.get("version", "1.0.0"), changelog or "", _j(p), owner, now_iso()))
    return list_versions(pid)


def list_versions(pid):
    with _conn() as c:
        rows = c.execute("SELECT id,version,changelog,created_by,created_at FROM policy_versions WHERE policy_id=? ORDER BY created_at DESC", (pid,)).fetchall()
    return [dict(r) for r in rows]


# --- tests / violations / approvals -----------------------------------
def log_test(project_id, policy_id, inp, result, owner):
    tid = new_id("test")
    with _conn() as c:
        c.execute("""INSERT INTO policy_tests (id,policy_id,project_id,input,decision,risk_level,matched_policies,reasons,created_by,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (tid, policy_id, project_id, _j(inp), result["decision"], result["risk_level"],
                   _j(result["matched_policies"]), _j(result["reasons"]), owner, now_iso()))
    return tid


def log_violation(project_id, policy_id, policy_name, result, inp, actor):
    with _conn() as c:
        c.execute("""INSERT INTO policy_violations (id,project_id,policy_id,policy_name,decision,risk_level,reason,input,actor_user_id,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (new_id("viol"), project_id, policy_id, policy_name, result["decision"], result["risk_level"],
                   "; ".join(result["reasons"])[:400], _j(inp), actor, now_iso()))


def list_violations(viewer=None, project_id=None, limit=100):
    q = """SELECT v.* FROM policy_violations v LEFT JOIN policy_projects p ON p.id=v.project_id
           WHERE (p.owner_user_id IS NULL OR p.owner_user_id=?)"""
    args = [viewer]
    if project_id and project_id != "all":
        q += " AND v.project_id=?"; args.append(project_id)
    q += " ORDER BY v.created_at DESC LIMIT ?"; args.append(limit)
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["input"] = _pj(d.get("input"), {}); out.append(d)
    return out


def create_approval(project_id, policy_id, policy_name, inp, reason, requester):
    aid = new_id("appr")
    with _conn() as c:
        c.execute("""INSERT INTO policy_approvals (id,project_id,policy_id,policy_name,input,reason,status,requested_by,created_at)
                     VALUES (?,?,?,?,?,?,'pending',?,?)""",
                  (aid, project_id, policy_id, policy_name, _j(inp), reason, requester, now_iso()))
    return aid


def list_approvals(viewer=None, status=None):
    q = """SELECT a.* FROM policy_approvals a LEFT JOIN policy_projects p ON p.id=a.project_id
           WHERE (p.owner_user_id IS NULL OR p.owner_user_id=?)"""
    args = [viewer]
    if status and status != "all":
        q += " AND a.status=?"; args.append(status)
    q += " ORDER BY a.created_at DESC"
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["input"] = _pj(d.get("input"), {}); out.append(d)
    return out


def resolve_approval(aid, status, reviewer, notes=None):
    with _conn() as c:
        r = c.execute("SELECT id FROM policy_approvals WHERE id=?", (aid,)).fetchone()
        if not r:
            return None
        c.execute("UPDATE policy_approvals SET status=?, reviewer_id=?, reviewer_notes=?, reviewed_at=? WHERE id=?",
                  (status, reviewer, notes, now_iso(), aid))
        row = c.execute("SELECT * FROM policy_approvals WHERE id=?", (aid,)).fetchone()
    d = dict(row); d["input"] = _pj(d.get("input"), {})
    return d


# --- analytics ---------------------------------------------------------
def dashboard_stats(viewer=None):
    vis = _visible()
    pvis = "(p.owner_user_id IS NULL OR p.owner_user_id=?)"
    with _conn() as c:
        active = c.execute(f"SELECT COUNT(*) n FROM policies WHERE {vis} AND status='active'", (viewer,)).fetchone()["n"]
        checks = c.execute(f"""SELECT COUNT(*) n FROM policy_tests t JOIN policy_projects p ON p.id=t.project_id WHERE {pvis}""", (viewer,)).fetchone()["n"]
        viol = c.execute(f"""SELECT COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id WHERE {pvis}""", (viewer,)).fetchone()["n"]
        blocked = c.execute(f"""SELECT COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id WHERE {pvis} AND v.decision='block'""", (viewer,)).fetchone()["n"]
        high = c.execute(f"""SELECT COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id WHERE {pvis} AND v.risk_level='high'""", (viewer,)).fetchone()["n"]
        pending = c.execute(f"""SELECT COUNT(*) n FROM policy_approvals a JOIN policy_projects p ON p.id=a.project_id WHERE {pvis} AND a.status='pending'""", (viewer,)).fetchone()["n"]
    return {"active_policies": active, "policy_checks": checks, "violations": viol,
            "blocked_requests": blocked, "high_risk_actions": high, "pending_approvals": pending}


def analytics(viewer=None):
    pvis = "(p.owner_user_id IS NULL OR p.owner_user_id=?)"
    with _conn() as c:
        by_decision = c.execute(f"""SELECT v.decision d, COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id
                                    WHERE {pvis} GROUP BY v.decision""", (viewer,)).fetchall()
        by_policy = c.execute(f"""SELECT v.policy_name nm, COUNT(*) n FROM policy_violations v JOIN policy_projects p ON p.id=v.project_id
                                 WHERE {pvis} GROUP BY v.policy_name ORDER BY n DESC LIMIT 8""", (viewer,)).fetchall()
        by_cat = c.execute(f"SELECT category c, COUNT(*) n FROM policies WHERE {_visible()} GROUP BY category", (viewer,)).fetchall()
    return {"by_decision": [dict(r) for r in by_decision], "top_policies": [dict(r) for r in by_policy],
            "by_category": [dict(r) for r in by_cat], **dashboard_stats(viewer)}
