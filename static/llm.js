/**
 * WINDI LLM Chat - Dual Channel Support v1.1
 * Date: 26-Jan-2026
 */

async function sendLLM() {
  const input = document.getElementById('llmInput');
  const msg = input.value.trim();
  if (!msg) return;
  
  const editorText = document.getElementById('editor').innerText;
  const box = document.getElementById('llmMessages');
  
  box.innerHTML += '<div class="llm-msg llm-user">' + escapeHtml(msg) + '</div>';
  input.value = '';
  
  box.innerHTML += '<div class="llm-msg llm-windi" id="thinking">Thinking...</div>';
  box.scrollTop = box.scrollHeight;
  
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        context: editorText,
        dragon: 'claude'
      })
    });
    
    const d = await r.json();
    
    const thinking = document.getElementById('thinking');
    if (thinking) thinking.remove();
    
    if (d.response) {
      const respId = 'resp-' + Date.now();
      const isDocument = d.is_document || false;
      const hasDocContent = d.document_content && d.document_content.trim().length > 0;
      
      let responseHtml = '<div class="llm-msg llm-windi" id="' + respId + '">';
      responseHtml += '<pre class="llm-text">' + escapeHtml(d.response) + '</pre>';
      
      if (d.receipt) {
        responseHtml += '<div class="llm-receipt">' + escapeHtml(d.receipt) + '</div>';
      }
      
      if (isDocument) {
        responseHtml += '<div class="llm-doc-indicator">📄 Document detected</div>';
      }
      
      if (hasDocContent) {
        const docContentB64 = btoa(unescape(encodeURIComponent(d.document_content)));
        responseHtml += '<button class="btn-insert" data-rid="' + respId + '" data-doc="' + docContentB64 + '">+ Insert Document</button>';
      } else {
        const fullContentB64 = btoa(unescape(encodeURIComponent(d.response)));
        responseHtml += '<button class="btn-insert" data-rid="' + respId + '" data-doc="' + fullContentB64 + '">+ Insert</button>';
      }
      
      responseHtml += '</div>';
      box.innerHTML += responseHtml;
      
    } else if (d.error) {
      box.innerHTML += '<div class="llm-msg llm-windi">[!] ' + escapeHtml(d.error) + '</div>';
    } else {
      box.innerHTML += '<div class="llm-msg llm-windi">[!] Unknown error</div>';
    }
    
  } catch (e) {
    const thinking = document.getElementById('thinking');
    if (thinking) thinking.remove();
    box.innerHTML += '<div class="llm-msg llm-windi">[!] Connection error</div>';
  }
  
  box.scrollTop = box.scrollHeight;
}

document.addEventListener("click", e => {
  if (e.target.classList.contains("btn-insert")) {
    insertToEditor(e.target);
  }
});

function insertToEditor(button) {
  const docContentB64 = button.dataset.doc;
  if (!docContentB64) return;
  
  try {
    const docContent = decodeURIComponent(escape(atob(docContentB64)));
    const editor = document.getElementById('editor');
    if (!editor) return;
    
    const htmlContent = escapeHtml(docContent).replace(/\n/g, '<br>');
    
    if (editor.innerText.trim().length > 0) {
      editor.innerHTML += '<br><br><hr style="border:1px solid #ccc;margin:20px 0;"><br>';
    }
    
    editor.innerHTML += htmlContent;
    
    button.disabled = true;
    button.textContent = '✓ Inserted';
    button.style.background = '#718096';
    
  } catch (e) {
    console.error('Insert error:', e);
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
