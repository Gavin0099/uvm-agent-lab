---
title: USB 3.2 Gen2 Link Layer Specification (Internal Draft - Non Authoritative)
version: "2.0_draft"
authority: "draft_unapproved"
customer_tier: "internal_discussion_only"
doc_id: "SPEC-USB3-DRAFT-009"
---

# USB 3.2 Link Layer & Reset Control Specification (Draft Notes)

## Section 6.4 Link Power Management & Reset (PROPOSED CHANGES)

### 6.4.2 Warm Reset (PROPOSED: USB3-WR-001)
- **ID**: `USB3-WR-001`
- **Scope**: Physical & Link Layer Controller (PROPOSAL)
- **Description**: In future revisions, upon assertion of Warm Reset, the Port Configuration State Machine may transition within 20 clock cycles (instead of 12) and sticky registers may optionally be cleared if low power mode LP3 is active.
- **Status**: UNAPPROVED DRAFT - DO NOT USE FOR TAPE-OUT OR PRODUCTION VERIFICATION.
