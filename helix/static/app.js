"use strict";

const byId = id => document.getElementById(id);

let chatHistory = [];
let previousRole = null;

const roleName = role =>
  role.charAt(0).toUpperCase() + role.slice(1);

async function api(path, method = "GET", body = null, id = null) {
  const key = byId("key").value.trim();

  if (!key) {
    throw new Error("Local access key missing.");
  }

  const headers = {
    Authorization: `Bearer ${key}`
  };

  if (body) {
    headers["Content-Type"] = "application/json";
  }

  if (id) {
    headers["Idempotency-Key"] = id;
  }

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

function message(label, text, type, meta = "") {
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
  box.scrollIntoView({ block: "nearest" });
}

byId("status").addEventListener("click", async () => {
  try {
    const [models, meter] = await Promise.all([
      api("/api/models"),
      api("/api/meter")
    ]);

    byId("connection").textContent =
      `${models.profiles
        .map(p => `${roleName(p.role)}: ${p.kind}`)
        .join(" · ")} | Model ledger: $${meter.model_cost_usd.toFixed(6)} this month`;

    byId("error").textContent = "";
  } catch (error) {
    byId("error").textContent = error.message;
  }
});

byId("chat-form").addEventListener("submit", async event => {
  event.preventDefault();

  const text = byId("prompt").value.trim();

  if (!text) {
    return;
  }

  byId("send").disabled = true;
  byId("error").textContent = "";

  const current = [
    ...chatHistory.slice(-14),
    {
      role: "user",
      content: text
    }
  ];

  const payload = {
    messages: current,
    role: byId("role").value || null,
    previous_role: previousRole,
    allow_external: false,
    max_output_tokens: 512,
    max_cost_usd: byId("budget").value
  };

  try {
    const data = await api(
      "/api/chat",
      "POST",
      payload,
      crypto.randomUUID()
    );

    message("You", text, "user");

    message(
      `Helix ${roleName(data.role)}`,
      data.text,
      "assistant",
      `${data.provider_mode} · ${data.model_id} · $${data.model_cost_usd.toFixed(6)} model cost · answer unverified`
    );

    chatHistory = [
      ...current,
      {
        role: "assistant",
        content: data.text
      }
    ];

    previousRole = data.role;
    byId("prompt").value = "";
  } catch (error) {
    byId("error").textContent = error.message;
  } finally {
    byId("send").disabled = false;
  }
});

/*
  Automatic local key bootstrap.

  Launcher opens:
  http://127.0.0.1:8765/#key=XXXX

  The fragment is read locally, saved to sessionStorage,
  then immediately removed from the visible URL.
*/
(() => {
  const params = new URLSearchParams(
    window.location.hash.substring(1)
  );

  const urlKey = params.get("key");
  const savedKey =
    window.sessionStorage.getItem("helixLocalKey");

  const activeKey = urlKey || savedKey;

  if (!activeKey) {
    return;
  }

  byId("key").value = activeKey;

  window.sessionStorage.setItem(
    "helixLocalKey",
    activeKey
  );

  if (urlKey) {
    window.history.replaceState(
      null,
      "",
      window.location.pathname + window.location.search
    );
  }

  setTimeout(() => {
    byId("status").click();
  }, 250);
})();

byId("key").addEventListener("input", () => {
  const value = byId("key").value.trim();

  if (value) {
    window.sessionStorage.setItem(
      "helixLocalKey",
      value
    );
  } else {
    window.sessionStorage.removeItem(
      "helixLocalKey"
    );
  }
});