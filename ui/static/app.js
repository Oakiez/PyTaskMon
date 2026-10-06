const REFRESH_MS = 2000;
const LEVELS = ["low", "below_normal", "normal", "above_normal", "high"];
const state = {
  processes: [], sortKey: "cpu_percent", sortDir: -1,
  search: "", stateFilter: "",
  treeMode: false, collapsed: new Set(),
};
const HISTORY_LEN = 30;   // 30 จุด x 2 วินาที = ย้อนหลัง 1 นาที
const history = { cpu: [], ram: [] };

const rowsEl = document.getElementById("rows");
const summaryEl = document.getElementById("summary");
const statusEl = document.getElementById("status");
const toastEl = document.getElementById("toast");
const dialogEl = document.getElementById("confirm-dialog");
const dialogTextEl = document.getElementById("confirm-text");
const treeHintEl = document.getElementById("tree-hint");

// ---------- แสดงผล ----------

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

// ---------- Process tree ----------

// รากของต้นไม้ = ไม่มีพ่อ, พ่อคือตัวเอง, หรือพ่อไม่อยู่ในรายการ (กฎเดียวกับ find_roots ใน collector)
function hasParentInList(p, pids) {
  return p.ppid !== null && p.ppid !== p.pid && pids.has(p.ppid);
}

function treeRows(procs) {
  const pids = new Set(procs.map(p => p.pid));
  const kids = new Map();
  const roots = [];
  for (const p of procs) {
    if (!hasParentInList(p, pids)) {
      roots.push(p);
    } else {
      if (!kids.has(p.ppid)) kids.set(p.ppid, []);
      kids.get(p.ppid).push(p);
    }
  }
  const byPid = (a, b) => a.pid - b.pid;
  roots.sort(byPid);

  const out = [];
  const seen = new Set();   // กันวนลูปไม่รู้จบ ถ้าข้อมูลพ่อ-ลูกผิดปกติ
  const walk = (p, depth) => {
    if (seen.has(p.pid)) return;
    seen.add(p.pid);
    const children = (kids.get(p.pid) || []).sort(byPid);
    out.push({ p, depth, hasChildren: children.length > 0 });
    if (!state.collapsed.has(p.pid)) {
      for (const c of children) walk(c, depth + 1);
    }
  };
  roots.forEach(r => walk(r, 0));
  return out;
}

function nameCell(tr, p, depth, hasChildren) {
  const td = document.createElement("td");
  td.style.paddingLeft = (10 + depth * 18) + "px";
  if (hasChildren) {
    const t = document.createElement("button");
    t.className = "twisty";
    t.textContent = state.collapsed.has(p.pid) ? "▸" : "▾";
    t.addEventListener("click", () => {
      if (state.collapsed.has(p.pid)) state.collapsed.delete(p.pid);
      else state.collapsed.add(p.pid);
      render();
    });
    td.appendChild(t);
  } else {
    const sp = document.createElement("span");
    sp.className = "twisty-space";
    td.appendChild(sp);
  }
  td.appendChild(document.createTextNode(p.name === null ? "—" : p.name));
  tr.appendChild(td);
}

// ---------- Actions ----------

let toastTimer = null;

function showToast(message, isError) {
  toastEl.textContent = message;
  toastEl.className = isError ? "error" : "";
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 5000);
}

async function sendAction(pid, action, extra) {
  try {
    const res = await fetch("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pid, action, ...extra }),
    });
    const result = await res.json();
    // แสดง message จาก ActionResult ตรงๆ ทั้งกรณีสำเร็จและถูกปฏิเสธ
    showToast(result.message, !result.ok);
  } catch (err) {
    showToast("ส่งคำสั่งไม่สำเร็จ: " + err.message, true);
  }
}

function confirmThenKill(p) {
  dialogTextEl.textContent =
    `ต้องการ kill "${p.name || "—"}" (PID ${p.pid}) จริงหรือไม่? การกระทำนี้ย้อนกลับไม่ได้`;
  dialogEl.onclose = () => {
    if (dialogEl.returnValue === "ok") {
      sendAction(p.pid, "kill", { confirm: true });
    }
  };
  dialogEl.returnValue = "";
  dialogEl.showModal();
}

function actionCell(tr, p) {
  const td = document.createElement("td");
  td.className = "actions";

  const mk = (label, onClick, cls) => {
    const b = document.createElement("button");
    b.textContent = label;
    if (cls) b.className = cls;
    b.addEventListener("click", onClick);
    td.appendChild(b);
  };

  mk("Suspend", () => sendAction(p.pid, "suspend"));
  mk("Resume", () => sendAction(p.pid, "resume"));
  mk("Kill", () => confirmThenKill(p), "danger");

  const sel = document.createElement("select");
  sel.appendChild(new Option("Priority…", ""));
  for (const level of LEVELS) sel.appendChild(new Option(level, level));
  sel.addEventListener("change", () => {
    if (sel.value) sendAction(p.pid, "set_priority", { level: sel.value });
    sel.value = "";
  });
  td.appendChild(sel);

  tr.appendChild(td);
}

// ---------- วาดตาราง ----------

function render() {
  const filtering = state.search.trim() !== "" || state.stateFilter !== "";
  const useTree = state.treeMode && !filtering;   // ค้นหา/กรองแล้วต้นไม้จะขาด จึงใช้รายการแบนแทน
  const rows = useTree
    ? treeRows(state.processes)
    : visibleProcesses().map(p => ({ p, depth: 0, hasChildren: false }));
  treeHintEl.textContent = state.treeMode && filtering ? "(แสดงเป็นรายการระหว่างค้นหา/กรอง)" : "";

  const frag = document.createDocumentFragment();
  for (const { p, depth, hasChildren } of rows) {
    const tr = document.createElement("tr");
    tr.className = "state-" + p.state;
    cell(tr, fmt(p.pid), true);
    if (useTree) nameCell(tr, p, depth, hasChildren);
    else cell(tr, fmt(p.name));
    cell(tr, fmt(p.ppid), true);
    cell(tr, fmt(p.state));
    cell(tr, fmt(p.priority));
    cell(tr, fmt(p.cpu_percent, 1), true);
    cell(tr, p.mem_rss === null ? null : (p.mem_rss / 1048576).toFixed(1), true);
    cell(tr, fmt(p.threads), true);
    actionCell(tr, p);
    frag.appendChild(tr);
  }
  rowsEl.replaceChildren(frag);
}

// ---------- กราฟ ----------

function drawChart(canvasId, values, color) {
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // เส้นกริด 0 / 50 / 100%
  ctx.strokeStyle = "#eee";
  ctx.lineWidth = 1;
  for (const pct of [0, 50, 100]) {
    const y = h - (pct / 100) * (h - 4) - 2;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  if (values.length < 2) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = (i / (HISTORY_LEN - 1)) * w;
    const y = h - (Math.min(v, 100) / 100) * (h - 4) - 2;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function pushHistory(list, value) {
  list.push(value);
  if (list.length > HISTORY_LEN) list.shift();   // ทิ้งจุดเก่าสุด
}

function renderSummary(s) {
  const hours = (s.uptime_s / 3600).toFixed(1);
  summaryEl.textContent =
    `CPU ${s.cpu_percent}% · RAM ${s.mem_percent}% · ` +
    `${s.process_count} processes · uptime ${hours} ชม.`;

  pushHistory(history.cpu, s.cpu_percent);
  pushHistory(history.ram, s.mem_percent);
  document.getElementById("cpu-now").textContent = s.cpu_percent + "%";
  document.getElementById("ram-now").textContent = s.mem_percent + "%";
  drawChart("cpu-chart", history.cpu, "#2b7de9");
  drawChart("ram-chart", history.ram, "#d9534f");
}

// ---------- ดึงข้อมูลเป็นรอบ ----------

async function refresh() {
  try {
    const res = await fetch("/api/snapshot");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const snap = await res.json();
    state.processes = snap.processes;
    // วาดตารางก่อน เพื่อให้กราฟที่พังไม่ลากตารางพังตาม
    // ไม่วาดตารางใหม่ขณะเปิดกล่องยืนยันหรือเลือก dropdown ค้างอยู่ ไม่งั้นจะหลุด
    const picking = document.activeElement && document.activeElement.tagName === "SELECT";
    if (!dialogEl.open && !picking) render();
    renderSummary(snap.system);
    statusEl.textContent = "อัปเดตล่าสุด " + new Date().toLocaleTimeString();
  } catch (err) {
    statusEl.textContent = "เชื่อมต่อ server ไม่ได้: " + err.message;
  } finally {
    setTimeout(refresh, REFRESH_MS);   // รอให้รอบนี้จบก่อนค่อยนัดรอบถัดไป
  }
}

// ---------- ผูก event ----------

document.getElementById("search").addEventListener("input", e => {
  state.search = e.target.value; render();
});
document.getElementById("state-filter").addEventListener("change", e => {
  state.stateFilter = e.target.value; render();
});
document.getElementById("tree-toggle").addEventListener("change", e => {
  state.treeMode = e.target.checked; render();
});
document.getElementById("expand-all").addEventListener("click", () => {
  state.collapsed.clear(); render();
});
document.getElementById("collapse-all").addEventListener("click", () => {
  const pids = new Set(state.processes.map(p => p.pid));
  for (const p of state.processes) {
    if (hasParentInList(p, pids)) state.collapsed.add(p.ppid);
  }
  render();
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