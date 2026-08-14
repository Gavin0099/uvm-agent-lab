---
title: USB 3.2 Gen2 Link Layer Specification
version: "1.0"
authority: "authoritative"
customer_tier: "tier_1_partner"
doc_id: "SPEC-USB3-LNK-001"
---

# USB 3.2 Link Layer & Reset Control Specification

## Section 6.4 Link Power Management & Reset

### 6.4.1 Cold Reset
Upon power-on reset, all registers must initialize to their default power-on values.

### 6.4.2 Warm Reset (Requirement: USB3-WR-001)
- **ID**: `USB3-WR-001`
- **Scope**: Physical & Link Layer Controller
- **Description**: Upon assertion of Warm Reset (`warm_reset_n` low for at least 10 clock cycles), the Port Configuration State Machine must transition from state `U0` to `Rx.Detect` within 12 clock cycles without modifying sticky register configurations (e.g. `cfg_port_id` and `link_speed_cap`).
- **Verification Criteria**:
  1. Trigger warm reset sequence via UVM sequence.
  2. Sample state transition from `U0` to `Rx.Detect`.
  3. Verify sticky registers retain prior programmed values.
