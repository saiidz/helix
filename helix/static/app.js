"use strict";

const byId = id => document.getElementById(id);

let chatHistory = [];
let previousRole = null;
let conversationId = window.localStorage.getItem("helixConversationId") || null;

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
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request rejected (" + response.status + ")."
    );
  }

  return data;
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
  if (conversationId) return conversationId;

  const data = await api(
    "/api/conversations",
    "POST",
    { title: "New conversation" }
  );

  conversationId = data.conversation.id;
  window.localStorage.setItem("helixConversationId", conversationId);
  return conversationId;
}

async function loadConversation() {
  if (!conversationId) return;

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

function message(label, text, type, meta = "") {
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

function updateRoute(role, reason = "") {
  const actualRole = role || "";
  const target = byId("route-target");
  const name = roleName(actualRole);

  target.className = "route-target " + roleClass(actualRole);
  target.innerHTML =
    '<span class="brain-dot ' + roleClass(actualRole) + '"></span>' +
    "<div><strong>" + name + "</strong><small>" +
    (reason || (actualRole ? "Selected explicitly" : "Waiting for a task")) +
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
    '<div><span class="vision-dot"></span><strong>Internet</strong><small>Next</small></div>',
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
      api("/api/meter")
    ]);
    const models = results[0];
    const meter = results[1];

    const local = models.profiles.length > 0 &&
      models.profiles.every(profile => profile.kind === "local");

    const modelIds = [...new Set(models.profiles.map(profile => profile.model_id))];
    const primaryModel = modelIds.join(", ");

    dot.classList.remove("error");
    dot.classList.add("ready");
    byId("runtime-label").textContent = local ? "Local runtime ready" : "Runtime ready";
    byId("runtime-short").textContent = primaryModel || "Connected";
    byId("model-name").textContent = primaryModel || "—";
    byId("provider-mode").textContent = local ? "Local" : "Mixed";
    byId("runtime-cost").textContent = "$" + meter.model_cost_usd.toFixed(6);
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
byId("memory-nav").addEventListener("click", openMemoryDrawer);
byId("memory-close").addEventListener("click", closeMemoryDrawer);
byId("memory-backdrop").addEventListener("click", closeMemoryDrawer);

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
    conversation_id: conversationId,
    memory_enabled: true,
    allow_external: false,
    max_output_tokens: selectedRole === "sage" ? 1024 : 512,
    max_cost_usd: byId("budget").value
  };

  message("You", text, "user");
  const pending = pendingMessage(selectedRole);

  byId("prompt").value = "";
  autoGrow();

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
        " · unverified"
    );

    if (data.memory_saved) {
      toast("Helix saved that to your private local memory.");
      refreshMemories();
    }

    chatHistory = [
      ...current,
      { role: "assistant", content: data.text }
    ];

    previousRole = data.role;
    updateRoute(data.role, data.reason || "Routed by Helix");
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

setRole("");
wireIntentCards();
autoGrow();
