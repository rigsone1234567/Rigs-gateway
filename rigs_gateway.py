#!/usr/bin/env python3
"""
RIGS GATEWAY v4.3 — The Final Ship
Unmocked: Connects to real AI APIs. 
Features: Hash-chained ledger, atomic rate limiting, XSS defense, chunked payload limits.
"""
import hashlib
import json
import os
import re
import time
import asyncio
import threading
import unicodedata
import secrets
import ipaddress
import httpx
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# Load environment variables securely from .env
load_dotenv()

# --- CONFIGURATION ---
RIGS_DIR = Path(__file__).parent / "rigs_gateway_data"
LEDGER = RIGS_DIR / "ledger.jsonl"
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 10
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change_me")
AI_API_URL = os.getenv("AI_API_URL", "https://openrouter.ai/api/v1/chat/completions")
AI_API_KEY = os.getenv("AI_API_KEY", "NO_KEY_FOUND")
AI_MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-r1:free")

RIGS_DIR.mkdir(exist_ok=True)
if not LEDGER.exists(): LEDGER.touch()

STATE = {"last_hash": "0" * 64, "head_index": -1, "client": None}
file_write_lock = threading.Lock()
ledger_async_lock = asyncio.Lock()

# --- 1. STRICT PAYLOAD LIMIT (Bypass-Proof) ---
class PayloadLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            body = b""
            async for chunk in request.stream():
                body += chunk
                if len(body) > 50000: # 50KB limit
                    return JSONResponse(status_code=413, content={"detail": "Payload Too Large"})
            request._body = body 
        return await call_next(request)

# --- 2. HARDENED SECURITY HEADERS ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        return response

# --- 3. FAIL-SAFE EXCEPTION HANDLER ---
async def global_exception_handler(request: Request, exc: Exception):
    err_msg = str(exc)[:200]
    try:
        await append_to_ledger("executor", "system_error", {"error": err_msg})
    except Exception:
        pass 
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# --- 4. THE SECURE HASH-CHAINED LEDGER ---
def _append_to_ledger_sync(event_json_string):
    with file_write_lock:
        with open(LEDGER, "a") as f:
            f.write(event_json_string)
            f.flush()
            os.fsync(f.fileno())

async def append_to_ledger(role, event_type, payload):
    async with ledger_async_lock:
        head = STATE["head_index"] + 1
        prev_hash = STATE["last_hash"]
        
        event = {
            "index": head, "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role, "event_type": event_type, "payload": payload, "prev_hash": prev_hash
        }
        
        canonical = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
        event["hash"] = hashlib.sha256(canonical).hexdigest()
        event_string = json.dumps(event, sort_keys=True) + "\n"
        
        await asyncio.to_thread(_append_to_ledger_sync, event_string)
        
        STATE["head_index"] = head
        STATE["last_hash"] = event["hash"]

def load_ledger_state():
    expected_prev = "0" * 64
    head = -1
    with open(LEDGER, "r") as f:
        for line in f:
            if not line.strip(): continue
            try: event = json.loads(line)
            except json.JSONDecodeError: continue 
            if event.get("prev_hash") != expected_prev:
                raise RuntimeError("Ledger tampered")
            check_event = dict(event)
            del check_event["hash"]
            canonical = json.dumps(check_event, sort_keys=True, separators=(",", ":")).encode()
            if event.get("hash") != hashlib.sha256(canonical).hexdigest():
                raise RuntimeError("Hash mismatch")
            expected_prev = event["hash"]
            head = event["index"]
    STATE["last_hash"] = expected_prev
    STATE["head_index"] = head

# --- 5. APP INITIALIZATION ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[RIGS] Verifying ledger integrity...")
    load_ledger_state()
    print(f"[RIGS] Ledger verified. Resuming at index {STATE['head_index']}.")
    STATE["client"] = httpx.AsyncClient(timeout=60.0)
    yield
    await STATE["client"].aclose()

# Docs disabled to prevent reconnaissance
app = FastAPI(title="RIGS Gateway", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(PayloadLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_exception_handler(Exception, global_exception_handler)

# --- 6. RATE LIMITER & GUARDRAILS ---
RATE_LIMITS = {}
rate_limit_lock = asyncio.Lock() 

async def check_rate_limit(client_ip: str, path: str):
    async with rate_limit_lock:
        current_time = time.time()
        key = f"{client_ip}:{path}"
        
        if len(RATE_LIMITS) > 10000: RATE_LIMITS.clear()
        if key not in RATE_LIMITS: RATE_LIMITS[key] = []
            
        RATE_LIMITS[key] = [t for t in RATE_LIMITS[key] if current_time - t < RATE_LIMIT_WINDOW]
        
        if len(RATE_LIMITS[key]) >= RATE_LIMIT_MAX:
            is_blocked = True
        else:
            RATE_LIMITS[key].append(current_time)
            is_blocked = False
            
    if is_blocked:
        await append_to_ledger("executor", "reject", {"reason": "rate_limit"})
        raise HTTPException(status_code=429, detail="Too Many Requests.")

HOMOGLYPHS = {'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x', 'і': 'i', 'ј': 'j', 'ѕ': 's', 'ԁ': 'd', 'ԛ': 'q', 'ԝ': 'w'}

def sanitize_prompt(text: str) -> str:
    for k, v in HOMOGLYPHS.items(): text = text.replace(k, v)
    normalized = unicodedata.normalize("NFKD", text).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^a-z0-9]', '', normalized.lower())

# --- 7. THE REAL AI CALL ---
async def call_real_ai(prompt: str):
    if AI_API_KEY == "NO_KEY_FOUND":
        raise HTTPException(status_code=500, detail="API Key missing. Check .env file.")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {AI_API_KEY}"}
    data = {"model": AI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
    
    try:
        response = await STATE["client"].post(AI_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        await append_to_ledger("executor", "action_failed", {"error": f"HTTP {e.response.status_code}"})
        raise HTTPException(status_code=502, detail="AI Provider Error")
    except Exception as e:
        await append_to_ledger("executor", "action_failed", {"error": str(e)})
        raise HTTPException(status_code=502, detail="AI Network Error")

# --- 8. API ENDPOINTS ---
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(..., min_length=1, max_length=10000)

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    if TRUST_PROXY:
        raw_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        try:
            ipaddress.ip_address(raw_ip)
            client_ip = raw_ip
        except ValueError:
            client_ip = request.client.host
    else:
        client_ip = request.client.host

    await check_rate_limit(client_ip, request.url.path)
    
    normalized_prompt = sanitize_prompt(req.prompt)
    sensitive_keywords = ["bypass", "password", "ssh", "privatekey", "rmrf", "hack"]
    
    if any(word in normalized_prompt for word in sensitive_keywords):
        await append_to_ledger("brain", "block", {"reason": "safety_guardrail", "prompt": req.prompt})
        raise HTTPException(status_code=403, detail="Blocked by RIGS safety guardrail.")
    
    await append_to_ledger("brain", "action_intent", {"prompt": req.prompt})
    ai_response = await call_real_ai(req.prompt)
    await append_to_ledger("executor", "action_performed", {"response": ai_response})
    
    return {"status": "success", "response": ai_response}

@app.get("/api/ledger")
async def get_ledger(limit: int = 20, request: Request = None):
    auth_header = request.headers.get("Authorization", "")
    expected_auth = f"Bearer {ADMIN_API_KEY}"
    if not secrets.compare_digest(auth_header, expected_auth):
        raise HTTPException(status_code=401, detail="Unauthorized")

    def _read():
        events = []
        with open(LEDGER, "r") as f:
            for line in f:
                if line.strip(): events.append(json.loads(line))
        return events[-limit:]
    events = await asyncio.to_thread(_read)
    return {"total_events": STATE["head_index"] + 1, "ledger": events}

# --- 9. THE WEB UI ---
@app.get("/", response_class=HTMLResponse)
async def index():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RIGS Gateway</title>
        <style>
            body { font-family: monospace; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: auto; }
            h1 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
            #chat-box { background: #161b22; border: 1px solid #30363d; padding: 15px; height: 300px; overflow-y: scroll; margin-bottom: 10px; border-radius: 6px; }
            .msg { margin-bottom: 10px; padding: 8px; border-radius: 4px; white-space: pre-wrap; }
            .user { background: #1f6feb; color: white; text-align: right; }
            .ai { background: #21262d; border-left: 3px solid #58a6ff; }
            .blocked { background: #ff7b72; color: #0d1117; font-weight: bold; }
            input[type="text"], input[type="password"] { width: 100%; padding: 12px; background: #0d1117; border: 1px solid #30363d; color: white; border-radius: 6px; box-sizing: border-box; }
            button { margin-top: 10px; padding: 10px 20px; background: #238636; color: white; border: none; border-radius: 6px; cursor: pointer; width: 100%; font-weight: bold; }
            #ledger { background: #161b22; border: 1px solid #30363d; padding: 15px; margin-top: 20px; border-radius: 6px; font-size: 0.8em; max-height: 200px; overflow-y: scroll; }
            .hash { color: #7ee787; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ RIGS Gateway v4.3</h1>
            <div id="chat-box"></div>
            <input type="text" id="prompt" placeholder="Type a message... (Try 'pаssword' with a Cyrillic 'а')" onkeypress="if(event.key === 'Enter') sendMessage()">
            <button onclick="sendMessage()">Send</button>
            
            <h2>⛓️ Cryptographic Ledger (Admin Only)</h2>
            <input type="password" id="adminKey" placeholder="Enter Admin API Key" style="margin-bottom:10px;">
            <div id="ledger">Waiting for authorization...</div>
        </div>

        <script>
            const chatBox = document.getElementById('chat-box');

            function appendMessage(className, text) {
                const div = document.createElement('div');
                div.className = 'msg ' + className;
                div.textContent = text; 
                chatBox.appendChild(div);
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            async function sendMessage() {
                const input = document.getElementById('prompt');
                const prompt = input.value.trim();
                if (!prompt) return;
                
                appendMessage('user', prompt);
                input.value = '';

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({prompt: prompt})
                    });
                    const data = await res.json();
                    
                    if (res.ok) appendMessage('ai', data.response);
                    else appendMessage('blocked', data.detail);
                } catch (e) {
                    appendMessage('blocked', 'Network Error');
                }
                fetchLedger();
            }

            async function fetchLedger() {
                const key = document.getElementById('adminKey').value;
                if (!key) return;

                const res = await fetch('/api/ledger', {
                    headers: {'Authorization': 'Bearer ' + key}
                });
                
                if (!res.ok) {
                    document.getElementById('ledger').textContent = "Unauthorized.";
                    return;
                }

                const data = await res.json();
                const ledgerDiv = document.getElementById('ledger');
                ledgerDiv.innerHTML = data.ledger.reverse().map(ev => `
                    <div>
                        <span style="color:#8b949e">[${ev.index}]</span> 
                        <b>${ev.role}</b> -> ${ev.event_type} <br>
                        <span class="hash">Hash: ${ev.hash.substring(0, 16)}...</span>
                    </div>
                `).join('<hr style="border-color:#30363d">');
            }

            setInterval(fetchLedger, 3000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

if __name__ == "__main__":
    import uvicorn
    # Fail-safe against multi-worker desync
    if os.environ.get("UVICORN_WORKERS", "1") != "1":
        print("FATAL: RIGS Gateway requires a single worker to maintain state integrity.")
        exit(1)
        
    uvicorn.run(app, host="0.0.0.0", port=8000)
