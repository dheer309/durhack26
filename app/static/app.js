const tabs = document.querySelectorAll('[data-tab]');
function showTab(moveFocus = false) {
  const name = location.hash === '#identify' ? 'identify' : 'create';
  document.querySelectorAll('.view').forEach(view => { view.hidden = view.id !== name; });
  tabs.forEach(tab => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle('active', active);
    if (active) tab.setAttribute('aria-current', 'page');
    else tab.removeAttribute('aria-current');
  });
  if (moveFocus) document.querySelector(`#${name}-heading`).focus();
}
window.addEventListener('hashchange', () => showTab(true));
showTab();

const documentInput = document.querySelector('#document');
documentInput.addEventListener('change', () => {
  const file = documentInput.files[0];
  document.querySelector('#document-name').textContent = file?.name || 'Choose a PDF';
  document.querySelector('#summary-name').textContent = file?.name || 'No PDF selected';
  document.querySelector('#summary-size').textContent = file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : 'Your original file stays on this device.';
});
document.querySelector('#image').addEventListener('change', event => {
  document.querySelector('#file-name').textContent = event.target.files[0]?.name || 'Choose a photo';
});

async function submitForm(form, url, feedback, busyText, onSuccess) {
  const button = form.querySelector('button');
  const originalLabel = button.innerHTML;
  button.disabled = true;
  button.textContent = busyText;
  feedback.textContent = '';
  feedback.classList.remove('success');
  try {
    const response = await fetch(url, { method: 'POST', body: new FormData(form) });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Something went wrong. Please try again.');
    }
    await onSuccess(response);
  } catch (error) {
    feedback.textContent = error.message || 'Something went wrong. Please try again.';
  } finally {
    button.disabled = false;
    button.innerHTML = originalLabel;
  }
}

document.querySelector('#generate-form').addEventListener('submit', event => {
  event.preventDefault();
  const feedback = document.querySelector('#generate-feedback');
  submitForm(event.currentTarget, '/generate', feedback, 'Generating…', async response => {
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)/)?.[1] || 'trace.pdf';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    feedback.classList.add('success');
    feedback.textContent = 'Marked PDF downloaded. Change the recipient to create another copy.';
    // Refresh the recent list without clearing the document being edited.
    try {
      const page = await fetch('/');
      if (page.ok) {
        const html = new DOMParser().parseFromString(await page.text(), 'text/html');
        document.querySelector('.recent').replaceWith(html.querySelector('.recent'));
      }
    } catch (_) { /* The PDF is already generated; the list can refresh later. */ }
  });
});

document.querySelector('#decode-form').addEventListener('submit', event => {
  event.preventDefault();
  document.querySelector('#result').hidden = true;
  submitForm(event.currentTarget, '/decode', document.querySelector('#decode-feedback'), 'Identifying…', async response => {
    const data = await response.json();
    for (const key of ['name', 'email', 'title']) document.querySelector(`#result-${key}`).textContent = data[key];
    document.querySelector('#result-id').textContent = data.identifier;
    document.querySelector('#result-confidence').textContent = `${data.confidence}%`;
    document.querySelector('#result').hidden = false;
  });
});
