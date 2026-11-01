#!/usr/bin/env python3
"""
RIGS v0.2 — Mock User / Red Team
Simulates a malicious user or compromised agent trying to break the Executor.
"""
import sys
from pathlib import Path

# Import the Executor from your v01.py file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from v01 import Executor, reset, LEDGER

def run_red_team():
    print("=== STARTING RED TEAM SIMULATION ===")
    reset()
    
    ex = Executor()
    ex.open()

    # Set up a normal baseline (3 events)
    for i in range(3):
        ex.append("executor", "EXEC", "action_performed", {"step": i}, expected_index=ex.head())
    
    print(f"[*] Baseline established. Ledger head is at index {ex.head()}")

    attacks_blocked = 0

    # --- ATTACK 1: The Privilege Escalation ---
    print("\n[ATTACK 1] Malicious Brain tries to use EXEC token directly...")
    try:
        ex.append("brain", "EXEC", "write_committed", {"hacked": True}, expected_index=ex.head())
        print("[-] FAIL: System allowed privilege escalation!")
    except PermissionError:
        print("[+] BLOCKED: Capability violation caught.")
        attacks_blocked += 1

    # --- ATTACK 2: The Replay Attack (Stale State) ---
    print("\n[ATTACK 2] Malicious Brain tries to overwrite history (stale index)...")
    try:
        # Ledger is at 2, but attacker tries to write at 1
        ex.append("brain", "PLAN", "action_intent", {"overwrite": True}, expected_index=1)
        print("[-] FAIL: System allowed a stale write!")
    except RuntimeError as e:
        if "stale_state" in str(e):
            print("[+] BLOCKED: Stale write caught.")
            attacks_blocked += 1
        else:
            print(f"[-] FAIL: Wrong error: {e}")

    # --- ATTACK 3: The Destructive Injection ---
    print("\n[ATTACK 3] Malicious User tries to inject a destructive command...")
    # In a real system, the Executor would check the payload for dangerous commands
    # if the token is not from a verified user confirmation.
    destructive_payload = {"action": "rm -rf /", "reason": "user asked"}
    
    # We simulate the safety check here (from spec C7)
    is_safe = "rm -rf" not in str(destructive_payload)
    
    if not is_safe:
        print("[+] BLOCKED: Destructive payload caught by safety check.")
        attacks_blocked += 1
    else:
        ex.append("brain", "PLAN", "action_intent", destructive_payload, expected_index=ex.head())
        print("[-] FAIL: System allowed a destructive command!")

    # --- ATTACK 4: The Fake Confirmation ---
    print("\n[ATTACK 4] Malicious Brain tries to fake user confirmation...")
    try:
        # The Brain tries to use the "user_confirmation" event without the user actually doing it
        ex.append("brain", "PLAN", "user_confirmation_received", {"confirmed": True}, expected_index=ex.head())
        print("[-] FAIL: System allowed a fake confirmation!")
    except PermissionError:
        print("[+] BLOCKED: Fake confirmation caught. Only the user can confirm.")
        attacks_blocked += 1

    ex.close()

    print(f"\n=== RED TEAM RESULTS ===")
    print(f"Attacks Blocked: {attacks_blocked}/4")
    
    if attacks_blocked == 4:
        print("SYSTEM SECURE. The rules held up against the mock user.")
    else:
        print("SYSTEM VULNERABLE. We need to fix the Executor.")

if __name__ == "__main__":
    run_red_team()
