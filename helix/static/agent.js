'use strict';
const $ = id => document.getElementById(id);
let key = '', sessionId = '', cursor = 0, approvalId = null, connected = false, timer = null, busy = false;
async function api(path, body) {
  const response = await fetch('/api/engineer-agent/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {Authorization: 'Bearer ' + key, 'Content-Type': 'application/json'},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})
  });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Request was rejected. Check the input.');
  return result;
}
function message(value) { $('status').textContent = value; }
function event(item) {
  const empty = $('log').querySelector('.empty'); if (empty) empty.remove();
  const details = document.createElement('details');
  const title = document.createElement('summary');
  title.textContent = '#' + item.id + ' · ' + item.kind.replaceAll('_', ' ');
  const content = document.createElement('pre');
  content.textContent = typeof item.value === 'string' ? item.value : JSON.stringify(item.value, null, 2);
  details.append(title, content);
  if (['error', 'summary', 'session_result'].includes(item.kind)) details.open = true;
  $('log').append(details);
  while ($('log').children.length > 200) $('log').firstChild.remove();
}
async function poll() {
  if (!connected || busy) return;
  busy = true;
  try {
    const result = await api('status?since=' + cursor + '&session_id=' + encodeURIComponent(sessionId));
    $('connection').textContent = result.enabled ? 'Workspace: ' + result.workspace : 'Repository control is disabled. Restart HELIX using START_HELIX_AGENT.cmd.';
    const session = result.session;
    $('start').disabled = !result.enabled || Boolean(session?.active);
    $('stop').disabled = !session?.active;
    message(session ? session.status.replaceAll('_', ' ') : (result.enabled ? 'Ready' : 'Workspace not enabled'));
    if (session) {
      if (session.id !== sessionId) { sessionId = session.id; cursor = 0; $('log').replaceChildren(); }
      for (const item of session.events) event(item);
      cursor = session.cursor;
      const approval = session.approval;
      $('approval').hidden = !approval;
      if (approval && approval.id !== approvalId) {
        approvalId = approval.id;
        $('approval-title').textContent = approval.kind === 'RUN' ? 'Run this command with your Windows permissions?' : 'Apply these exact file changes?';
        $('preview').textContent = approval.preview;
        $('approval-warning').textContent = approval.kind === 'RUN' ? 'This is not sandboxed. It may access the network, modify other files, or use your account permissions. Approve only a command you trust.' : 'Recovery copies are created before writing. Concurrent changes are checked again after approval.';
        $('approve').disabled = false; $('deny').disabled = false;
      }
      if (!approval) approvalId = null;
    }
  } catch (error) { message(error.message); }
  finally { busy = false; }
}
$('connect').addEventListener('click', async () => {
  key = $('key').value.trim(); connected = Boolean(key); cursor = 0;
  $('log').replaceChildren();
  clearInterval(timer); await poll(); timer = setInterval(poll, 1000);
});
$('start').addEventListener('click', async () => {
  const task = $('task').value.trim();
  if (!task) { message('Enter a task first.'); return; }
  $('start').disabled = true;
  try {
    const skills = $('skills').value.split(',').map(s => s.trim()).filter(Boolean);
    await api('start', {task, skills, max_steps: 24});
    sessionId = ''; cursor = 0; approvalId = null; $('log').replaceChildren(); await poll();
  } catch (error) { message(error.message); $('start').disabled = false; }
});
$('stop').addEventListener('click', async () => {
  try { await api('stop', {}); message('Stop requested. In-flight inference may finish; no next action is permitted.'); await poll(); }
  catch (error) { message(error.message); }
});
async function decide(decision) {
  if (!approvalId) return;
  $('approve').disabled = true; $('deny').disabled = true;
  try { await api('decision', {approval_id: approvalId, decision}); approvalId = null; $('approval').hidden = true; await poll(); }
  catch (error) { message(error.message); $('approve').disabled = false; $('deny').disabled = false; }
}
$('approve').addEventListener('click', () => decide('approve'));
$('deny').addEventListener('click', () => decide('deny'));
$('theme').addEventListener('click', () => {
  const light = document.body.classList.toggle('light');
  $('theme').textContent = light ? 'Dark mode' : 'Light mode';
});
