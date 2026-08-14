---
title: AXI4 Stream FIFO Controller Specification
version: "2.1"
authority: "authoritative"
customer_tier: "internal_engineering"
doc_id: "SPEC-AXI4-FIFO-002"
---

# AXI4 Stream FIFO Controller Specification

## Section 4.1 Flow Control & Backpressure (Requirement: AXI-BP-002)
- **ID**: `AXI-BP-002`
- **Scope**: AXI Stream Arbiter & FIFO Buffer
- **Description**: The FIFO controller must handle backpressure (`tready` deasserted) gracefully without dropping or corrupting any in-flight beats. When `tready` is toggled with randomized duty cycle (10% to 90% asserted), all packets must transfer correctly in FIFO order.
- **Verification Criteria**:
  1. Generate randomized backpressure sequence with variable `tready` latency.
  2. Verify scoreboard packet integrity under sustained backpressure.
