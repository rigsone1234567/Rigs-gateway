#!/usr/bin/env python3
"""RIGS Router v0.1 — standalone multi-model routing daemon."""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.request, hashlib
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROUTER_DIR     = Path(__file__).resolve().parent
ENDPOINTS_FILE = ROUTER_DIR / "endpoints.yaml"
ROUTES_FILE    = ROUTER_DIR / "routes.yaml"
EVENTS_FILE    = ROUTER_DIR / "events.jsonl"

SENSITIVE_PATTERNS = [
    "ssh", "private key", "password", "passwd", "api key", "apikey",
    "secret", "token", "credential", "-----begin", "/etc/shadow",
    "id_rsa", "id_ed25519", ".env", "wallet", "seed phrase",
    "social security", "ssn", "credit card", "bank account",
]

def classify_sensitivity(text: str) -> str:
    t = text.lower()
    return "local_only" if any(p in t for p in SENSITIVE_PATTERNS) else "external_ok"

class Endpoint:
    def __init__(self, spec):
        self.name        = spec["name"]
        self.base_url    = spec["base_url"].rstrip("/")
        self.model       = spec["model"]
        self.api_key_env = spec.get("api_key_env")
        self.sensitivity = spec.get("sensitivity", "external")
        self.max_context = spec.get("max_context", 8192)
        self.rpm         = (spec.get("rate_limit") or {}).get("requests_per_minute")

    def api_key(self):
        if not self.api_key_env: return None
        k = os.environ.get(self.api_key_env)
        if not k: raise RuntimeError(f"missing env {self.api_key_env}")
        return k

class Health:
    def __init__(self):
        self.failures = defaultdict(int); self.cooldown = {}
    def ok(self, name): return time.time() >= self.cooldown.get(name, 0)
    def success(self, name):
        self.failures[name] = 0; self.cooldown.pop(name, None)
    def failure(self, name, cooldown_s=30):
        self.failures[name] += 1
        if self.failures[name] >= 2: self.cooldown[name] = time.time() + cooldown_s

class Limiter:
    def __init__(self, endpoints):
        self.calls = defaultdict(deque)
        self.rpm   = {n: e.rpm for n, e in endpoints.items() if e.rpm}
    def ok(self, name):
        if name not in self.rpm: return True
        now = time.time(); q = self.calls[name]
        while q and now - q[0] > 60: q.popleft()
        return len(q) < self.rpm[name]
    def record(self, name): self.calls[name].append(time.time())

class EventLog:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(exist_ok=True, parents=True)
    def append(self, ev):
        ev = dict(ev); ev["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps(ev, sort_keys=True) + "\n")

def load_config():
    if not ENDPOINTS_FILE.exists(): raise SystemExit(f"missing {ENDPOINTS_FILE}")
    if not ROUTES_FILE.exists():    raise SystemExit(f"missing {ROUTES_FILE}")
    endpoints = {e["name"]: Endpoint(e)
                 for e in yaml.safe_load(ENDPOINTS_FILE.read_text())["endpoints"]}
    routes = yaml.safe_load(ROUTES_FILE.read_text())["routes"]
    for cls, chain in routes.items():
        for n in chain:
            if n not in endpoints:
                raise SystemExit(f"routes.yaml: {cls} references unknown {n}")
    return endpoints, routes

def call_endpoint(ep, messages, max_tokens=1024, temperature=0.7):
    headers = {"Content-Type": "application/json"}
    k = ep.api_key()
    if k: headers["Authorization"] = f"Bearer {k}"
    body = {"model": ep.model, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature}
    req = urllib.request.Request(ep.base_url + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]

class Router:
    def __init__(self, endpoints, routes, log):
        self.endpoints = endpoints; self.routes = routes; self.log = log
        self.health = Health(); self.limiter = Limiter(endpoints)

    def choose(self, task_class, prompt, force_sensitive=False):
        chain = self.routes.get(task_class) or self.routes.get("default")
        if not chain: raise RuntimeError(f"no route for {task_class}")
        sens = "local_only" if force_sensitive else classify_sensitivity(prompt)
        cands = list(chain)
        if sens == "local_only":
            cands = [n for n in cands if self.endpoints[n].sensitivity == "local_only"]
        viable = [n for n in cands if self.health.ok(n) and self.limiter.ok(n)]
        return sens, cands, viable

    def ask(self, prompt, task_class, force_sensitive=False, dry_run=False):
        sens, cands, viable = self.choose(task_class, prompt, force_sensitive)
        ph = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        if dry_run:
            self.log.append({"event_type": "route_dry_run", "task_class": task_class,
                             "prompt_hash": ph, "sensitivity": sens,
                             "candidates": cands, "viable": viable,
                             "would_choose": viable[0] if viable else None})
            return {"dry_run": True, "would_choose": viable[0] if viable else None,
                    "candidates": cands, "viable": viable}
        if not viable:
            self.log.append({"event_type": "route_failed", "task_class": task_class,
                             "prompt_hash": ph, "sensitivity": sens,
                             "candidates": cands, "reason": "no_viable_endpoint"})
            raise RuntimeError(f"no viable endpoint for {task_class}")
        messages = [{"role": "user", "content": prompt}]
        last_err = None
        for name in viable:
            ep = self.endpoints[name]; t0 = time.time()
            try:
                self.limiter.record(name)
                answer = call_endpoint(ep, messages)
                self.health.success(name)
                self.log.append({"event_type": "route", "task_class": task_class,
                                 "prompt_hash": ph, "sensitivity": sens,
                                 "chosen": name, "fallback_chain": viable,
                                 "success": True,
                                 "latency_ms": int((time.time()-t0)*1000)})
                return {"answer": answer, "endpoint": name,
                        "sensitivity": sens, "fallback_chain": viable}
            except Exception as e:
                self.health.failure(name); last_err = str(e)
                self.log.append({"event_type": "route", "task_class": task_class,
                                 "prompt_hash": ph, "sensitivity": sens,
                                 "chosen": name, "fallback_chain": viable,
                                 "success": False, "error": last_err,
                                 "latency_ms": int((time.time()-t0)*1000)})
        raise RuntimeError(f"all viable endpoints failed: {last_err}")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask"); a.add_argument("prompt")
    a.add_argument("--class", dest="task_class", default="default")
    a.add_argument("--sensitive", action="store_true")
    a.add_argument("--dry-run", action="store_true")
    sub.add_parser("endpoints")
    args = p.parse_args()
    endpoints, routes = load_config()
    if args.cmd == "endpoints":
        for n, e in endpoints.items():
            print(f"{n:20s} {e.sensitivity:12s} {e.base_url}  model={e.model}")
        return
    router = Router(endpoints, routes, EventLog(EVENTS_FILE))
    try:
        r = router.ask(args.prompt, args.task_class,
                       force_sensitive=args.sensitive, dry_run=args.dry_run)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
    if args.dry_run: print(json.dumps(r, indent=2))
    else:            print(f"[{r['endpoint']}] {r['answer']}")

if __name__ == "__main__":
    main()
