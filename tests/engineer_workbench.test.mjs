import test from 'node:test';
import assert from 'node:assert/strict';
import {safePath, skipDirectory, decodeText, readSkill, buildRequest, parseProposal, diffPreview,
  digest, writeApproved, BUILTIN_SKILLS} from '../helix/static/engineer-core.mjs';
const entry = () => ({path: 'src/example.py', content: 'print(1)\n'});
const raw = (path = 'src/example.py', content = 'print(2)\n') => JSON.stringify({path, summary: 'Fix; tests not run.', content});
for (const path of ['../x.py', '/etc/passwd', 'C:/x.py', 'a\\b.py', 'a//b.py', 'a/./b.py', '.env', '.ssh/config', '.git/config', 'node_modules/a.js', '.helix/config.json', 'credentials.json', 'access-token.json', 'private.key', 'image.png', 'nul.py', 'foo /a.py', 'a\u0000.py']) {
  test('reject unsafe path: ' + JSON.stringify(path), () => assert.throws(() => safePath(path)));
}
test('allows common code paths and reviewed example config', () => { for (const p of ['src/a.py', 'src/A.tsx', 'README.md', 'Dockerfile', '.gitignore', '.env.example']) assert.equal(safePath(p), p); });
test('skip generated and private directories', () => { assert.equal(skipDirectory('.git'), true); assert.equal(skipDirectory('node_modules'), true); assert.equal(skipDirectory('src'), false); });
test('reject binary and invalid utf8', () => { assert.throws(() => decodeText(new Uint8Array([0]))); assert.throws(() => decodeText(new Uint8Array([255]))); });
test('preserve BOM and CRLF when reading', () => { const s = '\uFEFFhello\r\n'; assert.equal(decodeText(new TextEncoder().encode(s)), s); });
test('skills import is inert and reads metadata', () => { const s = readSkill('SKILL.md', '---\nname: "safe-review"\ndescription: Review code\n---\nNever run commands.'); assert.equal(s.name, 'safe-review'); assert.equal(s.description, 'Review code'); });
test('reject executable and oversized skills', () => { assert.throws(() => readSkill('tool.js', 'alert(1)')); assert.throws(() => readSkill('SKILL.md', 'x'.repeat(6001))); });
test('code request uses local-only no-spend privacy settings', () => { const r = buildRequest(entry(), 'fix this', [BUILTIN_SKILLS[0]], true); assert.equal(r.allow_external, false); assert.equal(r.web_enabled, false); assert.equal(r.memory_enabled, false); assert.equal(r.max_cost_usd, 0); assert.equal(r.role, 'engineer'); assert.equal(r.max_output_tokens, 2048); assert.ok(r.messages.every(m => m.content.length <= 12000)); assert.equal('conversation_id' in r, false); });
test('large files analyze as explicit excerpt, not overwriteable drafts', () => { const e = {...entry(), content: 'x'.repeat(14000)}; assert.throws(() => buildRequest(e, 'change', [], true)); assert.ok(buildRequest(e, 'explain', []).messages.some(m => m.content.includes('EXCERPT ONLY'))); });
test('skill limit and prompt limit are enforced', () => { assert.throws(() => buildRequest(entry(), 'fix', BUILTIN_SKILLS)); assert.throws(() => buildRequest(entry(), 'x'.repeat(2001), [])); });
test('complete exact-target draft gets immutable checksums', async () => { const p = await parseProposal(raw(), entry()); assert.equal(p.before, 'print(1)\n'); assert.equal(p.after, 'print(2)\n'); assert.ok(Object.isFrozen(p)); assert.equal(p.beforeHash.length, 64); });
test('reject path redirection, extra fields, empty and truncated output', async () => { for (const r of [raw('../other.py'), '{"path":', raw(undefined, ''), JSON.stringify({path: 'src/example.py', summary: 'x', content: 'x', command: 'rm'})]) await assert.rejects(parseProposal(r, entry())); });
test('preserve original CRLF and BOM on a draft', async () => { const e = {...entry(), content: '\uFEFFprint(1)\r\n'}; assert.equal((await parseProposal(raw(), e)).after, '\uFEFFprint(2)\r\n'); });
test('no-op output rejected', async () => await assert.rejects(parseProposal(raw(undefined, 'print(1)\n'), entry())));
test('diff remains text, not HTML', () => { assert.equal(diffPreview('x\ny', 'x\n<script>'), '@@ lines 2–2 → 2–2 @@\n- y\n+ <script>'); });
function handle(initial, permission = 'granted', fail = false) {
  let content = initial, writes = 0, aborted = false;
  return {get content() {return content;}, get writes() {return writes;}, get aborted() {return aborted;},
    requestPermission: async () => permission,
    getFile: async () => ({arrayBuffer: async () => new TextEncoder().encode(content).buffer}),
    createWritable: async () => ({write: async v => {writes++; if (fail) throw new Error('disk'); content = v;}, close: async () => {}, abort: async () => {aborted = true;}})};
}
test('approval required before writes', async () => { const e = {...entry(), handle: handle(entry().content)}; await assert.rejects(writeApproved(e, await parseProposal(raw(), e))); assert.equal(e.handle.writes, 0); });
test('permission denial never writes', async () => { const e = {...entry(), handle: handle(entry().content, 'denied')}; await assert.rejects(writeApproved(e, await parseProposal(raw(), e), true), /permission/); assert.equal(e.handle.writes, 0); });
test('changed disk file never overwritten', async () => { const e = {...entry(), handle: handle('external change')}; await assert.rejects(writeApproved(e, await parseProposal(raw(), e), true), /changed since/); assert.equal(e.handle.writes, 0); });
test('proposal hash tampering never writes', async () => { const e = {...entry(), handle: handle(entry().content)}; const p = await parseProposal(raw(), e); await assert.rejects(writeApproved(e, {...p, after: 'evil'}, true), /integrity/); assert.equal(e.handle.writes, 0); });
test('approved write is read back and supports verified undo', async () => { const e = {...entry(), handle: handle(entry().content)}; const p = await parseProposal(raw(), e); assert.equal(await writeApproved(e, p, true), p.after); assert.equal(e.handle.writes, 1); const undo = {path:p.path, after:p.before, beforeHash:p.afterHash, afterHash:p.beforeHash}; assert.equal(await writeApproved(e, undo, true), p.before); });
test('failed write attempts abort and reports uncertainty', async () => { const e = {...entry(), handle: handle(entry().content, 'granted', true)}; await assert.rejects(writeApproved(e, await parseProposal(raw(), e), true), /Saving failed/); assert.equal(e.handle.aborted, true); });
test('missing handle has no apply capability', async () => await assert.rejects(writeApproved(entry(), await parseProposal(raw(), entry()), true), /handle/));
test('digest distinguishes newline formats', async () => assert.notEqual(await digest('a\n'), await digest('a\r\n')));
