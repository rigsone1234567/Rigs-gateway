#!/usr/bin/env python3
"""RIGS v0.1 — Charter validator. Tests: charter integrity §10.12."""
import json, re, sys, hashlib, tempfile, os
from pathlib import Path
import yaml

REQUIRED_TOP  = {"charter_version", "entity_id", "created", "rules", "preferences"}
REQUIRED_RULE = {"id", "text", "scope", "compression_safe"}
VALID_SCOPES  = {"absolute", "scoped", "weighted"}

class CharterError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code; self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)

def _hash_event(ev):
    canon = json.dumps(ev, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canon).hexdigest()

def parse_charter(path):
    text = Path(path).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m: raise CharterError("missing_frontmatter")
    head = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    missing = REQUIRED_TOP - head.keys()
    if missing: raise CharterError("missing_field", f"top: {sorted(missing)}")
    ids = set()
    for r in head["rules"]:
        miss = REQUIRED_RULE - set(r or {})
        if miss: raise CharterError("missing_field", f"rule {r.get('id')}: {sorted(miss)}")
        if r["scope"] not in VALID_SCOPES:
            raise CharterError("bad_scope", f"rule {r['id']}: {r['scope']}")
        if r["id"] in ids: raise CharterError("duplicate_id", r["id"])
        ids.add(r["id"])
    for p in head["preferences"]:
        w = (p or {}).get("weight", -1)
        if not isinstance(w, (int, float)) or not (0.0 <= w <= 1.0):
            raise CharterError("bad_weight", f"pref {p.get('id')}: {w}")
    if "## HISTORY" not in body:
        raise CharterError("missing_field", "body: ## HISTORY")
    raw = body.split("## HISTORY", 1)[1]
    hist = []
    for ln, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"): continue
        try: hist.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise CharterError("bad_history_json", f"line {ln}: {e.msg}")
    for e in hist:
        ref = e.get("references_rule")
        if ref and ref not in ids:
            raise CharterError("unknown_rule_ref", f"event {e.get('index')}: {ref}")
    return head, hist

def verify_chain(hist):
    for i, ev in enumerate(hist):
        if i == 0: continue
        if ev.get("prev_hash") != _hash_event(hist[i-1]):
            raise CharterError("chain_broken", f"event {ev.get('index')}")
    return True

GOOD = """---
charter_version: 1
entity_id: rigs
created: 2026-11-01T00:00:00Z
rules:
  - {id: R1, text: "Never write outside Executor", scope: absolute, compression_safe: false}
  - {id: R2, text: "Destructive actions need user confirm", scope: absolute, compression_safe: false}
preferences:
  - {id: P1, text: "prefer verifiable over fast", weight: 0.8}
  - {id: P2, text: "prefer reversible over optimal", weight: 0.6}
---

## RATIONALE
R1 protects C1. R2 protects C7.

## HISTORY
{"index":0,"event_type":"derogation","references_rule":"R1","justification":"ledger corruption"}
{"index":1,"event_type":"decision","references_rule":null,"chosen":"candidate_3"}
"""

CASES = [
    ("good", GOOD, None),
    ("missing_frontmatter", "no frontmatter\n## HISTORY\n", "missing_frontmatter"),
    ("missing_top", GOOD.replace("charter_version: 1\n", ""), "missing_field"),
    ("bad_scope", GOOD.replace("scope: absolute", "scope: maybe", 1), "bad_scope"),
    ("dup_id", GOOD.replace("id: R2", "id: R1"), "duplicate_id"),
    ("bad_weight", GOOD.replace("weight: 0.8", "weight: 1.8"), "bad_weight"),
    ("unknown_ref", GOOD.replace('"references_rule":"R1"', '"references_rule":"R9"'), "unknown_rule_ref"),
    ("bad_json", GOOD.replace('{"index":1', '{"index":1,,'), "bad_history_json"),
]

def run():
    passed = failed = 0
    for name, text, expect in CASES:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as f:
            f.write(text); path = f.name
        try:
            parse_charter(path); got = None
        except CharterError as e:
            got = e.code
        finally:
            os.unlink(path)
        ok = got == expect
        print(f"{'PASS' if ok else 'FAIL'}  {name:22s} expect={expect} got={got}")
        if ok: passed += 1
        else:  failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
