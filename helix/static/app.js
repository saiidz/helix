"use strict";

const byId = id => document.getElementById(id);

let chatHistory = [];
let previousRole = null;

const roleName = role => {
  if (!role) return "Auto";
  return role.charAt(0).toUpperCase() + role.slice(1);
};

async function api(path, method = "GET", body = null, id = null) {
  const key = byId("key").value.trim();

  if (!key) {
    throw new Error("Local access key missing.");
  }

  const headers = {
    Authorization: `Bearer ${key}`
  };

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
        : `Request rejected (${response.status}).`
    );
  }

  return data;
}

function removeWelcome() {
  byId("welcome")?.remove();
}

function message(label, text, type, meta = "") {
  removeWelcome();

  const box = document.createElement("div");
  box.className = `message ${type}`;

  const title = document.createElement("b");
  title.textContent = label;

  const content = document.createElement("p");
  content.textContent = text;

  box.append(title, content);

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

function setRole(role) {
  byId("role").value = role;

  document.querySelectorAll(".role-button").forEach(button => {
    button.classList.toggle("active", button.dataset.role === role);
  });

  const name = roleName(role);
  byId("role-chip").textContent = name;
  byId("composer-role").textContent =
    role ? `${name} selected` : "Auto routing";
}

function resetChat() {
  chatHistory = [];
  previousRole = null;

  byId("messages").innerHTML = `
    <div id="welcome" class="welcome">
      <div class="welcome-mark">H</div>
      <h1>What do you want to work on?</h1>
      <p>One interface for everyday help, coding, and deeper reasoning. Helix keeps the active model visible and stays local by default.</p>
      <div class="quick-prompts" aria-label="Suggested prompts">
        <button type="button" data-prompt="Help me plan what I should work on today.">Plan my day</button>
        <button type="button" data-prompt="Review this code with me and help me improve it.">Work on code</button>
        <button type="button" data-prompt="Think deeply about a hard problem with me.">Reason deeply</button>
      </div>
    </div>
  `;

  wireQuickPrompts();
  byId("prompt").focus();
}

async function refreshStatus() {
  const dot = byId("runtime-dot");

  try {
    const [models, meter] = await Promise.all([
      api("/api/models"),
      api("/api/meter")
    ]);

    const modes = models.profiles.map(profile => profile.kind);
    const allLocal = modes.length > 0 && modes.every(kind => kind === "local");
    const uniqueModels = [...new Set(models.profiles.map(profile => profile.model_id))];

    dot.classList.remove("error");
    dot.classList.add("ready");
    byId("runtime-label").textContent = allLocal ? "Local runtime ready" : "Runtime ready";
    byId("connection").textContent =
      `${models.profiles.map(profile => roleName(profile.role)).join(" · ")} · ${uniqueModels.join(", ")} · $${meter.model_cost_usd.toFixed(6)} this month`;
    byId("error").textContent = "";
  } catch (error) {
    dot.classList.remove("ready");
    dot.classList.add("error");
    byId("runtime-label").textContent = "Runtime unavailable";
    byId("connection").textContent = "Helix could not verify the local model connection.";
    byId("error").textContent = error.message;
  }
}

function wireQuickPrompts() {
  document.querySelectorAll("[data-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      byId("prompt").value = button.dataset.prompt;
      autoGrow();
      byId("prompt").focus();
    });
  });
}

function autoGrow() {
  const prompt = byId("prompt");
  prompt.style.height = "auto";
  prompt.style.height = `${Math.min(prompt.scrollHeight, 180)}px`;
}

byId("status").addEventListener("click", refreshStatus);
byId("new-chat").addEventListener("click", resetChat);

document.querySelectorAll(".role-button").forEach(button => {
  button.addEventListener("click", () => setRole(button.dataset.role));
});

byId("prompt").addEventListener("input", autoGrow);
byId("prompt").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    byId("chat-form").requestSubmit();
  }
});

byId("chat-form").addEventListener("submit", async event => {
  event.preventDefault();

  const text = byId("prompt").value.trim();
  if (!text) return;

  byId("send").disabled = true;
  byId("error").textContent = "";

  const selectedRole = byId("role").value || null;
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

  message("You", text, "user");
  const pending = message(
    selectedRole ? `Helix ${roleName(selectedRole)}` : "Helix",
    selectedRole === "sage" ? "Reasoning…" : "Working…",
    "assistant pending"
  );

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
      `Helix ${roleName(data.role)}`,
      data.text,
      "assistant",
      `${data.provider_mode} · ${data.model_id} · $${data.model_cost_usd.toFixed(6)} model cost · answer unverified`
    );

    chatHistory = [
      ...current,
      { role: "assistant", content: data.text }
    ];

    previousRole = data.role;

    if (!selectedRole) {
      byId("role-chip").textContent = `Auto → ${roleName(data.role)}`;
      byId("composer-role").textContent = `Auto routed to ${roleName(data.role)}`;
    }
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

    setTimeout(refreshStatus, 250);
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
wireQuickPrompts();
autoGrow();
