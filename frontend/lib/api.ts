async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { detail = (await r.json()).detail || detail; } catch {}
    const e = new Error(detail) as Error & { status?: number }; e.status = r.status; throw e;
  }
  return r.json();
}
const qs = (q: Record<string, string>) => { const s = new URLSearchParams(Object.entries(q).filter(([, v]) => v)).toString(); return s ? "?" + s : ""; };

export const api = {
  entitlements: () => req<any>("/api/auth/entitlements"),
  stats: () => req<any>("/api/stats"),
  meta: () => req<{ categories: string[]; enforcement_modes: string[]; rule_types: string[]; data_classifications: string[] }>("/api/meta"),
  analytics: () => req<any>("/api/analytics"),

  projects: () => req<{ projects: any[] }>("/api/projects").then((d) => d.projects),
  project: (id: string) => req<any>(`/api/projects/${id}`),
  createProject: (b: any) => req<any>("/api/projects", { method: "POST", body: JSON.stringify(b) }),

  policies: (q: Record<string, string> = {}) => req<{ policies: any[] }>(`/api/policies${qs(q)}`).then((d) => d.policies),
  policy: (id: string) => req<any>(`/api/policies/${id}`),
  createPolicy: (b: any) => req<any>("/api/policies", { method: "POST", body: JSON.stringify(b) }),
  updatePolicy: (id: string, b: any) => req<any>(`/api/policies/${id}`, { method: "PUT", body: JSON.stringify(b) }),
  snapshotPolicy: (id: string, changelog: string) => req<any>(`/api/policies/${id}/versions`, { method: "POST", body: JSON.stringify({ changelog }) }),

  test: (b: any) => req<any>("/api/test", { method: "POST", body: JSON.stringify(b) }),
  violations: (q: Record<string, string> = {}) => req<{ violations: any[] }>(`/api/violations${qs(q)}`).then((d) => d.violations),
  approvals: (q: Record<string, string> = {}) => req<{ approvals: any[] }>(`/api/approvals${qs(q)}`).then((d) => d.approvals),
  approve: (id: string, notes = "") => req<any>(`/api/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ notes }) }),
  reject: (id: string, notes = "") => req<any>(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ notes }) }),

  exportJsonUrl: (projectId?: string) => `/api/export/json${projectId ? "?project_id=" + projectId : ""}`,
  exportYamlUrl: (projectId?: string) => `/api/export/yaml${projectId ? "?project_id=" + projectId : ""}`,
};
