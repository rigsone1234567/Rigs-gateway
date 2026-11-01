#!/usr/bin/env python3
"""
RIGS v0.3 — Safety Guardrails (Historical Prototype)
Adds a sensitivity classifier to the Brain before sending to the Executor.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v01 import Executor, reset

SENSITIVE_PATTERNS = [
    "ssh", "private key", "password", "passwd", "api key", "apikey",
    "secret", "token", "credential", "-----begin", "/etc/shadow",
    "id_rsa", "id_ed25519", ".env", "wallet", "seed phrase",
    "social security", "ssn", "credit card", "bank account", "bypass"
]

def classify_sensitivity(text: str) -> str:
    t = text.lower()
    return "local_only" if any(p in t for p in SENSITIVE_PATTERNS) else "external_ok"

class Neuron:
    def __init__(self):
        self.model = "mock-llama-3"

    def generate(self, prompt: str):
        time.sleep(0.2)
        return [
            {"id": "A", "text": f"Fast answer to: {prompt}"},
            {"id": "B", "text": f"Careful, verified answer to: {prompt}"}
        ]

class Brain:
    def __init__(self, executor: Executor, neuron: Neuron):
        self.ex = executor
        self.neuron = neuron

    def process(self, user_prompt: str):
        print(f"\n[USER] {user_prompt}")
        
        sensitivity = classify_sensitivity(user_prompt)
        if sensitivity == "local_only":
            print(f"[BRAIN] ⚠️ BLOCKED: Prompt flagged as sensitive ({sensitivity}).")
            current_head = self.ex.head()
            self.ex.append(
                role="brain", token="PLAN", intent_type="action_intent",
                payload={"action": "blocked_prompt", "reason": "sensitive_data_detected", "original_prompt": user_prompt},
                expected_index=current_head
            )
            return 

        print("[BRAIN] Prompt is safe. Asking Neuron for candidates...")
        candidates = self.neuron.generate(user_prompt)
        chosen = candidates[1]
        print(f"[BRAIN] Chose Candidate {chosen['id']}: {chosen['text']}")
        
        current_head = self.ex.head()
        self.ex.append(
            role="brain", token="PLAN", intent_type="action_intent",
            payload={"chosen": chosen, "original_prompt": user_prompt},
            expected_index=current_head
        )

if __name__ == "__main__":
    print("=== RIGS v0.3 (Prototype) ===")
    reset()
    ex = Executor(); ex.open()
    brain = Brain(ex, Neuron())
    brain.process("What is the capital of France?")
    brain.process("How do I bypass an ssh password?")
    ex.close()
