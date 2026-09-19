"use strict";

(() => {
  const nav = document.getElementById("engineer-jobs-nav");
  if (!nav) return;

  const navState = document.getElementById("engineer-jobs-nav-state");
  const capState = document.getElementById("engineer-jobs-cap-state");
  const capLabel = document.getElementById("engineer-jobs-cap-label");
  const keyInput = document.getElementById("key");

  let drawer = null;
  let backdrop = null;
  let status = null;
  let sessionId = "";
  let cursor = 0;
  let selectedHistory = null;
  let polling = null;
  let lastActive = null;

  function key() {
    return (keyInput?.value || "").trim();
  }

  async function request(path, method = "GET", body = null) {
    const token = key();
    if (!token) throw new Error("Enter the local access key first.");
    const headers = { Authorization: "Bearer " + token };
    if (body !== null) headers["Content-Type"] = "application/json";
    const response = await fetch("/api/engineer-agent" + path, {
      method,
      headers,
      body: body === null ? null : JSON.stringify(body),
      cache: "no-store"
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Engineer request failed (" + response.status + ").");
    return data;
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function setAvailability(enabled, stateText = "") {
    const text = stateText || (enabled ? "Ready" : "Off");
    if (navState) navState.textContent = text;
    if (capLabel) capLabel.textContent = text;
    if (capState) capState.classList.toggle("live", Boolean(enabled));
  }

  function buildDrawer() {
    if (drawer) return;
    backdrop = node("div", "engineer-jobs-backdrop");
    backdrop.hidden = true;
    drawer = node("aside", "engineer-jobs-drawer");
    drawer.hidden = true;
    drawer.setAttribute("aria-label", "Engineer jobs");
    drawer.innerHTML = [
      '<div class="engineer-jobs-head"><div><span class="section-label">Unified engineering loop</span><h2>Engineer Jobs</h2></div><button id="engineer-jobs-close" class="engineer-close" type="button" aria-label="Close">×</button></div>',
      '<div id="engineer-runtime" class="engineer-runtime"><strong>Checking workspace…</strong><small></small></div>',
      '<div id="engineer-warning" class="engineer-warning">Command execution is not OS-sandboxed yet. Review every edit and command. Do not run HELIX as Administrator.</div>',
      '<form id="engineer-job-form" class="engineer-job-form"><textarea id="engineer-task" maxlength="6000" placeholder="Example: reproduce the failing checkout test, fix the smallest root cause, then rerun the relevant tests." required></textarea><div class="engineer-job-options"><label>Max steps <input id="engineer-max-steps" type="number" min="1" max="60" value="24"></label><button id="engineer-start" class="engineer-start" type="submit">Start job</button></div></form>',
      '<div id="engineer-state" class="engineer-state"><i></i><span>No active job</span></div>',
      '<div class="engineer-actions"><button id="engineer-stop" class="engineer-stop engineer-hidden" type="button">Stop</button><button id="engineer-refresh" class="engineer-refresh" type="button">Refresh</button><button id="engineer-live" class="engineer-live engineer-hidden" type="button">Back to live</button></div>',
      '<section id="engineer-approval" class="engineer-section engineer-approval" hidden><div class="engineer-section-title"><strong>Approval required</strong><span id="engineer-approval-kind"></span></div><pre id="engineer-approval-preview"></pre><div class="engineer-approval-actions"><button id="engineer-approve" class="engineer-approve" type="button">Approve exact action</button><button id="engineer-deny" class="engineer-deny" type="button">Deny</button></div></section>',
      '<section class="engineer-section"><div class="engineer-section-title"><strong id="engineer-activity-title">Live activity</strong><span id="engineer-receipts"></span></div><div id="engineer-events" class="engineer-events"><div class="engineer-empty">No activity yet.</div></div></section>',
      '<section class="engineer-section"><div class="engineer-section-title"><strong>Recent jobs</strong><span>local history</span></div><div id="engineer-history" class="engineer-history"><div class="engineer-empty">No jobs yet.</div></div></section>'
    ].join("");
    document.body.append(backdrop, drawer);

    drawer.querySelector("#engineer-jobs-close").addEventListener("click", close);
    backdrop.addEventListener("click", close);
    drawer.querySelector("#engineer-refresh").addEventListener("click", () => refresh(true));
    drawer.querySelector("#engineer-live").addEventListener("click", () => {
      selectedHistory = null;
      drawer.querySelector("#engineer-live").classList.add("engineer-hidden");
      drawer.querySelector("#engineer-activity-title").textContent = "Live activity";
      renderSession(status?.session || null, true);
    });
    drawer.querySelector("#engineer-job-form").addEventListener("submit", startJob);
    drawer.querySelector("#engineer-stop").addEventListener("click", stopJob);
    drawer.querySelector("#engineer-approve").addEventListener("click", () => decide("approve"));
    drawer.querySelector("#engineer-deny").addEventListener("click", () => decide("deny"));
    drawer.querySelector("#engineer-history").addEventListener("click", async event => {
      const button = event.target.closest("[data-job-id]");
      if (!button) return;
      await showHistory(button.dataset.jobId);
    });
  }

  function open() {
    buildDrawer();
    drawer.hidden = false;
    backdrop.hidden = false;
    refresh(true);
    if (!polling) polling = setInterval(() => refresh(false), 900);
  }

  function close() {
    if (!drawer) return;
    drawer.hidden = true;
    backdrop.hidden = true;
    if (polling) {
      clearInterval(polling);
      polling = null;
    }
  }

  function readable(value) {
    if (typeof value === "string") return value;
    try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
  }

  function appendEvents(events, reset = false, force = false) {
    if (selectedHistory && !force) return;
    const target = drawer.querySelector("#engineer-events");
    if (reset) target.innerHTML = "";
    for (const event of events || []) {
      const card = node("div", "engineer-event");
      const head = node("div", "engineer-event-head");
      head.append(node("span", "", String(event.kind || "event").replaceAll("_", " ")), node("span", "", "#" + (event.id ?? event.seq ?? "—")));
      const body = node("div", "engineer-event-body");
      const raw = readable(event.value);
      if (raw.length > 260 || raw.includes("\n")) {
        const pre = node("pre");
        pre.textContent = raw;
        body.append(pre);
      } else {
        body.textContent = raw;
      }
      card.append(head, body);
      target.append(card);
    }
    if (!target.children.length) target.append(node("div", "engineer-empty", "No activity yet."));
  }

  function renderApproval(approval) {
    const section = drawer.querySelector("#engineer-approval");
    section.hidden = !approval;
    if (!approval) return;
    drawer.querySelector("#engineer-approval-kind").textContent = approval.kind || "Review";
    drawer.querySelector("#engineer-approval-preview").textContent = approval.preview || "";
    section.dataset.approvalId = approval.id || "";
  }

  function statusLabel(value) {
    const raw = String(value || "running");
    const labels = {
      model_finished: "Completed · inspect evidence",
      waiting_for_approval: "Waiting for your approval",
      blocked_after_three_errors: "Blocked after repeated errors",
      step_limit: "Stopped at step limit",
      stopping: "Stopping…",
      cancelled: "Cancelled",
      interrupted: "Interrupted by restart"
    };
    return labels[raw] || raw.replaceAll("_", " ");
  }

  function renderSession(session, forceReset = false) {
    const state = drawer.querySelector("#engineer-state");
    const dot = state.querySelector("i");
    const stop = drawer.querySelector("#engineer-stop");
    const receipts = drawer.querySelector("#engineer-receipts");

    if (!session) {
      state.querySelector("span").textContent = "No active job";
      dot.classList.remove("live");
      stop.classList.add("engineer-hidden");
      receipts.textContent = "";
      renderApproval(null);
      if (!selectedHistory && forceReset) appendEvents([], true);
      return;
    }

    const changedSession = session.id !== sessionId;
    if (changedSession) {
      sessionId = session.id;
      cursor = 0;
      if (!selectedHistory) appendEvents([], true);
    }
    const stateText = statusLabel(session.status);
    state.querySelector("span").textContent = stateText + (session.job_id ? " · " + session.job_id.slice(0, 8) : "");
    dot.classList.toggle("live", Boolean(session.active));
    stop.classList.toggle("engineer-hidden", !session.active);
    receipts.textContent = (session.receipts?.length || 0) + " receipt" + ((session.receipts?.length || 0) === 1 ? "" : "s");
    if (!selectedHistory) renderApproval(session.approval || null);

    if (!selectedHistory) {
      appendEvents(session.events || [], changedSession || forceReset);
      cursor = Math.max(cursor, Number(session.cursor || 0));
    }
  }

  async function refreshJobs() {
    const data = await request("/jobs?limit=16");
    const list = drawer.querySelector("#engineer-history");
    list.innerHTML = "";
    for (const job of data.jobs || []) {
      const button = node("button");
      button.type = "button";
      button.dataset.jobId = job.id;
      const title = node("strong", "", job.task.length > 90 ? job.task.slice(0, 87) + "…" : job.task);
      const meta = node("small", "", String(job.status).replaceAll("_", " ") + " · " + new Date(job.updated_at).toLocaleString());
      button.append(title, meta);
      list.append(button);
    }
    if (!list.children.length) list.append(node("div", "engineer-empty", "No jobs yet."));
  }

  async function refresh(force = false) {
    if (!drawer || drawer.hidden) return;
    try {
      const suffix = sessionId && !force ? "?since=" + encodeURIComponent(cursor) + "&session_id=" + encodeURIComponent(sessionId) : "";
      status = await request("/status" + suffix);
      const runtime = drawer.querySelector("#engineer-runtime");
      const start = drawer.querySelector("#engineer-start");
      const form = drawer.querySelector("#engineer-task");
      runtime.querySelector("strong").textContent = status.enabled ? "Workspace enabled" : "Read-only mode";
      runtime.querySelector("small").textContent = status.enabled
        ? status.workspace
        : "Restart HELIX with an explicit --workspace path to enable reviewed engineering actions.";
      start.disabled = !status.enabled;
      form.disabled = !status.enabled;
      const s = status.session;
      const navText = s?.approval ? "Review" : s?.active ? "Running" : status.enabled ? "Ready" : "Off";
      setAvailability(status.enabled, navText);
      renderSession(s, force);
      if (lastActive !== Boolean(s?.active) || force) {
        lastActive = Boolean(s?.active);
        await refreshJobs();
      }
    } catch (error) {
      setAvailability(false, key() ? "Unavailable" : "Key");
      const runtime = drawer.querySelector("#engineer-runtime");
      runtime.querySelector("strong").textContent = "Engineer unavailable";
      runtime.querySelector("small").textContent = error.message;
    }
  }

  async function startJob(event) {
    event.preventDefault();
    const task = drawer.querySelector("#engineer-task").value.trim();
    const maxSteps = Number(drawer.querySelector("#engineer-max-steps").value);
    if (!task) return;
    try {
      selectedHistory = null;
      sessionId = "";
      cursor = 0;
      appendEvents([], true);
      const data = await request("/start", "POST", { task, skills: [], max_steps: Math.max(1, Math.min(60, maxSteps || 24)) });
      drawer.querySelector("#engineer-task").value = "";
      drawer.querySelector("#engineer-activity-title").textContent = "Live activity";
      drawer.querySelector("#engineer-live").classList.add("engineer-hidden");
      sessionId = data.session_id || "";
      await refresh(true);
    } catch (error) {
      drawer.querySelector("#engineer-runtime").querySelector("small").textContent = error.message;
    }
  }

  async function stopJob() {
    try {
      await request("/stop", "POST", {});
      await refresh(true);
    } catch (error) {
      drawer.querySelector("#engineer-runtime").querySelector("small").textContent = error.message;
    }
  }

  async function decide(decision) {
    const section = drawer.querySelector("#engineer-approval");
    const approvalId = section.dataset.approvalId;
    if (!approvalId) return;
    try {
      await request("/decision", "POST", { approval_id: approvalId, decision });
      renderApproval(null);
      await refresh(true);
    } catch (error) {
      drawer.querySelector("#engineer-runtime").querySelector("small").textContent = error.message;
    }
  }

  async function showHistory(jobId) {
    try {
      const data = await request("/jobs/" + encodeURIComponent(jobId));
      selectedHistory = jobId;
      drawer.querySelector("#engineer-live").classList.remove("engineer-hidden");
      drawer.querySelector("#engineer-activity-title").textContent = "Saved job · " + jobId.slice(0, 8);
      renderApproval(null);
      const events = (data.job.events || []).map(item => ({ id: item.seq, kind: item.kind, value: item.value }));
      const target = drawer.querySelector("#engineer-events");
      target.innerHTML = "";
      appendEvents(events, false, true);
      if (data.job.result) {
        appendEvents([{ id: "result", kind: "final_result", value: data.job.result }], false, true);
      }
    } catch (error) {
      drawer.querySelector("#engineer-runtime").querySelector("small").textContent = error.message;
    }
  }

  async function probeAvailability() {
    if (!key()) {
      setAvailability(false, "Key");
      return;
    }
    try {
      const current = await request("/status");
      status = current;
      const active = current.session;
      const text = active?.approval ? "Review" : active?.active ? "Running" : current.enabled ? "Ready" : "Off";
      setAvailability(current.enabled, text);
    } catch (_) {
      setAvailability(false, "Unavailable");
    }
  }

  nav.addEventListener("click", open);
  keyInput?.addEventListener("change", () => {
    if (drawer && !drawer.hidden) refresh(true);
    else probeAvailability();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && drawer && !drawer.hidden) close();
  });

  buildDrawer();
  setAvailability(false, "Off");
  setTimeout(probeAvailability, 300);
})();