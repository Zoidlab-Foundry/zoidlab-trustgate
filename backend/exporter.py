"""Nyquest Policy Package exporter."""


def to_package(project, policies, tests=None):
    return {
        "schema_version": "1.0",
        "package_type": "nyquest_policy_package",
        "project": {"name": (project or {}).get("name"), "description": (project or {}).get("description"),
                    "risk_level": (project or {}).get("risk_level")},
        "policies": [{
            "name": p["name"], "category": p.get("category"), "status": p.get("status"),
            "risk_level": p.get("risk_level"), "enforcement_mode": p.get("enforcement_mode"),
            "version": p.get("version"), "applies_to": p.get("applies_to") or {},
            "rules": p.get("rules") or [],
        } for p in policies],
        "governance": {
            "enforcement_modes": ["monitor", "warn", "require_approval", "block"],
            "audit_logging": True,
        },
        "test_cases": tests or [],
    }


def to_yaml(pkg):
    def emit(v, ind=0):
        pad = "  " * ind
        if isinstance(v, dict):
            out = []
            for k, val in v.items():
                if isinstance(val, (dict, list)) and val:
                    out.append(f"{pad}{k}:")
                    out.append(emit(val, ind + 1))
                else:
                    out.append(f"{pad}{k}: {_scalar(val)}")
            return "\n".join(out)
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, (dict, list)):
                    out.append(f"{pad}-")
                    out.append(emit(item, ind + 1))
                else:
                    out.append(f"{pad}- {_scalar(item)}")
            return "\n".join(out)
        return f"{pad}{_scalar(v)}"

    def _scalar(v):
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        s = str(v)
        return f'"{s}"' if (":" in s or "#" in s) else s

    return emit(pkg) + "\n"
