"use strict";

(() => {
  const nav = document.getElementById("follow-through-nav");
  if (!nav) return;
  let active = null;
  let selected = null;
  let view = "needs_you";
  let offset = 0;
  let generation = 0;
  let draftKey = crypto.randomUUID();
  let draftConversation = null;
  const dialog = document.createElement("dialog");
  dialog.id = "follow-through-dialog";
  dialog.setAttribute("aria-labelledby", "follow-heading");
  // This template is static. All user/source strings are assigned with textContent or value.
  dialog.innerHTML = `
    <header class="follow-head"><div><span class="section-label">Keep the next step clear</span><h2 id="follow-heading">Follow-through</h2></div><button type="button" id="follow-close" aria-label="Close follow-through">Close</button></header>
    <p class="follow-boundary">Local tracking only. No email access, background monitoring, notifications or automatic actions. Completion is your report, not independent verification.</p>
    <div class="follow-toolbar"><button type="button" id="follow-new">New tracker</button><button type="button" id="follow-refresh">Refresh</button><button type="button" id="follow-export">Export private data</button></div>
    <div id="follow-error" role="alert"></div>
    <div class="follow-layout">
      <section class="follow-overview" aria-label="Tracked outcomes"><nav id="follow-tabs" aria-label="Outcome views"><button type="button" data-view="needs_you" aria-pressed="true">Needs you</button><button type="button" data-view="waiting" aria-pressed="false">Waiting</button><button type="button" data-view="closed" aria-pressed="false">Closed</button></nav><p id="follow-count" class="follow-muted" aria-live="polite"></p><div id="follow-list"></div><div class="follow-paging"><button type="button" id="follow-prev">Previous</button><button type="button" id="follow-next">Next</button></div></section>
      <section id="follow-detail" aria-label="Review an outcome"><p class="follow-muted">Select a tracker or choose New tracker.</p></section>
    </div>`;
  document.body.append(dialog);
  const $ = id => document.getElementById(id);
  const detail = $("follow-detail");
  const chip = $("active-outcome-chip");

  function element(tag, text, className = "") {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function button(text, action) {
    const el = element("button", text);
    el.type = "button";
    el.addEventListener("click", () => guard(action));
    return el;
  }
  function error(message = "") { $("follow-error").textContent = message; }
  async function guard(action) {
    error();
    try { await action(); } catch (err) { error(err.message || "The operation could not be confirmed. Refresh before retrying."); }
  }
  async function request(path = "", method = "GET", body = null) {
    const key = $("key").value.trim();
    if (!key) throw new Error("Set your local access key in Admin, then return here.");
    const headers = { Authorization: "Bearer " + key };
    if (body !== null) headers["Content-Type"] = "application/json";
    const response = await fetch("/api/follow-through" + path, {
      method, headers, cache: "no-store", body: body === null ? null : JSON.stringify(body)
    });
    if ($("key").value.trim() !== key) throw new Error("The access key changed. Reopen follow-through.");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Review the required fields. Request failed (" + response.status + ").");
    return data;
  }
  function setActive(item) {
    active = item ? { id: item.id, title: item.title } : null;
    chip.replaceChildren();
    chip.hidden = !active;
    if (active) {
      chip.append(element("span", "Context: " + active.title), button("Clear", () => setActive(null)));
      chip.title = "Explicit context for Companion, Engineer chat and Sage. Not connected to Engineer jobs.";
    }
  }
  function clear() {
    generation += 1;
    setActive(null);
    selected = null;
    draftConversation = null;
    draftKey = crypto.randomUUID();
    detail.replaceChildren(element("p", "Select a tracker or choose New tracker.", "follow-muted"));
    $("follow-list").replaceChildren();
    $("follow-count").textContent = "";
    error();
    if (dialog.open) dialog.close();
  }
  function localValue(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }
  function isoValue(value) {
    if (!value) return null;
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) throw new Error("Choose a valid date and time.");
    // Reject nonexistent local wall-clock times (for example a spring-forward gap).
    if (localValue(date.toISOString()) !== value) throw new Error("That local time does not exist. Choose another time.");
    return date.toISOString();
  }
  function field(form, name, label, value, options = {}) {
    const wrap = element("label", label, "follow-field");
    const input = document.createElement(options.area ? "textarea" : "input");
    input.name = name;
    input.id = "follow-field-" + name;
    if (!options.area) input.type = options.type || "text";
    input.value = value || "";
    input.required = Boolean(options.required);
    input.readOnly = Boolean(options.readOnly);
    if (options.max) input.maxLength = options.max;
    if (options.area) input.rows = options.rows || 2;
    wrap.append(input);
    form.append(wrap);
    return input;
  }
  const labels = {active: "Active", waiting: "Waiting", needs_you: "Needs you", resolved_by_user: "Resolved — reported by you", cancelled: "Cancelled"};

  function renderEditor(item = null, source = "", conversation = null) {
    selected = item;
    draftConversation = conversation;
    draftKey = crypto.randomUUID();
    detail.replaceChildren();
    const heading = element("h3", item ? item.title : "Review before tracking");
    detail.append(heading);
    if (item) {
      detail.append(element("p", labels[item.state] + " · revision " + item.version + " · " + new Date(item.updated_at).toLocaleString(), "follow-muted"));
      const actions = element("div", undefined, "follow-toolbar");
      actions.append(button("Use in chat", () => { setActive(item); dialog.close(); $("prompt").focus(); }));
      actions.append(button("Delete tracker", async () => {
        if (!window.confirm("Delete this tracker, its source copy and event history? The original chat message stays. Backups are not securely erased.")) return;
        await request("/" + item.id + "?expected_version=" + item.version, "DELETE");
        if (active?.id === item.id) setActive(null);
        selected = null;
        detail.replaceChildren(element("p", "Tracker deleted. The original source message was not deleted."));
        await refresh();
      }));
      detail.append(actions);
      const evidence = element("details", undefined, "follow-source");
      evidence.append(element("summary", "Source and revision history"));
      evidence.append(element("p", item.source_kind === "conversation_message" ? "Selected saved user message. Deleting its conversation also deletes this tracker." : "User-provided text; not independently verified.", "follow-muted"));
      evidence.append(element("pre", item.source_text));
      evidence.append(element("p", "Source SHA-256: " + item.source_sha256, "follow-hash"));
      if (item.events_truncated) evidence.append(element("p", "Latest 100 revisions shown; export contains the full history."));
      for (const event of item.events || []) {
        evidence.append(element("h4", "Revision " + event.version + " · " + new Date(event.created_at).toLocaleString()));
        evidence.append(element("pre", JSON.stringify(event.details, null, 2)));
      }
      detail.append(evidence);
      if (["resolved_by_user", "cancelled"].includes(item.state)) {
        detail.append(element("p", item.resolution_note || "Cancelled by you."));
        detail.append(button("Reopen", async () => {
          await request("/" + item.id, "PATCH", {expected_version: item.version, state: "active", note: "Reopened by the user"});
          await show(item.id); await refresh();
        }));
        return;
      }
    }
    const form = element("form", undefined, "follow-form");
    if (!item) field(form, "source_text", conversation ? "Selected user message (saved source)" : "Source text you want to track", source, {area: true, rows: 3, required: true, readOnly: Boolean(conversation), max: 12000});
    field(form, "title", "Goal", item?.title || source.split("\n")[0].slice(0, 180), {required: true, max: 180});
    field(form, "success_criteria", "Resolved when… (what result are you expecting?)", item?.success_criteria, {area: true, required: true, max: 1200});
    field(form, "next_action", "Next step (optional)", item?.next_action, {area: true, max: 1200});
    field(form, "waiting_on", "Waiting on whom or what? (optional)", item?.waiting_on, {max: 180});
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "Browser local time";
    detail.append(element("p", "Dates use " + zone + ". Blank means unspecified. Check dates appear here only; no notification is scheduled.", "follow-muted"));
    if (item?.time_zone && item.time_zone !== zone) detail.append(element("p", "Previously entered timezone: " + item.time_zone + ". Dates below are displayed in " + zone + ".", "follow-muted"));
    field(form, "due_at", "Deadline (optional)", localValue(item?.due_at), {type: "datetime-local"});
    field(form, "next_check_at", "Check again (optional)", localValue(item?.next_check_at), {type: "datetime-local"});
    if (item) {
      const label = element("label", "Current state", "follow-field");
      const select = element("select"); select.name = "state";
      for (const [state, text] of Object.entries(labels)) {
        const option = element("option", text); option.value = state; select.append(option);
      }
      select.value = item.state; label.append(select); form.append(label);
      field(form, "note", "Correction reason or completion evidence (your report)", "", {area: true, required: true, max: 2000});
    } else {
      const label = element("label", undefined, "follow-review");
      const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.name = "reviewed"; checkbox.required = true;
      label.append(checkbox, element("span", "I reviewed the source, goal and completion rule. Tracking does not authorize actions or schedule notifications."));
      form.append(label);
    }
    const save = element("button", item ? "Save reviewed correction" : "Track this"); save.type = "submit";
    form.append(save);
    form.addEventListener("submit", event => {
      event.preventDefault();
      guard(async () => {
        save.disabled = true;
        const epoch = generation;
        try {
          const data = new FormData(form);
          const body = {};
          for (const name of ["title", "success_criteria", "next_action", "waiting_on"]) body[name] = String(data.get(name) || "").trim();
          body.due_at = isoValue(String(data.get("due_at") || ""));
          body.next_check_at = isoValue(String(data.get("next_check_at") || ""));
          body.time_zone = zone;
          if (item) {
            Object.assign(body, {expected_version: item.version, state: data.get("state"), note: String(data.get("note") || "").trim()});
          } else {
            Object.assign(body, {request_id: draftKey, reviewed: data.get("reviewed") === "on", source_text: String(data.get("source_text") || ""), conversation_id: draftConversation});
          }
          const result = await request(item ? "/" + item.id : "", item ? "PATCH" : "POST", body);
          if (epoch !== generation) return;
          if (active?.id === result.outcome.id) setActive(result.outcome);
          view = result.outcome.view; offset = 0;
          await show(result.outcome.id); await refresh();
        } finally { save.disabled = false; }
      });
    });
    detail.append(form);
  }
  async function show(id) {
    const epoch = ++generation;
    const data = await request("/" + id);
    if (epoch !== generation) return;
    renderEditor(data.outcome);
  }
  async function refresh() {
    const epoch = generation, requestedView = view, requestedOffset = offset;
    const data = await request("?view=" + view + "&limit=25&offset=" + offset);
    if (epoch !== generation || view !== requestedView || offset !== requestedOffset) return;
    const list = $("follow-list"); list.replaceChildren();
    for (const tab of $("follow-tabs").querySelectorAll("button")) {
      tab.setAttribute("aria-pressed", String(tab.dataset.view === view));
      const name = {needs_you: "Needs you", waiting: "Waiting", closed: "Closed"}[tab.dataset.view];
      tab.textContent = name + " (" + data.counts[tab.dataset.view] + ")";
    }
    $("follow-count").textContent = data.total ? (offset + 1) + "–" + (offset + data.items.length) + " of " + data.total + " · refreshed " + new Date(data.checked_at).toLocaleTimeString() : "Nothing in this view.";
    for (const item of data.items) {
      const card = button("", () => show(item.id)); card.className = "follow-card";
      card.append(element("strong", item.title), element("span", labels[item.state] + (item.check_due ? " · check due" : "")));
      if (item.next_action) card.append(element("small", item.next_action));
      list.append(card);
    }
    if (!data.items.length) list.append(element("p", "Track one real commitment. You choose the goal, the next step and what counts as resolved.", "follow-empty"));
    $("follow-prev").disabled = offset === 0;
    $("follow-next").disabled = !data.has_more;
  }
  async function open() {
    if (!dialog.open) dialog.showModal();
    await refresh();
  }
  function capture(text, conversation = null) {
    generation += 1;
    if (!dialog.open) dialog.showModal();
    error(); renderEditor(null, text, conversation);
    guard(refresh);
  }
  nav.addEventListener("click", () => guard(open));
  $("follow-through-mobile")?.addEventListener("click", () => guard(open));
  $("follow-close").addEventListener("click", () => dialog.close());
  $("follow-new").addEventListener("click", () => { generation += 1; error(); renderEditor(); });
  $("follow-refresh").addEventListener("click", () => guard(async () => { if (selected) await show(selected.id); await refresh(); }));
  $("follow-tabs").addEventListener("click", event => {
    const target = event.target.closest("[data-view]");
    if (!target) return;
    view = target.dataset.view; offset = 0; guard(refresh);
  });
  $("follow-prev").addEventListener("click", () => { offset = Math.max(0, offset - 25); guard(refresh); });
  $("follow-next").addEventListener("click", () => { offset += 25; guard(refresh); });
  $("follow-export").addEventListener("click", () => guard(async () => {
    if (!window.confirm("This export contains private source text and revision history. Continue?")) return;
    const data = await request("/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
    const link = document.createElement("a"); link.href = url; link.download = "helix-follow-through.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }));
  $("key").addEventListener("change", clear);
  window.helixFollowThrough = {capture, clear, activeId: () => active?.id || null};
})();
