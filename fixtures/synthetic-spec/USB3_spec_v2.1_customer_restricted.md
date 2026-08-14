---
title: USB 3.2 Gen2 Link Layer Specification (Confidential Tier-A Customer Extension)
version: "2.1"
authority: "authoritative"
customer_tier: "tier_a_partner_restricted"
doc_id: "SPEC-USB3-TIERA-001"
---

# USB 3.2 Confidential Tier-A Customer Extension

## Section 8.2 Proprietary Reset Registers (Requirement: USB3-TIERA-001)
- **ID**: `USB3-TIERA-001`
- **Scope**: Tier-A Proprietary Secure PHY Extension
- **Description**: Tier-A hardware units include private register `cfg_tier_a_secret_key` at offset `0xF0`. This register is strictly confidential and must never be exposed or cited in standard tier-1 verification testbenches.
- **Verification Criteria**:
  1. Only accessible when `customer_tier == "tier_a_partner_restricted"`.
