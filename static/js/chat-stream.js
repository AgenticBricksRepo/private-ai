// chat-stream.js — SSE streaming via fetch + ReadableStream
const messagesEl = document.getElementById('messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const cancelBtn = document.getElementById('cancel-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const modelSelect = document.getElementById('model-select');
const agentSelect = document.getElementById('agent-select');
const fileInput = document.getElementById('file-input');
const agentBanner = document.getElementById('agent-banner');
const agentBannerName = document.getElementById('agent-banner-name');
const agentBannerDesc = document.getElementById('agent-banner-desc');

function updateAgentBanner() {
  const opt = agentSelect.selectedOptions[0];
  if (opt && opt.value) {
    agentBannerName.textContent = opt.textContent;
    agentBannerDesc.textContent = opt.dataset.desc ? '— ' + opt.dataset.desc : '';
    agentBanner.classList.remove('hidden');
  } else {
    agentBanner.classList.add('hidden');
  }
}
agentSelect.addEventListener('change', updateAgentBanner);
updateAgentBanner();

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderMarkdown(text) {
  if (typeof marked !== 'undefined') {
    return '<div class="md-content">' + marked.parse(text) + '</div>';
  }
  return escapeHtml(text);
}

function appendMessage(role, content) {
  const align = role === 'user' ? 'chat-end' : 'chat-start';
  const bubble = role === 'user' ? 'chat-bubble-primary' : 'chat-bubble-secondary';
  const label = role === 'user' ? 'You' : (role === 'tool' ? 'System' : 'Assistant');
  const rendered = role === 'user' ? escapeHtml(content) : renderMarkdown(content);
  messagesEl.insertAdjacentHTML('beforeend',
    `<div class="chat ${align}" data-testid="message-${role}">
       <div class="chat-header opacity-50 text-xs">${label}</div>
       <div class="chat-bubble ${bubble}">${rendered}</div>
     </div>`);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function createSession() {
  const res = await fetch('/api/sessions', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({model_id: modelSelect.value, agent_id: agentSelect.value || null}),
  });
  const data = await res.json();
  currentSessionId = data.id;
  return data.id;
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  if (!currentSessionId) await createSession();

  chatInput.value = '';
  appendMessage('user', text);

  sendBtn.classList.add('hidden');
  cancelBtn.classList.remove('hidden');

  // Create assistant bubble to stream raw text into, then render markdown when done
  messagesEl.insertAdjacentHTML('beforeend',
    `<div class="chat chat-start" data-testid="message-assistant">
       <div class="chat-header opacity-50 text-xs">Assistant</div>
       <div class="chat-bubble chat-bubble-secondary" id="streaming-bubble"></div>
     </div>`);
  const bubble = document.getElementById('streaming-bubble');
  let rawText = '';

  try {
    const res = await fetch(`/api/sessions/${currentSessionId}/chat`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({content: text}),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});

      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === 'text') {
            rawText += event.content;
            bubble.textContent = rawText;  // Plain text while streaming
          }
          else if (event.type === 'tool_call') appendMessage('tool', `Using tool: ${event.name}`);
          else if (event.type === 'error') rawText += `\n[Error: ${event.message}]`;
        } catch (e) { /* skip malformed lines */ }
      }
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  } catch (e) {
    rawText += '\n[Connection error]';
  }

  // Render final markdown
  bubble.innerHTML = renderMarkdown(rawText);
  bubble.removeAttribute('id');
  sendBtn.classList.remove('hidden');
  cancelBtn.classList.add('hidden');
}

cancelBtn.addEventListener('click', () => {
  if (currentSessionId) fetch(`/api/sessions/${currentSessionId}/cancel`, {method: 'POST'});
});

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }});
newChatBtn.addEventListener('click', () => { currentSessionId = null; messagesEl.innerHTML = ''; });

fileInput.addEventListener('change', async () => {
  if (!fileInput.files.length) return;
  if (!currentSessionId) await createSession();
  const form = new FormData();
  form.append('file', fileInput.files[0]);
  const res = await fetch(`/api/sessions/${currentSessionId}/files`, {method: 'POST', body: form});
  const data = await res.json();
  if (res.ok) {
    appendMessage('tool', `Attached: ${fileInput.files[0].name}`);
  } else {
    appendMessage('tool', `[Upload failed: ${data.error}]`);
  }
  fileInput.value = '';
});
