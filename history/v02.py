#!/usr/bin/env python3
"""
RIGS v0.2 — Core Loop (Brain + Neuron + Executor)
Mocking the LLM intelligence, but building the real state machine.
"""
import sys
import time
from pathlib import Path

# Import the secure Executor we built in v01
sys.path.insert(0, str(Path(__file__).resolve().parent))
from v01 import Executor, reset

class Neuron:
    """The candidate generator. Mocked for phone testing."""
    def __init__(self):
        self.model = "mock-llama-3"

    def generate(self, prompt: str):
        # In a real system, this calls Ollama/Groq. Right now, it just fakes it.
        time.sleep(0.5) # Simulate network/GPU latency
        return [
            {"id": "A", "text": f"Fast answer to: {prompt}"},
            {"id": "B", "text": f"Careful, verified answer to: {prompt}"}
        ]

class Brain:
    """The planner and decider."""
    def __init__(self, executor: Executor, neuron: Neuron):
        self.ex = executor
        self.neuron = neuron

    def process(self, user_prompt: str):
        print(f"\n[USER] {user_prompt}")
        
        # 1. PERCEIVE -> Ask Neuron for candidates
        print("[BRAIN] Asking Neuron for candidates...")
        candidates = self.neuron.generate(user_prompt)
        
        # 2. PLAN -> Evaluate candidates
        # (Rule P1: Prefer verifiable over fast)
        print("[BRAIN] Evaluating candidates against Charter rules...")
        chosen = candidates[1] # We hardcode picking 'B' (verified)
        print(f"[BRAIN] Chose Candidate {chosen['id']}: {chosen['text']}")
        
        # 3. ACT -> Send intent to Executor
        # Notice the Brain uses the "PLAN" token, and type "action_intent"
        current_head = self.ex.head()
        self.ex.append(
            role="brain",
            token="PLAN",
            intent_type="action_intent",
            payload={"chosen": chosen, "original_prompt": user_prompt},
            expected_index=current_head
        )
        print(f"[BRAIN] Action committed to ledger at index {current_head + 1}")

        # 4. VERIFY -> Confirm it's in the ledger
        state = self.ex.read_at()
        last_event = state["events"][-1]
        if last_event["payload"]["chosen"]["id"] == chosen["id"]:
            print("[BRAIN] Verification successful. Loop complete.")
        else:
            print("[BRAIN] Verification FAILED!")

def run_system():
    print("=== STARTING RIGS v0.2 (CORE LOOP) ===")
    reset() # Wipe the old test data
    
    ex = Executor()
    ex.open()
    neuron = Neuron()
    brain = Brain(ex, neuron)

    try:
        # Run 3 iterations of the core loop
        brain.process("What is the capital of France?")
        brain.process("Write a script to delete temp files.")
        brain.process("How do I bypass an ssh password?")
    finally:
        ex.close()
        print("\n=== SYSTEM SHUTDOWN ===")

if __name__ == "__main__":
    run_system()
