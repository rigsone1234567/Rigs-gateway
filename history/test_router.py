#!/usr/bin/env python3
"""Tests for router.py. Mocks HTTP; no network, no pytest."""
import json, sys, tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import router as R

ENDPOINTS = """
endpoints:
  - {name: local_7b, base_url: "http://localhost:11434/v1", model: llama3.1:8b,
     api_key_env: null, sensitivity: local_only, max_context: 8192, rate_limit: null}
  - {name: external_a, base_url: "https://example.invalid/v1", model: foo,
     api_key_env: null, sensitivity: external, max_context: 32768,
     rate_limit: {requests_per_minute: 5}}
"""

ROUTES = """
routes:
  trivial: [local_7b]
  default: [local_7b]
  hard:    [external_a, local_7b]
"""

def setup():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "endpoints.yaml").write_text(ENDPOINTS)
    (tmp / "routes.yaml").write_text(ROUTES)
    R.ENDPOINTS_FILE = tmp / "endpoints.yaml"
    R.ROUTES_FILE    = tmp / "routes.yaml"
    R.EVENTS_FILE    = tmp / "events.jsonl"
    return tmp

def t_sensitivity_local():
    assert R.classify_sensitivity("my ssh key is abc") == "local_only"

def t_sensitivity_external():
    assert R.classify_sensitivity("what is 2+2") == "external_ok"

def t_route_trivial():
    tmp = setup(); eps, routes = R.load_config()
    router = R.Router(eps, routes, R.EventLog(tmp / "events.jsonl"))
    sens, _, viable = router.choose("trivial", "hi")
    assert sens == "external_ok" and viable == ["local_7b"]

def t_route_hard():
    tmp = setup(); eps, routes = R.load_config()
    router = R.Router(eps, routes, R.EventLog(tmp / "events.jsonl"))
    _, _, viable = router.choose("hard", "solve this")
    assert viable == ["external_a", "local_7b"]

def t_sensitive_filters_local():
    tmp = setup(); eps, routes = R.load_config()
    router = R.Router(eps, routes, R.EventLog(tmp / "events.jsonl"))
    sens, _, viable = router.choose("hard", "my api key is xyz")
    assert sens == "local_only" and viable == ["local_7b"]

def t_fallback_chain():
    tmp = setup(); eps, routes = R.load_config()
    router = R.Router(eps, routes, R.EventLog(tmp / "events.jsonl"))
    def fake(ep, messages, **kw):
        if ep.name == "external_a": raise RuntimeError("down")
        return "local answer"
    with mock.patch.object(R, "call_endpoint", side_effect=fake):
        r = router.ask("solve this", "hard")
    assert r["endpoint"] == "local_7b" and r["answer"] == "local answer"

def t_all_down():
    tmp = setup(); eps, routes = R.load_config()
    router = R.Router(eps, routes, R.EventLog(tmp / "events.jsonl"))
    with mock.patch.object(R, "call_endpoint", side_effect=RuntimeError("down")):
        try:
            router.ask("solve this", "hard"); assert False, "expected RuntimeError"
        except RuntimeError: pass

def t_event_logging():
    tmp = setup(); eps, routes = R.load_config()
    log = R.EventLog(tmp / "events.jsonl")
    router = R.Router(eps, routes, log)
    with mock.patch.object(R, "call_endpoint", return_value="ok"):
        router.ask("hi", "trivial")
    lines = (tmp / "events.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1, f"got {len(lines)} events"
    ev = json.loads(lines[0])
    assert ev["event_type"] == "route" and ev["chosen"] == "local_7b" and ev["success"] is True

TESTS = [
    ("sensitivity_local",      t_sensitivity_local),
    ("sensitivity_external",   t_sensitivity_external),
    ("route_trivial",          t_route_trivial),
    ("route_hard",             t_route_hard),
    ("sensitive_filters_local",t_sensitive_filters_local),
    ("fallback_chain",         t_fallback_chain),
    ("all_down",               t_all_down),
    ("event_logging",          t_event_logging),
]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            fn(); print(f"PASS {name}")
        except AssertionError as e:
            print(f"FAIL {name}: {e}"); fails += 1
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}"); fails += 1
    print(f"\n{len(TESTS)-fails} passed, {fails} failed")
    sys.exit(0 if fails == 0 else 1)
