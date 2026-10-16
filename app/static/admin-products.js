/* Progressive enhancement: the same validated form works with or without a dialog. */
(() => {
  'use strict';
  const modal = document.querySelector('.product-modal');
  let opener, dirty = false, saving = false, opening;
  const button = (text, action) => {
    const el = document.createElement('button');
    el.type = 'button'; el.className = 'text-button'; el.textContent = text;
    el.addEventListener('click', action); return el;
  };
  function mount(form) {
    form.addEventListener('input', () => { dirty = true; });
    const picker = form.querySelector('.drive-picker');
    const browser = picker.querySelector('[data-drive-browser]');
    const selection = picker.querySelector('[data-drive-selection]');
    let busy = false;
    async function load(folder = '', token = '', search = '') {
      if (busy) return;
      busy = true; browser.hidden = false; browser.textContent = 'Buscando en Drive…';
      try {
        const url = new URL(picker.dataset.driveUrl, location.origin);
        url.search = new URLSearchParams({folder, token, search});
        const response = await fetch(url, {headers: {Accept: 'application/json'}});
        if (response.redirected) throw new Error('La sesión venció. Abrí nuevamente el panel.');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        browser.replaceChildren();
        const heading = document.createElement('strong'); heading.textContent = data.folder.name; browser.append(heading);
        if (data.folder.id !== data.root) browser.append(button('Carpeta principal', () => load()));
        const searchRow = document.createElement('div'); searchRow.className = 'drive-search';
        const input = document.createElement('input'); input.type = 'search'; input.placeholder = 'Buscar archivo en esta carpeta'; input.setAttribute('aria-label', input.placeholder); input.value = search;
        searchRow.append(input, button('Buscar', () => load(data.folder.id, '', input.value)));
        input.addEventListener('keydown', event => {if (event.key === 'Enter') {event.preventDefault(); load(data.folder.id, '', input.value);}});
        browser.append(searchRow);
        const list = document.createElement('ul');
        for (const file of data.files) {
          const row = document.createElement('li');
          row.append(button((file.kind === 'folder' ? '▣ ' : file.kind === 'image' ? 'Portada · ' : 'Archivo · ') + file.name, () => {
            if (file.kind === 'folder') {load(file.id); return;}
            const name = file.kind === 'image' ? 'drive_image' : 'drive_file';
            form.elements[name].value = file.id;
            form.elements[file.kind === 'image' ? 'image' : 'digital_file'].value = '';
            if (file.kind !== 'image') form.elements.kind.value = 'digital';
            dirty = true; browser.hidden = true;
            selection.textContent = `Elegido: ${file.name}. Se copiará al guardar. Completá los datos del recurso.`;
            selection.append(button('Quitar selección', () => {form.elements[name].value = ''; selection.textContent = ''; dirty = true;}));
          }));
          list.append(row);
        }
        if (!data.files.length) list.textContent = 'No hay archivos compatibles en esta carpeta.';
        browser.append(list);
        if (data.token) browser.append(button('Página siguiente', () => load(data.folder.id, data.token, search)));
      } catch (error) { browser.textContent = error.message || 'No pudimos abrir Drive. Intentá nuevamente.'; }
      finally {busy = false;}
    }
    picker.querySelector('[data-drive-open]').addEventListener('click', () => load());
    for (const [local, remote] of [['image','drive_image'],['digital_file','drive_file']]) {
      form.elements[local].addEventListener('change', () => {if (form.elements[local].files.length) {form.elements[remote].value = ''; selection.textContent = '';}});
    }
    if (!modal?.contains(form)) return;
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (saving) return;
      saving = true; const submit = form.querySelector('[type="submit"], .editor-save button');
      const error = form.querySelector('[data-product-error]');
      submit.disabled = true; error.textContent = 'Guardando recurso…';
      try {
        const response = await fetch(form.action, {method:'POST', body:new FormData(form), headers:{'X-Product-Modal':'1', Accept:'application/json'}});
        if (response.redirected) throw new Error('La sesión venció. Volvé a ingresar al panel.');
        if (!response.headers.get('Content-Type')?.includes('application/json')) throw new Error('No pudimos guardar. Revisá el tamaño de los archivos (20 MB en total) o recargá el panel.');
        const data = await response.json();
        if (!response.ok || !data.saved) throw new Error(data.error || 'No pudimos guardar el recurso.');
        dirty = false; location.reload();
      } catch (problem) {error.textContent = problem.message;}
      finally {saving = false; submit.disabled = false;}
    });
  }
  document.querySelectorAll('.product-editor').forEach(mount);
  document.querySelectorAll('[data-product-modal]').forEach(link => link.addEventListener('click', async event => {
    if (!modal || !modal.showModal || event.ctrlKey || event.metaKey) return;
    event.preventDefault(); opener = link; dirty = false;
    opening?.abort(); opening = new AbortController();
    const body = modal.querySelector('[data-product-body]'); body.textContent = 'Abriendo formulario…';
    modal.querySelector('h2').textContent = link.textContent.trim() === 'Editar' ? 'Editar recurso' : 'Nuevo recurso';
    modal.showModal();
    try {
      const url = new URL(link.href); url.searchParams.set('modal','1');
      const response = await fetch(url,{signal:opening.signal});
      if (response.redirected || !response.ok) {location.assign(link.href); return;}
      body.innerHTML = await response.text();
      if (!modal.open) return;
      const form = body.querySelector('form'); mount(form);
      form.elements.title.focus();
      if (link.hasAttribute('data-open-drive')) form.querySelector('[data-drive-open]').click();
    } catch (error) {if (error.name === 'AbortError') return; body.textContent = 'No pudimos abrir el formulario. '; const fallback = document.createElement('a'); fallback.href = link.href; fallback.textContent = 'Abrir página de edición'; body.append(fallback);}
  }));
  function close(event) {
    if (saving || (dirty && !confirm('¿Cerrar y descartar los cambios sin guardar?'))) {event?.preventDefault(); return;}
    dirty = false; opening?.abort(); modal.close(); opener?.focus();
  }
  modal?.querySelector('[data-product-close]').addEventListener('click', close);
  modal?.addEventListener('cancel', event => {event.preventDefault(); close(event);});
  window.addEventListener('beforeunload', event => {if (modal?.open && dirty) {event.preventDefault(); event.returnValue = '';}});
})();
