const $ = (id) => document.getElementById(id);

const QUERY_FIELD_IDS = ["answerScope", "retrievalMode", "allowedScopes"];

const STATUS_LABEL = {
  answer: "已回答",
  missing_evidence: "證據不足",
  fictional_section: "虛構章節",
  authority_mismatch: "權威不符",
  out_of_scope: "超出目前範圍",
  conflict: "來源衝突",
  unknown: "等待中",
  error: "錯誤",
};

const EMPTY_ANSWER = "輸入 USB 規格問題後，這裡會顯示有依據的回答。";

const SERVICE_PLACEHOLDER = "下游埠可以在哪些 link state 發出 Warm Reset？";
const REAL_LOCAL_RAG_PLACEHOLDER = "USB 3.x 的 Warm Reset 在哪些 link state 發出？";

const FIXTURE_QUESTIONS = {
  answered: "USB 3.x Hub Class 的 PORT_POWER feature selector 值是多少？",
  abstain: "USB4 規格是否允許這個結論？",
  conflict: "PORT_POWER feature selector 的權威層級是什麼？",
};

const DISPLAY_ANSWER = {
  "Synthetic fixture answer: USB 3.x Hub Class PORT_POWER feature selector value is 8 (0x0008).":
    "USB 3.x Hub Class 的 PORT_POWER feature selector 值為 8（0x0008）。",
  "Synthetic fixture conflict: competing canned sources disagree on PORT_POWER authority.":
    "目前找到的 2 個模擬來源對 PORT_POWER 的權威層級不一致，因此暫不提供單一結論。",
  "現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論 (Abstain)。":
    "USB4 不在目前可查詢的 Phase 1 規格資料範圍內，因此系統不會根據未納入的規格內容推測答案。",
};

const DISPLAY_EXCERPT = {
  "Synthetic fixture: USB 3.x Hub Class PORT_POWER selector value is presented as 8 (0x0008).":
    "USB 3.x Hub Class 的 PORT_POWER feature selector 值為 8（0x0008）。",
  "Synthetic fixture: Phase 1 corpus does not include the USB4 specification.":
    "USB4 Specification 未包含於目前可查詢的 Phase 1 corpus。",
  "Synthetic fixture A treats PORT_POWER as an authoritative Hub Class selector value 8.":
    "PORT_POWER 被視為權威性的 Hub Class selector，值為 8。",
  "Synthetic fixture B treats PORT_POWER as informative-only.":
    "PORT_POWER 被視為資訊性內容。",
};

const DISPLAY_CLAIM = {
  "Synthetic fixture: PORT_POWER feature selector value is 8 (0x0008).":
    "PORT_POWER feature selector 值為 8（0x0008）。",
  "Synthetic fixture: Phase 1 corpus does not include the USB4 specification.":
    "USB4 Specification 未包含於目前可查詢的 Phase 1 corpus。",
  "Synthetic fixture A treats PORT_POWER as an authoritative Hub Class selector value 8.":
    "PORT_POWER 被視為權威性的 Hub Class selector，值為 8。",
  "Synthetic fixture B treats PORT_POWER as informative-only.":
    "PORT_POWER 被視為資訊性內容。",
};

const FIRST_LAYER_NOTE = {
  conflict: "這不是缺少資料，而是目前展示的來源彼此衝突。系統不會自行選擇其中一方作為答案。",
  conflict_service: "這不是缺少資料，而是現有來源彼此衝突。系統不會自行選擇其中一方作為答案。",
  out_of_scope: "這是目前資料範圍的限制，不代表該規格本身沒有答案。",
  out_of_scope_usb4: "這是目前資料範圍的限制，不代表 USB4 規格本身沒有答案。",
  missing_evidence: "目前缺少足以支持結論的證據。",
  fictional_section: "指定的 section 不存在於目前鎖定 corpus，系統不會用相鄰章節猜測。",
  authority_mismatch: "指定的 authority 不在目前鎖定 corpus，系統不會用其他來源替代。",
};

const BOUNDARY_REASON_LABEL = {
  OUT_OF_SCOPE: "目前範圍不在可查詢的 Phase 1 資料範圍內。",
  OUT_OF_SCOPE_USB4: "USB4 不在目前可查詢的 Phase 1 資料範圍內。",
  MISSING_EVIDENCE: "目前缺少足以支持結論的證據。",
  FICTIONAL_SECTION: "指定的 section 不存在於目前鎖定的 Phase 1 corpus。",
  AUTHORITY_MISMATCH: "指定的 authority 不在目前鎖定的 Phase 1 corpus。",
};

const CONFLICT_REASON_LABEL = {
  AUTHORITY_MISMATCH: "多個來源的權威層級不一致，因此無法認證單一結論。",
};

const AUTHORITY_LABEL = {
  authoritative: "權威來源",
  informative: "資訊性來源",
};

const RETRIEVAL_HINT = {
  single_scope: "只在目前選定的 USB 規格範圍內查找證據。",
  explicit_cross_scope: "可同時查找 USB 2.0、USB 3.x 等多個已允許範圍。",
};

const MODE_BADGE_TITLE = {
  fixture: "範例資料；問題不會被評分",
  service: "實際查詢服務；問題會送入既有 GovernedQAService。",
  real_local_rag: "Real PDF BM25 檢索後送入本機 local AI；development smoke only。",
};

function setModeBadge(mode) {
  const chip = $("fixtureChip");
  chip.hidden = false;
  const fixtureMode = mode === true || mode === "fixture";
  const realLocalRagMode = mode === "real_local_rag";
  chip.className = fixtureMode
    ? "mode-badge is-fixture"
    : realLocalRagMode
      ? "mode-badge is-rag"
      : "mode-badge is-service";
  chip.textContent = fixtureMode ? "範例" : realLocalRagMode ? "地端 RAG" : "服務";
  chip.title = fixtureMode
    ? MODE_BADGE_TITLE.fixture
    : realLocalRagMode
      ? MODE_BADGE_TITLE.real_local_rag
      : MODE_BADGE_TITLE.service;
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function textEl(tag, text, className) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  el.textContent = text == null ? "" : String(text);
  return el;
}

function isUsb4Scope(view) {
  return Boolean(view && view.scope === "USB4_SPEC");
}

function presentAnswer(text, view) {
  if (!text) return EMPTY_ANSWER;
  if (text === "現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論 (Abstain)。") {
    const kind = view ? uiKind(view) : "";
    if (kind === "out_of_scope") {
      return isUsb4Scope(view)
        ? "USB4 不在目前可查詢的 Phase 1 規格資料範圍內，因此系統不會根據未納入的規格內容推測答案。"
        : "這次查詢超出目前可認證範圍，因此系統不會推測答案。";
    }
    if (kind === "missing_evidence") {
      return "目前缺少足以支持結論的證據，因此暫不提供結論。";
    }
    return text;
  }
  return DISPLAY_ANSWER[text] || text;
}

function presentExcerpt(text) {
  if (!text) return "";
  return DISPLAY_EXCERPT[text] || text;
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

function uiKind(view) {
  const code = view.boundary_code || "";
  if (view.status === "conflict") return "conflict";
  if (code === "AUTHORITY_MISMATCH") return "authority_mismatch";
  if (code === "FICTIONAL_SECTION") return "fictional_section";
  if (code === "OUT_OF_SCOPE") return "out_of_scope";
  if (code === "MISSING_EVIDENCE" || view.status === "abstain") return "missing_evidence";
  if (view.status === "answer") return "answer";
  return view.status || "unknown";
}

function statusClass(kind) {
  if (kind === "conflict") return "conflict";
  if (kind === "out_of_scope" || kind === "missing_evidence" || kind === "fictional_section" || kind === "authority_mismatch") return "abstain";
  if (kind === "answer") return "answer";
  return kind;
}

function humanDocument(citation, view, index) {
  const kind = uiKind(view);
  const fixture = view.source === "fixture";
  if (kind === "out_of_scope") return "Phase 1 corpus";
  if (kind === "conflict" && fixture) {
    return index === 1 ? "範例來源 B" : "範例來源 A";
  }
  if (citation && citation.citation_kind === "governance") return "治理／corpus 中繼資料";
  const doc = citation && citation.document;
  if (!doc || doc === "operator-ui-fixture") {
    if (!fixture) return "治理／corpus 中繼資料";
    if (view.scope === "USB_3_X") return "USB 3.x Hub Specification";
    if (view.scope === "USB_2_0") return "USB 2.0 Specification";
    if (view.scope === "USB4_SPEC") return "USB4 Specification";
    if (view.scope === "USB_HUB_COMMON") return "USB Hub 共用規格";
    return "USB Hub Specification";
  }
  return doc;
}

function simulatedSpecName(citation, view, index) {
  if (citation && citation.section === "11.24.2.1") return "USB 2.0 Hub Specification";
  if (citation && citation.section === "10.16.2.1") return "USB 3.x Hub Specification";
  if (index === 1) return "USB 2.0 Hub Specification";
  if (view.scope === "USB_2_0") return "USB 2.0 Hub Specification";
  if (view.scope === "USB_3_X") return "USB 3.x Hub Specification";
  return "USB Hub Specification";
}

function titleCase(value) {
  if (!value) return "";
  return String(value).charAt(0).toUpperCase() + String(value).slice(1);
}

function authorityLabel(value) {
  if (!value) return "";
  return AUTHORITY_LABEL[value] || titleCase(value);
}

function presentClaim(text) {
  if (!text) return "";
  return DISPLAY_CLAIM[text] || text;
}

function renderSourceSummary(view) {
  const citations = view.citations || [];
  const kind = uiKind(view);
  const kicker = $("sourceKicker");
  const title = $("sourceLine");
  const meta = $("sourceMeta");
  const link = $("sourceOpen");
  clearNode(meta);
  meta.hidden = true;
  link.hidden = true;
  link.removeAttribute("href");
  if (kind === "conflict") {
    kicker.textContent = "衝突來源";
    const count = citations.length || 2;
    title.textContent = view.source === "fixture" ? `${count} 個模擬來源` : `${count} 個來源`;
    return;
  }
  if (kind === "out_of_scope") {
    kicker.textContent = "範圍依據";
    title.textContent = isUsb4Scope(view)
      ? "Phase 1 corpus · USB4 未納入"
      : (view.boundary || "這次查詢超出目前可認證範圍");
    return;
  }
  if (kind === "fictional_section") {
    kicker.textContent = "章節依據";
    title.textContent = "Phase 1 corpus · 未找到指定 section";
    return;
  }
  if (kind === "authority_mismatch") {
    kicker.textContent = "權威依據";
    title.textContent = "Phase 1 corpus · 未納入指定 authority";
    return;
  }
  if (kind === "missing_evidence") {
    kicker.textContent = "判定依據";
    title.textContent = "目前缺少足以支持結論的證據";
    return;
  }
  kicker.textContent = "來源";
  if (!citations.length) {
    title.textContent = "尚無來源";
    return;
  }
  const citation = citations[0];
  const parts = [humanDocument(citation, view, 0)];
  if (citation.section) parts.push(`§${citation.section}`);
  if (citation.authority_level) parts.push(authorityLabel(citation.authority_level));
  const prefix = view.source === "fixture" ? "範例來源：" : "";
  title.textContent = prefix + parts.join(" · ");
  if (citation.has_pdf_anchor && isSafePdfHref(citation.pdf_href)) {
    link.hidden = false;
    link.href = citation.pdf_href;
  }
}

function appendDlRow(dl, label, value) {
  if (!value) return;
  dl.appendChild(textEl("dt", label));
  dl.appendChild(textEl("dd", value));
}

function renderCitations(view) {
  const citations = view.citations || [];
  const kind = uiKind(view);
  const root = $("citations");
  const developer = $("developerCitations");
  clearNode(root);
  clearNode(developer);
  if (kind === "conflict") {
    $("evidenceSummary").textContent = "查看衝突來源";
    $("evidenceDesc").textContent = "條文摘錄";
  } else if (kind === "out_of_scope" || kind === "fictional_section" || kind === "authority_mismatch") {
    $("evidenceSummary").textContent = "查看範圍依據";
    $("evidenceDesc").textContent = "範圍與治理資料";
  } else {
    $("evidenceSummary").textContent = "查看引用原文";
    $("evidenceDesc").textContent = "條文摘錄";
  }
  $("evidenceCount").textContent = citations.length ? String(citations.length) : "";
  if (!citations.length) {
    root.appendChild(textEl("p", "沒有引用。", "muted"));
    return;
  }
  citations.forEach((citation, index) => {
    const article = document.createElement("article");
    article.className = "citation";
    if (view.source === "real_local_rag") {
      article.appendChild(textEl("p", index === 0 ? "主要依據" : "補充依據", "citation-role"));
    }
    article.appendChild(textEl("p", humanDocument(citation, view, index), "citation-meta"));
    if (kind === "conflict" && view.source === "fixture") {
      article.appendChild(textEl("p", `模擬：${simulatedSpecName(citation, view, index)}`, "citation-meta"));
    }
    const metaBits = [];
    if (citation.section) metaBits.push(`§${citation.section}`);
    if (citation.page_or_anchor) {
      metaBits.push(view.source === "real_local_rag" ? `PDF ${citation.page_or_anchor}` : citation.page_or_anchor);
    }
    if (citation.authority_level) metaBits.push(authorityLabel(citation.authority_level));
    if (metaBits.length) {
      article.appendChild(textEl("p", metaBits.join(" · "), "citation-meta"));
    }
    article.appendChild(textEl("p", presentExcerpt(citation.excerpt), "citation-quote"));
    if (citation.has_pdf_anchor && isSafePdfHref(citation.pdf_href)) {
      const link = document.createElement("a");
      link.href = citation.pdf_href;
      link.textContent = "開啟來源 ↗";
      article.appendChild(link);
    }
    root.appendChild(article);

    const item = document.createElement("dl");
    item.className = "dev-item";
    item.appendChild(textEl("p", humanDocument(citation, view, index), "citation-meta"));
    appendDlRow(item, "證據編號", citation.evidence_id);
    appendDlRow(item, "修訂版本", citation.revision);
    appendDlRow(item, "引用類型", citation.citation_kind);
    appendDlRow(item, "QA 回應來源", view.source);
    appendDlRow(item, view.source === "fixture" ? "範例資料來源" : "文件來源", citation.document || "—");
    appendDlRow(item, "檢索器", view.retrieval_kind);
    appendDlRow(item, "地端 AI", view.local_model);
    developer.appendChild(item);
  });
}

function renderSource(view) {
  const banner = $("dataSource");
  if (view.source === "fixture") {
    banner.className = "source-banner fixture";
    banner.textContent = "fixture\nQuery is NOT evaluated.";
    setModeBadge(true);
    return;
  }
  if (view.source === "service") {
    banner.className = "source-banner service";
    banner.textContent = "GovernedQAService";
    setModeBadge("service");
    return;
  }
  if (view.source === "real_local_rag") {
    banner.className = "source-banner real-local-rag";
    if (view.boundary_code) {
      banner.textContent = `Real PDF 邊界判定 · ${STATUS_LABEL[uiKind(view)] || "拒絕回答"}`;
      setModeBadge("real_local_rag");
      return;
    }
    const model = view.local_model || "local AI";
    const chunks = view.retrieved_chunk_count == null ? "" : ` · ${view.retrieved_chunk_count} chunks`;
    banner.textContent = `Real PDF BM25 → ${model}${chunks}`;
    setModeBadge("real_local_rag");
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
    list.appendChild(textEl("li", presentClaim(claim)));
  });
}

function shouldOpenGovernance(view) {
  return view.status === "error";
}

function render(view) {
  const kind = uiKind(view);
  $("statusRow").className = `status ${statusClass(kind)}`;
  $("statusRow").textContent = STATUS_LABEL[kind] || STATUS_LABEL[view.status] || view.status || "unknown";
  renderSource(view);
  const explainer = $("explainer");
  const answer = $("answerText");
  let note = FIRST_LAYER_NOTE[kind];
  if (kind === "conflict" && view.source !== "fixture") {
    note = FIRST_LAYER_NOTE.conflict_service;
  }
  if (kind === "out_of_scope") {
    note = isUsb4Scope(view) ? FIRST_LAYER_NOTE.out_of_scope_usb4 : FIRST_LAYER_NOTE.out_of_scope;
  }
  if (note) {
    explainer.hidden = false;
    explainer.textContent = note;
  } else {
    explainer.hidden = true;
  }
  answer.textContent = presentAnswer(view.answer, view);
  answer.className = view.answer ? "answer" : "answer is-empty";
  if (kind === "conflict" && note) {
    answer.parentNode.insertBefore(answer, explainer);
  } else if (note) {
    answer.parentNode.insertBefore(explainer, answer);
  }
  renderSourceSummary(view);
  $("scopeText").textContent = view.scope || "—";
  renderClaims(view.claims || []);
  renderCitations(view);
  if (view.source === "real_local_rag" && view.token_info) {
    renderTokenInfo(view.token_info, false);
  } else if (view.source !== "real_local_rag") {
    clearTokenInfo();
  }
  const boundaryBlock = $("boundaryBlock");
  if (view.boundary_code) {
    boundaryBlock.hidden = false;
    $("boundaryCode").textContent = view.boundary_code;
    if (view.boundary_code === "OUT_OF_SCOPE") {
      $("boundaryReason").textContent = isUsb4Scope(view)
        ? BOUNDARY_REASON_LABEL.OUT_OF_SCOPE_USB4
        : (view.boundary || BOUNDARY_REASON_LABEL.OUT_OF_SCOPE);
    } else {
      const labels = kind === "conflict" ? CONFLICT_REASON_LABEL : BOUNDARY_REASON_LABEL;
      $("boundaryReason").textContent = labels[view.boundary_code] || view.boundary || "—";
    }
  } else {
    boundaryBlock.hidden = true;
  }
  $("evidenceFold").open = false;
  $("governanceFold").open = shouldOpenGovernance(view);
}

function realLocalRagView(meta, answer, localModel) {
  const citations = Array.isArray(meta.citations) ? meta.citations : [];
  const evidenceIds = citations.map((citation) => citation.evidence_id).filter(Boolean);
  const resolvedModel = localModel === null ? null : (localModel || meta.local_model || null);
  const base = {
    source: "real_local_rag",
    status: "answer",
    answer: answer || "地端 AI 正在根據 real PDF 檢索證據產生回答……",
    claims: answer ? [answer] : [],
    citations,
    boundary_code: meta.boundary_code || null,
    boundary: meta.boundary || "Real PDF BM25 證據已送入本機 AI；語義蘊含尚未獨立驗證。",
    boundary_reason: meta.boundary_reason || "Real PDF BM25 證據已送入本機 AI；語義蘊含尚未獨立驗證。",
    scope: meta.scope || "USB_HUB_COMMON",
    evidence_ids: evidenceIds,
    claim_evidence_ids: answer ? [evidenceIds] : [],
    is_abstain: false,
    claim_ceiling: meta.claim_ceiling,
    local_model: resolvedModel,
    retrieval_kind: meta.retriever_kind,
    retrieved_chunk_count: meta.retrieved_chunk_count,
    corpus_sha256: meta.corpus_sha256,
  };
  if (meta.boundary_code) {
    return {
      ...base,
      status: "abstain",
      answer: answer || meta.boundary_answer || "目前請求被治理邊界拒絕。",
      claims: [],
      evidence_ids: [],
      claim_evidence_ids: [],
      is_abstain: true,
      local_model: null,
      retrieved_chunk_count: 0,
    };
  }
  if (answer === null) {
    return {
      ...base,
      status: "abstain",
      answer: "目前 real corpus 沒有足夠的 BM25 證據；地端 AI 未被呼叫。",
      claims: [],
      boundary_code: "MISSING_EVIDENCE",
      boundary: "Real PDF BM25 沒有找到匹配證據。",
      boundary_reason: "Real PDF BM25 沒有找到匹配證據；地端 AI 未被呼叫。",
      evidence_ids: [],
      claim_evidence_ids: [],
      is_abstain: true,
      local_model: null,
      retrieved_chunk_count: 0,
    };
  }
  return base;
}

function renderTokenInfo(info, streaming = false) {
  const node = $("tokenInfo");
  if (!node || !info) {
    if (node) node.hidden = true;
    return;
  }
  const bits = [];
  if (info.completion_tokens != null) {
    bits.push(`生成 token ${info.completion_tokens}`);
  } else if (streaming) {
    bits.push("生成 token 計算中");
  }
  if (info.prompt_tokens != null) bits.push(`提示 token ${info.prompt_tokens}`);
  if (info.total_tokens != null) bits.push(`總 token ${info.total_tokens}`);
  if (info.stream_chunks != null) bits.push(`串流片段 ${info.stream_chunks}（非 tokenizer token）`);
  if (info.completion_chars != null) bits.push(`字元 ${info.completion_chars}`);
  if (info.elapsed_ms != null) bits.push(`耗時 ${info.elapsed_ms} ms`);
  if (info.server_tokens_per_second != null) {
    bits.push(`速度 ${info.server_tokens_per_second} token/s`);
  }
  node.textContent = bits.join(" · ");
  node.hidden = bits.length === 0;
}

function clearTokenInfo() {
  const node = $("tokenInfo");
  if (!node) return;
  node.hidden = true;
  node.textContent = "";
}

async function streamRealLocalRag(body, generation, controller) {
  const resp = await fetch("/api/qa/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  });
  if (generation !== requestGeneration) return;
  if (!resp.ok) {
    let error = "request failed";
    try {
      const payload = await resp.json();
      error = payload.error || error;
    } catch (_err) {
      // Keep the generic error when the gateway did not return JSON.
    }
    throw new Error(error);
  }
  if (!resp.body) throw new Error("streaming response body is unavailable");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let meta = null;
  let answer = "";
  let finalEvent = null;

  const consumeEvent = (line) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (generation !== requestGeneration) return;
    if (event.type === "status") {
      $("dataSource").className = "source-banner real-local-rag";
      $("dataSource").textContent = event.message || "正在準備地端 RAG……";
      setModeBadge("real_local_rag");
      $("answerText").textContent = "正在準備 real PDF 證據……";
      $("answerText").className = "answer";
      renderTokenInfo({ stream_chunks: 0, completion_chars: 0, elapsed_ms: 0 }, true);
      return;
    }
    if (event.type === "meta") {
      meta = event;
      render(realLocalRagView(meta, "", event.local_model));
      renderTokenInfo({ stream_chunks: 0, completion_chars: 0, elapsed_ms: 0 }, true);
      return;
    }
    if (event.type === "token") {
      answer += event.text || "";
      $("answerText").textContent = answer;
      $("answerText").className = "answer";
      renderTokenInfo(event.token_info, true);
      return;
    }
    if (event.type === "done") {
      finalEvent = event;
      answer = typeof event.answer === "string" ? event.answer : null;
      if (meta) {
        render(realLocalRagView(meta, answer, event.local_model));
        renderTokenInfo(event.token_info, false);
      }
      return;
    }
    if (event.type === "error") throw new Error(event.error || "stream request failed");
    throw new Error(`unknown stream event type: ${event.type || "missing"}`);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (generation !== requestGeneration) {
      await reader.cancel();
      return;
    }
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";
    lines.forEach(consumeEvent);
  }
  buffer += decoder.decode();
  if (buffer.trim()) consumeEvent(buffer);
  if (!finalEvent) throw new Error("real-local-RAG stream ended before completion");
}

function applyFixtureQuestion() {
  const field = $("question");
  const name = $("fixture").value;
  field.value = FIXTURE_QUESTIONS[name] || FIXTURE_QUESTIONS.answered;
  autosizeQuestion();
}

function syncFixtureMode() {
  const sourceMode = $("source").value;
  const fixtureMode = sourceMode === "fixture";
  $("fixtureIgnoreHint").hidden = !fixtureMode;
  $("fixtureField").hidden = !fixtureMode;
  $("devModeCopy").textContent = fixtureMode
    ? "目前使用範例資料，問題不會送入實際檢索服務。"
    : sourceMode === "real_local_rag"
      ? "目前會先從鎖定的 real PDF 做 BM25，再把檢索證據送給本機 local AI。"
      : "目前會呼叫既有 GovernedQAService，不會捏造 PDF 錨點。";
  setModeBadge(sourceMode);
  $("askBtn").textContent = fixtureMode
    ? "預覽範例"
    : sourceMode === "real_local_rag"
      ? "送出到地端 RAG"
      : "提問";
  QUERY_FIELD_IDS.forEach((id) => {
    $(id).disabled = fixtureMode;
  });
  $("question").readOnly = fixtureMode;
  if (fixtureMode) {
    $("question").placeholder = FIXTURE_QUESTIONS[$("fixture").value] || FIXTURE_QUESTIONS.answered;
    applyFixtureQuestion();
  } else if (sourceMode === "real_local_rag") {
    $("question").placeholder = REAL_LOCAL_RAG_PLACEHOLDER;
    $("question").value = "";
    autosizeQuestion();
  } else {
    $("question").placeholder = SERVICE_PLACEHOLDER;
    $("question").value = "";
    autosizeQuestion();
  }
  $("fixture").disabled = !fixtureMode;
  resetWaitingView();
}

function autosizeQuestion() {
  const field = $("question");
  field.style.height = "auto";
  const next = Math.max(48, field.scrollHeight);
  field.style.height = `${next}px`;
}

function syncRetrievalHint() {
  const hint = $("retrievalHint");
  if (!hint) return;
  const mode = $("retrievalMode").value;
  hint.textContent = RETRIEVAL_HINT[mode] || RETRIEVAL_HINT.single_scope;
  const cross = mode === "explicit_cross_scope";
  $("allowedScopesField").hidden = !cross;
  if (!cross) $("allowedScopes").value = "";
}

function allowedEvidenceScopes() {
  if ($("retrievalMode").value !== "explicit_cross_scope") return null;
  const allowedRaw = $("allowedScopes").value.trim();
  return allowedRaw ? allowedRaw.split(",").map((s) => s.trim()).filter(Boolean) : null;
}

let requestGeneration = 0;
let activeController = null;

function invalidatePendingRequest() {
  requestGeneration += 1;
  if (activeController) {
    activeController.abort();
    activeController = null;
  }
}

function resetResultView(message) {
  $("statusRow").className = "status conflict";
  $("statusRow").textContent = STATUS_LABEL.error;
  $("dataSource").className = "source-banner waiting";
  $("dataSource").textContent = "error";
  $("explainer").hidden = true;
  $("explainer").textContent = "";
  $("answerText").textContent = message || "request failed";
  $("answerText").className = "answer";
  clearTokenInfo();
  $("sourceKicker").textContent = "來源";
  $("sourceLine").textContent = "尚無來源";
  $("sourceMeta").hidden = true;
  $("sourceOpen").hidden = true;
  $("sourceOpen").removeAttribute("href");
  clearNode($("citations"));
  clearNode($("developerCitations"));
  $("evidenceCount").textContent = "";
  $("evidenceSummary").textContent = "查看引用原文";
  $("evidenceDesc").textContent = "條文摘錄";
  $("scopeText").textContent = "—";
  clearNode($("claims"));
  $("boundaryBlock").hidden = true;
  $("boundaryCode").textContent = "—";
  $("boundaryReason").textContent = "—";
  $("evidenceFold").open = false;
  $("governanceFold").open = true;
}

function resetWaitingView() {
  invalidatePendingRequest();
  $("askBtn").disabled = false;
  $("askError").hidden = true;
  $("statusRow").className = "status unknown";
  $("statusRow").textContent = STATUS_LABEL.unknown;
  $("dataSource").className = "source-banner waiting";
  $("dataSource").textContent = "waiting";
  $("explainer").hidden = true;
  $("explainer").textContent = "";
  $("answerText").textContent = EMPTY_ANSWER;
  $("answerText").className = "answer is-empty";
  clearTokenInfo();
  $("sourceKicker").textContent = "來源";
  $("sourceLine").textContent = "尚無來源";
  $("sourceMeta").hidden = true;
  $("sourceOpen").hidden = true;
  $("sourceOpen").removeAttribute("href");
  clearNode($("citations"));
  clearNode($("developerCitations"));
  $("evidenceCount").textContent = "";
  $("evidenceSummary").textContent = "查看引用原文";
  $("evidenceDesc").textContent = "條文摘錄";
  $("scopeText").textContent = "—";
  clearNode($("claims"));
  $("boundaryBlock").hidden = true;
  $("boundaryCode").textContent = "—";
  $("boundaryReason").textContent = "—";
  $("evidenceFold").open = false;
  $("governanceFold").open = false;
}

$("askBtn").addEventListener("click", async () => {
  const askBtn = $("askBtn");
  const askError = $("askError");
  invalidatePendingRequest();
  const generation = requestGeneration;
  const controller = new AbortController();
  activeController = controller;
  askError.hidden = true;
  askBtn.disabled = true;
  const body = {
    question: $("question").value,
    answer_scope: $("answerScope").value,
    retrieval_mode: $("retrievalMode").value,
    allowed_evidence_scopes: allowedEvidenceScopes(),
    source: $("source").value,
    fixture: $("fixture").value,
  };
  try {
    if (body.source === "real_local_rag") {
      await streamRealLocalRag(body, generation, controller);
      return;
    }
    const resp = await fetch("/api/qa", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (generation !== requestGeneration) return;
    const data = await resp.json();
    if (generation !== requestGeneration) return;
    if (!resp.ok) {
      resetResultView(data.error || "request failed");
      askError.hidden = false;
      askError.textContent = data.error || "request failed";
      return;
    }
    render(data);
  } catch (err) {
    if (generation !== requestGeneration) return;
    if (err && err.name === "AbortError") return;
    const message = err && err.message ? err.message : "request failed";
    resetResultView(message);
    askError.hidden = false;
    askError.textContent = message;
  } finally {
    if (generation === requestGeneration) {
      askBtn.disabled = false;
      if (activeController === controller) activeController = null;
    }
  }
});

$("source").addEventListener("change", syncFixtureMode);
$("fixture").addEventListener("change", () => {
  if ($("source").value === "fixture") applyFixtureQuestion();
  resetWaitingView();
});
$("answerScope").addEventListener("change", resetWaitingView);
$("allowedScopes").addEventListener("change", resetWaitingView);
$("retrievalMode").addEventListener("change", () => {
  syncRetrievalHint();
  resetWaitingView();
});
$("question").addEventListener("input", autosizeQuestion);
$("advancedFold").open = false;
syncFixtureMode();
syncRetrievalHint();
autosizeQuestion();
