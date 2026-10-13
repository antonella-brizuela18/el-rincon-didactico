(() => {
  const body = document.body;
  const system = matchMedia('(prefers-color-scheme: dark)');
  let chosen;
  try { chosen = localStorage.getItem('rincon-mode'); } catch (_) {}
  const initial = ['light', 'dark'].includes(chosen) ? chosen : body.dataset.defaultMode;
  const apply = mode => {
    body.dataset.mode = mode === 'system' ? (system.matches ? 'dark' : 'light') : mode;
    const button = document.querySelector('.mode-toggle');
    if (button) {
      button.setAttribute('aria-pressed', String(body.dataset.mode === 'dark'));
      button.setAttribute('aria-label', body.dataset.mode === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro');
      button.querySelector('span').textContent = body.dataset.mode === 'dark' ? 'Modo claro' : 'Modo oscuro';
    }
  };
  apply(initial || 'system');
  system.addEventListener('change', () => { if (!chosen && initial === 'system') apply('system'); });
  document.querySelector('.mode-toggle')?.addEventListener('click', () => {
    chosen = body.dataset.mode === 'dark' ? 'light' : 'dark';
    apply(chosen);
    try { localStorage.setItem('rincon-mode', chosen); } catch (_) {}
  });
  const order = document.querySelector('[data-status-url]');
  if (order) {
    let failures = 0;
    const poll = async () => {
      if (!document.hidden) {
        try {
          const response = await fetch(order.dataset.statusUrl, {cache: 'no-store'});
          if (!response.ok) throw new Error();
          const value = await response.json();
          if (value.status !== order.dataset.orderStatus) { location.reload(); return; }
          failures = 0;
        } catch (_) { failures++; }
      }
      setTimeout(poll, Math.min(60000, 8000 * (failures + 1)));
    };
    setTimeout(poll, 8000);
  }
  const quote = document.querySelector('[data-quote-url]');
  const customization = document.querySelector('[data-customization-form]');
  customization?.addEventListener('change', () => {
    const status = customization.querySelector('[data-settings-status]');
    status.textContent = 'Tenés cambios sin guardar.';
    status.classList.add('unsaved');
  });
  quote?.addEventListener('click', async () => {
    const form = quote.closest('form');
    const result = document.querySelector('[data-quote-result]');
    quote.disabled = true;
    result.textContent = 'Consultando MiCorreo…';
    try {
      const response = await fetch(quote.dataset.quoteUrl, {method: 'POST', body: new URLSearchParams({csrf_token: form.elements.csrf_token.value, postal_code: form.elements.postal_code.value})});
      const value = await response.json();
      if (!response.ok) { result.textContent = value.error || 'No pudimos cotizar. Coordinaremos por WhatsApp.'; return; }
      const currency = new Intl.NumberFormat('es-AR', {style: 'currency', currency: 'ARS'});
      result.textContent = (value.test ? 'PRUEBA — no es una tarifa real. ' : '') + value.rates.map(rate => `${rate.name} · ${rate.delivery}: ${currency.format(rate.cents / 100)}`).join(' / ') + (value.valid_to ? ` · Vigencia informada: ${value.valid_to}` : '');
    } catch (_) { result.textContent = 'No pudimos cotizar ahora. Podés continuar y coordinar por WhatsApp.'; }
    finally { quote.disabled = false; }
  });
})();
