#!/usr/bin/env python3
"""
RIGS Monetization Engine
Automates the creation of funding configs, enterprise pages, and marketing copy.
"""
import os
from pathlib import Path

def create_funding_yml():
    """Creates the .github/FUNDING.yml to activate the GitHub Sponsor button."""
    github_dir = Path(".github")
    github_dir.mkdir(exist_ok=True)
    
    funding_file = github_dir / "FUNDING.yml"
    content = """# Enables the Sponsor button on GitHub
github: [rigsone1234567] 
# custom: ["https://your-website.com/donate"]
"""
    funding_file.write_text(content)
    print("[+] Created .github/FUNDING.yml (GitHub Sponsor button activated)")

def create_enterprise_md():
    """Creates an ENTERPRISE.md file for commercial users."""
    content = """# RIGS Gateway: Commercial & Enterprise

RIGS is open-source and free for personal and internal business use. 

However, if your organization requires **guaranteed SLAs, priority security patches, or a commercial license for embedded distribution**, we offer paid tiers.

### 🏢 Enterprise Offerings
1. **Integration & Setup:** We will deploy RIGS into your AWS/GCP environment and connect it to your internal LLM.
2. **Security Audits:** A deep-dive review of your AI agent's architecture using RIGS threat models.
3. **Custom Feature Development:** Need a specific compliance log format (e.g., SOC2, HIPAA)? We can build it.

### 📞 Contact
To discuss consulting or a commercial license, reach out at: **rigs.one@gmail.com**
"""
    Path("ENTERPRISE.md").write_text(content)
    print("[+] Created ENTERPRISE.md (Commercial funnel established)")

def generate_marketing_blast():
    """Outputs a copy-paste ready post for social media."""
    post = """
🚀 I just open-sourced RIGS Gateway: The Sovereign AI Runtime. 

Most AI wrappers blindly forward requests to OpenAI or DeepSeek. If an agent hallucinates a destructive command, or an attacker drains your API credits via botnets, you have no cryptographic proof of what happened.

I built RIGS to fix this. It's a zero-trust API gateway that acts as a firewall for your AI agents.

✨ Features:
🔒 Cryptographically auditable ledger (SHA-256)
🛡️ Zero-trust execution (Prompt injection defense)
⚡ Resilient rate-limiting (Stops API cost drains)
🐳 Docker-ready

Check out the code here: https://github.com/rigsone1234567/Rigs-gateway

If you're building with LLMs, I'd love your feedback. 

#AISecurity #Python #FastAPI #CyberSecurity #OpenSource
"""
    print("\n" + "="*50)
    print("📱 COPY THIS FOR TWITTER/LINKEDIN/REDDIT:")
    print("="*50)
    print(post)

if __name__ == "__main__":
    print("=== STARTING MONETIZATION ENGINE ===\n")
    create_funding_yml()
    create_enterprise_md()
    generate_marketing_blast()
    print("\n[SUCCESS] Files generated. Now commit them to GitHub!")
