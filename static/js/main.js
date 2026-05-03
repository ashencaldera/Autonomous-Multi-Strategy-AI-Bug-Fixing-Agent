/* ══════════════════════════════════════════════════════
   BugFixAI — Frontend
   Features: SSE streaming, diff view, syntax highlighting,
             line-by-line animated code reveal
   ══════════════════════════════════════════════════════ */

const state = {
  running: false, sessionId: null, sse: null,
  startTime: null, candidateMap: {}, stepMap: {},
  examples: [], dropdownOpen: false, dropdown: null,
  originalCode: "", _toastTimer: null,
};

/* ══════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", () => {
  window._els = {
    codeInput:       document.getElementById("code-input"),
    lineNumbers:     document.getElementById("line-numbers"),
    charCount:       document.getElementById("char-count"),
    btnFix:          document.getElementById("btn-fix"),
    btnExamples:     document.getElementById("btn-examples"),
    btnClear:        document.getElementById("btn-clear"),
    stepsContainer:  document.getElementById("steps-container"),
    emptyState:      document.getElementById("empty-state"),
    statusBadge:     document.getElementById("status-badge"),
    progressWrap:    document.getElementById("progress-bar-wrap"),
    progressBar:     document.getElementById("progress-bar"),
    errorCard:       document.getElementById("error-card"),
    candidatesCard:  document.getElementById("candidates-card"),
    candidatesGrid:  document.getElementById("candidates-grid"),
    candidatesCount: document.getElementById("candidates-count"),
    reflectionCard:  document.getElementById("reflection-card"),
    reflectionText:  document.getElementById("reflection-text"),
    reflectionAppr:  document.getElementById("reflection-approach"),
    resultPanel:     document.getElementById("result-panel"),
    resultIcon:      document.getElementById("result-icon"),
    resultTitle:     document.getElementById("result-title"),
    resultStrategy:  document.getElementById("result-strategy"),
    resultScore:     document.getElementById("result-score"),
    resultSubtitle:  document.getElementById("result-explanation"),
    resultCode:      document.getElementById("result-code"),
    resultLineNums:  document.getElementById("result-line-numbers"),
    resultOutBlock:  document.getElementById("result-output-block"),
    resultOutput:    document.getElementById("result-output"),
    resultStats:     document.getElementById("result-stats"),
    diffOld:         document.getElementById("diff-old"),
    diffNew:         document.getElementById("diff-new"),
    diffRemovedCt:   document.getElementById("diff-removed-count"),
    diffAddedCt:     document.getElementById("diff-added-count"),
    diffContainer:   document.getElementById("diff-container"),
    errorPlain:      document.getElementById("error-plain-english"),
    errorRoot:       document.getElementById("error-root-cause"),
    errorHints:      document.getElementById("error-hints"),
    errorTypeBadge:  document.getElementById("error-type-badge"),
    toast:           document.getElementById("toast"),
  };

  /* Floating dropdown */
  const dd = document.createElement("div");
  dd.style.cssText = "display:none;position:fixed;z-index:9999;background:#1c2128;border:1px solid #30363d;border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.5);min-width:270px;overflow:hidden;";
  document.body.appendChild(dd);
  state.dropdown = dd;

  const { codeInput, lineNumbers, btnFix, btnExamples, btnClear } = window._els;

  codeInput.addEventListener("input",  () => { updateLineNumbers(); updateCharCount(); });
  codeInput.addEventListener("keydown", e => {
    if (e.key === "Tab") {
      e.preventDefault();
      const s = codeInput.selectionStart;
      codeInput.value = codeInput.value.slice(0,s) + "    " + codeInput.value.slice(codeInput.selectionEnd);
      codeInput.selectionStart = codeInput.selectionEnd = s + 4;
      updateLineNumbers();
    }
  });
  codeInput.addEventListener("scroll", () => { lineNumbers.scrollTop = codeInput.scrollTop; });

  btnFix.addEventListener("click", startFix);
  btnClear.addEventListener("click", () => { codeInput.value = ""; updateLineNumbers(); updateCharCount(); resetUI(); });
  btnExamples.addEventListener("click", e => { e.stopPropagation(); toggleDropdown(); });
  document.addEventListener("click", e => { if (!dd.contains(e.target) && e.target !== btnExamples) closeDropdown(); });
  document.getElementById("btn-copy").addEventListener("click", copyFixed);
  document.getElementById("btn-use-fix").addEventListener("click", useThisFix);

  updateLineNumbers(); updateCharCount(); loadExamples();
  console.log("BugFixAI ready ✓");
});

/* ── Editor helpers ── */
function updateLineNumbers() {
  const { codeInput, lineNumbers } = window._els;
  const n = codeInput.value.split("\n").length;
  lineNumbers.textContent = Array.from({length:n}, (_,i) => i+1).join("\n");
}
function updateCharCount() {
  const { codeInput, charCount } = window._els;
  const len = codeInput.value.length;
  charCount.textContent = `${len} / 5000`;
  charCount.className = "char-count" + (len > 4500 ? " warn" : "") + (len >= 5000 ? " danger" : "");
}

/* ── Examples ── */
async function loadExamples() {
  try {
    const r = await fetch("/api/examples");
    state.examples = await r.json();
    buildDropdown();
  } catch(e) { console.warn("Examples failed:", e); }
}
function buildDropdown() {
  const dd = state.dropdown;
  dd.innerHTML = "";
  state.examples.forEach((ex, i) => {
    const btn = document.createElement("button");
    btn.style.cssText = "display:block;width:100%;padding:10px 16px;text-align:left;background:none;border:none;border-bottom:1px solid #30363d;color:#e6edf3;font-family:Inter,sans-serif;font-size:13px;cursor:pointer;transition:background .15s;";
    if (i === state.examples.length-1) btn.style.borderBottom = "none";
    btn.innerHTML = `<div style="font-weight:600">${ex.title}</div><div style="font-size:11px;color:#6e7681;font-family:'JetBrains Mono',monospace;margin-top:2px">${ex.code.slice(0,48).replace(/\n/g," ")}…</div>`;
    btn.onmouseenter = () => { btn.style.background="#22272e"; btn.style.color="#00e5ff"; };
    btn.onmouseleave = () => { btn.style.background="none"; btn.style.color="#e6edf3"; };
    btn.addEventListener("click", () => {
      window._els.codeInput.value = ex.code;
      updateLineNumbers(); updateCharCount(); closeDropdown();
    });
    dd.appendChild(btn);
  });
}
function toggleDropdown() {
  if (state.dropdownOpen) { closeDropdown(); return; }
  const rect = window._els.btnExamples.getBoundingClientRect();
  const dd = state.dropdown;
  dd.style.top  = (rect.bottom + 6) + "px";
  dd.style.left = Math.max(4, rect.right - 270) + "px";
  dd.style.display = "block";
  state.dropdownOpen = true;
}
function closeDropdown() { if (state.dropdown) state.dropdown.style.display = "none"; state.dropdownOpen = false; }

/* ══════════════════════════════════════════════════════
   MAIN FIX FLOW
   ══════════════════════════════════════════════════════ */
async function startFix() {
  if (state.running) return;
  const { codeInput, btnFix } = window._els;
  const code = codeInput.value.trim();
  if (!code)          { showToast("Paste your buggy code first.", "error"); return; }
  if (code.length > 5000) { showToast("Code too long (max 5000 chars).", "error"); return; }

  state.originalCode = code;
  state.running = true;
  state.startTime = Date.now();
  state.candidateMap = {}; state.stepMap = {};

  btnFix.disabled = true;
  btnFix.innerHTML = '<span class="btn-icon">⏳</span> Fixing…';
  setStatusBadge("running", "Agent Running…");
  showProgress(8);
  resetUI(false);

  try {
    const res = await fetch("/api/fix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    if (!res.ok) throw new Error("Server error " + res.status);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    state.sessionId = data.session_id;
    connectSSE(data.session_id);
  } catch(err) {
    showToast("Error: " + err.message, "error");
    finishRun(false);
  }
}

function connectSSE(sessionId) {
  state.sse = new EventSource(`/api/stream/${sessionId}`);
  state.sse.onmessage = e => {
    try { handleEvent(JSON.parse(e.data)); } catch(ex) { console.error("SSE parse:", ex); }
  };
  state.sse.addEventListener("close", () => state.sse.close());
  state.sse.onerror = () => { state.sse.close(); finishRun(false); };
}

function handleEvent(ev) {
  switch(ev.event) {
    case "step":                 renderStep(ev.data); break;
    case "error_analysis":       renderErrorAnalysis(ev.data); advanceProgress(30); break;
    case "reflection":           renderReflection(ev.data); break;
    case "candidates_generated": advanceProgress(55); break;
    case "candidate_result":     renderCandidate(ev.data); break;
    case "best_selected":        highlightBest(ev.data.candidate_id); advanceProgress(80); break;
    case "result":               renderResult(ev.data); advanceProgress(100); break;
    case "error":                showToast("Agent error: " + ev.data.message, "error"); finishRun(false); break;
    case "done":                 setTimeout(() => finishRun(true), 600); break;
  }
}

/* ── Steps ── */
function renderStep(data) {
  const { stepsContainer, emptyState } = window._els;
  const key = data.name;
  if (state.stepMap[key]) {
    const el = state.stepMap[key];
    el.className = `step-item ${data.status}`;
    el.querySelector(".step-indicator").className = `step-indicator ${data.status}`;
    el.querySelector(".step-indicator").textContent = data.status==="done"?"✓":data.status==="error"?"✗":"●";
    if (data.detail) el.querySelector(".step-detail").textContent = data.detail;
    return;
  }
  emptyState.classList.add("hidden");
  const el = document.createElement("div");
  el.className = `step-item ${data.status}`;
  el.innerHTML = `<div class="step-indicator ${data.status}">${data.status==="done"?"✓":"●"}</div><div class="step-text"><div class="step-name">${esc(data.name)}</div><div class="step-detail">${esc(data.detail||"")}</div></div>`;
  stepsContainer.appendChild(el);
  const panel = document.querySelector(".panel-output");
  if (panel) panel.scrollTop = panel.scrollHeight;
  state.stepMap[key] = el;
}

/* ── Error analysis ── */
function renderErrorAnalysis(data) {
  const { errorCard, errorPlain, errorRoot, errorHints, errorTypeBadge } = window._els;
  errorCard.classList.remove("hidden");
  errorPlain.textContent = data.plain_english || "";
  errorRoot.textContent  = data.root_cause || "";
  errorTypeBadge.textContent = data.error_category || "";
  errorTypeBadge.className = "badge badge-" + (data.severity==="major"?"error":data.severity==="minor"?"success":"running");
  errorHints.innerHTML = (data.fix_hints||[]).map(h=>`<div class="hint-item">${esc(h)}</div>`).join("");
}

/* ── Reflection ── */
function renderReflection(data) {
  if (data.attempt < 2) return;
  const { reflectionCard, reflectionText, reflectionAppr } = window._els;
  reflectionCard.classList.remove("hidden");
  reflectionText.textContent = data.reflection.summary || "";
  reflectionAppr.textContent = "→ " + (data.reflection.new_approach || "");
}

/* ── Candidates ── */
function renderCandidate(data) {
  const { candidatesCard, candidatesGrid, candidatesCount } = window._els;
  candidatesCard.classList.remove("hidden");
  const score = data.validation_score || 0;
  const scoreClass = score >= 0.7 ? "score-high" : score >= 0.4 ? "score-medium" : "score-low";
  const cell = document.createElement("div");
  cell.className = `candidate-cell${data.status==="success"?"":" failed-cell"}`;
  cell.dataset.id = data.candidate_id;
  cell.innerHTML = `
    <div class="cand-header">
      <span class="cand-strategy strategy-${esc(data.strategy)}">${esc(data.strategy)}</span>
      <span class="cand-score ${scoreClass}">${(score*100).toFixed(0)}%</span>
    </div>
    <div class="cand-status">${data.status==="success"?"✅":data.status==="timeout"?"⏱":"❌"} ${esc(data.status)}</div>
    <div class="cand-explanation">${esc(data.explanation||"")}</div>
    <div class="cand-notes">${esc(data.validation_notes||"")}</div>`;
  cell.addEventListener("click", () => showCodeModal(data.code, data.strategy));
  candidatesGrid.appendChild(cell);
  candidatesCount.textContent = candidatesGrid.children.length + " candidates";
  state.candidateMap[data.candidate_id] = cell;
}
function highlightBest(id) {
  const el = state.candidateMap[id];
  if (el) el.classList.add("selected");
}

/* ══════════════════════════════════════════════════════
   DIFF ENGINE
   ══════════════════════════════════════════════════════ */
function computeDiff(oldLines, newLines) {
  /* Simple LCS-based diff */
  const m = oldLines.length, n = newLines.length;
  const dp = Array.from({length:m+1}, () => new Array(n+1).fill(0));
  for (let i=m-1; i>=0; i--)
    for (let j=n-1; j>=0; j--)
      dp[i][j] = oldLines[i] === newLines[j]
        ? dp[i+1][j+1]+1
        : Math.max(dp[i+1][j], dp[i][j+1]);

  const ops = [];
  let i=0, j=0;
  while (i<m || j<n) {
    if (i<m && j<n && oldLines[i]===newLines[j]) {
      ops.push({type:"same", old:oldLines[i], new:newLines[j]});
      i++; j++;
    } else if (j<n && (i>=m || dp[i][j+1]>=dp[i+1][j])) {
      ops.push({type:"add", new:newLines[j]});
      j++;
    } else {
      ops.push({type:"remove", old:oldLines[i]});
      i++;
    }
  }
  return ops;
}

function renderDiff(oldCode, newCode) {
  const { diffOld, diffNew, diffRemovedCt, diffAddedCt, diffContainer } = window._els;
  diffContainer.classList.remove("hidden");

  const oldLines = oldCode.split("\n");
  const newLines = newCode.split("\n");
  const ops = computeDiff(oldLines, newLines);

  let removed = 0, added = 0;
  let oldLineNum = 1, newLineNum = 1;
  diffOld.innerHTML = "";
  diffNew.innerHTML = "";

  ops.forEach((op, idx) => {
    const delay = Math.min(idx * 18, 800);

    if (op.type === "same") {
      diffOld.appendChild(makeDiffLine(op.old, oldLineNum++, "same", delay));
      diffNew.appendChild(makeDiffLine(op.new, newLineNum++, "same", delay));
    } else if (op.type === "remove") {
      diffOld.appendChild(makeDiffLine(op.old, oldLineNum++, "removed", delay));
      /* empty spacer on new side */
      const spacer = document.createElement("div");
      spacer.className = "diff-line";
      spacer.style.minHeight = "21px";
      diffNew.appendChild(spacer);
      removed++;
    } else {
      /* empty spacer on old side */
      const spacer = document.createElement("div");
      spacer.className = "diff-line";
      spacer.style.minHeight = "21px";
      diffOld.appendChild(spacer);
      diffNew.appendChild(makeDiffLine(op.new, newLineNum++, "added", delay));
      added++;
    }
  });

  diffRemovedCt.textContent = removed ? `${removed} line${removed>1?"s":""} removed` : "";
  diffAddedCt.textContent   = added   ? `${added} line${added>1?"s":""} added`   : "";
}

function makeDiffLine(text, lineNum, type, delayMs) {
  const row = document.createElement("div");
  row.className = `diff-line diff-line-${type}`;
  row.style.animationDelay = delayMs + "ms";
  row.innerHTML = `<span class="diff-line-num">${lineNum}</span><span class="diff-line-content">${esc(text)}</span>`;
  return row;
}

/* ══════════════════════════════════════════════════════
   PYTHON SYNTAX HIGHLIGHTER
   ══════════════════════════════════════════════════════ */
const PY_KEYWORDS = new Set([
  "def","class","return","if","elif","else","for","while","in","not","and","or",
  "import","from","as","pass","break","continue","try","except","finally","raise",
  "with","yield","lambda","None","True","False","is","del","global","nonlocal","assert"
]);
const PY_BUILTINS = new Set([
  "print","len","range","int","str","float","list","dict","set","tuple","bool",
  "type","isinstance","hasattr","getattr","setattr","enumerate","zip","map","filter",
  "sorted","reversed","sum","min","max","abs","round","open","input","super"
]);

function highlightPython(code) {
  return code.split("\n").map((line, i) => {
    const hl = highlightLine(line);
    return `<span class="code-line" style="animation-delay:${i*30}ms">${hl}</span>`;
  }).join("\n");
}

function highlightLine(line) {
  /* Handle comment */
  const commentIdx = findCommentStart(line);
  if (commentIdx !== -1) {
    return highlightNonComment(line.slice(0, commentIdx)) +
           `<span class="sy-cmt">${esc(line.slice(commentIdx))}</span>`;
  }
  return highlightNonComment(line);
}

function findCommentStart(line) {
  let inStr = false, strChar = "";
  for (let i=0; i<line.length; i++) {
    if (!inStr && (line[i]==="'" || line[i]==='"')) { inStr=true; strChar=line[i]; }
    else if (inStr && line[i]===strChar && line[i-1]!=="\\") inStr=false;
    else if (!inStr && line[i]==="#") return i;
  }
  return -1;
}

function highlightNonComment(text) {
  /* Tokenise into: strings, decorators, numbers, identifiers, everything else */
  let out = "", i = 0;
  while (i < text.length) {
    /* String */
    if (text[i]==='"' || text[i]==="'") {
      const q = text[i];
      let j = i+1;
      while (j < text.length && !(text[j]===q && text[j-1]!=="\\")) j++;
      j++;
      out += `<span class="sy-str">${esc(text.slice(i,j))}</span>`;
      i = j; continue;
    }
    /* Decorator */
    if (text[i]==="@") {
      let j=i+1;
      while (j<text.length && /\w/.test(text[j])) j++;
      out += `<span class="sy-dec">${esc(text.slice(i,j))}</span>`;
      i=j; continue;
    }
    /* Number */
    if (/[0-9]/.test(text[i]) && (i===0 || !/\w/.test(text[i-1]))) {
      let j=i;
      while (j<text.length && /[\d._xXbBoO]/.test(text[j])) j++;
      out += `<span class="sy-num">${esc(text.slice(i,j))}</span>`;
      i=j; continue;
    }
    /* Identifier / keyword */
    if (/[a-zA-Z_]/.test(text[i])) {
      let j=i;
      while (j<text.length && /\w/.test(text[j])) j++;
      const word = text.slice(i,j);
      const next = text.slice(j).trimStart();
      if (PY_KEYWORDS.has(word))       out += `<span class="sy-kw">${esc(word)}</span>`;
      else if (PY_BUILTINS.has(word))  out += `<span class="sy-bi">${esc(word)}</span>`;
      else if (next.startsWith("("))   out += `<span class="sy-fn">${esc(word)}</span>`;
      else if (/^[A-Z]/.test(word))    out += `<span class="sy-cls">${esc(word)}</span>`;
      else                             out += esc(word);
      i=j; continue;
    }
    /* Operators */
    if (/[+\-*/%=<>!&|^~]/.test(text[i])) {
      out += `<span class="sy-op">${esc(text[i])}</span>`;
      i++; continue;
    }
    out += esc(text[i]); i++;
  }
  return out;
}

/* ══════════════════════════════════════════════════════
   RENDER FINAL RESULT
   ══════════════════════════════════════════════════════ */
function renderResult(data) {
  const {
    resultPanel, resultIcon, resultTitle, resultStrategy, resultScore,
    resultSubtitle, resultCode, resultLineNums,
    resultOutBlock, resultOutput, resultStats,
  } = window._els;

  resultPanel.classList.remove("hidden");

  const isFixed = data.status === "fixed" || data.status === "already_working";

  if (isFixed) {
    resultPanel.classList.remove("result-failed");
    resultIcon.textContent  = "✅";
    resultTitle.textContent = data.status === "already_working" ? "Code Already Works!" : "Bug Fixed!";
    resultStrategy.textContent = data.strategy ? `Strategy: ${data.strategy}` : "";
    resultStrategy.className   = "badge badge-success";
    resultScore.textContent    = data.validation_score ? `Score: ${(data.validation_score*100).toFixed(0)}%` : "";
    resultSubtitle.textContent = data.explanation || data.message || "";

    const fixedCode = data.fixed_code || data.best_effort_code || "";
    console.log("[BugFixAI] fixed_code length:", fixedCode.length, "| status:", data.status);

    /* 1. Diff view (only if both sides have code) */
    if (state.originalCode && fixedCode) {
      renderDiff(state.originalCode, fixedCode);
    }

    /* 2. Full fixed code with syntax highlighting + line numbers */
    if (fixedCode) {
      const lines = fixedCode.split("\n");
      resultLineNums.textContent = lines.map((_,i)=>i+1).join("\n");
      try {
        resultCode.innerHTML = highlightPython(fixedCode);
      } catch(e) {
        // Fallback: plain text if highlighter crashes
        resultCode.textContent = fixedCode;
      }
    } else {
      resultCode.textContent = "// No fixed code returned — check agent logs.";
      resultLineNums.textContent = "1";
    }

    /* 3. Output */
    if (data.output && data.output.trim()) {
      resultOutBlock.classList.remove("hidden");
      resultOutput.textContent = data.output;
    }

    /* Save fixed code for "Use This Fix" */
    state.lastFixedCode = fixedCode;

  } else {
    resultPanel.classList.add("result-failed");
    resultIcon.textContent  = "⚠️";
    resultTitle.textContent = "Could Not Fully Verify Fix";
    resultStrategy.textContent = "";
    resultScore.textContent = data.best_effort_score ? `Best: ${(data.best_effort_score*100).toFixed(0)}%` : "";
    resultSubtitle.textContent = data.message || "Agent reached its attempt limit.";

    const bestCode = data.best_effort_code || "";
    if (bestCode) {
      renderDiff(state.originalCode, bestCode);
      const lines = bestCode.split("\n");
      resultLineNums.textContent = lines.map((_,i)=>i+1).join("\n");
      resultCode.innerHTML = highlightPython(bestCode);
      state.lastFixedCode = bestCode;
    }
  }

  const elapsed = ((Date.now() - state.startTime)/1000).toFixed(1);
  resultStats.innerHTML = `
    <div class="stat-item"><span class="stat-label">Time</span><span class="stat-value">${elapsed}s</span></div>
    <div class="stat-item"><span class="stat-label">Attempts</span><span class="stat-value">${data.attempts_made ?? "—"}</span></div>
    <div class="stat-item"><span class="stat-label">Strategy</span><span class="stat-value">${data.strategy || "—"}</span></div>
    <div class="stat-item"><span class="stat-label">Score</span><span class="stat-value">${data.validation_score ? (data.validation_score*100).toFixed(0)+"%" : "—"}</span></div>`;

  // Scroll the output panel itself (not the whole page) to the result
  const outputPanel = document.querySelector(".panel-output");
  if (outputPanel) {
    setTimeout(() => {
      outputPanel.scrollTo({ top: outputPanel.scrollHeight, behavior: "smooth" });
    }, 300);
  } else {
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/* ── Code modal (candidates) ── */
function showCodeModal(code, strategy) {
  const overlay = document.createElement("div");
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:10000;display:flex;align-items:center;justify-content:center;padding:20px;";
  const box = document.createElement("div");
  box.style.cssText = "background:#080d18;border:1px solid rgba(0,229,255,.25);border-radius:12px;width:min(720px,90vw);max-height:82vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 0 60px rgba(0,229,255,.1);";
  const hdr = document.createElement("div");
  hdr.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid rgba(0,229,255,.15);background:rgba(0,229,255,.05);flex-shrink:0;";
  hdr.innerHTML = `<span style="font-family:'Oxanium',sans-serif;font-weight:700;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#00e5ff">Strategy: ${esc(strategy)}</span>`;
  const closeBtn = document.createElement("button");
  closeBtn.textContent = "✕ Close";
  closeBtn.style.cssText = "background:none;border:1px solid rgba(0,229,255,.3);color:#00e5ff;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-family:'Oxanium',sans-serif;";
  closeBtn.onclick = () => document.body.removeChild(overlay);
  hdr.appendChild(closeBtn);
  const pre = document.createElement("pre");
  pre.style.cssText = "margin:0;padding:18px;font-family:'JetBrains Mono',monospace;font-size:12.5px;line-height:1.75;overflow:auto;color:#b8d4f0;flex:1;background:rgba(0,0,0,.3);";
  pre.innerHTML = highlightPython(code || "(no code)");
  box.appendChild(hdr); box.appendChild(pre); overlay.appendChild(box);
  overlay.addEventListener("click", e => { if(e.target===overlay) document.body.removeChild(overlay); });
  document.body.appendChild(overlay);
}

/* ── Actions ── */
function copyFixed() {
  const code = window._els.resultCode.textContent;
  navigator.clipboard.writeText(code)
    .then(() => showToast("Copied to clipboard ✓", "success"))
    .catch(() => showToast("Copy failed — select manually", "error"));
}

function useThisFix() {
  if (!state.lastFixedCode) return;
  window._els.codeInput.value = state.lastFixedCode;
  updateLineNumbers(); updateCharCount();
  window._els.codeInput.scrollIntoView({ behavior:"smooth" });
  showToast("Fixed code loaded into editor ✓", "success");
}

/* ── UI helpers ── */
function resetUI(clearSteps = true) {
  const { stepsContainer, emptyState, errorCard, candidatesCard, candidatesGrid, reflectionCard, resultPanel, resultOutBlock } = window._els;
  if (clearSteps) {
    stepsContainer.innerHTML = ""; stepsContainer.appendChild(emptyState);
    emptyState.classList.remove("hidden");
    state.stepMap = {}; state.candidateMap = {};
  }
  [errorCard, candidatesCard, reflectionCard, resultPanel, resultOutBlock].forEach(el => el.classList.add("hidden"));
  candidatesGrid.innerHTML = "";
  state.lastFixedCode = "";
}

function finishRun(success) {
  state.running = false;
  if (state.sse) { state.sse.close(); state.sse = null; }
  const { btnFix } = window._els;
  btnFix.disabled = false;
  btnFix.innerHTML = '<span class="btn-icon">🤖</span> Fix My Code';
  setStatusBadge(success ? "success" : "idle", success ? "Done ✓" : "Idle");
  window._els.progressWrap.classList.remove("active");
}

function setStatusBadge(type, text) { const el=window._els.statusBadge; el.className=`badge badge-${type}`; el.textContent=text; }
function showProgress(pct) { window._els.progressWrap.classList.add("active"); window._els.progressBar.style.width=pct+"%"; }
function advanceProgress(pct) { const pb=window._els.progressBar; if(pct>(parseInt(pb.style.width)||0)) pb.style.width=pct+"%"; }
function showToast(msg, type="info") {
  const t=window._els.toast;
  t.textContent=msg; t.className=`toast toast-${type}`; t.classList.remove("hidden");
  clearTimeout(state._toastTimer);
  state._toastTimer=setTimeout(()=>t.classList.add("hidden"), 3500);
}
function esc(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

window.startFix  = startFix;
window.copyFixed = copyFixed;