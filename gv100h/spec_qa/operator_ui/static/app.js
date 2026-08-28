const $ = (id) => document.getElementById(id);

function badges(citation) {
  const items = [];
  if (citation.section) items.push(`section ${citation.section}`);
  if (citation.authority_level) items.push(citation.authority_level);
  if (citation.document) items.push(citation.document);
  if (citation.revision) items.push(`rev ${citation.revision}`);
  if (citation.citation_kind) items.push(citation.citation_kind);
  return items.map((text) => `<span class="badge">${text}</span>`).join("");
}

function renderCitations(citations) {
  if (!citations.length) {
    $("citations").innerHTML = "<p class=\"muted\">No citations.</p>";
    return;
  }
  $("citations").innerHTML = citations.map((citation) => {
    const hrefNote = citation.has_pdf_anchor && citation.pdf_href
      ? `<a href="${citation.pdf_href}">PDF anchor</a>`
      : `<span class="muted">No PDF anchor (not fabricated)</span>`;
    return `<article class="citation">
      <div>${badges(citation)}</div>
      <p><code>${citation.evidence_id}</code></p>
      <p>${citation.excerpt || ""}</p>
      <p>${hrefNote}</p>
    </article>`;
  }).join("");
}

function render(view) {
  const status = view.status || "unknown";
  $("statusRow").className = `status ${status}`;
  $("statusRow").textContent = status;
  const explainer = $("explainer");
  if (status === "abstain" || status === "conflict") {
    explainer.hidden = false;
    explainer.textContent = view.boundary_reason || "系統不是不知道答案，而是目前證據不足以在治理規則下回答。";
  } else {
    explainer.hidden = true;
  }
  $("answerText").textContent = view.answer || "—";
  $("scopeText").textContent = view.scope || "—";
  $("claims").innerHTML = (view.claims || []).map((claim) => `<li>${claim}</li>`).join("") || "<li class=\"muted\">none</li>";
  renderCitations(view.citations || []);
  $("boundaryCode").textContent = view.boundary_code || "none";
  $("boundaryReason").textContent = view.boundary_reason || view.boundary || "—";
}

$("askBtn").addEventListener("click", async () => {
  const allowedRaw = $("allowedScopes").value.trim();
  const body = {
    question: $("question").value,
    answer_scope: $("answerScope").value,
    retrieval_mode: $("retrievalMode").value,
    allowed_evidence_scopes: allowedRaw ? allowedRaw.split(",").map((s) => s.trim()).filter(Boolean) : null,
    source: $("source").value,
    fixture: $("fixture").value,
  };
  const resp = await fetch("/api/qa", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) {
    $("statusRow").className = "status conflict";
    $("statusRow").textContent = "error";
    $("answerText").textContent = data.error || "request failed";
    return;
  }
  render(data);
});
