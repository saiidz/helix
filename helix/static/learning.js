'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let key = '';
  let enabled = false;
  let busy = false;
  const status = message => { $('status').textContent = message; };
  async function api(path, method = 'GET', body) {
    const headers = {Authorization: `Bearer ${key}`};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {method, headers, cache: 'no-store',
      body: body === undefined ? undefined : JSON.stringify(body)});
    let data;
    try { data = await response.json(); } catch (_) { throw new Error('Invalid server response. Restart the updated HELIX app.'); }
    if (!response.ok) {
      if (response.status === 401) disconnect();
      throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}).`);
    }
    return data;
  }
  async function action(fn) {
    if (busy) return;
    busy = true;
    document.querySelectorAll('button').forEach(button => { button.disabled = true; });
    try { await fn(); } catch (error) { status(error.message || 'Request failed.'); }
    finally {
      busy = false;
      document.querySelectorAll('button').forEach(button => { button.disabled = false; });
      $('review').disabled = !enabled || !$('conversation').value;
      $('disconnect').disabled = !key;
      document.querySelectorAll('[data-approve]').forEach(button => { button.disabled = !enabled; });
    }
  }
  function disconnect() {
    key = ''; enabled = false;
    $('key').value = '';
    $('items').replaceChildren();
    $('conversation').replaceChildren();
    $('workspace').hidden = true;
    $('disconnect').disabled = true;
    status('Disconnected.');
  }
  function button(text, handler) {
    const element = document.createElement('button');
    element.type = 'button'; element.textContent = text;
    element.addEventListener('click', () => action(handler));
    return element;
  }
  async function refresh() {
    const [state, history] = await Promise.all([api('/api/learning'), api('/api/conversations?limit=100')]);
    enabled = state.settings.enabled;
    $('enabled').checked = enabled;
    const selected = $('conversation').value;
    $('conversation').replaceChildren();
    for (const conversation of history.conversations) {
      const option = document.createElement('option');
      option.value = conversation.id; option.textContent = conversation.title;
      $('conversation').append(option);
    }
    if (history.conversations.some(item => item.id === selected)) $('conversation').value = selected;
    $('workspace').hidden = false;
    $('items').replaceChildren();
    const pending = state.items.filter(item => item.status === 'pending').length;
    $('count').textContent = `${pending} pending · ${state.items.length - pending} approved`;
    if (!state.items.length) {
      const empty = document.createElement('p');
      empty.className = 'muted'; empty.textContent = 'No suggestions yet. Enable learning, select a saved chat, and review it.';
      $('items').append(empty);
    }
    for (const item of state.items) {
      const article = document.createElement('article'); article.className = 'candidate';
      const heading = document.createElement('h3'); heading.textContent = `${item.kind} · ${item.status}`;
      const source = document.createElement('p'); source.className = 'source';
      source.textContent = `Source: chat ${item.conversation_id} · ${item.source_created_at}`;
      article.append(heading, source);
      const row = document.createElement('div'); row.className = 'row';
      if (item.status === 'pending') {
        const input = document.createElement('textarea'); input.value = item.content;
        input.maxLength = 280; input.rows = 3; input.setAttribute('aria-label', 'Review or edit suggested memory');
        article.append(input);
        const approve = button('Approve memory', async () => {
          await api(`/api/learning/${encodeURIComponent(item.id)}/approve`, 'POST', {content: input.value});
          await refresh(); status('Approved. Normal chat may now retrieve this memory when Memory is on.');
        });
        approve.dataset.approve = 'true'; approve.disabled = !enabled;
        row.append(approve, button('Dismiss', async () => {
          await api(`/api/learning/${encodeURIComponent(item.id)}/dismiss`, 'POST');
          await refresh(); status('Suggestion dismissed.');
        }));
      } else {
        const content = document.createElement('p'); content.textContent = item.content; article.append(content);
        row.append(button('Forget this memory', async () => {
          if (!confirm('Forget this learned memory? The original chat remains.')) return;
          await api(`/api/learning/items/${encodeURIComponent(item.id)}`, 'DELETE');
          await refresh(); status('Learning entry forgotten.');
        }));
      }
      article.append(row); $('items').append(article);
    }
  }
  $('connect-form').addEventListener('submit', event => {
    event.preventDefault();
    action(async () => { key = $('key').value.trim(); $('key').value = ''; await refresh(); status('Connected. Nothing is scanned until you select and review a chat.'); });
  });
  $('disconnect').addEventListener('click', disconnect);
  $('save-settings').addEventListener('click', () => action(async () => {
    await api('/api/learning/settings', 'PUT', {enabled: $('enabled').checked});
    await refresh(); status(enabled ? 'Reviewed learning enabled. Select a chat to review.' : 'Learning is off. Existing approved memories remain until forgotten.');
  }));
  $('refresh').addEventListener('click', () => action(async () => { await refresh(); status('Refreshed.'); }));
  $('review').addEventListener('click', () => action(async () => {
    const id = $('conversation').value;
    if (!id) throw new Error('Select a saved conversation first.');
    const result = await api(`/api/learning/conversations/${encodeURIComponent(id)}/review`, 'POST');
    await refresh();
    status(`${result.suggestions_added} suggestions from ${result.messages_considered} user messages. Nothing is learned until approved.${result.limit_reached ? ' Queue limit reached; export and clear entries before adding more.' : ''}`);
  }));
  $('clear').addEventListener('click', () => action(async () => {
    if (!confirm('Forget all learning entries and this feature’s derived memories, and turn learning off? Original chats, manual memories and previous exports remain.')) return;
    await api('/api/learning', 'DELETE'); await refresh(); status('Learning data cleared and learning turned off. Original chat history is unchanged.');
  }));
  $('export').addEventListener('click', () => action(async () => {
    const data = await api('/api/learning/export');
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'helix-chat-memory.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000); status('Export created. It contains private information; keep it secure.');
  }));
  $('theme').addEventListener('click', () => {
    const light = document.documentElement.dataset.theme !== 'light';
    document.documentElement.dataset.theme = light ? 'light' : 'dark';
    $('theme').textContent = light ? 'Dark mode' : 'Light mode';
  });
})();
