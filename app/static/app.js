const HISTORY_KEY = "askive_chat_history";

let sessionId = crypto.randomUUID();
let currentMessages = []; // {role, text, sources, timestamp}

const fileInput = document.getElementById("file-input");
const fileNameLabel = document.getElementById("file-name");
const uploadBtn = document.getElementById("upload-btn");
const uploadStatus = document.getElementById("upload-status");
const docListEl = document.getElementById("doc-list");
const docPreviewEl = document.getElementById("doc-preview");
const newChatBtn = document.getElementById("new-chat-btn");
const historyBtn = document.getElementById("history-btn");
const historyPanelEl = document.getElementById("history-panel");

const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const questionInput = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");

const documents = [];
let selectedDocId = null;
let previewObjectUrl = null;

const EMPTY_STATE_HTML = `
  <div class="empty-state">
    <svg width="28" height="28" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M11 14.5C11 12.567 12.567 11 14.5 11H25.5C27.433 11 29 12.567 29 14.5V21.5C29 23.433 27.433 25 25.5 25H18.8L14.2 28.6C13.8 28.9 13.25 28.6 13.25 28.1V25H14.5C12.567 25 11 23.433 11 21.5V14.5Z"
        fill="currentColor"
      />
    </svg>
    <p>Upload a document on the right, then ask anything about it.</p>
  </div>
`;

fileInput.addEventListener("change", () => {
  fileNameLabel.textContent = fileInput.files[0]?.name || "Add a PDF, Word, or text file…";
});

function resizeQuestionInput() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${questionInput.scrollHeight}px`;
}

questionInput.addEventListener("input", resizeQuestionInput);

questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    setUploadStatus("Pick a file first.", true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  uploadBtn.disabled = true;
  setUploadStatus("Uploading and chunking…", false);

  try {
    const res = await fetch("/upload/", { method: "POST", body: formData });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    documents.push({
      id: data.document_id,
      name: file.name,
      file,
      chunks: data.chunks_created,
    });
    renderDocList();
    selectDocument(data.document_id);

    setUploadStatus(`Uploaded — ${data.chunks_created} chunks created.`, false);
    fileInput.value = "";
    fileNameLabel.textContent = "Add a PDF, Word, or text file…";
  } catch (err) {
    setUploadStatus(`Upload failed: ${err.message}`, true);
  } finally {
    uploadBtn.disabled = false;
  }
});

newChatBtn.addEventListener("click", () => {
  startNewChat();
});

historyBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const isOpen = historyPanelEl.classList.toggle("open");
  if (isOpen) renderHistoryList();
});

document.addEventListener("click", (e) => {
  if (!historyPanelEl.contains(e.target) && e.target !== historyBtn) {
    historyPanelEl.classList.remove("open");
  }
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  removeEmptyState();
  addMessage("user", question);
  questionInput.value = "";
  resizeQuestionInput();
  sendBtn.disabled = true;

  const loadingEl = addTypingIndicator();

  try {
    const res = await fetch("/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        session_id: sessionId,
        document_ids: documents.map((d) => d.id),
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    loadingEl.remove();
    addMessage("assistant", data.answer, data.sources);
    persistCurrentSession();
  } catch (err) {
    loadingEl.remove();
    addMessage("error", `Something went wrong: ${err.message}`, null, { record: false });
  } finally {
    sendBtn.disabled = false;
    questionInput.focus();
  }
});

function setUploadStatus(text, isError) {
  uploadStatus.textContent = text;
  uploadStatus.classList.toggle("error", isError);
}

function removeEmptyState() {
  messagesEl.querySelector(".empty-state")?.remove();
}

// --- Chat history (browser-local) ---

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function saveHistory(history) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 30)));
  } catch {
    // localStorage unavailable (private mode, quota, etc.) - history just won't persist.
  }
}

function persistCurrentSession() {
  if (currentMessages.length === 0) return;
  const history = loadHistory();
  const firstUserMsg = currentMessages.find((m) => m.role === "user");
  const title = firstUserMsg ? firstUserMsg.text.slice(0, 60) : "New chat";
  const entry = { sessionId, title, messages: currentMessages, updatedAt: Date.now() };
  const idx = history.findIndex((h) => h.sessionId === sessionId);
  if (idx >= 0) history[idx] = entry;
  else history.unshift(entry);
  saveHistory(history);
}

function startNewChat() {
  persistCurrentSession();
  sessionId = crypto.randomUUID();
  currentMessages = [];
  messagesEl.innerHTML = EMPTY_STATE_HTML;
  historyPanelEl.classList.remove("open");
}

function loadSession(id) {
  persistCurrentSession();
  const entry = loadHistory().find((h) => h.sessionId === id);
  if (!entry) return;

  sessionId = entry.sessionId;
  currentMessages = [...entry.messages];
  messagesEl.innerHTML = "";
  for (const m of currentMessages) {
    renderMessage(m.role, m.text, m.sources, m.timestamp);
  }
  historyPanelEl.classList.remove("open");
}

function renderHistoryList() {
  const history = loadHistory();
  historyPanelEl.innerHTML = "";

  if (history.length === 0) {
    historyPanelEl.innerHTML = '<div class="history-empty">No past chats yet — they\'ll show up here as you go.</div>';
    return;
  }

  for (const entry of history) {
    const item = document.createElement("div");
    item.className = `history-item${entry.sessionId === sessionId ? " active" : ""}`;

    const info = document.createElement("div");
    info.className = "history-item-info";
    info.innerHTML = `
      <div class="history-item-title">${escapeHtml(entry.title || "New chat")}</div>
      <div class="history-item-time">${relativeTime(entry.updatedAt)}</div>
    `;
    info.addEventListener("click", () => loadSession(entry.sessionId));

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "history-delete-btn";
    deleteBtn.title = "Delete this chat";
    deleteBtn.innerHTML =
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 7H20M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M18 7L17.2 19.2A2 2 0 0 1 15.2 21H8.8a2 2 0 0 1-2-1.8L6 7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteSession(entry.sessionId);
    });

    item.appendChild(info);
    item.appendChild(deleteBtn);
    historyPanelEl.appendChild(item);
  }

  const clearAllBtn = document.createElement("button");
  clearAllBtn.type = "button";
  clearAllBtn.className = "history-clear-btn";
  clearAllBtn.textContent = "Clear all history";
  clearAllBtn.addEventListener("click", () => {
    saveHistory([]);
    renderHistoryList();
  });
  historyPanelEl.appendChild(clearAllBtn);
}

function deleteSession(id) {
  const history = loadHistory().filter((h) => h.sessionId !== id);
  saveHistory(history);
  renderHistoryList();
}

function relativeTime(ms) {
  const diff = Date.now() - ms;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(ms).toLocaleDateString();
}

// --- Document list & preview ---

function renderDocList() {
  docListEl.innerHTML = "";
  for (const doc of documents) {
    const item = document.createElement("div");
    item.className = `doc-item${doc.id === selectedDocId ? " active" : ""}`;
    item.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
        <path d="M14 2v6h6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
      </svg>
      <div class="doc-item-text">
        <div class="doc-item-name">${escapeHtml(doc.name)}</div>
        <div class="doc-item-meta">${doc.chunks} chunks</div>
      </div>
    `;
    item.addEventListener("click", () => selectDocument(doc.id));
    docListEl.appendChild(item);
  }
}

async function selectDocument(id) {
  selectedDocId = id;
  renderDocList();

  const doc = documents.find((d) => d.id === id);
  if (!doc) return;

  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = null;
  }

  docPreviewEl.innerHTML = "";

  const name = doc.name.toLowerCase();
  const isPdf = doc.file.type === "application/pdf" || name.endsWith(".pdf");
  const isDocx = name.endsWith(".docx");

  if (isPdf) {
    previewObjectUrl = URL.createObjectURL(doc.file);
    const iframe = document.createElement("iframe");
    iframe.className = "doc-preview-frame";
    iframe.src = previewObjectUrl;
    docPreviewEl.appendChild(iframe);
  } else if (isDocx) {
    try {
      const arrayBuffer = await doc.file.arrayBuffer();
      const { value: html } = await mammoth.convertToHtml({ arrayBuffer });
      const container = document.createElement("div");
      container.className = "doc-preview-docx";
      container.innerHTML = html;
      docPreviewEl.appendChild(container);
    } catch (err) {
      const empty = document.createElement("div");
      empty.className = "doc-preview-empty";
      empty.textContent = `Couldn't render a preview for this Word document (${err.message}), but you can still chat with it below.`;
      docPreviewEl.appendChild(empty);
    }
  } else {
    const text = await doc.file.text();
    const pre = document.createElement("pre");
    pre.className = "doc-preview-text";
    pre.textContent = text;
    docPreviewEl.appendChild(pre);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// --- Chat messages ---

function makeRow(role) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = `avatar ${role === "error" ? "assistant" : role}`;
  avatar.textContent = role === "user" ? "You" : "AI";

  const col = document.createElement("div");
  col.className = "message-col";

  row.appendChild(avatar);
  row.appendChild(col);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { row, col };
}

function addTypingIndicator() {
  const { row, col } = makeRow("assistant");
  const bubble = document.createElement("div");
  bubble.className = "message";
  bubble.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  col.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return row;
}

// Adds a message to the chat: renders it AND records it into currentMessages
// (so it survives a "New chat" switch or page reload via localStorage),
// unless options.record is false (used for transient errors).
function addMessage(role, text, sources, options = {}) {
  const timestamp = Date.now();
  if (options.record !== false) {
    currentMessages.push({ role, text, sources: sources || [], timestamp });
  }
  return renderMessage(role, text, sources, timestamp);
}

function renderMessage(role, text, sources, timestamp) {
  const { row, col } = makeRow(role);

  const bubble = document.createElement("div");
  bubble.className = "message";
  bubble.textContent = text;

  if (sources && sources.length) {
    const details = document.createElement("details");
    details.className = "sources";
    const summary = document.createElement("summary");
    summary.textContent = `${sources.length} source chunk${sources.length > 1 ? "s" : ""}`;
    details.appendChild(summary);
    const ol = document.createElement("ol");
    for (const s of sources) {
      const li = document.createElement("li");
      li.textContent = s;
      ol.appendChild(li);
    }
    details.appendChild(ol);
    bubble.appendChild(details);
  }

  const meta = document.createElement("div");
  meta.className = "message-meta";

  const timestampEl = document.createElement("span");
  timestampEl.className = "timestamp";
  timestampEl.textContent = new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  meta.appendChild(timestampEl);

  if (role === "assistant") {
    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "copy-btn";
    copyBtn.title = "Copy answer";
    copyBtn.innerHTML =
      '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="9" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="M5 15V5a2 2 0 0 1 2-2h10" stroke="currentColor" stroke-width="1.8"/></svg>';
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(text);
        copyBtn.title = "Copied!";
      } catch {
        copyBtn.title = "Copy blocked by browser permissions";
      }
      setTimeout(() => (copyBtn.title = "Copy answer"), 1500);
    });
    meta.appendChild(copyBtn);
  }

  col.appendChild(bubble);
  col.appendChild(meta);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return row;
}
