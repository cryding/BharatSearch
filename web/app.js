(() => {
  const form = document.querySelector('#search-form');
  const input = document.querySelector('#query');
  const status = document.querySelector('#status');
  const results = document.querySelector('#results');
  const dialog = document.querySelector('#settings');
  const apiInput = document.querySelector('#api-url');
  const DEFAULT_API = 'http://127.0.0.1:8000';
  let apiBase = DEFAULT_API;
  try { apiBase = localStorage.getItem('bharatsearch_api') || DEFAULT_API; } catch (_) {}
  apiInput.value = apiBase;
  const safeUrl = value => {
    try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : '#'; }
    catch (_) { return '#'; }
  };
  function message(text) { status.textContent = text; }
  function showResults(items) {
    results.replaceChildren();
    if (!items.length) {
      const p = document.createElement('p');
      p.className = 'result';
      p.textContent = 'No indexed results yet. This independent search index only returns pages that have been crawled.';
      results.append(p); return;
    }
    for (const item of items) {
      const article = document.createElement('article'); article.className = 'result';
      const link = document.createElement('a'); link.href = safeUrl(item.url); link.textContent = item.title || item.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      const url = document.createElement('div'); url.className = 'url'; url.textContent = item.url;
      const desc = document.createElement('p'); desc.textContent = item.description || (item.snippet || '').replace(/<\/?b>/g, '');
      article.append(link, url, desc); results.append(article);
    }
  }
  async function search(q) {
    input.value = q; results.replaceChildren();
    message('Searching the indexed pages…');
    try {
      const endpoint = new URL('/api/search', apiBase);
      endpoint.searchParams.set('q', q);
      const response = await fetch(endpoint, {headers: {'Accept': 'application/json'}});
      if (!response.ok) throw new Error('Search API returned HTTP ' + response.status);
      const data = await response.json();
      showResults(data.results || []);
      message((data.results || []).length + ' results from the BharatSearch index');
    } catch (err) {
      message('Search API unavailable. Start the backend and configure its URL using ⚙.');
      const p = document.createElement('p'); p.className = 'result'; p.textContent = err.message; results.append(p);
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); const q = input.value.trim(); if (q) search(q); });
  document.querySelector('#clear').addEventListener('click', () => { input.value = ''; input.focus(); results.replaceChildren(); message('Ready to search the indexed pages.'); });
  document.querySelector('#lucky').addEventListener('click', () => { input.value = 'India'; search('India'); });
  document.querySelectorAll('[data-query]').forEach(button => button.addEventListener('click', () => { input.value = button.dataset.query; input.focus(); }));
  document.querySelector('#settings-open').addEventListener('click', () => dialog.showModal());
  document.querySelector('#save-api').addEventListener('click', event => {
    event.preventDefault();
    try {
      const u = new URL(apiInput.value.trim());
      if (!['http:', 'https:'].includes(u.protocol)) throw new Error();
      apiBase = u.origin;
      try { localStorage.setItem('bharatsearch_api', apiBase); } catch (_) {}
      dialog.close(); message('API URL saved: ' + apiBase);
    } catch (_) { alert('Enter a valid HTTP or HTTPS API URL.'); }
  });
})();
