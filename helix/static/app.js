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
  web: false
};
let staleBackendWarningShown = false;
let currentAbortController = null;

const THEME_KEY = "helixTheme";
const WEB_MODE_KEY = "helixWebMode";
let webMode = window.localStorage.getItem(WEB_MODE_KEY) || "auto";

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

async function loadConversation() {
  if (!runtimeFeatures.persistent_conversations || !conversationId) return;

  try {
    const data = await api("/api/conversations/" + encodeURIComponent(conversationId));
    const stored = data.conversation.messages || [];

    if (!stored.length) return;

    byId("messages").innerHTML = "";
    chatHistory = [];

    for (const item of stored) {
      if (item.role === "user") {
        message("You", item.content, "user");
      } else {
        message("Helix", item.content, "assistant", "restored from local conversation");
      }

      chatHistory.push({ role: item.role, content: item.content });
    }

    toast("Restored your local conversation.");
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

  return { box, title, body, meta, text: "", sources: [], knowledge: [] };
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
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + key,
      "Content-Type": "application/json",
      "Idempotency-Key": requestId
    },
    body: JSON.stringify(payload),
    signal: currentAbortController.signal
  });

  if (!response.ok) {
    let detail = "Streaming request rejected (" + response.status + ").";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch (_) {}
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
          if (event.knowledge_learned) {
            toast("Helix learned " + event.knowledge_learned + " sourced web item(s) locally.");
          }
          if (event.web_error) toast("Web: " + event.web_error);
          if (event.memory_saved) {
            toast("Helix saved that to your private local memory.");
            refreshMemories();
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
      web: Boolean(advertised.web)
    };

    setWebMode(webMode, false);

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
byId("new-chat").addEventListener("click", resetChat);
byId("theme-toggle").addEventListener("click", toggleTheme);
byId("memory-nav").addEventListener("click", openMemoryDrawer);
byId("memory-close").addEventListener("click", closeMemoryDrawer);
byId("memory-backdrop").addEventListener("click", closeMemoryDrawer);

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
        (data.web_sources && data.web_sources.length
          ? " · web grounded"
          : "") +
        " · unverified",
      data.web_sources || [],
      data.knowledge_used || []
    );

    if (data.knowledge_learned) {
      toast("Helix learned " + data.knowledge_learned + " sourced web item(s) locally.");
    }

    if (data.web_error) {
      toast("Web: " + data.web_error);
    }

    if (data.memory_saved && runtimeFeatures.persistent_memory) {
      toast("Helix saved that to your private local memory.");
      refreshMemories();
    }

    chatHistory = [
      ...current,
      { role: "assistant", content: data.text }
    ];

    previousRole = data.role;
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
setRole("");
wireIntentCards();
autoGrow();
