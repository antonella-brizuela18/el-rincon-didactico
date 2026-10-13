/* Native admin/order forms, theme preference and payment-status polling. */
(() => {
  'use strict';
  const system = matchMedia('(prefers-color-scheme: dark)');
  let chosen;
  try { chosen = localStorage.getItem('rincon-mode'); } catch (_) {}
  let pageLife = new AbortController();
  let submission = false;
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
            if (value.status !== order.dataset.orderStatus) { if (!submission) location.reload(); return; }
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
    document.documentElement.dataset.navigation = 'native';
  }
  function unsaved() {
    return document.querySelector('[data-customization-form][data-dirty="true"]');
  }
  document.addEventListener('click', event => {
    const toggle = event.target.closest?.('.mode-toggle');
    if (toggle) { chosen = document.body.dataset.mode === 'dark' ? 'light' : 'dark'; applyMode(); try {localStorage.setItem('rincon-mode', chosen);} catch (_) {} return; }
  });
  document.addEventListener("submit", () => { submission = true; });
  window.addEventListener("beforeunload", event => {
    if (unsaved() && !submission) { event.preventDefault(); event.returnValue = ""; }
  });
  mount();
})();
