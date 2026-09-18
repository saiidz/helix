import {LIMITS, BUILTIN_SKILLS, safePath, skipDirectory, decodeText, readSkill, buildRequest,
  parseProposal, diffPreview, writeApproved} from './engineer-core.mjs';
const $ = id => document.getElementById(id);
let entries = [], skills = [...BUILTIN_SKILLS], selected = null, proposal = null, recovery = null;
let controller = null, runId = 0, busy = false;
const enabled = new Set();
function status(message, error = false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function theme(next) {
  document.documentElement.dataset.theme = next;
  $('theme').textContent = next === 'dark' ? 'Light mode' : 'Dark mode';
  try { localStorage.setItem('helixTheme', next); } catch {}
}
try { theme(localStorage.getItem('helixTheme') === 'light' ? 'light' : 'dark'); } catch { theme('dark'); }
$('theme').addEventListener('click', () => theme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
function setBusy(value) {
  busy = value;
  document.querySelectorAll('[data-control],#skills input').forEach(el => {el.disabled = value;});
  $('stop').disabled = !value; updateApply();
}
function updateApply() { $('apply').disabled = busy || !proposal || !$('approve').checked || !selected?.handle; }
function resetProposal() { proposal = null; $('proposal').hidden = true; $('approve').checked = false; updateApply(); }
function renderSkills() {
  $('skills').replaceChildren();
  for (const skill of skills) {
    const label = document.createElement('label'), input = document.createElement('input');
    input.type = 'checkbox'; input.checked = enabled.has(skill.id);
    const text = document.createElement('span'), title = document.createElement('strong'), small = document.createElement('small');
    title.textContent = skill.name; small.textContent = skill.description; text.append(title, small); label.append(input, text);
    input.addEventListener('change', () => {
      if (input.checked && enabled.size >= LIMITS.skills) { input.checked = false; status('Enable at most three skills.', true); return; }
      if (input.checked) enabled.add(skill.id); else enabled.delete(skill.id);
      $('skill-preview').textContent = skills.filter(s => enabled.has(s.id)).map(s => s.name + '\n\n' + s.text).join('\n\n———\n\n') || 'No skills enabled.';
      resetProposal();
    });
    const details = document.createElement('details'), heading = document.createElement('summary'), instructions = document.createElement('pre');
    heading.textContent = 'Read instructions'; instructions.textContent = skill.text; details.append(heading, instructions);
    $('skills').append(label, details);
  }
}
function selectEntry(index) {
  selected = entries[index] || null; resetProposal(); recovery = null; $('restore').hidden = true;
  $('path').value = selected?.path || ''; $('path').readOnly = !selected?.isNew;
  $('source').textContent = selected ? (selected.content.slice(0, 30000) || '(Empty new file)') : 'No file selected.';
  $('source-title').textContent = selected && selected.content.length > 30000 ? 'Source preview · first 30,000 characters' : 'Original source';
  $('answer').textContent = 'The answer or proposed change will appear here.';
}
function renderEntries() {
  $('files').replaceChildren();
  entries.forEach((entry, index) => { const option = document.createElement('option'); option.value = index; option.textContent = entry.path; $('files').append(option); });
  if (entries.length) $('files').value = '0'; selectEntry(0);
}
async function openEntry(file, path, handle = null) {
  safePath(path); const content = decodeText(await file.arrayBuffer());
  return {path, content, handle, size: file.size, isNew: false};
}
async function collect(items) {
  const next = [], rejected = []; let total = 0, visited = 0;
  for await (const item of items) {
    if (++visited > 5000) { rejected.push('Folder enumeration limit reached.'); break; }
    if (next.length >= LIMITS.files) { rejected.push('400-file limit reached.'); break; }
    try {
      // Validate before reading; avoid loading unsupported or oversized files.
      safePath(item.path);
      const file = item.file || await item.handle.getFile();
      if (file.size > LIMITS.fileBytes) throw new Error('over 350 KB');
      if (total + file.size > LIMITS.totalBytes) { rejected.push('12 MB total limit reached.'); break; }
      const entry = await openEntry(file, item.path, item.handle || null);
      if (next.some(e => e.path === entry.path)) throw new Error('duplicate path');
      next.push(entry); total += file.size;
    } catch (error) { rejected.push(item.path + ': ' + error.message); }
  }
  entries = next; renderEntries();
  $('file-status').textContent = `${entries.length} file(s) selected · ${total.toLocaleString()} bytes · ${rejected.length} skipped/limit notices. Filename exclusions are not a secret scanner; review files before sending.`;
  $('file-status').title = rejected.slice(0, 15).join('\n');
  status(entries.length ? 'Files opened in this tab. Select one to analyze or edit. No files have been sent to the model yet.' : 'No supported files were selected.', !entries.length);
}
async function* walk(directory, prefix = '', depth = 0, budget = {seen: 0}) {
  if (depth > 12) return;
  for await (const [name, handle] of directory.entries()) {
    if (++budget.seen > 5000) return;
    const path = prefix + name;
    if (handle.kind === 'directory') { if (!skipDirectory(name)) yield* walk(handle, path + '/', depth + 1, budget); }
    else yield {path, handle};
  }
}
async function guarded(action) {
  if (busy) return;
  try { await action(); } catch (error) { if (error.name !== 'AbortError') status(error.message, true); }
}
$('open').addEventListener('click', () => guarded(async () => {
  if (typeof window.showOpenFilePicker !== 'function') { $('file-input').click(); return; }
  const handles = await window.showOpenFilePicker({multiple: true}); setBusy(true);
  try { await collect(handles.map(handle => ({path: handle.name, handle}))); } finally { setBusy(false); }
}));
$('folder').addEventListener('click', () => guarded(async () => {
  if (typeof window.showDirectoryPicker !== 'function') { $('folder-input').click(); return; }
  const directory = await window.showDirectoryPicker({mode: 'read'}); setBusy(true);
  try { await collect(walk(directory)); } finally { setBusy(false); }
}));
for (const id of ['file-input', 'folder-input']) $(id).addEventListener('change', () => guarded(async () => {
  const items = Array.from($(id).files || []).map(file => ({file, path: file.webkitRelativePath || file.name}));
  setBusy(true); try { await collect(items); } finally { setBusy(false); $(id).value = ''; }
}));
$('files').addEventListener('change', () => { if (!busy) selectEntry(Number($('files').value)); });
$('new').addEventListener('click', () => {
  if (busy) return; if (entries.length >= LIMITS.files) {status('400-file limit reached.', true); return;} entries.push({path: 'new-file.py', content: '', handle: null, size: 0, isNew: true});
  renderEntries(); $('files').value = String(entries.length - 1); selectEntry(entries.length - 1); $('path').focus();
});
$('path').addEventListener('input', () => { if (selected?.isNew) { selected.path = $('path').value; const option = $('files').selectedOptions[0]; if (option) option.textContent = selected.path; resetProposal(); } });
$('instruction').addEventListener('input', resetProposal);
$('import-skill').addEventListener('click', () => { if (!busy) $('skill-input').click(); });
$('skill-input').addEventListener('change', () => guarded(async () => {
  const file = $('skill-input').files?.[0]; if (!file) return;
  setBusy(true);
  try {
    if (file.size > 24000 || skills.length >= BUILTIN_SKILLS.length + 12) throw new Error('Skill size or 12-import limit exceeded.');
    skills.push(readSkill(file.name, decodeText(await file.arrayBuffer()))); renderSkills();
    status('Skill imported but disabled. Review its instructions and enable it explicitly before use.');
  } finally { $('skill-input').value = ''; setBusy(false); }
}));
$('clear').addEventListener('click', () => {
  if (busy) return; entries = []; skills = [...BUILTIN_SKILLS]; enabled.clear(); renderSkills(); renderEntries();
  $('skill-preview').textContent = 'No skills enabled.'; $('file-status').textContent = 'No files selected.';
  status('Files, file handles, draft recovery, and imported skills cleared from this tab.');
});
async function run(edit) {
  if (busy) return;
  try {
    if (!selected) throw new Error('Open a file or create a new draft first.');
    const key = $('key').value.trim(); if (key.length < 24) throw new Error('Enter the local access key under Local connection.');
    const entry = selected, request = buildRequest(entry, $('instruction').value, skills.filter(s => enabled.has(s.id)), edit);
    resetProposal(); setBusy(true); controller = new AbortController(); const thisRun = ++runId;
    status('Waiting for the local model. No files will change without a separate approval.');
    const response = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json',
      Authorization: 'Bearer ' + key, 'Idempotency-Key': crypto.randomUUID()}, body: JSON.stringify(request), signal: controller.signal});
    let result; try { result = await response.json(); } catch { throw new Error('HELIX returned an unreadable response. Restart the updated backend.'); }
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'HELIX request failed (HTTP ' + response.status + ').');
    if (thisRun !== runId) return;
    if (typeof result.text !== 'string') throw new Error('HELIX returned no answer text.');
    $('answer').textContent = result.text;
    if (edit) {
      if (result.provider_mode !== 'local') throw new Error('A real local model is required for an applicable draft. Demo or cloud output cannot be applied.');
      proposal = await parseProposal(result.text, entry);
      $('summary').textContent = proposal.summary + ' · Model-generated; tests have not been run.';
      $('diff').textContent = diffPreview(proposal.before, proposal.after); $('after').textContent = proposal.after;
      $('proposal').hidden = false; updateApply();
      status('Draft ready for review. Nothing has been changed. ' + (entry.handle ? 'Approve to save this selected file.' : 'Download is available; this selection has no writable handle.'));
    } else status('Analysis complete. This is model output, not a test run or verified audit.');
  } catch (error) { status(error.name === 'AbortError' ? 'Request stopped in this tab. No files changed; the local backend may finish the request.' : error.message, error.name !== 'AbortError'); }
  finally { controller = null; setBusy(false); }
}
$('analyze').addEventListener('click', () => run(false)); $('draft').addEventListener('click', () => run(true));
$('stop').addEventListener('click', () => { ++runId; controller?.abort(); });
$('approve').addEventListener('change', updateApply);
function download(text, name) {
  const blob = new Blob([text], {type: 'text/plain;charset=utf-8'}), url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
}
$('download').addEventListener('click', () => { if (proposal && !busy) download(proposal.after, proposal.path.split('/').at(-1)); });
$('backup').addEventListener('click', () => { if (proposal && !busy) download(proposal.before, proposal.path.split('/').at(-1) + '.original.txt'); });
$('apply').addEventListener('click', () => guarded(async () => {
  if (!proposal || !$('approve').checked) return;
  const draft = proposal, entry = selected;
  recovery = {entry, draft}; // Keep the original even when a write fails.
  const pending = writeApproved(entry, draft, true); setBusy(true);
  try {
    entry.content = await pending; $('source').textContent = entry.content;
    resetProposal(); $('restore').hidden = false; status('Saved and read back successfully: ' + entry.path + '. Tests were not run. Restore original is available in this tab.');
  } finally { setBusy(false); }
}));
$('restore').addEventListener('click', () => guarded(async () => {
  if (!recovery || !window.confirm('Restore the original contents of ' + recovery.entry.path + '? This is another file write.')) return;
  const {entry, draft} = recovery;
  const undo = {path: draft.path, before: draft.after, after: draft.before, beforeHash: draft.afterHash, afterHash: draft.beforeHash};
  const pending = writeApproved(entry, undo, true); setBusy(true);
  try { entry.content = await pending; $('source').textContent = entry.content; recovery = null; $('restore').hidden = true; resetProposal(); status('Original file restored and read back successfully.'); }
  finally { setBusy(false); }
}));
renderSkills();

window.addEventListener('beforeunload', event => { if (recovery || proposal) {event.preventDefault(); event.returnValue = '';} });
