#!/usr/bin/env python3
"""RIGS v0.1 — Skeleton (spec §11). Tests §10.1, §10.2, §10.3."""
import json, os, sys, fcntl, shutil
from datetime import datetime, timezone
from pathlib import Path

RIGS_DIR = Path(__file__).parent / "rigs_data"
LEDGER   = RIGS_DIR / "ledger.jsonl"
LOCK     = RIGS_DIR / "ledger.lock"

CAPABILITIES = {
    "PLAN":        {"candidate_request", "action_intent", "write_intent"},
    "EXEC":        {"action_performed", "action_failed", "write_committed"},
    "GENERATE":    {"candidate_supplied"},
    "READ":        {"recall_query"},
    "COMPRESS":    {"compaction_intent"},
    "EMIT_INTENT": {"write_intent", "compaction_intent"},
}
ROLE_TOKENS = {
    "brain":    {"PLAN", "READ", "EMIT_INTENT"},
    "neuron":   {"GENERATE"},
    "executor": {"EXEC"},
    "memory":   {"READ", "COMPRESS", "EMIT_INTENT"},
}

class Executor:
    def __init__(self):
        RIGS_DIR.mkdir(exist_ok=True)
        if not LEDGER.exists(): LEDGER.touch()
        self._lock = None
        self._fh   = None

    def open(self):
        self._lock = open(LOCK, "a")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock.close(); self._lock = None
            raise RuntimeError("executor_already_running")
        self._fh = open(LEDGER, "a")

    def close(self):
        if self._fh: self._fh.close(); self._fh = None
        if self._lock:
            fcntl.flock(self._lock, fcntl.LOCK_UN)
            self._lock.close(); self._lock = None

    def head(self):
        last = -1
        with open(LEDGER) as f:
            for line in f:
                if line.strip(): last = json.loads(line)["index"]
        return last

    def append(self, role, token, intent_type, payload, expected_index):
        if token not in ROLE_TOKENS.get(role, set()):
            self._reject(role, token, "capability_violation", intent_type)
            raise PermissionError(f"capability_violation: role={role} token={token}")
        if intent_type not in CAPABILITIES[token]:
            self._reject(role, token, "intent_type_forbidden", intent_type)
            raise PermissionError(f"intent_type_forbidden: {token}/{intent_type}")
        head = self.head()
        if expected_index != head:
            self._reject(role, token, "stale_state",
                         {"expected": expected_index, "head": head})
            raise RuntimeError(f"stale_state: expected={expected_index} head={head}")
        new_index = head + 1
        event = {"index": new_index,
                 "timestamp": datetime.now(timezone.utc).isoformat(),
                 "role": role, "capability_token": token,
                 "event_type": intent_type, "parent_index": head,
                 "payload": payload}
        self._fh.write(json.dumps(event, sort_keys=True) + "\n")
        self._fh.flush(); os.fsync(self._fh.fileno())
        return new_index

    def _reject(self, role, token, reason, detail):
        print(f"[REJECT] role={role} token={token} reason={reason} detail={detail}",
              file=sys.stderr)

    def read_at(self, index=None):
        if index is None: index = self.head()
        events = []
        with open(LEDGER) as f:
            for line in f:
                if not line.strip(): continue
                e = json.loads(line)
                if e["index"] <= index: events.append(e)
                else: break
        return {"head": index, "events": events}

def reset():
    if RIGS_DIR.exists(): shutil.rmtree(RIGS_DIR)

def test_10_1_capability():
    reset(); ex = Executor(); ex.open()
    try:
        try:
            ex.append("brain", "EXEC", "write_committed", {}, expected_index=ex.head())
            assert False, "expected PermissionError"
        except PermissionError: pass
        assert ex.head() == -1
    finally: ex.close()
    print("PASS 10.1 capability")

def test_10_2_single_writer():
    reset(); ex1 = Executor(); ex1.open()
    try:
        ex2 = Executor()
        try:
            ex2.open(); assert False, "expected second open to fail"
        except RuntimeError as e:
            assert "executor_already_running" in str(e)
    finally: ex1.close()
    print("PASS 10.2 single_writer")

def test_10_3_stale_state():
    reset(); ex = Executor(); ex.open()
    try:
        for i in range(4):
            ex.append("executor", "EXEC", "action_performed",
                      {"i": i}, expected_index=ex.head())
        assert ex.read_at(3)["head"] == 3
        ex.append("executor", "EXEC", "action_performed",
                  {"i": 4}, expected_index=3)
        try:
            ex.append("brain", "PLAN", "action_intent",
                      {"stale": True}, expected_index=3)
            assert False, "expected stale_state"
        except RuntimeError as e:
            assert "stale_state" in str(e)
        assert ex.head() == 4
    finally: ex.close()
    print("PASS 10.3 stale_state")

if __name__ == "__main__":
    print("RIGS v0.1 — acceptance tests §10.1–10.3")
    test_10_1_capability()
    test_10_2_single_writer()
    test_10_3_stale_state()
    print("\nALL PASS. v0.1 gate satisfied (spec §11).")
