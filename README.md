w# 🛡️ RIGS Gateway: The Sovereign AI Runtime

**RIGS** is an enterprise-grade, zero-trust API gateway designed for autonomous AI agents. It sits securely between your application and your LLM provider (OpenAI, DeepSeek, Ollama) to enforce strict state validation, protect against resource exhaustion, and maintain a cryptographically verifiable audit trail of all AI interactions.

Most AI wrappers blindly forward requests. RIGS treats every AI prompt as a potential threat vector.

## ✨ Key Capabilities

- **🔒 Cryptographically Auditable:** Every interaction and rejected request is recorded in a tamper-evident ledger.
- **🛡️ Zero-Trust Execution:** Advanced input sanitization and strict payload validation prevent prompt injections and data exfiltration attempts.
- **⚡ Resilient Rate Limiting:** Defends against concurrency attacks, IP spoofing, and resource exhaustion.
- **🔌 Provider Agnostic:** Drop-in compatibility with any OpenAI-compatible API.
- **🌐 Built-in Web UI:** Includes a secure, real-time dashboard for monitoring AI responses and verifying the integrity of the cryptographic ledger.

## 🚀 Quick Start (Local)

### 1. Clone & Install

    git clone https://github.com/rigsone1234567/Rigs-gateway.git
    cd Rigs-gateway
    pip install -r requirements.txt

### 2. Configure Environment

Create a `.env` file in the root directory and add your secure credentials:

    AI_API_KEY=your-provider-api-key
    AI_MODEL=deepseek/deepseek-r1:free
    AI_API_URL=https://openrouter.ai/api/v1/chat/completions
    ADMIN_API_KEY=your_secure_ui_password

### 3. Launch

    python3 rigs_gateway.py

Access the secure dashboard at `http://127.0.0.1:8000`. Enter your `ADMIN_API_KEY` to view the live ledger feed.

## 🐳 Deployment (Docker)

RIGS is container-ready for easy deployment to your own servers or cloud infrastructure.

    docker build -t rigs-gateway .
    docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/rigs_gateway_data rigs-gateway

## 🗺️ Future Roadmap

- [ ] **Multi-Model Consensus:** Routing requests across multiple models for verification.
- [ ] **Shadow Logging:** Advanced tracking of rejected context and alternative model thoughts.
- [ ] **Edge Integration:** Native optimization for local, hardware-accelerated deployments.

## 📜 License

This project is licensed under the MIT License.

---

## 💎 Need 99.9% Uptime? Get RIGS Gateway PRO

The Free version is great for hobbyists. But if you are building a production app, you need **RIGS PRO**.

**Premium Features:**
- **Multi-Model Fallback Routing:** Never go down if OpenAI/DeepSeek fails.
- **Security Webhook Alerts:** Get instant Discord/Slack notifications on attacks.
- **Priority Support.**

👉 **[Buy RIGS Gateway PRO for $29](https://rigsone.gumroad.com/l/rigs-pro)**
