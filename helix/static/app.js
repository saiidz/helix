"use strict";

const byId = id => document.getElementById(id);

let chatHistory = [];
let previousRole = null;
let conversationId = window.localStorage.getItem("helixConversationId") || null;
let runtimeFeatures = {
  persistent_memory: false,
  persistent_conversations: false,
  routing_scores: false,
  adaptive_reasoning: false,
  streaming: false,
  web: false,
  files: false,
  projects: false,
  tasks: false
};
let staleBackendWarningShown = false;
let currentAbortController = null;

const THEME_KEY = "helixTheme";
const WEB_MODE_KEY = "helixWebMode";
const PROJECT_KEY = "helixProjectId";
let webMode = window.localStorage.getItem(WEB_MODE_KEY) || "auto";
let activeProjectId = window.localStorage.getItem(PROJECT_KEY) || null;
let activeProject = null;
let taskFilter = "open";
const TASK_ALERTS_KEY = "helixTaskAlerts";
let taskAlertsEnabled = window.localStorage.getItem(TASK_ALERTS_KEY) === "true";
const dueTaskSeen = new Set(
  JSON.parse(window.sessionStorage.getItem("helixDueTasksSeen") || "[]")
);

function applyTheme(theme) {
  const nextTheme = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = nextTheme;
  window.localStorage.setItem(THEME_KEY, nextTheme);

  const icon = byId("theme-icon");
  const label = byId("theme-label");
  const button = byId("theme-toggle");

  if (icon) icon.textContent = nextTheme === "dark" ? "☼" : "☾";
  if (label) label.textContent = nextTheme === "dark" ? "Light" : "Dark";
  if (button) {
    button.setAttribute("aria-pressed", nextTheme === "light" ? "true" : "false");
    button.title = nextTheme === "dark"
      ? "Switch to light mode"
      : "Switch to dark mode";
  }
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
}

function setWebMode(mode, announce = true) {
  const allowed = new Set(["auto", "on", "off"]);
  webMode = allowed.has(mode) ? mode : "auto";
  window.localStorage.setItem(WEB_MODE_KEY, webMode);

  const available = runtimeFeatures.web;
  const labelText = !available
    ? "Web Restart"
    : webMode === "on"
      ? "Web On"
      : webMode === "off"
        ? "Web Off"
        : "Web Auto";

  document.querySelectorAll("[data-web-toggle]").forEach(button => {
    button.classList.toggle("active", available && webMode === "on");
    button.classList.toggle("auto", available && webMode === "auto");
    button.setAttribute("aria-pressed", webMode === "on" ? "true" : "false");
    button.title = !available
      ? "Restart Helix to enable the web connector"
      : webMode === "on"
        ? "Web mode On: research every request"
        : webMode === "off"
          ? "Web mode Off: never use live research"
          : "Web mode Auto: research current-information requests";

    button.querySelectorAll(".web-toggle-label").forEach(label => {
      label.textContent = labelText;
    });
  });

  const state = byId("web-cap-state");
  const label = byId("web-cap-label");

  if (state) {
    state.classList.toggle("live", available && webMode !== "off");
  }
  if (label) {
    label.textContent = !available
      ? "Restart"
      : webMode === "on"
        ? "On"
        : webMode === "off"
          ? "Off"
          : "Auto";
  }

  if (announce) {
    toast(
      !available
        ? "Restart Helix to enable web research."
        : webMode === "on"
          ? "Web research is on for every request."
          : webMode === "off"
            ? "Web research is off."
            : "Web research is automatic for fresh/current questions."
    );
  }
}

function cycleWebMode() {
  if (!runtimeFeatures.web) {
    warnStaleBackend();
    return;
  }

  const next = webMode === "auto"
    ? "on"
    : webMode === "on"
      ? "off"
      : "auto";

  setWebMode(next);
}

function shouldAutoUseWeb(text) {
  return /\b(latest|today|current|currently|recent|recently|news|live|right now|this week|this month|search the web|search online|look up|internet|online|2026)\b/i.test(text);
}

const roleName = role => {
  if (!role) return "Auto";
  return role.charAt(0).toUpperCase() + role.slice(1);
};

const roleClass = role => role || "auto";

async function api(path, method = "GET", body = null, id = null) {
  const key = byId("key").value.trim();

  if (!key) throw new Error("Local access key missing.");

  const headers = { Authorization: "Bearer " + key };
  if (body) headers["Content-Type"] = "application/json";
  if (id) headers["Idempotency-Key"] = id;

  const response = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null
  });

  const data = await response.json();

  if (!response.ok) {
    const error = new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request rejected (" + response.status + ")."
    );
    error.status = response.status;
    throw error;
  }

  return data;
}

async function readHealth() {
  const response = await fetch("/health", { cache: "no-store" });
  if (!response.ok) throw new Error("Helix health check failed.");
  return response.json();
}

function warnStaleBackend() {
  if (staleBackendWarningShown) return;
  staleBackendWarningShown = true;
  toast("Helix UI is newer than the running backend. Chat will still work; restart Helix to enable memory and the newest routing.");
}

function toast(text) {
  const box = byId("toast");
  box.textContent = text;
  box.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => box.classList.remove("show"), 2200);
}

function removeWelcome() {
  const welcome = byId("welcome");
  if (welcome) welcome.remove();
}

async function ensureConversation() {
  if (!runtimeFeatures.persistent_conversations) return null;
  if (conversationId) return conversationId;

  try {
    const data = await api(
      "/api/conversations",
      "POST",
      { title: "New conversation" }
    );

    conversationId = data.conversation.id;
    window.localStorage.setItem("helixConversationId", conversationId);
    return conversationId;
  } catch (error) {
    if (error.status === 404) {
      runtimeFeatures.persistent_conversations = false;
      runtimeFeatures.persistent_memory = false;
      conversationId = null;
      window.localStorage.removeItem("helixConversationId");
      warnStaleBackend();
      return null;
    }
    throw error;
  }
}

function renderConversationMessages(conversation) {
  const stored = conversation.messages || [];
  byId("messages").innerHTML = "";
  chatHistory = [];
  previousRole = null;

  if (!stored.length) {
    byId("messages").innerHTML = welcomeMarkup();
    wireIntentCards();
    return;
  }

  for (const item of stored) {
    if (item.role === "user") {
      message("You", item.content, "user");
    } else {
      message("Helix", item.content, "assistant", "restored from local conversation");
    }

    chatHistory.push({ role: item.role, content: item.content });
  }
}

function renderConversationList(conversations) {
  const list = byId("conversation-list");
  if (!list) return;
  list.innerHTML = "";

  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "conversation-empty";
    empty.textContent = "No conversations yet";
    list.append(empty);
    return;
  }

  for (const conversation of conversations) {
    const row = document.createElement("div");
    row.className = "conversation-row";
    row.classList.toggle("active", conversation.id === conversationId);
    row.dataset.conversationId = conversation.id;

    const open = document.createElement("button");
    open.type = "button";
    open.className = "conversation-open";
    open.dataset.conversationOpen = conversation.id;
    open.title = conversation.title;

    const title = document.createElement("span");
    title.textContent = conversation.title || "New conversation";

    const when = document.createElement("small");
    when.textContent = new Date(conversation.updated_at).toLocaleDateString();

    open.append(title, when);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "conversation-delete";
    remove.dataset.conversationDelete = conversation.id;
    remove.setAttribute("aria-label", "Delete " + (conversation.title || "conversation"));
    remove.textContent = "×";

    row.append(open, remove);
    list.append(row);
  }
}

async function refreshConversationList() {
  if (!runtimeFeatures.persistent_conversations) return;

  try {
    const data = await api("/api/conversations?limit=12");
    renderConversationList(data.conversations || []);
  } catch (error) {
    const list = byId("conversation-list");
    if (list) {
      list.innerHTML = '<div class="conversation-empty">Could not load history</div>';
    }
  }
}

async function loadConversationById(id, announce = true) {
  if (!runtimeFeatures.persistent_conversations) return;

  const data = await api("/api/conversations/" + encodeURIComponent(id));
  conversationId = data.conversation.id;
  window.localStorage.setItem("helixConversationId", conversationId);
  renderConversationMessages(data.conversation);
  await refreshAttachments();
  await refreshConversationList();

  if (announce) {
    toast("Conversation restored.");
  }
}

async function loadConversation() {
  if (!runtimeFeatures.persistent_conversations || !conversationId) return;

  try {
    await loadConversationById(conversationId, false);
  } catch (error) {
    if (String(error.message).includes("Conversation not found")) {
      conversationId = null;
      window.localStorage.removeItem("helixConversationId");
      return;
    }
    throw error;
  }
}

function openMemoryDrawer() {
  if (!runtimeFeatures.persistent_memory) {
    warnStaleBackend();
    return;
  }

  byId("memory-drawer").hidden = false;
  byId("memory-backdrop").hidden = false;
  refreshMemories();
}

function closeMemoryDrawer() {
  byId("memory-drawer").hidden = true;
  byId("memory-backdrop").hidden = true;
}

function updateActiveProjectChip() {
  const chip = byId("active-project-chip");
  if (!chip) return;

  if (!activeProject) {
    chip.hidden = true;
    chip.textContent = "";
    return;
  }

  chip.hidden = false;
  chip.textContent = "⌘ " + activeProject.name + " · " + activeProject.file_count + " files";
}

function renderProjectFiles(files) {
  const list = byId("project-file-list");
  if (!list) return;
  list.innerHTML = "";

  if (!files.length) {
    const empty = document.createElement("div");
    empty.className = "project-empty";
    empty.textContent = "No project files imported yet.";
    list.append(empty);
    return;
  }

  for (const file of files.slice(0, 250)) {
    const row = document.createElement("div");
    row.className = "project-file-row";

    const path = document.createElement("span");
    path.textContent = file.path;
    path.title = file.path;

    const lang = document.createElement("small");
    lang.textContent = file.language;

    row.append(path, lang);
    list.append(row);
  }
}

function renderProjects(projects) {
  const list = byId("project-list");
  if (!list) return;
  list.innerHTML = "";

  if (!projects.length) {
    const empty = document.createElement("div");
    empty.className = "project-empty";
    empty.textContent = "No projects yet. Create one, then import a folder.";
    list.append(empty);
    return;
  }

  for (const project of projects) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "project-row";
    button.dataset.projectId = project.id;
    button.classList.toggle("active", project.id === activeProjectId);

    const copy = document.createElement("span");
    copy.innerHTML = "<strong></strong><small></small>";
    copy.querySelector("strong").textContent = project.name;
    copy.querySelector("small").textContent = project.file_count + " files";

    const arrow = document.createElement("b");
    arrow.textContent = "→";

    button.append(copy, arrow);
    list.append(button);
  }
}

async function refreshProjects() {
  if (!runtimeFeatures.projects) return;

  try {
    const data = await api("/api/projects?limit=50");
    renderProjects(data.projects || []);

    if (activeProjectId) {
      const found = (data.projects || []).find(item => item.id === activeProjectId);
      if (!found) {
        activeProjectId = null;
        activeProject = null;
        window.localStorage.removeItem(PROJECT_KEY);
        updateActiveProjectChip();
        byId("project-detail").hidden = true;
      }
    }
  } catch (error) {
    toast("Projects: " + error.message);
  }
}

async function loadProject(id, announce = true) {
  if (!runtimeFeatures.projects) {
    warnStaleBackend();
    return;
  }

  const data = await api("/api/projects/" + encodeURIComponent(id));
  activeProjectId = data.project.id;
  activeProject = data.project;
  window.localStorage.setItem(PROJECT_KEY, activeProjectId);

  byId("project-detail").hidden = false;
  byId("project-detail-name").textContent = activeProject.name;
  byId("project-file-count").textContent = activeProject.file_count + " files";
  renderProjectFiles(data.files || []);
  updateActiveProjectChip();
  renderProjects((await api("/api/projects?limit=50")).projects || []);

  if (announce) {
    toast("Project context active: " + activeProject.name);
  }
}

function openProjectsDrawer() {
  if (!runtimeFeatures.projects) {
    warnStaleBackend();
    return;
  }

  byId("projects-drawer").hidden = false;
  byId("projects-backdrop").hidden = false;
  refreshProjects();

  if (activeProjectId) {
    loadProject(activeProjectId, false).catch(() => {});
  }
}

function closeProjectsDrawer() {
  byId("projects-drawer").hidden = true;
  byId("projects-backdrop").hidden = true;
}

function openTasksDrawer() {
  if (!runtimeFeatures.tasks) {
    warnStaleBackend();
    return;
  }

  byId("tasks-drawer").hidden = false;
  byId("tasks-backdrop").hidden = false;
  refreshTasks();
}

function closeTasksDrawer() {
  byId("tasks-drawer").hidden = true;
  byId("tasks-backdrop").hidden = true;
}

function renderTasks(tasks) {
  const list = byId("task-list");
  if (!list) return;
  list.innerHTML = "";

  if (!tasks.length) {
    const empty = document.createElement("div");
    empty.className = "task-empty";
    empty.textContent = taskFilter === "done"
      ? "No completed tasks yet."
      : taskFilter === "all"
        ? "No tasks yet."
        : "No open tasks. Add one or say “Add task …” in chat.";
    list.append(empty);
    return;
  }

  for (const task of tasks) {
    const card = document.createElement("article");
    card.className = "task-item";
    card.classList.toggle("done", task.status === "done");
    card.dataset.taskId = task.id;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "task-toggle";
    toggle.dataset.taskAction = "toggle";
    toggle.dataset.done = task.status === "done" ? "true" : "false";
    toggle.setAttribute(
      "aria-label",
      task.status === "done" ? "Reopen task" : "Complete task"
    );
    toggle.textContent = task.status === "done" ? "✓" : "";

    const copy = document.createElement("div");
    copy.className = "task-copy";

    const title = document.createElement("strong");
    title.textContent = task.title;

    const details = document.createElement("p");
    details.textContent = task.details || "";
    details.hidden = !task.details;

    const meta = document.createElement("small");
    if (task.due_at) {
      const due = new Date(task.due_at);
      meta.textContent = "Due " + (Number.isNaN(due.getTime()) ? task.due_at : due.toLocaleString());
    } else {
      meta.textContent = task.status === "done" ? "Completed" : "No due time";
    }

    copy.append(title, details, meta);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "task-delete";
    remove.dataset.taskAction = "delete";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "Delete " + task.title);

    card.append(toggle, copy, remove);
    list.append(card);
  }
}

async function refreshTasks() {
  if (!runtimeFeatures.tasks) return;

  try {
    const data = await api(
      "/api/tasks?status=" + encodeURIComponent(taskFilter) + "&limit=100"
    );
    renderTasks(data.tasks || []);

    const open = taskFilter === "open"
      ? (data.tasks || []).length
      : (await api("/api/tasks?status=open&limit=100")).tasks.length;

    const badge = byId("tasks-nav")?.querySelector("em");
    const cap = byId("task-cap-label");
    if (badge) badge.textContent = open ? String(open) : "Ready";
    if (cap) cap.textContent = open ? open + " open" : "Ready";
  } catch (error) {
    const list = byId("task-list");
    if (list) {
      list.innerHTML = '<div class="task-empty">Could not load tasks</div>';
    }
    toast("Tasks: " + error.message);
  }
}

function updateTaskAlertButton() {
  const button = byId("task-alerts");
  if (!button) return;

  const supported = "Notification" in window;
  const granted = supported && Notification.permission === "granted";
  button.classList.toggle("active", taskAlertsEnabled && granted);
  button.textContent =
    taskAlertsEnabled && granted
      ? "Alerts on"
      : supported && Notification.permission === "denied"
        ? "Alerts blocked"
        : "Enable alerts";
}

async function enableTaskAlerts() {
  if (!("Notification" in window)) {
    toast("This browser does not support desktop notifications.");
    return;
  }

  let permission = Notification.permission;
  if (permission === "default") {
    permission = await Notification.requestPermission();
  }

  taskAlertsEnabled = permission === "granted";
  window.localStorage.setItem(TASK_ALERTS_KEY, taskAlertsEnabled ? "true" : "false");
  updateTaskAlertButton();

  toast(
    taskAlertsEnabled
      ? "Task alerts enabled while Helix is open."
      : "Task alerts were not enabled."
  );
}

async function checkDueTasks() {
  if (!runtimeFeatures.tasks || !byId("key")?.value.trim()) return;

  try {
    const data = await api("/api/tasks?status=open&limit=100");
    const now = Date.now();

    for (const task of data.tasks || []) {
      if (!task.due_at || dueTaskSeen.has(task.id)) continue;

      const due = new Date(task.due_at).getTime();
      if (Number.isNaN(due) || due > now) continue;

      dueTaskSeen.add(task.id);
      window.sessionStorage.setItem(
        "helixDueTasksSeen",
        JSON.stringify([...dueTaskSeen])
      );

      toast("Task due: " + task.title);

      if (
        taskAlertsEnabled &&
        "Notification" in window &&
        Notification.permission === "granted"
      ) {
        new Notification("Helix task due", {
          body: task.title,
          tag: "helix-task-" + task.id
        });
      }
    }
  } catch (_) {
    // Due checking is best-effort; normal chat/task operations surface their own errors.
  }
}

async function importProjectFolder(fileList) {
  if (!runtimeFeatures.projects || !activeProjectId) {
    throw new Error("Select a project before importing files.");
  }

  const files = Array.from(fileList || []).slice(0, 400);
  if (!files.length) return;

  const allowed = new Set([
    "txt","md","markdown","json","yaml","yml","toml","ini","cfg","csv","tsv",
    "py","js","mjs","cjs","ts","tsx","jsx","java","c","h","cpp","hpp","cs",
    "go","rs","rb","php","swift","kt","kts","sql","sh","ps1","bat","cmd",
    "html","css","scss","xml","vue","svelte","graphql","gql","properties","gradle"
  ]);
  const allowedNames = new Set([
    "dockerfile","makefile","procfile","gemfile","rakefile","license","readme",
    "agents.md","claude.md",".gitignore",".dockerignore",".editorconfig"
  ]);

  const prepared = [];
  let skipped = 0;

  for (const file of files) {
    const relative = file.webkitRelativePath || file.name;
    const leaf = file.name.toLowerCase();
    const extension = leaf.includes(".") ? leaf.split(".").pop() : "";
    const allowedPath =
      allowed.has(extension) ||
      allowedNames.has(leaf) ||
      leaf.endsWith(".env.example");

    if (!allowedPath || file.size > 500000) {
      skipped += 1;
      continue;
    }

    let content;
    try {
      content = await file.text();
    } catch (_) {
      skipped += 1;
      continue;
    }

    if (!content.trim() || content.includes("\u0000")) {
      skipped += 1;
      continue;
    }

    prepared.push({ path: relative, content });
  }

  let imported = 0;
  let batch = [];
  let batchChars = 0;

  async function flushBatch() {
    if (!batch.length) return;

    const data = await api(
      "/api/projects/" + encodeURIComponent(activeProjectId) + "/files/batch",
      "POST",
      { files: batch }
    );

    imported += (data.added || []).length;
    skipped += (data.skipped || []).length;
    batch = [];
    batchChars = 0;
  }

  for (const item of prepared) {
    const size = item.path.length + item.content.length;

    if (batch.length >= 20 || (batch.length && batchChars + size > 450000)) {
      await flushBatch();
    }

    batch.push(item);
    batchChars += size;
  }

  await flushBatch();

  await loadProject(activeProjectId, false);
  await refreshProjects();
  toast(
    "Imported " + imported + " project file(s)" +
    (skipped ? " · skipped " + skipped : "") + "."
  );
}

function renderFileChips(files) {
  const wrap = byId("file-chips");
  if (!wrap) return;
  wrap.innerHTML = "";

  for (const file of files) {
    const chip = document.createElement("span");
    chip.className = "file-chip";
    chip.title = file.name + " · " + Math.max(1, Math.round(file.size_bytes / 1024)) + " KB";

    const name = document.createElement("span");
    name.className = "file-chip-name";
    name.textContent = file.name;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.fileId = file.id;
    remove.setAttribute("aria-label", "Remove " + file.name);
    remove.textContent = "×";

    chip.append(name, remove);
    wrap.append(chip);
  }
}

async function refreshAttachments() {
  if (!runtimeFeatures.files || !conversationId) {
    renderFileChips([]);
    return;
  }

  try {
    const data = await api("/api/files/" + encodeURIComponent(conversationId));
    renderFileChips(data.files || []);
  } catch (error) {
    toast("Files: " + error.message);
  }
}

async function attachFiles(fileList) {
  if (!runtimeFeatures.files) {
    warnStaleBackend();
    return;
  }

  await ensureConversation();
  if (!conversationId) {
    throw new Error("A conversation is required before attaching files.");
  }

  const files = Array.from(fileList || []).slice(0, 5);
  if (!files.length) return;

  let added = 0;

  for (const file of files) {
    if (file.size > 750000) {
      toast(file.name + " is too large. Keep text/code files under about 750 KB.");
      continue;
    }

    const content = await file.text();
    if (!content.trim()) {
      toast(file.name + " is empty or not readable as text.");
      continue;
    }

    await api("/api/files", "POST", {
      conversation_id: conversationId,
      name: file.name,
      mime_type: file.type || "text/plain",
      content
    });
    added += 1;
  }

  await refreshAttachments();

  if (added) {
    toast("Attached " + added + " local file(s).");
  }
}

function renderMemoryList(memories) {
  const list = byId("memory-list");
  list.innerHTML = "";

  if (!memories.length) {
    const empty = document.createElement("div");
    empty.className = "memory-empty";
    empty.textContent = "No saved memories yet. Add one here or tell Helix “Remember that …”";
    list.append(empty);
    return;
  }

  for (const item of memories) {
    const card = document.createElement("article");
    card.className = "memory-item";
    card.dataset.memoryId = item.id;

    const top = document.createElement("div");
    top.className = "memory-item-top";

    const kind = document.createElement("span");
    kind.className = "memory-kind";
    kind.textContent = item.kind + (item.pinned ? " · pinned" : "");

    const actions = document.createElement("div");
    actions.className = "memory-item-actions";

    const pin = document.createElement("button");
    pin.type = "button";
    pin.dataset.memoryAction = "pin";
    pin.dataset.pinned = item.pinned ? "true" : "false";
    pin.textContent = item.pinned ? "Unpin" : "Pin";

    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.memoryAction = "delete";
    remove.textContent = "Delete";

    actions.append(pin, remove);
    top.append(kind, actions);

    const text = document.createElement("p");
    text.textContent = item.content;

    const meta = document.createElement("div");
    meta.className = "memory-item-meta";
    meta.textContent = "Source: " + item.source;

    card.append(top, text, meta);
    list.append(card);
  }
}

async function refreshMemories() {
  if (!runtimeFeatures.persistent_memory) return;

  try {
    const data = await api("/api/memories?limit=100");
    renderMemoryList(data.memories || []);
  } catch (error) {
    byId("memory-list").innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "memory-empty";
    empty.textContent = error.message;
    byId("memory-list").append(empty);
  }

  await refreshKnowledge();
}

function renderKnowledgeList(entries) {
  const list = byId("knowledge-list");
  if (!list) return;
  list.innerHTML = "";

  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "knowledge-empty";
    empty.textContent = "No sourced web knowledge saved yet.";
    list.append(empty);
    return;
  }

  for (const entry of entries) {
    const card = document.createElement("article");
    card.className = "knowledge-item";

    const link = document.createElement("a");
    link.href = entry.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = entry.title;

    const query = document.createElement("small");
    query.textContent = "Learned from: " + entry.query;

    const time = document.createElement("small");
    time.textContent = "Updated: " + new Date(entry.updated_at).toLocaleString();

    card.append(link, query, time);
    list.append(card);
  }
}

async function refreshKnowledge() {
  const list = byId("knowledge-list");
  if (!list) return;

  if (!runtimeFeatures.web) {
    list.innerHTML = '<div class="knowledge-empty">Restart Helix to enable sourced web knowledge.</div>';
    return;
  }

  try {
    const data = await api("/api/knowledge?limit=50");
    renderKnowledgeList(data.knowledge || []);

    const label = byId("knowledge-cap-label");
    if (label) {
      label.textContent = (data.knowledge || []).length + " sourced";
    }
  } catch (error) {
    list.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "knowledge-empty";
    empty.textContent = error.message;
    list.append(empty);
  }
}

function appendInline(parent, text) {
  const pattern = /(\*\*[^*]+\*\*)/g;
  let last = 0;
  const matches = text.matchAll(pattern);

  for (const match of matches) {
    if (match.index > last) {
      parent.append(document.createTextNode(text.slice(last, match.index)));
    }

    const strong = document.createElement("strong");
    strong.textContent = match[0].slice(2, -2);
    parent.append(strong);
    last = match.index + match[0].length;
  }

  if (last < text.length) {
    parent.append(document.createTextNode(text.slice(last)));
  }
}

function renderRichText(container, text) {
  const lines = text.replace(/\r/g, "").split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(line.trim())) {
      const list = document.createElement("ul");

      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        const item = document.createElement("li");
        appendInline(item, lines[i].trim().replace(/^[-*]\s+/, ""));
        list.append(item);
        i += 1;
      }

      container.append(list);
      continue;
    }

    if (/^\d+\.\s+/.test(line.trim())) {
      const list = document.createElement("ol");

      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        const item = document.createElement("li");
        appendInline(item, lines[i].trim().replace(/^\d+\.\s+/, ""));
        list.append(item);
        i += 1;
      }

      container.append(list);
      continue;
    }

    const paragraph = document.createElement("p");
    appendInline(paragraph, line);
    container.append(paragraph);
    i += 1;
  }
}

function appendSources(box, sources, headingText = "Web sources", prefix = "") {
  if (!Array.isArray(sources) || !sources.length) return;

  const wrap = document.createElement("div");
  wrap.className = "sources";

  const heading = document.createElement("div");
  heading.className = "sources-title";
  heading.textContent = headingText;
  wrap.append(heading);

  sources.forEach((source, index) => {
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    const label = source.index || (index + 1);
    link.textContent = "[" + prefix + label + "] " + source.title;
    wrap.append(link);
  });

  box.append(wrap);
}

function message(label, text, type, meta = "", sources = [], knowledge = []) {
  removeWelcome();

  const box = document.createElement("div");
  box.className = "message " + type;

  const title = document.createElement("b");
  title.textContent = label;
  box.append(title);

  const body = document.createElement("div");
  body.className = "message-body";

  if (type.includes("assistant")) {
    renderRichText(body, text);
  } else {
    const p = document.createElement("p");
    p.textContent = text;
    body.append(p);
  }

  box.append(body);

  if (meta) {
    const tag = document.createElement("div");
    tag.className = "meta";
    tag.textContent = meta;
    box.append(tag);
  }

  appendSources(box, sources, "Live web sources");
  appendSources(box, knowledge, "Learned knowledge", "K");
  byId("messages").append(box);
  box.scrollIntoView({ block: "end", behavior: "smooth" });
  return box;
}

function pendingMessage(role) {
  removeWelcome();

  const box = document.createElement("div");
  box.className = "message assistant pending";

  const title = document.createElement("b");
  title.textContent = role ? "Helix " + roleName(role) : "Helix";

  const typing = document.createElement("div");
  typing.className = "typing";
  typing.innerHTML = "<i></i><i></i><i></i>";

  box.append(title, typing);
  byId("messages").append(box);
  box.scrollIntoView({ block: "end", behavior: "smooth" });
  return box;
}

function streamingMessage(role) {
  removeWelcome();

  const box = document.createElement("div");
  box.className = "message assistant streaming";

  const title = document.createElement("b");
  title.textContent = role ? "Helix " + roleName(role) : "Helix";

  const body = document.createElement("div");
  body.className = "message-body live-output";
  body.textContent = "";

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = "streaming…";

  box.append(title, body, meta);
  byId("messages").append(box);
  box.scrollIntoView({ block: "end", behavior: "smooth" });

  return { box, title, body, meta, text: "", sources: [], knowledge: [], files: [] };
}

function setGenerationState(active) {
  const send = byId("send");
  if (active) {
    send.disabled = false;
    send.textContent = "Stop";
    send.classList.add("stop");
  } else {
    send.disabled = false;
    send.textContent = "Send";
    send.classList.remove("stop");
  }
}

async function streamChat(payload, selectedRole) {
  const key = byId("key").value.trim();
  if (!key) throw new Error("Local access key missing.");

  currentAbortController = new AbortController();
  setGenerationState(true);

  const requestId = crypto.randomUUID();
  let response;

  try {
    response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Idempotency-Key": requestId
      },
      body: JSON.stringify(payload),
      signal: currentAbortController.signal
    });
  } catch (error) {
    currentAbortController = null;
    setGenerationState(false);
    throw error;
  }

  if (!response.ok) {
    let detail = "Streaming request rejected (" + response.status + ").";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch (_) {}

    currentAbortController = null;
    setGenerationState(false);
    throw new Error(detail);
  }

  const live = streamingMessage(selectedRole);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let metaEvent = null;
  let doneEvent = null;

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const raw of lines) {
        if (!raw.trim()) continue;
        const event = JSON.parse(raw);

        if (event.type === "meta") {
          metaEvent = event;
          live.title.textContent = "Helix " + roleName(event.role);
          updateRoute(
            event.role,
            event.reason || "Routed by Helix",
            event.routing_confidence,
            event.reasoning_mode
          );
          live.sources = event.web_sources || [];
          live.knowledge = event.knowledge_used || [];
          live.files = event.files_used || [];
          if (event.knowledge_learned) {
            toast("Helix learned " + event.knowledge_learned + " sourced web item(s) locally.");
            refreshKnowledge();
          }
          if (event.web_error) toast("Web: " + event.web_error);
          if (event.memory_saved) {
            toast("Helix saved that to your private local memory.");
            refreshMemories();
          }
          if (event.task_saved) {
            toast("Helix added “" + event.task_saved.title + "” to your task list. No notification was scheduled.");
            refreshTasks();
          }
        } else if (event.type === "delta") {
          live.text += event.text || "";
          live.body.textContent = live.text;
          live.box.scrollIntoView({ block: "end" });
        } else if (event.type === "done") {
          doneEvent = event;
        } else if (event.type === "error") {
          throw new Error(event.detail || "Streaming request failed.");
        }
      }
    }

    live.box.classList.remove("streaming");
    live.body.innerHTML = "";
    renderRichText(live.body, live.text || "No visible response was returned.");

    const providerMode = metaEvent?.provider_mode || "local";
    const modelId = metaEvent?.model_id || "model";
    const cost = typeof doneEvent?.model_cost_usd === "number"
      ? doneEvent.model_cost_usd.toFixed(6)
      : "0.000000";

    live.meta.textContent =
      providerMode + " · " + modelId + " · $" + cost +
      (metaEvent?.memory_used?.length ? " · " + metaEvent.memory_used.length + " memory" : "") +
      (live.files.length ? " · " + live.files.length + " file" + (live.files.length === 1 ? "" : "s") : "") +
      (live.sources.length ? " · web grounded" : "") +
      " · unverified";

    appendSources(live.box, live.sources, "Live web sources");
    appendSources(live.box, live.knowledge, "Learned knowledge", "K");

    return {
      text: live.text,
      role: metaEvent?.role || selectedRole || "companion",
      meta: metaEvent,
      done: doneEvent
    };
  } catch (error) {
    if (error.name === "AbortError") {
      live.box.classList.remove("streaming");
      live.body.textContent = live.text || "Generation stopped.";
      live.meta.textContent = "stopped by user · partial response not saved";
      toast("Generation stopped.");
      return { aborted: true, text: live.text };
    }
    live.box.remove();
    throw error;
  } finally {
    currentAbortController = null;
    setGenerationState(false);
  }
}

function updateRoute(role, reason = "", confidence = null, mode = "") {
  const actualRole = role || "";
  const target = byId("route-target");
  const name = roleName(actualRole);

  let detail = reason || (actualRole ? "Selected explicitly" : "Waiting for a task");

  if (typeof confidence === "number") {
    detail += " · " + Math.round(confidence * 100) + "%";
  }

  if (mode) {
    detail += " · " + mode;
  }

  target.className = "route-target " + roleClass(actualRole);
  target.innerHTML =
    '<span class="brain-dot ' + roleClass(actualRole) + '"></span>' +
    "<div><strong>" + name + "</strong><small>" +
    detail +
    "</small></div>";

  byId("route-badge").textContent = name.toUpperCase();
}

function setRole(role) {
  byId("role").value = role;

  document.querySelectorAll(".brain-choice").forEach(button => {
    button.classList.toggle("active", button.dataset.role === role);
  });

  byId("composer-mode").innerHTML =
    '<span class="brain-dot ' + roleClass(role) + '"></span> ' +
    (role ? roleName(role) : "Auto route");

  byId("thinking-mode").textContent =
    role === "sage"
      ? "Deep reasoning"
      : role === "engineer"
        ? "Fast build mode"
        : role === "companion"
          ? "Fast conversation"
          : "Fast by default";

  updateRoute(role);
}

function welcomeMarkup() {
  return [
    '<div id="welcome" class="welcome">',
    '<div class="hero-orb" aria-hidden="true"><div class="hero-ring ring-a"></div><div class="hero-ring ring-b"></div><div class="hero-core">H</div></div>',
    '<div class="eyebrow">YOUR UNIVERSAL AI · LOCAL FIRST</div>',
    '<h1>What should Helix handle?</h1>',
    '<p class="welcome-copy">Ask naturally. Helix chooses Companion, Engineer, or Sage, keeps the route visible, and only uses capabilities you have actually connected.</p>',
    '<div class="intent-grid">',
    '<button type="button" class="intent-card" data-role-prompt="companion" data-prompt="Help me organize what I need to do today and prioritize it."><span class="intent-icon companion">C</span><span><strong>Run my day</strong><small>Plan, organize, explain, remember context</small></span><b>→</b></button>',
    '<button type="button" class="intent-card" data-role-prompt="engineer" data-prompt="Help me work on my software project. Start by asking what I want to build or fix."><span class="intent-icon engineer">E</span><span><strong>Build something</strong><small>Code, debug, architecture, systems</small></span><b>→</b></button>',
    '<button type="button" class="intent-card" data-role-prompt="sage" data-prompt="Help me reason deeply about a difficult problem."><span class="intent-icon sage">S</span><span><strong>Think deeply</strong><small>Research, compare, reason, verify</small></span><b>→</b></button>',
    "</div>",
    '<div class="vision-strip">',
    '<div><span class="vision-dot live"></span><strong>Local AI</strong><small>Connected</small></div>',
    '<div><span class="vision-dot live"></span><strong>Long-term memory</strong><small>Connected</small></div>',
    '<div><span class="vision-dot live"></span><strong>Internet</strong><small>Auto + opt-in</small></div>',
    '<div><span class="vision-dot"></span><strong>Voice</strong><small>Planned</small></div>',
    '<div><span class="vision-dot"></span><strong>Actions</strong><small>Planned</small></div>',
    "</div>",
    "</div>"
  ].join("");
}

function resetChat() {
  chatHistory = [];
  previousRole = null;
  conversationId = null;
  window.localStorage.removeItem("helixConversationId");
  setRole("");
  byId("messages").innerHTML = welcomeMarkup();
  renderFileChips([]);
  wireIntentCards();
  byId("prompt").focus();
}

async function refreshStatus() {
  const dot = byId("runtime-dot");

  try {
    const results = await Promise.all([
      api("/api/models"),
      api("/api/meter"),
      readHealth()
    ]);
    const models = results[0];
    const meter = results[1];
    const health = results[2];
    const knowledgeStatus = health.capabilities?.knowledge_cache
      ? await api("/api/knowledge/status").catch(() => ({ count: 0 }))
      : { count: 0 };

    const advertised = health.capabilities || {};
    const legacyMemory = health.memory === "local_sqlite";

    runtimeFeatures = {
      persistent_memory: Boolean(advertised.persistent_memory || legacyMemory),
      persistent_conversations: Boolean(advertised.persistent_conversations || legacyMemory),
      routing_scores: Boolean(advertised.routing_scores),
      adaptive_reasoning: Boolean(advertised.adaptive_reasoning),
      streaming: Boolean(advertised.streaming),
      web: Boolean(advertised.web),
      files: Boolean(advertised.files),
      projects: Boolean(advertised.projects),
      tasks: Boolean(advertised.tasks)
    };

    setWebMode(webMode, false);

    document.querySelectorAll("[data-file-picker]").forEach(button => {
      button.disabled = !runtimeFeatures.files;
      button.title = runtimeFeatures.files
        ? "Attach text or code files"
        : "Restart Helix to enable local file attachments";
    });

    const fileState = byId("file-cap-state");
    const fileLabel = byId("file-cap-label");
    if (fileState) fileState.classList.toggle("live", runtimeFeatures.files);
    if (fileLabel) fileLabel.textContent = runtimeFeatures.files ? "Ready" : "Restart";

    const projectState = byId("project-cap-state");
    const projectLabel = byId("project-cap-label");
    const projectBadge = byId("projects-nav")?.querySelector("em");
    if (projectState) projectState.classList.toggle("live", runtimeFeatures.projects);
    if (projectLabel) projectLabel.textContent = runtimeFeatures.projects ? "Ready" : "Restart";
    if (projectBadge) projectBadge.textContent = runtimeFeatures.projects ? "Ready" : "Restart";

    const taskState = byId("task-cap-state");
    const taskLabel = byId("task-cap-label");
    const taskBadge = byId("tasks-nav")?.querySelector("em");
    if (taskState) taskState.classList.toggle("live", runtimeFeatures.tasks);
    if (taskLabel) taskLabel.textContent = runtimeFeatures.tasks ? "Ready" : "Restart";
    if (taskBadge) taskBadge.textContent = runtimeFeatures.tasks ? "Ready" : "Restart";

    const memoryBadge = byId("memory-nav")?.querySelector("em");
    if (memoryBadge) {
      memoryBadge.textContent = runtimeFeatures.persistent_memory ? "Ready" : "Restart";
    }

    if (!runtimeFeatures.persistent_conversations) {
      conversationId = null;
      window.localStorage.removeItem("helixConversationId");
    }

    const local = models.profiles.length > 0 &&
      models.profiles.every(profile => profile.kind === "local");

    const modelIds = [...new Set(models.profiles.map(profile => profile.model_id))];
    const primaryModel = modelIds.join(", ");

    dot.classList.remove("error");
    dot.classList.add("ready");
    byId("runtime-label").textContent = local ? "Local runtime ready" : "Runtime ready";
    byId("runtime-short").textContent =
      (primaryModel || "Connected") +
      (runtimeFeatures.persistent_memory ? "" : " · restart for v0.2 backend");
    byId("model-name").textContent = primaryModel || "—";
    byId("provider-mode").textContent = local ? "Local" : "Mixed";
    byId("runtime-cost").textContent = "$" + meter.model_cost_usd.toFixed(6);
    const knowledgeLabel = byId("knowledge-cap-label");
    if (knowledgeLabel) {
      knowledgeLabel.textContent = knowledgeStatus.count + " sourced";
    }
    byId("error").textContent = "";
  } catch (error) {
    dot.classList.remove("ready");
    dot.classList.add("error");
    byId("runtime-label").textContent = "Runtime unavailable";
    byId("runtime-short").textContent = "Check local model";
    byId("error").textContent = error.message;
  }
}

function wireIntentCards() {
  document.querySelectorAll("[data-role-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      setRole(button.dataset.rolePrompt || "");
      byId("prompt").value = button.dataset.prompt;
      autoGrow();
      byId("prompt").focus();
    });
  });
}

function autoGrow() {
  const prompt = byId("prompt");
  prompt.style.height = "auto";
  prompt.style.height = Math.min(prompt.scrollHeight, 170) + "px";
}

byId("status").addEventListener("click", refreshStatus);
byId("new-chat").addEventListener("click", () => {
  resetChat();
  refreshConversationList();
});
byId("refresh-conversations").addEventListener("click", refreshConversationList);

byId("conversation-list").addEventListener("click", async event => {
  const open = event.target.closest("[data-conversation-open]");
  const remove = event.target.closest("[data-conversation-delete]");

  try {
    if (remove) {
      const id = remove.dataset.conversationDelete;
      if (!confirm("Delete this local conversation?")) return;

      await api("/api/conversations/" + encodeURIComponent(id), "DELETE");

      if (conversationId === id) {
        resetChat();
      }

      toast("Conversation deleted.");
      await refreshConversationList();
      return;
    }

    if (open) {
      await loadConversationById(open.dataset.conversationOpen);
    }
  } catch (error) {
    toast("History: " + error.message);
  }
});
byId("theme-toggle").addEventListener("click", toggleTheme);
byId("projects-nav").addEventListener("click", openProjectsDrawer);
byId("projects-close").addEventListener("click", closeProjectsDrawer);
byId("projects-backdrop").addEventListener("click", closeProjectsDrawer);
byId("tasks-nav").addEventListener("click", openTasksDrawer);
byId("tasks-close").addEventListener("click", closeTasksDrawer);
byId("tasks-backdrop").addEventListener("click", closeTasksDrawer);
byId("memory-nav").addEventListener("click", openMemoryDrawer);
byId("memory-close").addEventListener("click", closeMemoryDrawer);
byId("memory-backdrop").addEventListener("click", closeMemoryDrawer);

document.querySelectorAll("[data-file-picker]").forEach(button => {
  button.addEventListener("click", () => {
    if (!runtimeFeatures.files) {
      warnStaleBackend();
      return;
    }
    byId("file-input").click();
  });
});

byId("file-input").addEventListener("change", async event => {
  try {
    await attachFiles(event.target.files);
  } catch (error) {
    toast("Files: " + error.message);
  } finally {
    event.target.value = "";
  }
});

byId("file-chips").addEventListener("click", async event => {
  const button = event.target.closest("[data-file-id]");
  if (!button || !conversationId) return;

  try {
    await api(
      "/api/files/" + encodeURIComponent(conversationId) + "/" + encodeURIComponent(button.dataset.fileId),
      "DELETE"
    );
    toast("Attachment removed.");
    await refreshAttachments();
  } catch (error) {
    toast("Files: " + error.message);
  }
});

byId("project-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!runtimeFeatures.projects) {
    warnStaleBackend();
    return;
  }

  const name = byId("project-name").value.trim();
  if (!name) return;

  try {
    const data = await api("/api/projects", "POST", { name });
    byId("project-name").value = "";
    await loadProject(data.project.id);
    await refreshProjects();
  } catch (error) {
    toast("Projects: " + error.message);
  }
});

byId("project-list").addEventListener("click", async event => {
  const button = event.target.closest("[data-project-id]");
  if (!button) return;

  try {
    await loadProject(button.dataset.projectId);
  } catch (error) {
    toast("Projects: " + error.message);
  }
});

byId("project-import").addEventListener("click", () => {
  if (!activeProjectId) {
    toast("Create or select a project first.");
    return;
  }
  byId("project-folder-input").click();
});

byId("project-folder-input").addEventListener("change", async event => {
  byId("project-import").disabled = true;
  try {
    await importProjectFolder(event.target.files);
  } catch (error) {
    toast("Projects: " + error.message);
  } finally {
    event.target.value = "";
    byId("project-import").disabled = false;
  }
});

byId("project-refresh").addEventListener("click", async () => {
  if (!activeProjectId) return;
  try {
    await loadProject(activeProjectId, false);
  } catch (error) {
    toast("Projects: " + error.message);
  }
});

byId("project-delete").addEventListener("click", async () => {
  if (!activeProjectId || !activeProject) return;
  if (!confirm("Delete the local project snapshot “" + activeProject.name + "”?")) return;

  try {
    await api("/api/projects/" + encodeURIComponent(activeProjectId), "DELETE");
    activeProjectId = null;
    activeProject = null;
    window.localStorage.removeItem(PROJECT_KEY);
    updateActiveProjectChip();
    byId("project-detail").hidden = true;
    toast("Project snapshot deleted.");
    await refreshProjects();
  } catch (error) {
    toast("Projects: " + error.message);
  }
});

byId("task-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!runtimeFeatures.tasks) {
    warnStaleBackend();
    return;
  }

  const title = byId("task-title").value.trim();
  if (!title) return;

  const dueValue = byId("task-due").value;
  let dueAt = null;

  if (dueValue) {
    const parsed = new Date(dueValue);
    if (!Number.isNaN(parsed.getTime())) {
      dueAt = parsed.toISOString();
    }
  }

  byId("task-create").disabled = true;

  try {
    await api("/api/tasks", "POST", {
      title,
      details: byId("task-details").value.trim(),
      due_at: dueAt
    });

    byId("task-title").value = "";
    byId("task-details").value = "";
    byId("task-due").value = "";
    taskFilter = "open";

    document.querySelectorAll("[data-task-filter]").forEach(button => {
      button.classList.toggle("active", button.dataset.taskFilter === taskFilter);
    });

    toast("Task added.");
    await refreshTasks();
    await checkDueTasks();
  } catch (error) {
    toast("Tasks: " + error.message);
  } finally {
    byId("task-create").disabled = false;
  }
});

document.querySelectorAll("[data-task-filter]").forEach(button => {
  button.addEventListener("click", () => {
    taskFilter = button.dataset.taskFilter;
    document.querySelectorAll("[data-task-filter]").forEach(item => {
      item.classList.toggle("active", item === button);
    });
    refreshTasks();
  });
});

byId("task-alerts").addEventListener("click", enableTaskAlerts);

byId("task-list").addEventListener("click", async event => {
  const button = event.target.closest("[data-task-action]");
  if (!button) return;

  const card = button.closest("[data-task-id]");
  if (!card) return;

  const taskId = card.dataset.taskId;

  try {
    if (button.dataset.taskAction === "delete") {
      await api("/api/tasks/" + encodeURIComponent(taskId), "DELETE");
      toast("Task deleted.");
    } else {
      const done = button.dataset.done !== "true";
      await api(
        "/api/tasks/" + encodeURIComponent(taskId),
        "PATCH",
        { done }
      );
      toast(done ? "Task completed." : "Task reopened.");
    }

    await refreshTasks();
  } catch (error) {
    toast("Tasks: " + error.message);
  }
});

document.querySelectorAll("[data-web-toggle]").forEach(button => {
  button.addEventListener("click", cycleWebMode);
});

byId("memory-form").addEventListener("submit", async event => {
  event.preventDefault();

  const memoryContent = byId("memory-content").value.trim();
  if (!memoryContent) return;

  byId("memory-save").disabled = true;

  try {
    await api("/api/memories", "POST", {
      content: memoryContent,
      kind: byId("memory-kind").value,
      pinned: byId("memory-pinned").checked,
      importance: byId("memory-pinned").checked ? 0.9 : 0.6
    });

    byId("memory-content").value = "";
    byId("memory-pinned").checked = false;
    toast("Memory saved locally.");
    await refreshMemories();
  } catch (error) {
    toast(error.message);
  } finally {
    byId("memory-save").disabled = false;
  }
});

byId("memory-list").addEventListener("click", async event => {
  const button = event.target.closest("[data-memory-action]");
  if (!button) return;

  const card = button.closest("[data-memory-id]");
  const memoryId = card.dataset.memoryId;

  try {
    if (button.dataset.memoryAction === "delete") {
      await api("/api/memories/" + encodeURIComponent(memoryId), "DELETE");
      toast("Memory deleted.");
    } else {
      const pinned = button.dataset.pinned !== "true";
      await api(
        "/api/memories/" + encodeURIComponent(memoryId),
        "PATCH",
        { pinned }
      );
      toast(pinned ? "Memory pinned." : "Memory unpinned.");
    }

    await refreshMemories();
  } catch (error) {
    toast(error.message);
  }
});

byId("knowledge-clear").addEventListener("click", async () => {
  if (!confirm("Clear all locally learned web knowledge? User memories and conversations will not be deleted.")) {
    return;
  }

  try {
    const data = await api("/api/knowledge", "DELETE");
    toast("Cleared " + data.deleted + " sourced knowledge item(s).");
    await refreshKnowledge();
  } catch (error) {
    toast(error.message);
  }
});

document.querySelectorAll(".brain-choice").forEach(button => {
  button.addEventListener("click", () => setRole(button.dataset.role));
});

document.querySelectorAll("[data-soon]").forEach(button => {
  button.addEventListener("click", () => {
    toast(button.dataset.soon + " is part of the Helix roadmap, but is not connected yet.");
  });
});

byId("send").addEventListener("click", event => {
  if (currentAbortController) {
    event.preventDefault();
    currentAbortController.abort();
  }
});

byId("prompt").addEventListener("input", autoGrow);
byId("prompt").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    byId("chat-form").requestSubmit();
  }
});

document.addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n") {
    event.preventDefault();
    resetChat();
  }
});

byId("chat-form").addEventListener("submit", async event => {
  event.preventDefault();

  const text = byId("prompt").value.trim();
  if (!text) return;

  byId("send").disabled = true;
  byId("error").textContent = "";

  const selectedRole = byId("role").value || null;

  try {
    await ensureConversation();
  } catch (error) {
    byId("send").disabled = false;
    byId("error").textContent = error.message;
    return;
  }

  const current = [
    ...chatHistory.slice(-14),
    { role: "user", content: text }
  ];

  const payload = {
    messages: current,
    role: selectedRole,
    previous_role: previousRole,
    allow_external: false,
    max_output_tokens: selectedRole === "sage" ? 1024 : 512,
    max_cost_usd: byId("budget").value
  };

  if (runtimeFeatures.persistent_conversations && conversationId) {
    payload.conversation_id = conversationId;
  }

  if (runtimeFeatures.persistent_memory) {
    payload.memory_enabled = true;
  }

  if (runtimeFeatures.projects && activeProjectId) {
    payload.project_id = activeProjectId;
  }

  const autoWeb = runtimeFeatures.web && shouldAutoUseWeb(text);
  if (runtimeFeatures.web) {
    payload.web_enabled =
      webMode === "on" ||
      (webMode === "auto" && autoWeb);

    if (payload.web_enabled && webMode === "auto") {
      toast("Helix automatically enabled live web research for this current-information request.");
    }
  }

  message("You", text, "user");
  byId("prompt").value = "";
  autoGrow();

  if (runtimeFeatures.streaming) {
    byId("send").disabled = false;
    try {
      const result = await streamChat(payload, selectedRole);
      if (!result.aborted) {
        chatHistory = [
          ...current,
          { role: "assistant", content: result.text }
        ];
        previousRole = result.role;
        refreshConversationList();
      }
    } catch (error) {
      byId("error").textContent = error.message;
      setGenerationState(false);
    } finally {
      byId("prompt").focus();
    }
    return;
  }

  const pending = pendingMessage(selectedRole);

  try {
    const data = await api(
      "/api/chat",
      "POST",
      payload,
      crypto.randomUUID()
    );

    pending.remove();

    message(
      "Helix " + roleName(data.role),
      data.text,
      "assistant",
      data.provider_mode + " · " + data.model_id + " · $" +
        data.model_cost_usd.toFixed(6) +
        (data.memory_used && data.memory_used.length
          ? " · " + data.memory_used.length + " memory"
          : "") +
        (data.files_used && data.files_used.length
          ? " · " + data.files_used.length + " file" + (data.files_used.length === 1 ? "" : "s")
          : "") +
        (data.web_sources && data.web_sources.length
          ? " · web grounded"
          : "") +
        " · unverified",
      data.web_sources || [],
      data.knowledge_used || []
    );

    if (data.knowledge_learned) {
      toast("Helix learned " + data.knowledge_learned + " sourced web item(s) locally.");
      refreshKnowledge();
    }

    if (data.web_error) {
      toast("Web: " + data.web_error);
    }

    if (data.memory_saved && runtimeFeatures.persistent_memory) {
      toast("Helix saved that to your private local memory.");
      refreshMemories();
    }

    if (data.task_saved && runtimeFeatures.tasks) {
      toast("Helix added “" + data.task_saved.title + "” to your task list. No notification was scheduled.");
      refreshTasks();
    }

    chatHistory = [
      ...current,
      { role: "assistant", content: data.text }
    ];

    previousRole = data.role;
    refreshConversationList();
    updateRoute(
      data.role,
      data.reason || "Routed by Helix",
      data.routing_confidence,
      data.reasoning_mode
    );
  } catch (error) {
    pending.remove();
    byId("error").textContent = error.message;
  } finally {
    byId("send").disabled = false;
    byId("prompt").focus();
  }
});

(() => {
  const params = new URLSearchParams(window.location.hash.substring(1));
  const urlKey = params.get("key");
  const savedKey = window.sessionStorage.getItem("helixLocalKey");
  const activeKey = urlKey || savedKey;

  if (activeKey) {
    byId("key").value = activeKey;
    window.sessionStorage.setItem("helixLocalKey", activeKey);

    if (urlKey) {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search
      );
    }

    setTimeout(async () => {
      await refreshStatus();
      try {
        await loadConversation();
        await refreshMemories();
        await refreshAttachments();
        await refreshConversationList();
        await refreshProjects();
        await refreshTasks();
        updateTaskAlertButton();
        await checkDueTasks();
        if (activeProjectId && runtimeFeatures.projects) {
          await loadProject(activeProjectId, false).catch(() => {
            activeProjectId = null;
            activeProject = null;
            window.localStorage.removeItem(PROJECT_KEY);
            updateActiveProjectChip();
          });
        }
      } catch (error) {
        byId("error").textContent = error.message;
      }
    }, 250);
  }
})();

byId("key").addEventListener("input", () => {
  const value = byId("key").value.trim();

  if (value) {
    window.sessionStorage.setItem("helixLocalKey", value);
  } else {
    window.sessionStorage.removeItem("helixLocalKey");
  }
});

applyTheme(window.localStorage.getItem(THEME_KEY) || "dark");
updateTaskAlertButton();
window.setInterval(checkDueTasks, 60000);
setRole("");
wireIntentCards();
autoGrow();
