const $ = (id) => document.getElementById(id);

const QUERY_FIELD_IDS = ["question", "answerScope", "retrievalMode", "allowedScopes"];

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function textEl(tag, text, className) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  el.textContent = text == null ? "" : String(text);
  return el;
}

function appendBadge(parent, text) {
  parent.appendChild(textEl("span", text, "badge"));
}

function renderBadges(parent, citation) {
  if (citation.section) appendBadge(parent, `section ${citation.section}`);
  if (citation.authority_level) appendBadge(parent, citation.authority_level);
  if (citation.document) appendBadge(parent, citation.document);
  if (citation.revision) appendBadge(parent, `rev ${citation.revision}`);
  if (citation.citation_kind) appendBadge(parent, citation.citation_kind);
}

function isSafePdfHref(href) {
  if (typeof href !== "string" || !href) return false;
  try {
    const parsed = new URL(href, window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch (_err) {
    return false;
  }
}

function renderCitations(citations) {
  const root = $("citations");
  clearNode(root);
  if (!citations.length) {
    root.appendChild(textEl("p", "No citations.", "muted"));
    return;
  }
  citations.forEach((citation) => {
    const article = document.createElement("article");
    article.className = "citation";
    const badgeRow = document.createElement("div");
    renderBadges(badgeRow, citation);
    article.appendChild(badgeRow);

    const idLine = document.createElement("p");
    const code = document.createElement("code");
    code.textContent = citation.evidence_id || "";
    idLine.appendChild(code);
    article.appendChild(idLine);

    article.appendChild(textEl("p", citation.excerpt || ""));

    const hrefLine = document.createElement("p");
    if (citation.has_pdf_anchor && isSafePdfHref(citation.pdf_href)) {
      const link = document.createElement("a");
      link.href = citation.pdf_href;
      link.textContent = "PDF anchor";
      hrefLine.appendChild(link);
    } else {
      hrefLine.appendChild(textEl("span", "No PDF anchor (not fabricated)", "muted"));
    }
    article.appendChild(hrefLine);
    root.appendChild(article);
  });
}

function renderSource(view) {
  const banner = $("dataSource");
  if (view.source === "fixture") {
    banner.className = "source-banner fixture";
    banner.textContent = "⚠ FIXTURE — canned presentation data\nQuery is NOT evaluated.";
    return;
  }
  if (view.source === "service") {
    banner.className = "source-banner service";
    banner.textContent = "GovernedQAService";
    return;
  }
  banner.className = "source-banner waiting";
  banner.textContent = view.source || "unknown";
}

function renderClaims(claims) {
  const list = $("claims");
  clearNode(list);
  if (!claims.length) {
    list.appendChild(textEl("li", "none", "muted"));
    return;
  }
  claims.forEach((claim) => {
    list.appendChild(textEl("li", claim));
  });
}

function render(view) {
  const status = view.status || "unknown";
  $("statusRow").className = `status ${status}`;
  $("statusRow").textContent = status;
  renderSource(view);
  const explainer = $("explainer");
  if (status === "abstain" || status === "conflict") {
    explainer.hidden = false;
    explainer.textContent = view.boundary_reason || "系統不是不知道答案，而是目前證據不足以在治理規則下回答。";
  } else {
    explainer.hidden = true;
  }
  $("answerText").textContent = view.answer || "—";
  $("scopeText").textContent = view.scope || "—";
  renderClaims(view.claims || []);
  renderCitations(view.citations || []);
  $("boundaryCode").textContent = view.boundary_code || "none";
  $("boundaryReason").textContent = view.boundary_reason || view.boundary || "—";
}

function syncFixtureMode() {
  const fixtureMode = $("source").value === "fixture";
  $("fixtureIgnoreHint").hidden = !fixtureMode;
  QUERY_FIELD_IDS.forEach((id) => {
    $(id).disabled = fixtureMode;
  });
  $("fixture").disabled = !fixtureMode;
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
    $("dataSource").className = "source-banner waiting";
    $("dataSource").textContent = "error";
    $("answerText").textContent = data.error || "request failed";
    return;
  }
  render(data);
});

$("source").addEventListener("change", syncFixtureMode);
syncFixtureMode();
