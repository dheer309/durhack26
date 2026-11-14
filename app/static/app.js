const tabs = document.querySelectorAll('[data-tab]');
function showTab() {
  const name = location.hash === '#identify' ? 'identify' : 'create';
  document.querySelectorAll('.view').forEach(view => { view.hidden = view.id !== name; });
  tabs.forEach(tab => { tab.classList.toggle('active', tab.dataset.tab === name); if (tab.dataset.tab === name) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current'); });
}
window.addEventListener('hashchange', showTab); showTab();
const title = document.querySelector('#title'), body = document.querySelector('#body');
title.addEventListener('input', () => document.querySelector('#preview-title').textContent = title.value || 'Document title');
body.addEventListener('input', () => { document.querySelector('#preview-body').textContent = body.value || 'Your content will appear here.'; document.querySelector('#count').textContent = `${body.value.length} / 2400`; });
document.querySelector('#image').addEventListener('change', event => { document.querySelector('#file-name').textContent = event.target.files[0]?.name || 'Choose a photo'; });
async function submitForm(form, url, feedback, onSuccess) {
  const button = form.querySelector('button'); button.disabled = true; feedback.textContent = '';
  try { const response = await fetch(url, {method:'POST', body:new FormData(form)}); if (!response.ok) { const data = await response.json(); throw new Error(data.error || 'Something went wrong. Please try again.'); } await onSuccess(response); }
  catch (error) { feedback.textContent = error.message || 'Something went wrong. Please try again.'; }
  finally { button.disabled = false; }
}
document.querySelector('#generate-form').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/generate', document.querySelector('#generate-feedback'), async response => { const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)/)?.[1] || 'trace.pdf'; link.click(); URL.revokeObjectURL(url); location.reload(); }); });
document.querySelector('#decode-form').addEventListener('submit', event => { event.preventDefault(); document.querySelector('#result').hidden = true; submitForm(event.currentTarget, '/decode', document.querySelector('#decode-feedback'), async response => { const data = await response.json(); for (const key of ['name','email','title']) document.querySelector(`#result-${key}`).textContent = data[key]; document.querySelector('#result-id').textContent = data.identifier; document.querySelector('#result-confidence').textContent = `${data.confidence}%`; document.querySelector('#result').hidden = false; }); });
