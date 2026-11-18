// Ticket Arena, local mode: a small stand-in for the claude.ai dashboard runtime (`dash`),
// so the same index.html runs from the control server at http://localhost:8765.
(function () {
  const SOURCES = { tickets: '/data/tickets.json', comments: '/data/comments.json', team: '/data/team.json', drafts: '/data/drafts.json' };
  const store = {};
  const calcs = [];
  const draws = {};
  const onDatas = [];
  let started = false;

  Object.keys(SOURCES).forEach((k) => { store[k] = { status: 'loading', data: [] }; });

  function runCalcs() {
    calcs.forEach(({ id, inputs, fn }) => {
      const ins = inputs.map((i) => store[i] || { status: 'missing', data: [] });
      if (ins.every((x) => x.status === 'ok')) {
        try { store[id] = { status: 'ok', data: fn(...ins.map((x) => x.data)) }; } catch (e) { console.error(id, e); store[id] = { status: 'error', data: null }; }
      } else {
        store[id] = { status: ins.some((x) => x.status === 'error') ? 'error' : 'loading', data: null };
      }
    });
  }

  function runDraw(name) {
    const fn = draws[name];
    if (!fn) return;
    document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => {
      try { fn(el); } catch (e) { console.error('draw', name, e); }
    });
  }

  function drawAll() {
    onDatas.forEach((fn) => { try { fn(); } catch (e) { console.error(e); } });
    Object.keys(draws).forEach(runDraw);
  }

  async function load() {
    await Promise.all(Object.entries(SOURCES).map(async ([id, url]) => {
      try {
        const r = await fetch(url, { cache: 'no-store' });
        if (!r.ok) throw new Error(r.status);
        store[id] = { status: 'ok', data: await r.json() };
      } catch (e) {
        if (!store[id] || store[id].status !== 'ok') store[id] = { status: 'error', data: [] };
      }
    }));
    runCalcs();
    if (window.ta) window.ta.refreshing = false;
    if (window.ta) window.ta.pendingSwitch = null;
    drawAll();
  }

  window.dash = {
    data: (id) => store[id] || { status: 'missing', data: [] },
    calc: (id, def) => { calcs.push({ id, inputs: def.inputs, fn: def.fn }); store[id] = { status: 'loading', data: null }; },
    loader: () => {},
    draw: (name, fn) => { if (fn) { draws[name] = fn; if (started) runDraw(name); } else runDraw(name); },
    onData: (fn) => { onDatas.push(fn); },
    refresh: () => load(),
    params: () => ({}), setParams: () => {}, resetParams: () => {}, setLink: () => {},
    colors: [],
  };
  window.taReload = load;

  window.taToast = (msg, ok) => {
    let t = document.getElementById('ta-toast');
    if (!t) {
      t = document.createElement('div'); t.id = 'ta-toast'; t.setAttribute('role', 'status');
      t.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);max-width:min(560px,calc(100vw - 32px));padding:12px 18px;font:600 14px "Chakra Petch",system-ui,sans-serif;color:#0c0a17;z-index:50;box-shadow:0 8px 30px rgba(0,0,0,.5);transition:opacity .3s';
      document.body.append(t);
    }
    t.textContent = msg;
    t.style.background = ok === false ? '#ff5a4e' : '#77f56a';
    t.style.opacity = '1';
    clearTimeout(t._h);
    t._h = setTimeout(() => { t.style.opacity = '0'; }, 4500);
  };

  document.addEventListener('DOMContentLoaded', () => {
    started = true;
    drawAll();
    load();
    setInterval(load, 60000); // pick up the server's 15-minute refreshes without reloading the page
  });
})();
