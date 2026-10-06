const REFRESH_MS = 2000;
const state = { processes: [], sortKey: "cpu_percent", sortDir: -1, search: "", stateFilter: "" };

const rowsEl = document.getElementById("rows");
const summaryEl = document.getElementById("summary");
const statusEl = document.getElementById("status");

// ค่า null แสดงเป็น "—" ห้ามให้หน้าเว็บพัง
function fmt(v, digits) {
  if (v === null || v === undefined) return null;
  return digits === undefined ? String(v) : Number(v).toFixed(digits);
}

function compare(a, b) {
  const x = a[state.sortKey], y = b[state.sortKey];
  if (x === null || x === undefined) return 1;   // null ไปท้ายเสมอ
  if (y === null || y === undefined) return -1;
  if (typeof x === "string") return x.localeCompare(y) * state.sortDir;
  return (x - y) * state.sortDir;
}

function visibleProcesses() {
  const q = state.search.trim().toLowerCase();
  return state.processes
    .filter(p => !state.stateFilter || p.state === state.stateFilter)
    .filter(p => !q || String(p.pid).includes(q) || (p.name || "").toLowerCase().includes(q))
    .sort(compare);
}

function cell(tr, text, numeric) {
  const td = document.createElement("td");
  if (text === null) {
    td.textContent = "—";
    td.className = "dash";
  } else {
    td.textContent = text;
  }
  if (numeric) td.classList.add("num");
  tr.appendChild(td);
}

function render() {
  const frag = document.createDocumentFragment();
  for (const p of visibleProcesses()) {
    const tr = document.createElement("tr");
    tr.className = "state-" + p.state;
    cell(tr, fmt(p.pid), true);
    cell(tr, fmt(p.name));
    cell(tr, fmt(p.ppid), true);
    cell(tr, fmt(p.state));
    cell(tr, fmt(p.priority));
    cell(tr, fmt(p.cpu_percent, 1), true);
    cell(tr, p.mem_rss === null ? null : (p.mem_rss / 1048576).toFixed(1), true);
    cell(tr, fmt(p.threads), true);
    frag.appendChild(tr);
  }
  rowsEl.replaceChildren(frag);
}

function renderSummary(s) {
  const hours = (s.uptime_s / 3600).toFixed(1);
  summaryEl.textContent =
    `CPU ${s.cpu_percent}% · RAM ${s.mem_percent}% · ` +
    `${s.process_count} processes · uptime ${hours} ชม.`;
}

async function refresh() {
  try {
    const res = await fetch("/api/snapshot");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const snap = await res.json();
    state.processes = snap.processes;
    renderSummary(snap.system);
    render();
    statusEl.textContent = "อัปเดตล่าสุด " + new Date().toLocaleTimeString();
  } catch (err) {
    statusEl.textContent = "เชื่อมต่อ server ไม่ได้: " + err.message;
  } finally {
    setTimeout(refresh, REFRESH_MS);   // รอให้รอบนี้จบก่อนค่อยนัดรอบถัดไป
  }
}

document.getElementById("search").addEventListener("input", e => {
  state.search = e.target.value; render();
});
document.getElementById("state-filter").addEventListener("change", e => {
  state.stateFilter = e.target.value; render();
});
document.querySelectorAll("th[data-key]").forEach(th => {
  th.addEventListener("click", () => {
    const key = th.dataset.key;
    state.sortDir = state.sortKey === key ? -state.sortDir : 1;
    state.sortKey = key;
    render();
  });
});

refresh();