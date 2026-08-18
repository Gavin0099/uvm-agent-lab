# USB Hub Spec QA Agent — Deployment & Integration Specification

> **Target Repository**: `Gavin0099/usb-if-hub-spec-reference` (Repo B)  
> **Backend Integration**: `Gavin0099/uvm-agent-lab` (Repo A)  
> **Status**: Approved Specification for Independent Repo B PR

---

## 🛡️ 1. 安全隔離與部署架構 (Deployment Boundary)

```text
+─────────────────────────────────────────────────────────────+
| Public Browser / Client (VitePress Static Site)              |
+─────────────────────────────────────────────────────────────+
                              │
                  Same-Origin /api/qa POST
                              │
                              ▼
+─────────────────────────────────────────────────────────────+
| Same-Origin QA Backend / Proxy                               |
|   - Strips sensitive headers & controls rate limits         |
|   - NO public exposure of internal model IPs or API keys     |
+─────────────────────────────────────────────────────────────+
                              │
                   Internal Private Network
                              │
                              ▼
+─────────────────────────────────────────────────────────────+
| GV100H Model Gateway (http://internal-gv100:8000/v1)        |
+─────────────────────────────────────────────────────────────+
```

### 🔒 邊界硬規則 (Hard Deployment Rules)
1. **No API Keys in Frontend**: Public VitePress JS bundles must NEVER contain internal model endpoint IPs, tokens, or credentials.
2. **Read-Only Surface**: The QA Agent is strictly read-only and cannot mutate any repository files or records.
3. **Structured Citation UI**: Citations must be rendered as clickable badges linking to in-scope governed spec anchor tags.
4. **Abstain Presentation**: When evidence is missing or out-of-scope, the UI renders an amber warning badge stating that governed reference does not support the claim.
