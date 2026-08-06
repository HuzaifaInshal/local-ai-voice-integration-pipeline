// -------------------------------------------------------------
// AI VOICE STUDIO - MAIN APPLICATION & SPEECH STREAMING ENGINE
// -------------------------------------------------------------

const sessionId = "kaggle-poc-" + Math.random().toString(36).slice(2);

let chatContainer, input, sendBtn, resetBtn, backBtn, sessionHint, heroText;
let statusPillText, headerMicBadge, bottomMicBtn, heroWaveform;

// View State Management
// Modes: 'IDLE_WAITING_WAKEWORD', 'LISTENING_QUERY', 'SUBMITTING'
let currentVoiceMode = 'IDLE_WAITING_WAKEWORD';
let silenceTimer = null;
let finalQueryText = '';
let speechRecognition = null;

// Expanded Wake Word Regex to capture phonetic variations
const wakeWordRegex = /\b(alfa|alpha|al\s+fa|al\-fa|olfa|elpha|elfa)\b/i;

let activeReasoningBox = null;
let activeReasoningPre = null;
let activeReasoningSummary = null;
let activeReasoningStartTime = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatInlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return html;
}

function splitMarkdownTableRow(line) {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map(cell => cell.trim());
}

function isMarkdownTableSeparator(line) {
  const cells = splitMarkdownTableRow(line);
  return cells.length > 1 && cells.every(cell => /^:?-{3,}:?$/.test(cell));
}

function renderMarkdown(text) {
  text = stripUnsafeAssistantMarkup(text);
  const lines = String(text ?? "").split(/\r?\n/);
  const html = [];
  let paragraph = [];

  function flushParagraph() {
    if (!paragraph.length) return;
    html.push("<p>" + paragraph.map(formatInlineMarkdown).join("<br>") + "</p>");
    paragraph = [];
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const next = lines[i + 1] || "";

    if (line.includes("|") && next.includes("|") && isMarkdownTableSeparator(next)) {
      flushParagraph();
      const headers = splitMarkdownTableRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(splitMarkdownTableRow(lines[i]));
        i++;
      }
      i--;

      html.push('<div class="md-table-wrap"><table class="md-table"><thead><tr>');
      headers.forEach(header => html.push("<th>" + formatInlineMarkdown(header) + "</th>"));
      html.push("</tr></thead><tbody>");
      rows.forEach(row => {
        html.push("<tr>");
        headers.forEach((_, index) => {
          html.push("<td>" + formatInlineMarkdown(row[index] || "") + "</td>");
        });
        html.push("</tr>");
      });
      html.push("</tbody></table></div>");
    } else if (!line.trim()) {
      flushParagraph();
    } else {
      paragraph.push(line);
    }
  }

  flushParagraph();
  return html.join("");
}

function stripUnsafeAssistantMarkup(text) {
  return String(text ?? "")
    .replace(/!\[[^\]]*\]\([^)]+\)/g, "[chart rendered above]")
    .replace(/data:image\/[^;\s]+;base64,[A-Za-z0-9+/=\s]+/g, "[chart rendered above]");
}

function addMsg(role, text) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  if (role === "bot") {
    div.classList.add("markdown");
    div.dataset.rawMarkdown = text || "";
    div.innerHTML = renderMarkdown(text || "");
  } else {
    div.textContent = text;
  }
  chatContainer.appendChild(div);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return div;
}

function addTypingIndicator() {
  const div = document.createElement("div");
  div.className = "typing";
  div.innerHTML = "<span></span><span></span><span></span>";
  chatContainer.appendChild(div);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return div;
}

function addTrace(t) {
  const details = document.createElement("details");
  details.className = "trace";
  const summary = document.createElement("summary");
  summary.textContent = "tool call: " + t.tool + "(" + JSON.stringify(t.args) + ")";
  const pre = document.createElement("pre");
  pre.textContent = t.result;
  details.appendChild(summary);
  details.appendChild(pre);
  chatContainer.appendChild(details);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function appendToken(bubble, text) {
  if (!text) return;
  bubble.dataset.rawMarkdown = (bubble.dataset.rawMarkdown || "") + text;
  bubble.innerHTML = renderMarkdown(bubble.dataset.rawMarkdown);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function appendReasoningToken(text) {
  if (!text) return;
  const cleaned = text.replace(/<\/?think>/gi, "");
  if (!cleaned) return;

  if (!activeReasoningBox) {
    activeReasoningStartTime = Date.now();
    const details = document.createElement("details");
    details.className = "reasoning-box thinking";
    details.open = true;

    const summary = document.createElement("summary");
    summary.innerHTML = `<span class="thinking-spinner">🧠</span> <span>Thinking...</span> <span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span>`;
    details.appendChild(summary);

    const pre = document.createElement("pre");
    details.appendChild(pre);

    activeReasoningSummary = summary;
    activeReasoningPre = pre;
    activeReasoningBox = details;

    chatContainer.appendChild(details);
  }
  activeReasoningPre.textContent += cleaned;
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function finalizeActiveReasoning() {
  if (activeReasoningBox) {
    if (!activeReasoningPre || !activeReasoningPre.textContent.trim()) {
      activeReasoningBox.remove();
    } else {
      activeReasoningBox.classList.remove("thinking");
      if (activeReasoningSummary) {
        const elapsedSec = activeReasoningStartTime ? ((Date.now() - activeReasoningStartTime) / 1000).toFixed(1) : null;
        const timeStr = elapsedSec ? ` (${elapsedSec}s)` : "";
        activeReasoningSummary.innerHTML = `<span>🧠</span> Thought Process${timeStr}`;
      }
      activeReasoningBox.open = false;
    }
    activeReasoningBox = null;
    activeReasoningPre = null;
    activeReasoningSummary = null;
    activeReasoningStartTime = null;
  }
}

function addTableArtifact(event) {
  const wrap = document.createElement("div");
  wrap.className = "artifact";

  const head = document.createElement("div");
  head.className = "artifact-head";
  const title = document.createElement("div");
  title.className = "artifact-title";
  title.textContent = event.title || "Table";
  head.appendChild(title);

  const actions = document.createElement("div");
  actions.className = "artifact-actions";
  const csvBtn = document.createElement("button");
  csvBtn.className = "artifact-action-btn";
  csvBtn.type = "button";
  csvBtn.textContent = "CSV";
  csvBtn.addEventListener("click", () => downloadCsv(event));
  actions.appendChild(csvBtn);
  head.appendChild(actions);
  wrap.appendChild(head);

  const tableWrap = document.createElement("div");
  tableWrap.className = "artifact-table-wrap";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  (event.columns || []).forEach(column => {
    const th = document.createElement("th");
    th.textContent = column;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  (event.rows || []).forEach(row => {
    const tr = document.createElement("tr");
    (event.columns || []).forEach(column => {
      const td = document.createElement("td");
      td.textContent = row[column] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  wrap.appendChild(tableWrap);

  if (event.row_count && event.rows && event.row_count > event.rows.length) {
    const meta = document.createElement("div");
    meta.className = "artifact-meta";
    meta.textContent = `Showing ${event.rows.length} of ${event.row_count} rows.`;
    wrap.appendChild(meta);
  }

  chatContainer.appendChild(wrap);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addChartArtifact(event) {
  const wrap = document.createElement("div");
  wrap.className = "artifact chart-card-wrapper";

  const head = document.createElement("div");
  head.className = "artifact-head";
  const title = document.createElement("div");
  title.className = "artifact-title";
  title.textContent = event.title || "Chart";
  head.appendChild(title);

  const actions = document.createElement("div");
  actions.className = "artifact-actions";
  const pngBtn = document.createElement("button");
  pngBtn.className = "artifact-action-btn";
  pngBtn.type = "button";
  pngBtn.textContent = "PNG";
  actions.appendChild(pngBtn);
  head.appendChild(actions);
  wrap.appendChild(head);

  const canvas = document.createElement("canvas");
  canvas.className = "chart-canvas";
  canvas.width = 720;
  canvas.height = 280;
  wrap.appendChild(canvas);

  const meta = document.createElement("div");
  meta.className = "artifact-meta";
  meta.textContent = chartMetaText(event) + " • Click graph to expand full-screen";
  wrap.appendChild(meta);

  chatContainer.appendChild(wrap);
  drawChart(canvas, event);

  canvas.addEventListener("click", () => openChartModal(event));
  pngBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    downloadCanvasPng(canvas, event.title || "chart");
  });
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addDiagramArtifact(event) {
  const wrap = document.createElement("div");
  wrap.className = "artifact";

  const title = document.createElement("div");
  title.className = "artifact-title";
  title.textContent = event.title || "Diagram";
  wrap.appendChild(title);

  const diagram = document.createElement("div");
  diagram.className = "diagram";
  (event.nodes || []).forEach(node => {
    const card = document.createElement("div");
    card.className = "diagram-node";

    const nodeTitle = document.createElement("div");
    nodeTitle.className = "diagram-node-title";
    nodeTitle.textContent = node.label || node.id || "Node";
    card.appendChild(nodeTitle);

    (node.fields || []).forEach(field => {
      const fieldEl = document.createElement("div");
      fieldEl.className = "diagram-field";
      fieldEl.textContent = field;
      card.appendChild(fieldEl);
    });

    diagram.appendChild(card);
  });
  wrap.appendChild(diagram);

  if (event.edges && event.edges.length) {
    const edges = document.createElement("div");
    edges.className = "diagram-edges";
    event.edges.forEach(edge => {
      const edgeEl = document.createElement("div");
      edgeEl.className = "diagram-edge";
      edgeEl.textContent = `${edge.from} -> ${edge.to} via ${edge.label || "relationship"}`;
      edges.appendChild(edgeEl);
    });
    wrap.appendChild(edges);
  }

  chatContainer.appendChild(wrap);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addDashboardArtifact(event) {
  const wrap = document.createElement("div");
  wrap.className = "dashboard-artifact";

  const head = document.createElement("div");
  head.className = "dashboard-header";

  const title = document.createElement("div");
  title.className = "dashboard-title";
  title.innerHTML = `<span>📊</span> ${escapeHtml(event.title || "Executive Analytics Dashboard")}`;
  head.appendChild(title);

  if (event.subtitle) {
    const sub = document.createElement("div");
    sub.className = "dashboard-subtitle";
    sub.textContent = event.subtitle;
    head.appendChild(sub);
  }
  wrap.appendChild(head);

  if (event.kpis && event.kpis.length) {
    const kpiGrid = document.createElement("div");
    kpiGrid.className = "kpi-grid";

    event.kpis.forEach(kpi => {
      const card = document.createElement("div");
      card.className = "kpi-card";

      const label = document.createElement("div");
      label.className = "kpi-label";
      label.textContent = kpi.label || "";
      card.appendChild(label);

      const value = document.createElement("div");
      value.className = "kpi-value";
      value.textContent = kpi.value || "";
      card.appendChild(value);

      if (kpi.subtext || kpi.trend) {
        const footer = document.createElement("div");
        footer.className = "kpi-footer";

        const sub = document.createElement("span");
        sub.className = "kpi-subtext";
        sub.textContent = kpi.subtext || "";
        footer.appendChild(sub);

        if (kpi.trend) {
          const trend = document.createElement("span");
          trend.className = `kpi-trend ${kpi.trend}`;
          trend.textContent = kpi.trend === "up" ? "▲" : kpi.trend === "down" ? "▼" : "•";
          footer.appendChild(trend);
        }
        card.appendChild(footer);
      }
      kpiGrid.appendChild(card);
    });
    wrap.appendChild(kpiGrid);
  }

  if (event.charts && event.charts.length) {
    const chartsGrid = document.createElement("div");
    chartsGrid.className = "dashboard-charts-grid";

    event.charts.forEach(chartSpec => {
      const card = document.createElement("div");
      card.className = "dashboard-chart-card chart-card-wrapper";

      const cTitle = document.createElement("div");
      cTitle.className = "dashboard-chart-title";
      cTitle.textContent = chartSpec.title || "Chart";
      card.appendChild(cTitle);

      const canvas = document.createElement("canvas");
      canvas.className = "chart-canvas";
      canvas.width = 340;
      canvas.height = 220;
      card.appendChild(canvas);

      card.addEventListener("click", () => openChartModal(chartSpec));

      chartsGrid.appendChild(card);
      setTimeout(() => drawChart(canvas, chartSpec), 10);
    });
    wrap.appendChild(chartsGrid);
  }

  chatContainer.appendChild(wrap);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setUIMode(mode) {
  if (mode === 'hero') {
    document.body.classList.remove('mode-chat');
    document.body.classList.add('mode-hero');
  } else {
    document.body.classList.remove('mode-hero');
    document.body.classList.add('mode-chat');
  }
}

// Main Function to submit user message to server & update UI
async function sendQuery(text) {
  const trimmed = text.trim();
  if (!trimmed) return;

  setUIMode('chat');

  addMsg("user", trimmed);
  input.value = "";
  sendBtn.disabled = true;
  sendBtn.innerHTML = `<span class="btn-loader"></span>`;

  activeReasoningBox = null;
  activeReasoningPre = null;
  activeReasoningSummary = null;
  activeReasoningStartTime = null;

  const typingEl = addTypingIndicator();
  let botBubble = null;

  function finalizeBotBubble() {
    if (botBubble) {
      if (!botBubble.dataset.rawMarkdown || !botBubble.dataset.rawMarkdown.trim()) {
        botBubble.remove();
      }
      botBubble = null;
    }
  }

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: trimmed })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop();

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") continue;

        let event;
        try { event = JSON.parse(payload); } catch { continue; }

        if (event.type === "reasoning") {
          finalizeBotBubble();
          if (typingEl.parentNode) typingEl.remove();
          appendReasoningToken(event.text);
        } else if (event.type === "tool") {
          finalizeActiveReasoning();
          finalizeBotBubble();
          if (typingEl.parentNode) typingEl.remove();
          addTrace(event);
        } else if (event.type === "table") {
          finalizeActiveReasoning();
          finalizeBotBubble();
          if (typingEl.parentNode) typingEl.remove();
          addTableArtifact(event);
        } else if (event.type === "chart") {
          finalizeActiveReasoning();
          finalizeBotBubble();
          if (typingEl.parentNode) typingEl.remove();
          addChartArtifact(event);
        } else if (event.type === "dashboard") {
          finalizeActiveReasoning();
          finalizeBotBubble();
          if (typingEl.parentNode) typingEl.remove();
          addDashboardArtifact(event);
        } else if (event.type === "diagram") {
          finalizeActiveReasoning();
          finalizeBotBubble();
          if (typingEl.parentNode) typingEl.remove();
          addDiagramArtifact(event);
        } else if (event.type === "token") {
          finalizeActiveReasoning();
          if (typingEl.parentNode) typingEl.remove();
          if (!botBubble) botBubble = addMsg("bot", "");
          appendToken(botBubble, event.text);
        } else if (event.type === "error") {
          finalizeActiveReasoning();
          finalizeBotBubble();
          if (typingEl.parentNode) typingEl.remove();
          addMsg("bot", "Error: " + event.message);
        }
      }
    }
  } catch (e) {
    finalizeActiveReasoning();
    finalizeBotBubble();
    if (typingEl.parentNode) typingEl.remove();
    addMsg("bot", "Error: " + e.message);
  } finally {
    finalizeActiveReasoning();
    finalizeBotBubble();
    sendBtn.disabled = false;
    sendBtn.innerHTML = "Send";
    resetVoiceStateToIdle();
  }
}

// -------------------------------------------------------------
// WEB SPEECH RECOGNITION & WAKE WORD ("alfa") LOGIC
// -------------------------------------------------------------

function resetVoiceStateToIdle() {
  currentVoiceMode = 'IDLE_WAITING_WAKEWORD';
  finalQueryText = '';
  if (silenceTimer) clearTimeout(silenceTimer);
  silenceTimer = null;

  if (heroText) {
    heroText.classList.add("placeholder");
    heroText.textContent = 'Say "Alfa" to start';
  }
  if (statusPillText) {
    statusPillText.textContent = 'Say "Alfa" to start • Auto search is on';
  }
  if (headerMicBadge) headerMicBadge.className = "mic-badge listening";
  if (bottomMicBtn) bottomMicBtn.classList.remove("active");
  if (heroWaveform) heroWaveform.classList.remove("active");
  if (input) {
    input.value = '';
    input.placeholder = "Ask something or say 'Alfa'...";
  }

  restartSpeechRecognition();
}

function restartSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    if (statusPillText) statusPillText.textContent = 'Web Speech API not supported in this browser. Please type below.';
    if (headerMicBadge) headerMicBadge.className = "mic-badge off";
    if (heroWaveform) heroWaveform.classList.remove("active");
    if (heroText) heroText.textContent = "Voice input unavailable";
    return;
  }

  if (speechRecognition) {
    speechRecognition.onstart = null;
    speechRecognition.onresult = null;
    speechRecognition.onerror = null;
    speechRecognition.onend = null;
    try { speechRecognition.abort(); } catch (err) { }
  }

  speechRecognition = new SpeechRecognition();
  speechRecognition.continuous = true;
  speechRecognition.interimResults = true;
  speechRecognition.lang = 'en-US';

  speechRecognition.onstart = () => {
    if (headerMicBadge) headerMicBadge.className = "mic-badge listening";
    if (currentVoiceMode === 'LISTENING_QUERY') {
      if (heroWaveform) heroWaveform.classList.add("active");
      if (bottomMicBtn) bottomMicBtn.classList.add("active");
    } else {
      if (heroWaveform) heroWaveform.classList.remove("active");
      if (bottomMicBtn) bottomMicBtn.classList.remove("active");
    }
  };

  speechRecognition.onresult = (event) => {
    let fullTranscript = '';
    for (let i = 0; i < event.results.length; ++i) {
      fullTranscript += event.results[i][0].transcript + ' ';
    }

    const rawSpokenText = fullTranscript.trim();
    const match = rawSpokenText.match(wakeWordRegex);

    if (currentVoiceMode === 'IDLE_WAITING_WAKEWORD') {
      if (match) {
        currentVoiceMode = 'LISTENING_QUERY';
        setUIMode('hero');
        if (heroWaveform) heroWaveform.classList.add("active");
        if (bottomMicBtn) bottomMicBtn.classList.add("active");
        if (statusPillText) statusPillText.textContent = 'Wake word "Alfa" detected • Listening...';
        if (heroText) heroText.classList.remove("placeholder");

        const wakeIndex = match.index;
        let textAfterWake = rawSpokenText.slice(wakeIndex + match[0].length).replace(/^[,\s\-.:]+/, '').trim();

        if (textAfterWake) {
          finalQueryText = textAfterWake;
          if (heroText) heroText.textContent = finalQueryText;
          if (input) input.value = finalQueryText;
          scheduleSilenceEnd();
        } else {
          finalQueryText = '';
          if (heroText) heroText.textContent = 'Listening...';
          if (input) {
            input.value = '';
            input.placeholder = 'Listening...';
          }
        }
      } else {
        if (heroText) {
          heroText.classList.add("placeholder");
          heroText.textContent = 'Say "Alfa" to start';
        }
        if (heroWaveform) heroWaveform.classList.remove("active");
        if (bottomMicBtn) bottomMicBtn.classList.remove("active");
        if (currentVoiceMode === 'IDLE_WAITING_WAKEWORD' && input) {
          input.placeholder = "Ask something or say 'Alfa'...";
        }
      }
    } else if (currentVoiceMode === 'LISTENING_QUERY') {
      setUIMode('hero');
      if (heroWaveform) heroWaveform.classList.add("active");
      if (bottomMicBtn) bottomMicBtn.classList.add("active");

      let queryPart = rawSpokenText;
      if (match) {
        queryPart = rawSpokenText.slice(match.index + match[0].length).replace(/^[,\s\-.:]+/, '').trim();
      }

      if (queryPart) {
        finalQueryText = queryPart;
        if (heroText) {
          heroText.classList.remove("placeholder");
          heroText.textContent = finalQueryText;
        }
        if (input) input.value = finalQueryText;
        scheduleSilenceEnd();
      } else {
        if (heroText) heroText.textContent = 'Listening...';
        if (input && !input.value) {
          input.placeholder = 'Listening...';
        }
      }
    }
  };

  speechRecognition.onerror = (e) => {
    if (e.error !== 'no-speech') {
      console.warn("Speech recognition error:", e.error);
    }
  };

  speechRecognition.onend = () => {
    if (currentVoiceMode !== 'SUBMITTING') {
      try { speechRecognition.start(); } catch (err) { }
    }
  };

  try { speechRecognition.start(); } catch (err) { }
}

function scheduleSilenceEnd() {
  if (silenceTimer) clearTimeout(silenceTimer);
  silenceTimer = setTimeout(() => {
    if (currentVoiceMode === 'LISTENING_QUERY' && finalQueryText.trim()) {
      triggerVoiceSubmit();
    }
  }, 3500);
}

function triggerVoiceSubmit() {
  if (!finalQueryText.trim()) return;
  currentVoiceMode = 'SUBMITTING';
  if (silenceTimer) clearTimeout(silenceTimer);
  silenceTimer = null;

  const textToSend = finalQueryText.trim();

  if (speechRecognition) {
    speechRecognition.onend = null;
    try { speechRecognition.abort(); } catch (err) { }
  }

  sendQuery(textToSend);
}

function toggleActiveListening() {
  if (currentVoiceMode === 'LISTENING_QUERY') {
    if (finalQueryText.trim()) {
      triggerVoiceSubmit();
    } else {
      resetVoiceStateToIdle();
    }
  } else {
    currentVoiceMode = 'LISTENING_QUERY';
    setUIMode('hero');
    if (heroWaveform) heroWaveform.classList.add("active");
    if (bottomMicBtn) bottomMicBtn.classList.add("active");
    if (heroText) {
      heroText.classList.remove("placeholder");
      heroText.textContent = "Listening...";
    }
    if (input) {
      input.value = "";
      input.placeholder = "Listening...";
    }
    if (statusPillText) statusPillText.textContent = "Listening for your voice query...";
  }
}

// DOM Init
window.addEventListener("DOMContentLoaded", () => {
  chatContainer = document.getElementById("chatContainer");
  input = document.getElementById("userInput");
  sendBtn = document.getElementById("sendBtn");
  resetBtn = document.getElementById("resetBtn");
  backBtn = document.getElementById("backBtn");
  sessionHint = document.getElementById("sessionHint");
  heroText = document.getElementById("heroText");
  statusPillText = document.getElementById("statusPillText");
  headerMicBadge = document.getElementById("headerMicBadge");
  bottomMicBtn = document.getElementById("bottomMicBtn");
  heroWaveform = document.getElementById("heroWaveform");

  if (sessionHint) sessionHint.textContent = "session: " + sessionId;

  if (sendBtn && input) {
    sendBtn.addEventListener("click", () => sendQuery(input.value));
    input.addEventListener("keydown", e => { if (e.key === "Enter") sendQuery(input.value); });
  }

  if (backBtn) {
    backBtn.addEventListener("click", () => {
      setUIMode('hero');
      resetVoiceStateToIdle();
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", async () => {
      await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId })
      });
      if (chatContainer) chatContainer.innerHTML = "";
      setUIMode('hero');
      resetVoiceStateToIdle();
    });
  }

  if (bottomMicBtn) bottomMicBtn.addEventListener("click", toggleActiveListening);
  if (heroWaveform) heroWaveform.addEventListener("click", toggleActiveListening);

  resetVoiceStateToIdle();
});
