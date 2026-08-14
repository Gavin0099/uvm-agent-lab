// uvm-agent-lab — Interactive Dashboard Logic

const BENCHMARK_CASES = [
  { id: "UVM-001", type: "create_testcase", req: "USB3-WR-001", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-002", type: "modify_sequence", req: "AXI-BP-002", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-003", type: "fix_compile_error", req: "USB3-WR-001", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-004", type: "debug_simulation", req: "AXI-BP-002", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-005", type: "coverage_closure", req: "USB3-WR-001", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-006", type: "uvm_ral_model", req: "USB3-WR-001", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-007", type: "sva_assertions", req: "AXI-BP-002", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-008", type: "constrained_random", req: "AXI-BP-002", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-009", type: "error_injection", req: "USB3-WR-001", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
  { id: "UVM-010", type: "multi_agent_arb", req: "AXI-BP-002", comp: "pass", sim: "pass", evid: 100.0, gov: "PASS", score: 100.0 },
];

document.addEventListener("DOMContentLoaded", () => {
  renderBenchmarkTable();
  setupNavigationTabs();
});

function renderBenchmarkTable() {
  const tbody = document.getElementById("benchmarkTableBody");
  if (!tbody) return;

  tbody.innerHTML = BENCHMARK_CASES.map(c => `
    <tr>
      <td><span class="code-badge">${c.id}</span></td>
      <td>${c.type}</td>
      <td><span class="code-badge" style="color: #60a5fa;">${c.req}</span></td>
      <td><span class="badge-pill badge-pass">${c.comp}</span></td>
      <td><span class="badge-pill badge-pass">${c.sim}</span></td>
      <td>${c.evid.toFixed(1)}%</td>
      <td><span class="badge-pill badge-pass">${c.gov}</span></td>
      <td><strong>${c.score.toFixed(1)}</strong></td>
      <td><span class="badge-pill badge-pass">PASSED</span></td>
    </tr>
  `).join("");
}

function setupNavigationTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");

      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => {
        p.style.display = "none";
        p.classList.remove("active");
      });

      btn.classList.add("active");
      const activePane = document.getElementById(`pane-${targetTab}`);
      if (activePane) {
        activePane.style.display = "block";
        activePane.classList.add("active");
      }
    });
  });
}
