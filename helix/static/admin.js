"use strict";

const byId = id => document.getElementById(id);
const theme = window.localStorage.getItem("helixTheme") === "light" ? "light" : "dark";
document.documentElement.dataset.theme = theme;

function localKey() {
  const hash = new URLSearchParams(window.location.hash.substring(1));
  const urlKey = hash.get("key");
  const saved = window.sessionStorage.getItem("helixLocalKey");
  const key = urlKey || saved || "";
  if (urlKey) {
    window.sessionStorage.setItem("helixLocalKey", urlKey);
    window.history.replaceState(null, "", window.location.pathname);
  }
  return key;
}

const KEY = localKey();

async function api(path, method = "GET", body = null) {
  if (!KEY) throw new Error("Local access key missing. Open Admin from the running HELIX app.");
  const headers = { Authorization: "Bearer " + KEY };
  if (body !== null) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    body: body === null ? null : JSON.stringify(body),
    cache: "no-store"
  });
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed (" + response.status + ")");
  return data;
}

function yes(value, on = "Ready", off = "Off") {
  return value ? on : off;
}

function setState(id, text, live = null) {
  const element = byId(id);
  if (!element) return;
  element.textContent = text;
  if (live !== null) element.classList.toggle("live", Boolean(live));
}

async function load() {
  const error = byId("admin-error");
  try {
    const [health, models, meter, knowledge, engineer] = await Promise.all([
      fetch("/health", { cache: "no-store" }).then(r => r.json()),
      api("/api/models"),
      api("/api/meter"),
      api("/api/knowledge/status").catch(() => ({ count: 0 })),
      api("/api/engineer-agent/status").catch(() => null)
    ]);

    const caps = health.capabilities || {};
    setState("admin-health", "HELIX " + health.version + " · local", true);
    setState("runtime-state", "Connected", true);
    setState("model-cost", "$" + Number(meter.model_cost_usd || 0).toFixed(6));
    setState("streaming-state", yes(caps.streaming), caps.streaming);
    setState("tool-first-state", yes(caps.tool_first_routing), caps.tool_first_routing);

    const list = byId("model-list");
    list.innerHTML = "";
    for (const profile of models.profiles || []) {
      const row = document.createElement("div");
      row.className = "model-row";
      const role = document.createElement("strong");
      role.textContent = String(profile.role).replace(/^./, s => s.toUpperCase());
      const value = document.createElement("span");
      value.textContent = profile.model_id + " · " + profile.kind;
      row.append(role, value);
      list.append(row);
    }

    setState("web-state", caps.web ? "Connected" : "Off", caps.web);
    setState("web-connector", yes(caps.web, "Enabled", "Disabled"), caps.web);
    setState("server-auto", yes(caps.server_web_auto, "Enabled", "Legacy"), caps.server_web_auto);
    setState("knowledge-count", (knowledge.count || 0) + " sourced");
    setState("cache-state", (knowledge.count || 0) + " entries");

    setState("memory-state", yes(caps.persistent_memory), caps.persistent_memory);
    setState("conversation-state", yes(caps.persistent_conversations), caps.persistent_conversations);
    setState("clock-state", yes(caps.clock), caps.clock);
    setState("calculator-state", yes(caps.calculator), caps.calculator);
    setState("voice-state", yes(caps.voice, "Enabled", "Not connected"), caps.voice);

    if (engineer) {
      byId("workspace-path").textContent = engineer.workspace || "No workspace connected";
      setState("engineer-state", engineer.actions_enabled ? "Ready" : engineer.lockdown?.locked ? "Locked" : "Read only", engineer.actions_enabled);
      setState("actions-state", yes(engineer.actions_enabled, "Reviewed", "Disabled"), engineer.actions_enabled);
      setState("jobs-state", yes(engineer.history_persistent, "Persistent", "Ephemeral"), engineer.history_persistent);
      setState("sandbox-state", engineer.os_sandbox ? "Isolated" : "Not isolated", engineer.os_sandbox);

      const locked = Boolean(engineer.lockdown?.locked);
      setState("lock-state", locked ? "LOCKED" : "Armed", !locked);
      byId("lockdown").disabled = locked;
      byId("lockdown").textContent = locked ? "LOCKED" : "Activate Emergency Lockdown";
      if (locked) {
        byId("lock-copy").textContent =
          "Engineer actions are disabled across restarts. Reset only from RESET_HELIX_LOCKDOWN.cmd in a separate local terminal." +
          (engineer.lockdown?.reason ? " Reason: " + engineer.lockdown.reason : "");
      }
    } else {
      setState("engineer-state", "Unavailable", false);
      setState("actions-state", "Unavailable", false);
      setState("jobs-state", "Unavailable", false);
      setState("sandbox-state", "Unavailable", false);
      setState("lock-state", "Unavailable", false);
      byId("lockdown").disabled = true;
    }

    error.hidden = true;
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
    setState("admin-health", "Admin unavailable", false);
  }
}

byId("lockdown").addEventListener("click", async () => {
  if (!window.confirm("Activate persistent Emergency Lockdown? This disables Engineer actions until reset from a separate local terminal.")) return;
  try {
    await api("/api/engineer-agent/lockdown", "POST", {});
    await load();
  } catch (err) {
    const error = byId("admin-error");
    error.textContent = err.message;
    error.hidden = false;
  }
});

load();
setInterval(load, 5000);
