/* Progressive SPA: one document, server-authoritative pages and forms, no private HTML cache. */
(() => {
  'use strict';
  const system = matchMedia('(prefers-color-scheme: dark)');
  let chosen;
  try { chosen = localStorage.getItem('rincon-mode'); } catch (_) {}
  let pageLife = new AbortController();
  let requestLife;
  let submission = false;
  let sequence = 0;
  let displayedURL = location.href;
  const headSelector = 'meta[name="description"],meta[name="robots"],meta[property^="og:"],link[rel="canonical"]';
  const applyMode = () => {
    const mode = chosen || document.body.dataset.defaultMode || 'system';
    document.body.dataset.mode = mode === 'system' ? (system.matches ? 'dark' : 'light') : mode;
    const button = document.querySelector('.mode-toggle');
    if (button) {
      const dark = document.body.dataset.mode === 'dark';
      button.setAttribute('aria-pressed', String(dark));
      button.setAttribute('aria-label', dark ? 'Activar modo claro' : 'Activar modo oscuro');
      button.querySelector('span').textContent = dark ? 'Modo claro' : 'Modo oscuro';
    }
  };
  system.addEventListener('change', () => { if (!chosen) applyMode(); });
  function eligible(url) {
    return url.origin === location.origin && /^(\/|\/catalogo|\/producto\/\d+|\/carrito(?:\/.*)?|\/pedido(?:\/.*)?|\/admin(?:\/.*)?|\/privacidad(?:\/.*)?)$/.test(url.pathname) && !/\/descarga\//.test(url.pathname);
  }
  function status(message, error = false) {
    let region = document.getElementById('navigation-status');
    if (!region) {
      region = document.createElement('p'); region.id = 'navigation-status'; region.className = 'navigation-status';
      region.setAttribute('role', 'status'); region.setAttribute('aria-live', 'polite');
      document.body.append(region);
    }
    region.classList.toggle('navigation-error', error);
    region.textContent = message;
  }
  function rememberScroll() {
    history.replaceState({rincon: true, x: scrollX, y: scrollY}, '', location.href);
  }
  function moveTo(url, restore) {
    const hash = new URL(url, location.href).hash;
    let target;
    if (hash) { try { target = document.getElementById(decodeURIComponent(hash.slice(1))); } catch (_) {} }
    if (restore) scrollTo({left: restore.x || 0, top: restore.y || 0, behavior: 'instant'});
    else if (target) target.scrollIntoView({behavior: 'instant', block: 'start'});
    else scrollTo({top: 0, left: 0, behavior: 'instant'});
    const heading = document.querySelector('main h1') || document.querySelector('main');
    if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus({preventScroll: true}); }
  }
  function mount() {
    applyMode();
    const signal = pageLife.signal;
    const order = document.querySelector('[data-status-url]');
    if (order) {
      let timer, failures = 0;
      signal.addEventListener('abort', () => clearTimeout(timer), {once: true});
      const poll = async () => {
        if (signal.aborted) return;
        if (!document.hidden && !document.documentElement.dataset.navigating) {
          try {
            const response = await fetch(order.dataset.statusUrl, {cache: 'no-store', signal});
            if (!response.ok) throw new Error();
            const value = await response.json();
            if (value.status !== order.dataset.orderStatus) { if (!submission) navigate(location.href, {replace: true}); return; }
            failures = 0;
          } catch (error) { if (error.name === 'AbortError') return; failures++; }
        }
        timer = setTimeout(poll, Math.min(60000, 8000 * (failures + 1)));
      };
      timer = setTimeout(poll, 8000);
    }
    document.querySelector('[data-customization-form]')?.addEventListener('change', event => {
      const indicator = event.currentTarget.querySelector('[data-settings-status]');
      if (indicator) { indicator.textContent = 'Tenés cambios sin guardar.'; indicator.classList.add('unsaved'); }
      event.currentTarget.dataset.dirty = 'true';
    }, {signal});
    const quote = document.querySelector('[data-quote-url]');
    quote?.addEventListener('click', async () => {
      const form = quote.closest('form'), result = form.querySelector('[data-quote-result]');
      quote.disabled = true; result.textContent = 'Consultando MiCorreo…';
      try {
        const response = await fetch(quote.dataset.quoteUrl, {method: 'POST', signal,
          body: new URLSearchParams({csrf_token: form.elements.csrf_token.value, postal_code: form.elements.postal_code.value})});
        const value = await response.json();
        if (!response.ok) { result.textContent = value.error || 'No pudimos cotizar. Coordinaremos por WhatsApp.'; return; }
        const currency = new Intl.NumberFormat('es-AR', {style: 'currency', currency: 'ARS'});
        result.textContent = (value.test ? 'PRUEBA — no es una tarifa real. ' : '') + value.rates.map(rate => `${rate.name} · ${rate.delivery}: ${currency.format(rate.cents / 100)}`).join(' / ') + (value.valid_to ? ` · Vigencia informada: ${value.valid_to}` : '');
      } catch (error) { if (error.name !== 'AbortError') result.textContent = 'No pudimos cotizar ahora. Podés continuar y coordinar por WhatsApp.'; }
      finally { if (!signal.aborted) quote.disabled = false; }
    }, {signal});
    document.documentElement.dataset.navigation = 'spa';
  }
  function unsaved() {
    return document.querySelector('[data-customization-form][data-dirty="true"]');
  }
  async function navigate(href, options = {}) {
    if (submission) return;
    const url = new URL(href, location.href);
    const post = options.method === 'POST';
    if (post) submission = true;
    requestLife?.abort(); requestLife = new AbortController();
    const ticket = ++sequence;
    const submittedForm = options.form;
    const buttons = submittedForm ? [...submittedForm.querySelectorAll('button[type="submit"],button:not([type]),input[type="submit"]')].filter(button => !button.disabled) : [];
    buttons.forEach(button => { button.disabled = true; });
    document.documentElement.dataset.navigating = 'true';
    document.querySelector('main')?.setAttribute('aria-busy', 'true');
    status(post ? 'Enviando…' : 'Cargando…');
    const controller = requestLife;
    let timeout = setTimeout(() => controller.abort(), 30000);
    let destination;
    try {
      const response = await fetch(url.href, {method: options.method || 'GET', body: options.body,
        credentials: 'same-origin', cache: 'no-store', headers: {'X-Rincon-Navigation': '1'}, signal: requestLife.signal});
      if (ticket !== sequence) return;
      destination = new URL(response.url);
      if (destination.origin !== location.origin) throw new Error('Unexpected redirect');
      if (!response.headers.get('content-type')?.includes('text/html')) throw new Error('Not a page');
      const html = await response.text();
      const next = new DOMParser().parseFromString(html, 'text/html');
      next.querySelectorAll('script').forEach(node => node.remove());
      if (!next.querySelector('meta[name="rincon-app"]') || !next.querySelector('main')) throw new Error('Not a store page');
      const revision = next.querySelector('meta[name="rincon-revision"]')?.content;
      if (revision !== document.querySelector('meta[name="rincon-revision"]')?.content) {
        location.assign(destination.href); return; // GET only; never repeat a submitted POST.
      }
      if (!options.pop) rememberScroll();
      const finalURL = destination.pathname + destination.search + (destination.pathname === url.pathname ? url.hash : '');
      if (options.replace || options.pop) history.replaceState({rincon: true}, '', finalURL);
      else history.pushState({rincon: true}, '', finalURL);
      displayedURL = location.href;
      pageLife.abort(); pageLife = new AbortController();
      document.title = next.title;
      document.head.querySelectorAll(headSelector).forEach(node => node.remove());
      next.head.querySelectorAll(headSelector).forEach(node => document.head.append(document.importNode(node, true)));
      for (const attribute of [...document.body.attributes]) document.body.removeAttribute(attribute.name);
      for (const attribute of next.body.attributes) document.body.setAttribute(attribute.name, attribute.value);
      document.body.replaceChildren(...[...next.body.childNodes].filter(node => node.nodeName !== 'SCRIPT').map(node => document.importNode(node, true)));
      mount();
      if (post && submittedForm?.matches('[data-customization-form]')) {
        const appearance = document.querySelector('link[data-appearance]');
        if (appearance) appearance.href = '/apariencia.css?refresh=' + Date.now();
      }
      moveTo(finalURL, options.restore);
      if (response.status >= 400) status('Revisá los datos indicados en esta página.', true);
      else status('');
      document.dispatchEvent(new Event('rincon:navigated'));
    } catch (error) {
      if (ticket !== sequence) return;
      if (error.name === 'AbortError' && !post) {
        // A newer navigation cancels the old one; a timeout falls back to a normal GET.
        if (requestLife.signal.aborted) location.assign(url.href);
      } else if (!post) location.assign(url.href);
      else {
        status('No pudimos confirmar el envío. No lo repetimos automáticamente. Revisá tu correo o el estado del pedido y recargá esta página antes de intentar otra vez.', true);
        submittedForm?.setAttribute('data-uncertain', 'true');
      }
    } finally {
      clearTimeout(timeout);
      if (ticket === sequence) {
        submission = false; delete document.documentElement.dataset.navigating;
        document.querySelector('main')?.removeAttribute('aria-busy');
        buttons.forEach(button => { if (!submittedForm?.hasAttribute('data-uncertain')) button.disabled = false; });
      }
    }
  }
  document.addEventListener('click', event => {
    const toggle = event.target.closest?.('.mode-toggle');
    if (toggle) { chosen = document.body.dataset.mode === 'dark' ? 'light' : 'dark'; applyMode(); try {localStorage.setItem('rincon-mode', chosen);} catch (_) {} return; }
    const link = event.target.closest?.('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target || link.hasAttribute('download') || link.hasAttribute('data-native')) return;
    const url = new URL(link.href, location.href);
    if (!eligible(url) || (url.pathname === location.pathname && url.search === location.search && url.hash)) return;
    if (unsaved()) return; // Native navigation retains beforeunload protection.
    event.preventDefault(); navigate(url.href);
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.hasAttribute('data-native') || form.target) return;
    const url = new URL(event.submitter?.hasAttribute('formaction') ? event.submitter.formAction : (form.action || location.href), location.href);
    if (!eligible(url) || /\/pedido\/[^/]+\/pagar$/.test(url.pathname)) return;
    if (form.hasAttribute('data-uncertain')) { event.preventDefault(); return; }
    event.preventDefault();
    if (submission) return;
    const method = (event.submitter?.getAttribute('formmethod') || form.method || 'get').toUpperCase();
    const data = new FormData(form);
    if (event.submitter?.name) data.append(event.submitter.name, event.submitter.value);
    if (method === 'GET') {
      url.search = new URLSearchParams([...data].filter(([,value]) => typeof value === 'string')).toString();
      navigate(url.href, {form});
    } else if (method === 'POST') navigate(url.href, {method, body: data, form});
  });
  window.addEventListener('popstate', event => {
    if (submission) { location.reload(); return; }
    if (unsaved() && !confirm('Tenés cambios sin guardar. ¿Querés salir de esta página?')) {
      history.pushState({rincon: true, x: scrollX, y: scrollY}, '', displayedURL); return;
    }
    navigate(location.href, {pop: true, restore: event.state});
  });
  window.addEventListener('beforeunload', event => {
    if (unsaved() && !submission) { event.preventDefault(); event.returnValue = ''; }
  });
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  history.replaceState({rincon: true, x: scrollX, y: scrollY}, '', location.href);
  mount();
})();
