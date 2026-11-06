/* Kotiza - single-page UI (vanilla JS, no build step). */
'use strict';

const $app = document.getElementById('app');
const $modal = document.getElementById('modal');

// ---------------------------------------------------------------- helpers

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch('/api' + path, opts);
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty */ }
  if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status})`);
  return data;
}

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  let value;
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'class') e.className = v;
    else if (k === 'value') value = v;
    else if (k === 'dataset') Object.assign(e.dataset, v);
    else if (k === 'checked' || k === 'disabled' || k === 'selected') e[k] = !!v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    e.append(c instanceof Node ? c : String(c));
  }
  if (value !== undefined) e.value = value;
  return e;
}

function toast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.className = 'toast'; }, isError ? 4500 : 1600);
}

async function attempt(fn, okMsg) {
  try {
    const r = await fn();
    if (okMsg) toast(okMsg);
    return r;
  } catch (err) {
    toast(err.message, true);
    throw err;
  }
}

const num = (v) => { const x = parseFloat(v); return Number.isFinite(x) ? x : 0; };
const fmtN = (v, d = 2) => num(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtQ = (v) => num(v).toLocaleString('en-US', { maximumFractionDigits: 4 });

function moneyFmt(currency) {
  let f;
  try { f = new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD' }); }
  catch (_) { f = { format: (v) => `${currency} ${fmtN(v)}` }; }
  return (v) => f.format(num(v));
}
let money = moneyFmt('USD');

const esc = (s) => String(s ?? '').replace(/"/g, '\\"');

/** Re-render while keeping keyboard focus on the element with the same data-fk. */
async function keepFocus(fn) {
  const a = document.activeElement;
  const fk = a && a.dataset ? a.dataset.fk : null;
  const scroll = window.scrollY;
  await fn();
  window.scrollTo(0, scroll);
  if (fk) {
    const el = document.querySelector(`[data-fk="${esc(fk)}"]`);
    if (el) el.focus();
  }
}

function numInput(value, attrs = {}) {
  return h('input', { type: 'number', step: 'any', class: 'num', value: value ?? 0, ...attrs });
}

function options(list, selected, { blank } = {}) {
  const out = [];
  if (blank !== undefined) out.push(h('option', { value: '' }, blank));
  const groups = new Map();
  for (const o of list) {
    const g = o.group || '';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(h('option', { value: o.value, selected: String(o.value) === String(selected ?? '') }, o.label));
  }
  for (const [g, opts] of groups) {
    out.push(g ? h('optgroup', { label: g }, opts) : opts);
  }
  return out;
}

function field(label, input, cls) {
  return h('div', { class: 'field' + (cls ? ' ' + cls : '') }, h('label', {}, label), input);
}

const STATUSES = ['draft', 'submitted', 'won', 'lost'];
const METHOD_LABELS = { lump: 'Quantity × rate', pct_direct: '% of direct cost', pct_labor: '% of direct labor' };

// ---------------------------------------------------------------- reference data

const refs = {};
const REF_PATHS = {
  labor: '/labor', equipment: '/equipment', materials: '/materials', crews: '/crews',
  units: '/units', library: '/library', indirectLib: '/indirect-library',
};
async function loadRefs(...keys) {
  await Promise.all(keys.map(async (k) => { refs[k] = await api('GET', REF_PATHS[k]); }));
}
const byId = (list, id) => (list || []).find((x) => String(x.id) === String(id));

function unitDatalist() {
  return h('datalist', { id: 'units-list' }, (refs.units || []).map((u) => h('option', { value: u.code }, u.name)));
}

// ---------------------------------------------------------------- modal

function openModal(title, body, footer) {
  $modal.replaceChildren(
    h('div', { class: 'modal-head' }, h('h2', { style: 'margin:0' }, title),
      h('button', { class: 'icon', onclick: () => $modal.close(), title: 'Close' }, '✕')),
    h('div', { class: 'modal-body' }, body),
    h('div', { class: 'modal-foot' }, footer));
  if (!$modal.open) $modal.showModal();
}

function confirmBox(msg) { return window.confirm(msg); }

// ---------------------------------------------------------------- router

const routes = [
  [/^#\/estimates$/, renderEstimates, 'estimates'],
  [/^#\/estimate\/(\d+)$/, renderEstimate, 'estimates'],
  [/^#\/estimate\/(\d+)\/report$/, renderReport, 'estimates'],
  [/^#\/db\/crews$/, renderCrews, 'crews'],
  [/^#\/db\/library$/, renderLibrary, 'library'],
  [/^#\/db\/(labor|equipment|materials|indirect-library|units)$/, renderSimple, null],
];

async function router() {
  const hash = location.hash || '#/estimates';
  if ($modal.open) $modal.close();
  for (const [rx, fn, nav] of routes) {
    const m = hash.match(rx);
    if (m) {
      const navKey = nav || m[1];
      document.querySelectorAll('[data-nav]').forEach((a) => a.classList.toggle('active', a.dataset.nav === navKey));
      try {
        await fn(...m.slice(1));
      } catch (err) {
        $app.replaceChildren(h('div', { class: 'panel empty' }, 'Error: ' + err.message));
      }
      return;
    }
  }
  location.hash = '#/estimates';
}
window.addEventListener('hashchange', router);

// ================================================================ ESTIMATES LIST

async function renderEstimates() {
  const list = await api('GET', '/estimates');
  const newEstimate = async () => {
    const name = prompt('Estimate / project name:');
    if (!name) return;
    const today = new Date().toISOString().slice(0, 10);
    const r = await attempt(() => api('POST', '/estimates', {
      name, estimate_date: today, currency: 'USD', hours_per_day: 8,
      contingency_pct: 3, overhead_pct: 8, profit_pct: 10, bond_pct: 0, tax_pct: 7,
    }));
    location.hash = `#/estimate/${r.id}`;
  };
  $app.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', {}, h('h1', {}, 'Estimates'),
        h('div', { class: 'sub' }, 'Each estimate is built task by task from the cost database.')),
      h('div', { class: 'actions' }, h('button', { class: 'primary', onclick: newEstimate }, '+ New estimate'))),
    h('div', { class: 'panel' }, list.length === 0
      ? h('div', { class: 'empty' }, 'No estimates yet. Click “New estimate” to start.')
      : h('div', { class: 'table-wrap' }, h('table', {},
        h('thead', {}, h('tr', {},
          h('th', {}, 'Name'), h('th', {}, 'Client'), h('th', {}, 'Date'), h('th', {}, 'Status'),
          h('th', { class: 'n' }, 'Tasks'), h('th', { class: 'n' }, 'Direct cost'),
          h('th', { class: 'n' }, 'Contract price'), h('th', {}))),
        h('tbody', {}, list.map((e) => {
          const m = moneyFmt(e.currency);
          return h('tr', {},
            h('td', {}, h('a', { href: `#/estimate/${e.id}` }, h('b', {}, e.name))),
            h('td', {}, e.client), h('td', {}, e.estimate_date),
            h('td', {}, h('span', { class: 'tag ' + e.status }, e.status)),
            h('td', { class: 'n' }, e.task_count),
            h('td', { class: 'n' }, m(e.direct)),
            h('td', { class: 'n' }, h('b', {}, m(e.contract_price))),
            h('td', { class: 'actions-cell' },
              h('a', { class: 'btn', href: `#/estimate/${e.id}` }, 'Open'), ' ',
              h('button', {
                onclick: async () => {
                  const r = await attempt(() => api('POST', `/estimates/${e.id}/duplicate`), 'Duplicated');
                  location.hash = `#/estimate/${r.id}`;
                },
              }, 'Duplicate'), ' ',
              h('button', {
                class: 'danger', onclick: async () => {
                  if (!confirmBox(`Delete estimate “${e.name}”? This cannot be undone.`)) return;
                  await attempt(() => api('DELETE', `/estimates/${e.id}`), 'Deleted');
                  renderEstimates();
                },
              }, 'Delete')));
        }))))));
}

// ================================================================ ESTIMATE EDITOR

let current = null; // { estimate, tasks, indirects, crews, summary }

async function renderEstimate(id) {
  await loadRefs('crews', 'library', 'indirectLib', 'materials', 'units');
  current = await api('GET', `/estimates/${id}`);
  money = moneyFmt(current.estimate.currency);
  drawEstimate();
}

async function refreshEstimate() {
  const id = current.estimate.id;
  await keepFocus(async () => {
    current = await api('GET', `/estimates/${id}`);
    money = moneyFmt(current.estimate.currency);
    drawEstimate();
  });
}

async function saveEstimateField(f, value) {
  await attempt(() => api('PUT', `/estimates/${current.estimate.id}`, { [f]: value }), 'Saved');
  await refreshEstimate();
}

function drawEstimate() {
  const { estimate: e } = current;
  const est = (f, label, type = 'text', cls) => {
    const attrs = { value: e[f], dataset: { fk: 'est-' + f }, onchange: (ev) => saveEstimateField(f, ev.target.value) };
    const input = type === 'num' ? numInput(e[f], attrs)
      : type === 'textarea' ? h('textarea', attrs)
        : h('input', { type, ...attrs });
    return field(label, input, cls);
  };

  $app.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', {},
        h('div', { class: 'sub' }, h('a', { href: '#/estimates' }, '← Estimates')),
        h('h1', {}, e.name, ' ', h('span', { class: 'tag ' + e.status }, e.status))),
      h('div', { class: 'actions' },
        h('a', { class: 'btn', href: `#/estimate/${e.id}/report` }, 'Report / print'),
        h('a', { class: 'btn', href: `/api/estimates/${e.id}/export.csv` }, 'Export CSV'),
        h('button', {
          onclick: async () => {
            const r = await attempt(() => api('POST', `/estimates/${e.id}/duplicate`), 'Duplicated');
            location.hash = `#/estimate/${r.id}`;
          },
        }, 'Duplicate'),
        h('button', {
          class: 'danger', onclick: async () => {
            if (!confirmBox(`Delete estimate “${e.name}”?`)) return;
            await attempt(() => api('DELETE', `/estimates/${e.id}`), 'Deleted');
            location.hash = '#/estimates';
          },
        }, 'Delete'))),
    h('div', { class: 'est-layout' },
      h('div', {},
        h('div', { class: 'panel' },
          h('div', { class: 'panel-head' }, h('h2', {}, 'Project')),
          h('div', { class: 'grid' },
            est('name', 'Estimate name', 'text', 'wide'),
            est('client', 'Client'),
            est('location', 'Location'),
            est('estimate_date', 'Date', 'date'),
            est('currency', 'Currency (ISO code)'),
            field('Status', h('select', {
              dataset: { fk: 'est-status' }, onchange: (ev) => saveEstimateField('status', ev.target.value),
            }, options(STATUSES.map((s) => ({ value: s, label: s })), e.status))),
            field('Wage scale (CAPAC–SUNTRACS)', h('select', {
              dataset: { fk: 'est-wage_scale' }, onchange: (ev) => saveEstimateField('wage_scale', ev.target.value),
            }, options([{ value: 'private', label: 'Private works (inversión privada)' }, { value: 'public', label: 'Public works (inversión pública)' }], e.wage_scale))),
            est('hours_per_day', 'Working hours / day', 'num'),
            est('notes', 'Notes / scope assumptions', 'textarea', 'wide'))),
        drawTasksPanel(),
        drawIndirectsPanel()),
      drawSummaryPanel()));
}

// ---------------------------------------------------------------- tasks

function drawTasksPanel() {
  const { tasks, summary: s } = current;
  const lib = refs.library || [];
  const libSel = h('select', { dataset: { fk: 'lib-sel' } },
    options(lib.map((t) => ({ value: t.id, group: t.category || 'Uncategorized', label: `${t.code} — ${t.description} (${t.unit})` })), '', { blank: '— choose a standard task —' }));
  const libQty = numInput('', { placeholder: 'Quantity', dataset: { fk: 'lib-qty' } });
  libQty.value = '';

  const addFromLib = async () => {
    if (!libSel.value) return toast('Choose a task from the library first', true);
    await attempt(() => api('POST', `/estimates/${current.estimate.id}/tasks`,
      { library_id: libSel.value, quantity: num(libQty.value) }), 'Task added');
    await refreshEstimate();
  };

  const rows = tasks.map((t, i) => {
    const c = t.calc;
    return h('tr', {},
      h('td', { class: 'code' }, t.code || h('span', { class: 'muted' }, `#${i + 1}`)),
      h('td', { class: 'desc' }, t.description,
        c.warnings.map((w) => h('div', {}, h('span', { class: 'warn' }, '⚠ ' + w)))),
      h('td', {}, t.unit),
      h('td', { style: 'width:90px' }, numInput(t.quantity, {
        dataset: { fk: `tq-${t.id}` },
        onchange: async (ev) => {
          await attempt(() => api('PUT', `/tasks/${t.id}`, { quantity: ev.target.value }), 'Saved');
          await refreshEstimate();
        },
      })),
      h('td', { class: 'code', title: t.crew_name }, t.crew_code || '—'),
      h('td', { class: 'n' }, fmtQ(t.production_rate)),
      h('td', { class: 'n' }, fmtN(c.crew_days, 1)),
      h('td', { class: 'n' }, fmtN(c.labor)),
      h('td', { class: 'n' }, fmtN(c.equipment)),
      h('td', { class: 'n' }, fmtN(c.material)),
      h('td', { class: 'n' }, fmtN(c.consumable)),
      h('td', { class: 'n' }, h('b', {}, fmtN(c.direct))),
      h('td', { class: 'n' }, fmtN(c.unit_cost)),
      h('td', { class: 'n' }, h('b', {}, fmtN(c.bid_unit_price))),
      h('td', { class: 'actions-cell' },
        h('button', { class: 'icon', title: 'Edit task (crew, rate, materials, consumables)', onclick: () => editEstimateTask(t) }, '✎'),
        h('button', { class: 'icon', title: 'Move up', disabled: i === 0, onclick: () => moveRow('tasks', t.id, -1) }, '↑'),
        h('button', { class: 'icon', title: 'Move down', disabled: i === tasks.length - 1, onclick: () => moveRow('tasks', t.id, 1) }, '↓'),
        h('button', {
          class: 'icon danger', title: 'Delete task', onclick: async () => {
            if (!confirmBox(`Delete task “${t.description}”?`)) return;
            await attempt(() => api('DELETE', `/tasks/${t.id}`), 'Deleted');
            await refreshEstimate();
          },
        }, '✕')));
  });

  return h('div', { class: 'panel' },
    h('div', { class: 'panel-head' },
      h('h2', {}, `Tasks — direct cost (${current.estimate.currency})`),
      h('span', { class: 'hint' }, 'Quantity × (crew at production rate + materials + consumables). Bid unit price includes indirects & markups, excludes tax.')),
    h('div', { class: 'table-wrap' }, h('table', { class: 'dense' },
      h('thead', {}, h('tr', {},
        h('th', {}, 'Code'), h('th', {}, 'Description'), h('th', {}, 'Unit'),
        h('th', { class: 'n' }, 'Quantity'), h('th', {}, 'Crew'), h('th', { class: 'n' }, 'Rate/day'),
        h('th', { class: 'n' }, 'Crew-days'), h('th', { class: 'n' }, 'Labor'), h('th', { class: 'n' }, 'Equip.'),
        h('th', { class: 'n' }, 'Materials'), h('th', { class: 'n' }, 'Consum.'), h('th', { class: 'n' }, 'Direct'),
        h('th', { class: 'n' }, 'Unit cost'), h('th', { class: 'n' }, 'Bid price/unit'), h('th', {}))),
      h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: 15, class: 'empty' }, 'No tasks yet. Add one below.'))),
      tasks.length ? h('tfoot', {}, h('tr', { class: 'total' },
        h('td', { colspan: 6 }, 'Total direct cost'),
        h('td', { class: 'n' }, fmtN(s.duration_crew_days, 1)),
        h('td', { class: 'n' }, fmtN(s.labor)), h('td', { class: 'n' }, fmtN(s.equipment)),
        h('td', { class: 'n' }, fmtN(s.material)), h('td', { class: 'n' }, fmtN(s.consumable)),
        h('td', { class: 'n' }, fmtN(s.direct)), h('td', { colspan: 3 }))) : null)),
    h('div', { class: 'add-bar' },
      libSel, libQty,
      h('button', { class: 'primary', onclick: addFromLib }, 'Add from library'),
      h('span', { class: 'muted' }, 'or'),
      h('button', { onclick: () => editEstimateTask(null) }, '+ Build a new task')));
}

async function moveRow(kind, id, dir) {
  await attempt(() => api('POST', `/${kind}/${id}/move`, { dir }));
  await refreshEstimate();
}

function editEstimateTask(task) {
  openTaskEditor({
    mode: 'estimate',
    task: task || { code: '', description: '', unit: 'm2', quantity: 0, crew_id: null, production_rate: 0, notes: '', resources: [] },
    hpd: current.estimate.hours_per_day,
    title: task ? `Edit task ${task.code || ''}` : 'New task',
    onSave: async (data) => {
      if (task) await api('PUT', `/tasks/${task.id}`, data);
      else await api('POST', `/estimates/${current.estimate.id}/tasks`, data);
      await refreshEstimate();
    },
    onDelete: task ? async () => {
      await api('DELETE', `/tasks/${task.id}`);
      await refreshEstimate();
    } : null,
    onToLibrary: task ? async (data) => {
      await api('PUT', `/tasks/${task.id}`, data);
      const r = await api('POST', `/tasks/${task.id}/to-library`);
      await loadRefs('library');
      await refreshEstimate();
      return `Saved to task library as ${r.code}`;
    } : null,
  });
}

// ---------------------------------------------------------------- task editor (shared)

/** Modal for building a task: measure, crew + production rate, materials, consumables. */
function openTaskEditor({ mode, task, hpd, title, onSave, onDelete, onToLibrary }) {
  const st = {
    code: task.code || '', description: task.description || '', category: task.category || '',
    unit: task.unit || 'ea', quantity: task.quantity ?? 0, crew_id: task.crew_id || '',
    production_rate: task.production_rate ?? 0, notes: task.notes || '',
    resources: (task.resources || []).map((r) => ({ material_id: r.material_id, qty_per_unit: r.qty_per_unit })),
  };
  const isEst = mode === 'estimate';
  hpd = num(hpd) || 8;

  const set = (f) => (ev) => { st[f] = ev.target.value; };
  const setDraw = (f) => (ev) => { st[f] = ev.target.value; draw(); };

  function preview() {
    const crew = byId(refs.crews, st.crew_id);
    const rate = num(st.production_rate);
    const hrsPerUnit = rate > 0 ? hpd / rate : 0;
    const labor = crew ? crew.labor_hourly * hrsPerUnit : 0;
    const equip = crew ? crew.equipment_hourly * hrsPerUnit : 0;
    let mat = 0; let cons = 0;
    for (const r of st.resources) {
      const m = byId(refs.materials, r.material_id);
      if (!m) continue;
      const v = num(r.qty_per_unit) * (1 + num(m.waste_pct) / 100) * num(m.unit_cost);
      if (m.kind === 'consumable') cons += v; else mat += v;
    }
    return { crew, hrsPerUnit, labor, equip, mat, cons, unit: labor + equip + mat + cons };
  }

  function resourceRows(kind) {
    const mats = (refs.materials || []).filter((m) => m.kind === kind);
    const rows = [];
    st.resources.forEach((r, idx) => {
      const m = byId(refs.materials, r.material_id);
      if ((m ? m.kind : kind) !== kind) return;
      if (!m && r._kind !== kind) return;
      const perUnit = m ? num(r.qty_per_unit) * (1 + num(m.waste_pct) / 100) * num(m.unit_cost) : 0;
      rows.push(h('tr', {},
        h('td', {}, h('select', {
          dataset: { fk: `res-${idx}-m` },
          onchange: (ev) => { r.material_id = ev.target.value; draw(); },
        }, options(mats.map((x) => ({ value: x.id, group: x.category, label: `${x.code} — ${x.description}` })), r.material_id, { blank: '— select —' }))),
        h('td', { style: 'width:120px' }, numInput(r.qty_per_unit, {
          dataset: { fk: `res-${idx}-q` },
          onchange: (ev) => { r.qty_per_unit = ev.target.value; draw(); },
        })),
        h('td', {}, m ? m.unit : ''),
        h('td', { class: 'n' }, m ? money(m.unit_cost) : ''),
        h('td', { class: 'n' }, m ? fmtN(m.waste_pct, 1) + '%' : ''),
        h('td', { class: 'n' }, money(perUnit)),
        h('td', { class: 'actions-cell' }, h('button', {
          class: 'icon danger', onclick: () => { st.resources.splice(idx, 1); draw(); },
        }, '✕'))));
    });
    return rows;
  }

  function resourceTable(kind, label) {
    return [
      h('h3', {}, label, h('span', { class: 'hint' }, `  — quantity per 1 ${st.unit || 'unit'} of task`)),
      h('table', {},
        h('thead', {}, h('tr', {},
          h('th', {}, kind === 'material' ? 'Material' : 'Consumable'), h('th', { class: 'n' }, `Qty / ${st.unit || 'unit'}`),
          h('th', {}, 'Unit'), h('th', { class: 'n' }, 'Unit cost'), h('th', { class: 'n' }, 'Waste'),
          h('th', { class: 'n' }, `Cost / ${st.unit || 'unit'}`), h('th', {}))),
        h('tbody', {}, resourceRows(kind))),
      h('button', {
        class: 'icon', style: 'margin-top:6px',
        onclick: () => { st.resources.push({ material_id: '', qty_per_unit: 0, _kind: kind }); draw(); },
      }, `+ Add ${kind}`),
    ];
  }

  function draw() {
    const scrollBox = $modal.querySelector('.modal-body');
    const scroll = scrollBox ? scrollBox.scrollTop : 0;
    const a = document.activeElement;
    const fk = a && a.dataset ? a.dataset.fk : null;

    const p = preview();
    const q = num(st.quantity);
    const crewOpts = (refs.crews || []).map((c) => ({ value: c.id, label: `${c.code} — ${c.name} (${money(c.hourly_cost)}/hr)` }));
    const body = h('div', {},
      unitDatalist(),
      h('div', { class: 'grid' },
        field('Code', h('input', { value: st.code, dataset: { fk: 't-code' }, oninput: set('code') })),
        field('Description', h('input', { value: st.description, dataset: { fk: 't-desc' }, oninput: set('description') }), 'wide'),
        !isEst ? field('Category', h('input', { value: st.category, dataset: { fk: 't-cat' }, oninput: set('category') })) : null,
        field('Unit of measure', h('input', { value: st.unit, list: 'units-list', dataset: { fk: 't-unit' }, onchange: setDraw('unit') })),
        isEst ? field('Quantity', numInput(st.quantity, { dataset: { fk: 't-qty' }, onchange: setDraw('quantity') })) : null),
      h('h3', {}, 'Crew & productivity'),
      h('div', { class: 'grid' },
        field('Crew', h('select', { dataset: { fk: 't-crew' }, onchange: setDraw('crew_id') }, options(crewOpts, st.crew_id, { blank: '— no crew (materials only) —' })), 'wide'),
        field(`Production rate (${st.unit || 'units'} per crew-day)`, numInput(st.production_rate, { dataset: { fk: 't-rate' }, onchange: setDraw('production_rate') })),
        field('Crew-hours per unit', h('input', { value: fmtN(p.hrsPerUnit, 4), disabled: true }))),
      p.crew ? h('div', { class: 'hint', style: 'margin-top:4px' },
        `${p.crew.name}: `, p.crew.labor.map((m) => `${fmtQ(m.qty)} × ${m.trade}`).join(', '),
        p.crew.equipment.length ? ' + ' + p.crew.equipment.map((m) => `${fmtQ(m.qty)} × ${m.description}`).join(', ') : '',
        ` — labor ${money(p.crew.labor_hourly)}/hr, equipment ${money(p.crew.equipment_hourly)}/hr (at ${hpd} h/day)`) : null,
      resourceTable('material', 'Materials'),
      resourceTable('consumable', 'Consumables'),
      h('h3', {}, 'Notes'),
      h('textarea', { value: st.notes, dataset: { fk: 't-notes' }, oninput: set('notes') }),
      h('div', { class: 'preview-box' },
        h('div', {}, h('span', {}, `Labor / ${st.unit}`), h('b', {}, money(p.labor))),
        h('div', {}, h('span', {}, `Equipment / ${st.unit}`), h('b', {}, money(p.equip))),
        h('div', {}, h('span', {}, `Materials / ${st.unit}`), h('b', {}, money(p.mat))),
        h('div', {}, h('span', {}, `Consumables / ${st.unit}`), h('b', {}, money(p.cons))),
        h('div', {}, h('span', {}, `Direct unit cost`), h('b', {}, money(p.unit))),
        isEst ? h('div', {}, h('span', {}, 'Crew-days'), h('b', {}, fmtN(num(st.production_rate) > 0 ? q / num(st.production_rate) : 0, 2))) : null,
        isEst ? h('div', {}, h('span', {}, 'Task direct cost'), h('b', {}, money(p.unit * q))) : null));

    const collect = () => {
      const data = {
        code: st.code, description: st.description, unit: st.unit, crew_id: st.crew_id || null,
        production_rate: st.production_rate, notes: st.notes,
        resources: st.resources.filter((r) => r.material_id).map((r) => ({ material_id: r.material_id, qty_per_unit: r.qty_per_unit })),
      };
      if (isEst) data.quantity = st.quantity; else data.category = st.category;
      return data;
    };
    const footer = [
      h('div', { class: 'actions' }, onDelete ? h('button', {
        class: 'danger', onclick: async () => {
          if (!confirmBox('Delete this task?')) return;
          await attempt(onDelete, 'Deleted');
          $modal.close();
        },
      }, 'Delete') : null,
      onToLibrary ? h('button', {
        title: 'Save this task and copy it into the task library as a reusable standard task',
        onclick: async () => {
          if (!st.description.trim()) return toast('Description is required', true);
          const msg = await attempt(() => onToLibrary(collect()));
          toast(msg);
          $modal.close();
        },
      }, 'Save + copy to library') : null),
      h('div', { class: 'actions' },
        h('button', { onclick: () => $modal.close() }, 'Cancel'),
        h('button', {
          class: 'primary', onclick: async () => {
            if (!st.description.trim()) return toast('Description is required', true);
            const data = collect();
            await attempt(() => onSave(data), 'Saved');
            $modal.close();
          },
        }, 'Save task')),
    ];
    openModal(title, body, footer);
    const nb = $modal.querySelector('.modal-body');
    if (nb) nb.scrollTop = scroll;
    if (fk) { const el = $modal.querySelector(`[data-fk="${esc(fk)}"]`); if (el) el.focus(); }
  }
  draw();
}

// ---------------------------------------------------------------- indirects

function drawIndirectsPanel() {
  const { indirects, summary: s } = current;
  const libSel = h('select', {},
    options((refs.indirectLib || []).map((x) => ({
      value: x.id, group: x.category || 'General',
      label: x.method === 'lump' ? `${x.description} (${money(x.rate)}/${x.unit})` : `${x.description} (${x.percent}% ${x.method === 'pct_labor' ? 'of labor' : 'of direct'})`,
    })), '', { blank: '— choose a standard indirect cost —' }));

  const save = (it, f) => async (ev) => {
    await attempt(() => api('PUT', `/indirects/${it.id}`, { [f]: ev.target.value }), 'Saved');
    await refreshEstimate();
  };

  const rows = indirects.map((it, i) => {
    const lump = it.method === 'lump';
    return h('tr', {},
      h('td', {}, h('input', { value: it.description, dataset: { fk: `i-${it.id}-d` }, onchange: save(it, 'description') })),
      h('td', { style: 'width:120px' }, h('input', { value: it.category, dataset: { fk: `i-${it.id}-c` }, onchange: save(it, 'category') })),
      h('td', { style: 'width:150px' }, h('select', { dataset: { fk: `i-${it.id}-m` }, onchange: save(it, 'method') },
        options(Object.entries(METHOD_LABELS).map(([v, l]) => ({ value: v, label: l })), it.method))),
      h('td', { style: 'width:95px' }, lump ? h('input', { value: it.unit, list: 'units-list', dataset: { fk: `i-${it.id}-u` }, onchange: save(it, 'unit') }) : ''),
      h('td', { style: 'width:90px' }, lump ? numInput(it.quantity, { dataset: { fk: `i-${it.id}-q` }, onchange: save(it, 'quantity') }) : ''),
      h('td', { style: 'width:110px' }, lump ? numInput(it.rate, { dataset: { fk: `i-${it.id}-r` }, onchange: save(it, 'rate') }) : ''),
      h('td', { style: 'width:90px' }, lump ? '' : numInput(it.percent, { dataset: { fk: `i-${it.id}-p` }, onchange: save(it, 'percent') })),
      h('td', { class: 'n' }, h('b', {}, money(it.amount))),
      h('td', { class: 'actions-cell' },
        h('button', { class: 'icon', disabled: i === 0, onclick: () => moveRow('indirects', it.id, -1) }, '↑'),
        h('button', { class: 'icon', disabled: i === indirects.length - 1, onclick: () => moveRow('indirects', it.id, 1) }, '↓'), ' ',
        h('button', {
          class: 'icon danger', onclick: async () => {
            await attempt(() => api('DELETE', `/indirects/${it.id}`), 'Deleted');
            await refreshEstimate();
          },
        }, '✕')));
  });

  return h('div', { class: 'panel' },
    unitDatalist(),
    h('div', { class: 'panel-head' },
      h('h2', {}, 'Indirect costs'),
      h('span', { class: 'hint' }, 'Site overheads (staff, facilities, mobilization) as quantity × rate, or a % of direct cost / direct labor.')),
    h('div', { class: 'table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {},
        h('th', {}, 'Description'), h('th', {}, 'Category'), h('th', {}, 'Method'), h('th', {}, 'Unit'),
        h('th', { class: 'n' }, 'Qty'), h('th', { class: 'n' }, 'Rate'), h('th', { class: 'n' }, '%'),
        h('th', { class: 'n' }, 'Amount'), h('th', {}))),
      h('tbody', {}, rows.length ? rows : h('tr', {}, h('td', { colspan: 9, class: 'empty' }, 'No indirect costs.'))),
      indirects.length ? h('tfoot', {}, h('tr', { class: 'total' },
        h('td', { colspan: 7 }, 'Total indirect costs'),
        h('td', { class: 'n' }, money(s.indirect)), h('td', {}))) : null)),
    h('div', { class: 'add-bar' },
      libSel,
      h('button', {
        class: 'primary', onclick: async () => {
          if (!libSel.value) return toast('Choose an item first', true);
          await attempt(() => api('POST', `/estimates/${current.estimate.id}/indirects`, { library_id: libSel.value }), 'Added');
          await refreshEstimate();
        },
      }, 'Add from library'),
      h('button', {
        onclick: async () => {
          await attempt(() => api('POST', `/estimates/${current.estimate.id}/indirects`,
            { description: 'New indirect cost', method: 'lump', unit: 'ls', quantity: 1, rate: 0 }));
          await refreshEstimate();
        },
      }, '+ Blank line')));
}

// ---------------------------------------------------------------- summary

function drawSummaryPanel() {
  const { estimate: e, summary: s } = current;
  const row = (label, value, cls) => h('div', { class: 'row' + (cls ? ' ' + cls : '') }, h('span', {}, label), h('span', {}, value));
  const pct = (f, label) => [
    h('label', {}, label),
    numInput(e[f], { dataset: { fk: 'est-' + f }, onchange: (ev) => saveEstimateField(f, ev.target.value) }),
  ];
  const share = (v) => (s.contract_price ? fmtN((v / s.contract_price) * 100, 1) + '%' : '—');

  return h('div', { class: 'panel summary' },
    h('h2', {}, 'Contract price build-up'),
    row('Labor', money(s.labor)),
    row('Equipment', money(s.equipment)),
    row('Materials', money(s.material)),
    row('Consumables', money(s.consumable)),
    row('Direct cost', money(s.direct), 'strong sep'),
    row('Indirect costs', money(s.indirect)),
    row('Total cost', money(s.cost), 'strong sep'),
    s.markups.map((m) => row(`${m.label} ${fmtN(m.percent, 2)}%`, money(m.amount))),
    row('Price before tax', money(s.price_before_tax), 'strong sep'),
    row(`Tax ${fmtN(s.tax_pct, 2)}%`, money(s.tax)),
    h('div', { class: 'price' },
      h('div', { class: 'muted' }, 'Contract price'),
      h('div', { class: 'big' }, money(s.contract_price))),
    h('h3', {}, 'Markups (%)'),
    h('div', { class: 'markup-inputs' },
      pct('contingency_pct', 'Contingency'),
      pct('overhead_pct', 'Overhead (home office)'),
      pct('profit_pct', 'Profit'),
      pct('bond_pct', 'Bonds / guarantees'),
      pct('tax_pct', 'Tax (e.g. ITBMS)')),
    h('div', { class: 'hint', style: 'margin-top:6px' }, 'Each markup is applied to the running total, in the order shown.'),
    h('h3', {}, 'Indicators'),
    row('K factor (price excl. tax ÷ direct)', fmtN(s.k_factor, 4)),
    row('Indirects as % of direct', s.direct ? fmtN((s.indirect / s.direct) * 100, 1) + '%' : '—'),
    row('Profit share of contract price', share(s.markups.find((m) => m.key === 'profit').amount)),
    row('Labor share of direct', s.direct ? fmtN((s.labor / s.direct) * 100, 1) + '%' : '—'),
    row('Total crew-days', fmtN(s.duration_crew_days, 1)),
    row('Total man-hours', fmtN(s.man_hours, 0)));
}

// ================================================================ REPORT

async function renderReport(id) {
  const data = await api('GET', `/estimates/${id}`);
  const { estimate: e, tasks, indirects, summary: s, crews } = data;
  money = moneyFmt(e.currency);
  const hpd = num(e.hours_per_day) || 8;
  let showApu = true;
  try { showApu = localStorage.getItem('kotiza-apu') !== '0'; } catch (_) { /* ignore */ }

  const crewMap = Object.fromEntries(crews.map((c) => [c.id, c]));

  function apu(t, i) {
    const c = t.calc;
    const crew = crewMap[t.crew_id];
    const rate = num(t.production_rate);
    const hrsPerUnit = rate > 0 ? hpd / rate : 0;
    const lines = [];
    if (crew) {
      for (const m of crew.labor) {
        lines.push(['Labor', m.trade, `${fmtQ(m.qty)} × ${fmtN(hrsPerUnit, 4)} h`, 'hr', money(m.loaded_rate), money(m.cost_hr * hrsPerUnit)]);
      }
      for (const m of crew.equipment) {
        lines.push(['Equipment', m.description, `${fmtQ(m.qty)} × ${fmtN(hrsPerUnit, 4)} h`, 'hr', money(m.hourly_rate), money(m.cost_hr * hrsPerUnit)]);
      }
    }
    for (const r of t.resources) {
      const q = num(r.qty_per_unit) * (1 + num(r.waste_pct) / 100);
      lines.push([r.kind === 'consumable' ? 'Consumable' : 'Material', r.description,
        fmtQ(q) + (num(r.waste_pct) ? ` (incl. ${fmtQ(r.waste_pct)}% waste)` : ''), r.unit, money(r.unit_cost), money(r.unit_cost_per_task_unit)]);
    }
    return h('div', { class: 'apu' },
      h('div', { class: 'apu-head' },
        h('span', {}, `${i + 1}. ${t.code ? t.code + ' — ' : ''}${t.description}`),
        h('span', {}, `Unit: ${t.unit}`)),
      h('div', { class: 'hint' },
        crew ? `Crew ${crew.code} (${crew.name}) at ${fmtQ(rate)} ${t.unit}/day, ${hpd} h/day → ${fmtN(hrsPerUnit, 4)} crew-h per ${t.unit}` : 'No crew assigned'),
      h('table', {},
        h('thead', {}, h('tr', {}, h('th', {}, 'Type'), h('th', {}, 'Resource'), h('th', {}, 'Quantity / ' + t.unit),
          h('th', {}, 'Unit'), h('th', { class: 'n' }, 'Rate'), h('th', { class: 'n' }, 'Cost / ' + t.unit))),
        h('tbody', {}, lines.map((l) => h('tr', {}, l.map((v, k) => h('td', { class: k >= 4 ? 'n' : '' }, v))))),
        h('tfoot', {},
          h('tr', { class: 'total' }, h('td', { colspan: 5 }, 'Direct unit cost'), h('td', { class: 'n' }, money(c.unit_cost))),
          h('tr', { class: 'subtle' }, h('td', { colspan: 5 }, `Indirects, markups (K = ${fmtN(s.k_factor, 4)})`), h('td', { class: 'n' }, money(c.bid_unit_price - c.unit_cost))),
          h('tr', {}, h('td', { colspan: 5 }, h('b', {}, 'Bid unit price (excl. tax)')), h('td', { class: 'n' }, h('b', {}, money(c.bid_unit_price)))))));
  }

  function draw() {
    $app.replaceChildren(
      h('div', { class: 'page-head no-print' },
        h('div', {}, h('a', { href: `#/estimate/${e.id}` }, '← Back to estimate')),
        h('div', { class: 'actions' },
          h('label', {}, h('input', {
            type: 'checkbox', checked: showApu, style: 'width:auto;margin-right:6px',
            onchange: (ev) => { showApu = ev.target.checked; try { localStorage.setItem('kotiza-apu', showApu ? '1' : '0'); } catch (_) { /* ignore */ } draw(); },
          }), 'Include internal cost analysis'),
          h('button', { class: 'primary', onclick: () => window.print() }, 'Print / Save PDF'))),
      h('div', { class: 'report' },
        h('h1', {}, e.name),
        h('div', { class: 'meta' },
          h('div', {}, 'Client: ', h('b', {}, e.client || '—')),
          h('div', {}, 'Location: ', h('b', {}, e.location || '—')),
          h('div', {}, 'Date: ', h('b', {}, e.estimate_date || '—')),
          h('div', {}, 'Currency: ', h('b', {}, e.currency)),
          h('div', {}, 'Status: ', h('b', {}, e.status))),
        e.notes ? h('p', { style: 'white-space:pre-wrap' }, e.notes) : null,

        h('h2', {}, 'Bill of quantities'),
        h('table', {},
          h('thead', {}, h('tr', {}, h('th', {}, 'Item'), h('th', {}, 'Description'), h('th', {}, 'Unit'),
            h('th', { class: 'n' }, 'Quantity'), h('th', { class: 'n' }, 'Unit price'), h('th', { class: 'n' }, 'Amount'))),
          h('tbody', {}, tasks.map((t, i) => h('tr', {},
            h('td', {}, i + 1), h('td', {}, t.description), h('td', {}, t.unit),
            h('td', { class: 'n' }, fmtQ(t.quantity)), h('td', { class: 'n' }, money(t.calc.bid_unit_price)),
            h('td', { class: 'n' }, money(t.calc.bid_total))))),
          h('tfoot', {},
            h('tr', { class: 'total' }, h('td', { colspan: 5 }, 'Subtotal'), h('td', { class: 'n' }, money(s.price_before_tax))),
            h('tr', {}, h('td', { colspan: 5 }, `Tax (${fmtN(s.tax_pct, 2)}%)`), h('td', { class: 'n' }, money(s.tax))),
            h('tr', { class: 'total' }, h('td', { colspan: 5 }, 'CONTRACT PRICE'), h('td', { class: 'n' }, money(s.contract_price))))),

        showApu ? [
          h('h2', {}, 'Cost build-up (internal)'),
          h('table', {}, h('tbody', {},
            [['Labor', s.labor], ['Equipment', s.equipment], ['Materials', s.material], ['Consumables', s.consumable]]
              .map(([l, v]) => h('tr', {}, h('td', {}, l), h('td', { class: 'n' }, money(v)))),
            h('tr', { class: 'total' }, h('td', {}, 'Direct cost'), h('td', { class: 'n' }, money(s.direct))),
            indirects.map((it) => h('tr', { class: 'subtle' },
              h('td', {}, '  ' + it.description + (it.method === 'lump' ? ` (${fmtQ(it.quantity)} ${it.unit} × ${money(it.rate)})` : ` (${fmtQ(it.percent)}% of ${it.method === 'pct_labor' ? 'labor' : 'direct'})`)),
              h('td', { class: 'n' }, money(it.amount)))),
            h('tr', {}, h('td', {}, 'Indirect costs'), h('td', { class: 'n' }, money(s.indirect))),
            h('tr', { class: 'total' }, h('td', {}, 'Total cost'), h('td', { class: 'n' }, money(s.cost))),
            s.markups.map((m) => h('tr', {}, h('td', {}, `${m.label} (${fmtN(m.percent, 2)}%)`), h('td', { class: 'n' }, money(m.amount)))),
            h('tr', { class: 'total' }, h('td', {}, 'Price before tax'), h('td', { class: 'n' }, money(s.price_before_tax))),
            h('tr', {}, h('td', {}, `Tax (${fmtN(s.tax_pct, 2)}%)`), h('td', { class: 'n' }, money(s.tax))),
            h('tr', { class: 'total' }, h('td', {}, 'Contract price'), h('td', { class: 'n' }, money(s.contract_price))))),
          h('h2', {}, 'Unit price analysis (internal)'),
          tasks.map(apu),
        ] : null));
  }
  draw();
}

// ================================================================ CREWS

async function renderCrews() {
  await loadRefs('crews', 'labor', 'equipment');
  money = moneyFmt('USD');
  const list = refs.crews;
  $app.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', {}, h('h1', {}, 'Crews'),
        h('div', { class: 'sub' }, 'A crew combines labor trades and equipment into one hourly cost. Tasks use a crew at a production rate. Costs shown at private-works wages; estimates set to public works use public wages.')),
      h('button', { class: 'primary', onclick: () => editCrew(null) }, '+ New crew')),
    h('div', { class: 'panel' }, h('div', { class: 'table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, h('th', {}, 'Code'), h('th', {}, 'Name'), h('th', {}, 'Composition'),
        h('th', { class: 'n' }, 'Headcount'), h('th', { class: 'n' }, 'Labor $/hr'), h('th', { class: 'n' }, 'Equip. $/hr'),
        h('th', { class: 'n' }, 'Crew $/hr'), h('th', { class: 'n' }, 'Crew $/day (8h)'), h('th', {}))),
      h('tbody', {}, list.length ? list.map((c) => h('tr', {},
        h('td', { class: 'code' }, c.code), h('td', {}, h('b', {}, c.name), c.description ? h('div', { class: 'hint' }, c.description) : null),
        h('td', { class: 'hint' }, [...c.labor.map((m) => `${fmtQ(m.qty)} ${m.trade}`), ...c.equipment.map((m) => `${fmtQ(m.qty)} ${m.description}`)].join(', ')),
        h('td', { class: 'n' }, fmtQ(c.headcount)),
        h('td', { class: 'n' }, money(c.labor_hourly)), h('td', { class: 'n' }, money(c.equipment_hourly)),
        h('td', { class: 'n' }, h('b', {}, money(c.hourly_cost))), h('td', { class: 'n' }, money(c.hourly_cost * 8)),
        h('td', { class: 'actions-cell' }, h('button', { onclick: () => editCrew(c) }, 'Edit'), ' ',
          h('button', {
            class: 'danger', onclick: async () => {
              if (!confirmBox(`Delete crew ${c.code}?`)) return;
              await attempt(() => api('DELETE', `/crews/${c.id}`), 'Deleted');
              renderCrews();
            },
          }, 'Delete'))))
        : h('tr', {}, h('td', { colspan: 9, class: 'empty' }, 'No crews yet.')))))));
}

function editCrew(crew) {
  const st = {
    code: crew?.code || '', name: crew?.name || '', description: crew?.description || '',
    labor: (crew?.labor || []).map((m) => ({ labor_id: m.labor_id, qty: m.qty })),
    equipment: (crew?.equipment || []).map((m) => ({ equipment_id: m.equipment_id, qty: m.qty })),
  };

  function draw() {
    const a = document.activeElement;
    const fk = a && a.dataset ? a.dataset.fk : null;
    let labHr = 0; let eqHr = 0; let heads = 0;
    const labRows = st.labor.map((m, i) => {
      const l = byId(refs.labor, m.labor_id);
      const rate = l ? l.loaded_rate : 0;
      labHr += rate * num(m.qty); heads += num(m.qty);
      return h('tr', {},
        h('td', {}, h('select', { dataset: { fk: `cl-${i}` }, onchange: (ev) => { m.labor_id = ev.target.value; draw(); } },
          options(refs.labor.map((x) => ({ value: x.id, label: `${x.code} — ${x.trade}` })), m.labor_id, { blank: '— select —' }))),
        h('td', { style: 'width:110px' }, numInput(m.qty, { dataset: { fk: `clq-${i}` }, onchange: (ev) => { m.qty = ev.target.value; draw(); } })),
        h('td', { class: 'n' }, money(rate)), h('td', { class: 'n' }, money(rate * num(m.qty))),
        h('td', { class: 'actions-cell' }, h('button', { class: 'icon danger', onclick: () => { st.labor.splice(i, 1); draw(); } }, '✕')));
    });
    const eqRows = st.equipment.map((m, i) => {
      const e = byId(refs.equipment, m.equipment_id);
      const rate = e ? e.hourly_rate : 0;
      eqHr += rate * num(m.qty);
      return h('tr', {},
        h('td', {}, h('select', { dataset: { fk: `ce-${i}` }, onchange: (ev) => { m.equipment_id = ev.target.value; draw(); } },
          options(refs.equipment.map((x) => ({ value: x.id, label: `${x.code} — ${x.description}` })), m.equipment_id, { blank: '— select —' }))),
        h('td', { style: 'width:110px' }, numInput(m.qty, { dataset: { fk: `ceq-${i}` }, onchange: (ev) => { m.qty = ev.target.value; draw(); } })),
        h('td', { class: 'n' }, money(rate)), h('td', { class: 'n' }, money(rate * num(m.qty))),
        h('td', { class: 'actions-cell' }, h('button', { class: 'icon danger', onclick: () => { st.equipment.splice(i, 1); draw(); } }, '✕')));
    });

    const body = h('div', {},
      h('div', { class: 'grid' },
        field('Code', h('input', { value: st.code, dataset: { fk: 'c-code' }, oninput: (ev) => { st.code = ev.target.value; } })),
        field('Name', h('input', { value: st.name, dataset: { fk: 'c-name' }, oninput: (ev) => { st.name = ev.target.value; } })),
        field('Description', h('input', { value: st.description, dataset: { fk: 'c-desc' }, oninput: (ev) => { st.description = ev.target.value; } }), 'wide')),
      h('h3', {}, 'Labor'),
      h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, 'Trade'), h('th', { class: 'n' }, 'Qty'), h('th', { class: 'n' }, 'Loaded $/hr'), h('th', { class: 'n' }, 'Cost/hr'), h('th', {}))),
        h('tbody', {}, labRows)),
      h('button', { class: 'icon', style: 'margin-top:6px', onclick: () => { st.labor.push({ labor_id: '', qty: 1 }); draw(); } }, '+ Add trade'),
      h('h3', {}, 'Equipment'),
      h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, 'Equipment'), h('th', { class: 'n' }, 'Qty'), h('th', { class: 'n' }, '$/hr'), h('th', { class: 'n' }, 'Cost/hr'), h('th', {}))),
        h('tbody', {}, eqRows)),
      h('button', { class: 'icon', style: 'margin-top:6px', onclick: () => { st.equipment.push({ equipment_id: '', qty: 1 }); draw(); } }, '+ Add equipment'),
      h('div', { class: 'preview-box' },
        h('div', {}, h('span', {}, 'Headcount'), h('b', {}, fmtQ(heads))),
        h('div', {}, h('span', {}, 'Labor $/hr'), h('b', {}, money(labHr))),
        h('div', {}, h('span', {}, 'Equipment $/hr'), h('b', {}, money(eqHr))),
        h('div', {}, h('span', {}, 'Crew $/hr'), h('b', {}, money(labHr + eqHr))),
        h('div', {}, h('span', {}, 'Crew $/day (8h)'), h('b', {}, money((labHr + eqHr) * 8)))));

    openModal(crew ? `Edit crew ${crew.code}` : 'New crew', body, [
      h('span', {}),
      h('div', { class: 'actions' },
        h('button', { onclick: () => $modal.close() }, 'Cancel'),
        h('button', {
          class: 'primary', onclick: async () => {
            const payload = {
              ...st,
              labor: st.labor.filter((m) => m.labor_id),
              equipment: st.equipment.filter((m) => m.equipment_id),
            };
            if (crew) await attempt(() => api('PUT', `/crews/${crew.id}`, payload), 'Crew saved');
            else await attempt(() => api('POST', '/crews', payload), 'Crew created');
            $modal.close();
            renderCrews();
          },
        }, 'Save crew'))]);
    if (fk) { const el = $modal.querySelector(`[data-fk="${esc(fk)}"]`); if (el) el.focus(); }
  }
  draw();
}

// ================================================================ TASK LIBRARY

async function renderLibrary() {
  await loadRefs('library', 'crews', 'materials', 'units');
  money = moneyFmt('USD');
  const list = refs.library;
  const edit = (t) => openTaskEditor({
    mode: 'library',
    task: t || { code: '', description: '', category: '', unit: 'm2', crew_id: null, production_rate: 0, resources: [] },
    hpd: 8,
    title: t ? `Edit standard task ${t.code}` : 'New standard task',
    onSave: async (data) => {
      if (t) await api('PUT', `/library/${t.id}`, data);
      else await api('POST', '/library', data);
      renderLibrary();
    },
    onDelete: t ? async () => { await api('DELETE', `/library/${t.id}`); renderLibrary(); } : null,
  });

  $app.replaceChildren(
    h('div', { class: 'page-head' },
      h('div', {}, h('h1', {}, 'Task library'),
        h('div', { class: 'sub' }, 'Standard tasks (unit-price analyses) you can drop into any estimate. Changes here do not alter tasks already in estimates.')),
      h('button', { class: 'primary', onclick: () => edit(null) }, '+ New standard task')),
    h('div', { class: 'panel' }, h('div', { class: 'table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, h('th', {}, 'Code'), h('th', {}, 'Description'), h('th', {}, 'Category'),
        h('th', {}, 'Unit'), h('th', {}, 'Crew'), h('th', { class: 'n' }, 'Rate/day'),
        h('th', { class: 'n' }, 'Resources'), h('th', { class: 'n' }, 'Direct unit cost*'), h('th', {}))),
      h('tbody', {}, list.length ? list.map((t) => h('tr', {},
        h('td', { class: 'code' }, t.code), h('td', {}, h('b', {}, t.description)), h('td', {}, t.category),
        h('td', {}, t.unit), h('td', {}, t.crew_name || '—'), h('td', { class: 'n' }, fmtQ(t.production_rate)),
        h('td', { class: 'n' }, t.resources.length), h('td', { class: 'n' }, money(t.unit_cost_preview)),
        h('td', { class: 'actions-cell' }, h('button', { onclick: () => edit(t) }, 'Edit'), ' ',
          h('button', {
            class: 'danger', onclick: async () => {
              if (!confirmBox(`Delete standard task ${t.code}?`)) return;
              await attempt(() => api('DELETE', `/library/${t.id}`), 'Deleted');
              renderLibrary();
            },
          }, 'Delete'))))
        : h('tr', {}, h('td', { colspan: 9, class: 'empty' }, 'No standard tasks yet.'))))),
    h('div', { class: 'hint', style: 'margin-top:8px' }, '* At current database prices and 8 working hours per day.')));
}

// ================================================================ SIMPLE TABLES

const SIMPLE = {
  labor: {
    title: 'Labor trades', path: '/labor', search: true,
    hint: 'Hourly wage (private and public works) plus burden. Trades on “Standard” burden use the calculator above; the loaded rate is what crews cost.',
    tableTitle: 'Trades',
    before: renderBurdenPanels,
    headActions: (reload) => h('button', {
      class: 'primary', onclick: async () => {
        if (!confirmBox('Load the CAPAC–SUNTRACS convention wages?\n\nTrades are matched by code (HLP, PRI, MAS, CAR, IRW, PLU, ELE, WEL, PNT, OPR). Existing ones get updated wages and switch to Standard burden; missing ones are added. Other trades are not touched.')) return;
        const r = await attempt(() => api('POST', '/labor/load-capac'));
        toast(`CAPAC–SUNTRACS rates loaded: ${r.updated} updated, ${r.inserted} added`);
        reload();
      },
    }, 'Load CAPAC–SUNTRACS rates'),
    cols: [
      { f: 'code', label: 'Code', w: 80 }, { f: 'trade', label: 'Trade' },
      { f: 'category', label: 'Category', w: 150, list: 'labor-cats' },
      { f: 'base_rate', label: 'Wage / hr private', num: true, w: 105 },
      { f: 'public_rate', label: 'Wage / hr public', num: true, w: 105 },
      { f: 'use_standard_burden', label: 'Burden', w: 115, select: [['1', 'Standard'], ['0', 'Custom']] },
      { f: 'burden_pct', label: 'Custom %', num: true, w: 85, disabled: (r) => String(r.use_standard_burden) === '1' },
      { calc: (r) => (r.effective_burden === undefined ? '' : fmtN(r.effective_burden, 2) + '%'), label: 'Burden used' },
      { calc: (r) => (r.loaded_rate === undefined ? '' : money(r.loaded_rate)), label: 'Loaded private' },
      { calc: (r) => (r.loaded_public === undefined ? '' : money(r.loaded_public)), label: 'Loaded public' },
    ],
    blank: { code: '', trade: '', category: 'Calificado', base_rate: 0, public_rate: 0, use_standard_burden: 1, burden_pct: 0 },
  },
  equipment: {
    title: 'Equipment', path: '/equipment',
    hint: 'Hourly cost including ownership or rental, fuel, and maintenance. Operators are added to crews as labor.',
    cols: [
      { f: 'code', label: 'Code', w: 100 }, { f: 'description', label: 'Description' },
      { f: 'hourly_rate', label: 'Cost / hr', num: true, w: 130 },
    ],
    blank: { code: '', description: '', hourly_rate: 0 },
  },
  materials: {
    title: 'Materials & consumables', path: '/materials', search: true,
    hint: 'Materials are incorporated into the work; consumables are used up doing it (wire, nails, discs, form oil…). Waste % is added to quantities.',
    cols: [
      { f: 'code', label: 'Code', w: 100 }, { f: 'description', label: 'Description' },
      { f: 'kind', label: 'Type', w: 130, select: [['material', 'Material'], ['consumable', 'Consumable']] },
      { f: 'category', label: 'Category', w: 130 },
      { f: 'unit', label: 'Unit', w: 80, units: true },
      { f: 'unit_cost', label: 'Unit cost', num: true, w: 120 },
      { f: 'waste_pct', label: 'Waste %', num: true, w: 90 },
    ],
    blank: { code: '', description: '', kind: 'material', category: '', unit: 'ea', unit_cost: 0, waste_pct: 0 },
  },
  'indirect-library': {
    title: 'Indirect cost library', path: '/indirect-library',
    hint: 'Standard indirect items to add to estimates: site staff and facilities (quantity × rate, e.g. per month), or a % of direct cost or direct labor.',
    cols: [
      { f: 'description', label: 'Description' }, { f: 'category', label: 'Category', w: 130 },
      { f: 'method', label: 'Method', w: 170, select: Object.entries(METHOD_LABELS) },
      { f: 'unit', label: 'Unit', w: 90, units: true },
      { f: 'rate', label: 'Rate', num: true, w: 120 },
      { f: 'percent', label: '%', num: true, w: 90 },
    ],
    blank: { description: '', category: '', method: 'lump', unit: 'month', rate: 0, percent: 0 },
  },
  units: {
    title: 'Units of measure', path: '/units',
    hint: 'Units offered when defining tasks and materials (you can also type any unit).',
    cols: [{ f: 'code', label: 'Code', w: 140 }, { f: 'name', label: 'Name' }],
    blank: { code: '', name: '' },
  },
};

let simpleFilter = '';
let simpleFilterKey = '';

async function renderSimple(key) {
  const def = SIMPLE[key];
  if (simpleFilterKey !== key) { simpleFilter = ''; simpleFilterKey = key; }
  money = moneyFmt('USD');
  const [rows] = await Promise.all([api('GET', def.path), loadRefs('units')]);
  const fresh = { ...def.blank };

  const input = (row, col, onChange) => {
    const fk = `s-${row.id || 'new'}-${col.f}`;
    const disabled = col.disabled ? col.disabled(row) : false;
    if (col.select) {
      return h('select', { dataset: { fk }, disabled, onchange: onChange }, options(col.select.map(([v, l]) => ({ value: v, label: l })), row[col.f]));
    }
    if (col.num) return numInput(row[col.f], { dataset: { fk }, disabled, onchange: onChange });
    return h('input', { value: row[col.f], list: col.units ? 'units-list' : col.list || null, dataset: { fk }, disabled, onchange: onChange });
  };

  const q = simpleFilter.toLowerCase();
  const shown = def.search && q
    ? rows.filter((r) => Object.values(r).some((v) => String(v).toLowerCase().includes(q)))
    : rows;

  const reload = () => keepFocus(() => renderSimple(key));

  const newRow = h('tr', { class: 'dirty' },
    def.cols.map((c) => h('td', { style: c.w ? `width:${c.w}px` : null },
      c.calc ? '' : input(fresh, c, (ev) => {
        fresh[c.f] = ev.target.value;
        if (c.select) { const d = ev.target.closest('tr').querySelectorAll('input'); d.forEach((el) => { const cc = def.cols.find((x) => `s-new-${x.f}` === el.dataset.fk); if (cc && cc.disabled) el.disabled = cc.disabled(fresh); }); }
      }))),
    h('td', { class: 'actions-cell' }, h('button', {
      class: 'primary icon', onclick: async () => {
        await attempt(() => api('POST', def.path, fresh), 'Added');
        renderSimple(key);
      },
    }, 'Add')));

  const bodyRows = shown.map((r) => h('tr', {},
    def.cols.map((c) => h('td', { class: c.calc ? 'n' : '' },
      c.calc ? c.calc(r) : input(r, c, async (ev) => {
        try {
          await attempt(() => api('PUT', `${def.path}/${r.id}`, { [c.f]: ev.target.value }), 'Saved');
        } finally { reload(); }
      }))),
    h('td', { class: 'actions-cell' }, h('button', {
      class: 'icon danger', onclick: async () => {
        if (!confirmBox('Delete this record?')) return;
        await attempt(() => api('DELETE', `${def.path}/${r.id}`), 'Deleted');
        renderSimple(key);
      },
    }, '✕'))));

  const before = def.before ? await def.before(reload) : null;
  $app.replaceChildren(
    unitDatalist(),
    h('datalist', { id: 'labor-cats' }, ['Ayudante general', 'Principiante', 'Calificado', 'Fuera de convención'].map((c) => h('option', { value: c }))),
    h('div', { class: 'page-head' },
      h('div', {}, h('h1', {}, def.title), h('div', { class: 'sub' }, def.hint)),
      h('div', { class: 'actions' },
        def.search ? h('input', {
          placeholder: 'Search…', style: 'width:240px', value: simpleFilter, dataset: { fk: 'search' },
          oninput: (ev) => { simpleFilter = ev.target.value; reload(); },
        }) : null,
        def.headActions ? def.headActions(reload) : null)),
    ...(before || []),
    h('div', { class: 'panel' },
      def.tableTitle ? h('div', { class: 'panel-head' }, h('h2', {}, def.tableTitle)) : null,
      h('div', { class: 'table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, def.cols.map((c) => h('th', { class: c.num || c.calc ? 'n' : '' }, c.label)), h('th', {}))),
      h('tbody', {}, newRow, bodyRows)))),
    h('div', { class: 'hint' }, 'Edits save automatically when you leave a field. The highlighted top row adds a new record.'));
}


// ---------------------------------------------------------------- labor burden (Panama)

async function renderBurdenPanels(reload) {
  const b = await api('GET', '/burden');
  const save = (c, f) => async (ev) => {
    const v = ev.target.type === 'checkbox' ? (ev.target.checked ? 1 : 0) : ev.target.value;
    try { await attempt(() => api('PUT', `/burden-components/${c.id}`, { [f]: v }), 'Saved'); } finally { reload(); }
  };
  const rows = b.components.map((c) => h('tr', { class: c.active ? '' : 'subtle' },
    h('td', { style: 'width:40px;text-align:center' }, h('input', { type: 'checkbox', checked: !!c.active, style: 'width:auto', title: 'Include', onchange: save(c, 'active') })),
    h('td', {}, h('input', { value: c.name, dataset: { fk: `b-${c.id}-n` }, onchange: save(c, 'name') })),
    h('td', { style: 'width:130px' }, h('select', { dataset: { fk: `b-${c.id}-k` }, onchange: save(c, 'kind') },
      options([{ value: 'leave', label: 'Paid leave' }, { value: 'charge', label: 'Charge' }], c.kind))),
    h('td', { style: 'width:90px' }, numInput(c.percent, { dataset: { fk: `b-${c.id}-p` }, onchange: save(c, 'percent') })),
    h('td', {}, h('input', { value: c.notes, dataset: { fk: `b-${c.id}-o` }, onchange: save(c, 'notes') })),
    h('td', { class: 'actions-cell' }, h('button', {
      class: 'icon danger', onclick: async () => {
        if (!confirmBox(`Remove “${c.name}” from the burden?`)) return;
        await attempt(() => api('DELETE', `/burden-components/${c.id}`), 'Removed');
        reload();
      },
    }, '✕'))));

  const cats = Object.entries(b.category_rates);
  return [
    h('div', { class: 'panel' },
      h('div', { class: 'panel-head' },
        h('h2', {}, 'Standard labor burden — cargas sociales y prestaciones'),
        h('div', { class: 'actions' },
          h('button', {
            onclick: async () => {
              await attempt(() => api('POST', '/burden-components', { name: 'New item', kind: 'charge', percent: 0, sort: 900 }));
              reload();
            },
          }, '+ Add item'),
          h('button', {
            onclick: async () => {
              if (!confirmBox('Replace all burden items with the Panama defaults?')) return;
              await attempt(() => api('POST', '/burden/reset'), 'Reset to defaults');
              reload();
            },
          }, 'Reset to Panama defaults'))),
      h('div', { class: 'table-wrap' }, h('table', {},
        h('thead', {}, h('tr', {}, h('th', {}, 'Use'), h('th', {}, 'Item'), h('th', {}, 'Applies to'),
          h('th', { class: 'n' }, '%'), h('th', {}, 'Basis / notes'), h('th', {}))),
        h('tbody', {}, rows))),
      h('div', { class: 'preview-box' },
        h('div', {}, h('span', {}, 'Paid leave (L)'), h('b', {}, fmtN(b.leave_pct, 2) + '%')),
        h('div', {}, h('span', {}, 'Charges (C)'), h('b', {}, fmtN(b.charge_pct, 2) + '%')),
        h('div', {}, h('span', {}, 'Standard burden = L + (1+L)·C'), h('b', { style: 'font-size:18px' }, fmtN(b.total_pct, 2) + '%')),
        h('div', {}, h('span', {}, 'Calificado private, loaded'), h('b', {}, money((b.category_rates.Calificado || [0])[0] * (1 + b.total_pct / 100)) + '/hr'))),
      h('div', { class: 'hint', style: 'margin-top:8px' },
        'Paid leave is time paid but not worked, so it is spread over the hours actually worked. Charges (CSS, seguro educativo, riesgos profesionales, XIII mes, prima de antigüedad…) apply to wage plus paid leave. Defaults are a starting point: confirm them with your accountant and your CSS statement.')),
    h('div', { class: 'panel' },
      h('div', { class: 'panel-head' },
        h('h2', {}, 'Convention reference'),
        h('span', { class: 'hint' }, `${b.convention.name} — ${b.convention.step}`)),
      h('table', { style: 'max-width:620px' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Category'), h('th', { class: 'n' }, 'Private works / hr'), h('th', { class: 'n' }, 'Public works / hr'))),
        h('tbody', {}, cats.map(([name, [pv, pb]]) => h('tr', {}, h('td', {}, name), h('td', { class: 'n' }, money(pv)), h('td', { class: 'n' }, money(pb)))))),
      h('div', { class: 'hint', style: 'margin-top:8px' },
        'Category-level minimums. The official table lists individual occupations, some of them above these rates: verify each trade against the signed table and update the wages below.')),
  ];
}

// ---------------------------------------------------------------- start
router();
