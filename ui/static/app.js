const REFRESH_MS = 1000;
const LEVELS = ["low", "below_normal", "normal", "above_normal", "high"];
const state = {
  processes: [], sortKey: "cpu_percent", sortDir: -1,
  search: "", stateFilter: "",
  treeMode: false, collapsed: new Set(),
};
const HISTORY_LEN = 60;   // 60 จุด x 1 วินาที = ย้อนหลัง 1 นาที
const history = { cpu: [], ram: [] };
const CHART_COLORS = { cpu: "88, 166, 255", ram: "163, 113, 247" };   // rgb ของเส้นกราฟ
const PLATFORM_NAMES = { windows: "Windows", macos: "macOS" };
const FLASH_DELTA = 3;        // CPU% (รวมทั้งเครื่อง) ที่เปลี่ยนจากรอบก่อนเกินค่านี้ จะกะพริบแถว
let prevCpu = new Map();      // pid -> cpu_percent ของรอบก่อน
let flashPids = new Set();    // pid ที่ต้องกะพริบในรอบวาดนี้

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

// ป้าย priority ระดับนามธรรม (สีกำหนดใน CSS ด้วย class prio-xxx)
function priorityCell(tr, level) {
  const td = document.createElement("td");
  if (level === null) {
    td.textContent = "—";
    td.className = "dash";
  } else {
    const badge = document.createElement("span");
    badge.className = "prio prio-" + level;
    badge.textContent = level;
    td.appendChild(badge);
  }
  tr.appendChild(td);
}

// เซลล์ตัวเลขพร้อมแถบความยาวตามสัดส่วน fraction (0-1)
function barCell(tr, text, fraction, kind) {
  const td = document.createElement("td");
  td.className = "num has-bar";
  if (text === null) {
    td.textContent = "—";
    td.classList.add("dash");
  } else {
    const bar = document.createElement("span");
    bar.className = "bar bar-" + kind;
    const fill = document.createElement("span");
    fill.className = "bar-fill";
    const pct = Math.max(0, Math.min(1, fraction)) * 100;
    fill.style.width = (pct > 0 && pct < 2 ? 2 : pct) + "%";   // มีค่าแต่น้อยมาก ให้เห็นเป็นขีดเล็กๆ
    bar.appendChild(fill);
    const val = document.createElement("span");
    val.className = "bar-val";
    val.textContent = text;
    td.append(bar, val);
  }
  tr.appendChild(td);
}

// ลูกศร ▲▼ บนหัวคอลัมน์ที่กำลังเรียง (โหมดต้นไม้ไม่ใช้การเรียง จึงซ่อน)
function updateSortIndicators(active) {
  document.querySelectorAll("th[data-key]").forEach(th => {
    th.classList.remove("sort-asc", "sort-desc");
    if (active && th.dataset.key === state.sortKey) {
      th.classList.add(state.sortDir === 1 ? "sort-asc" : "sort-desc");
    }
  });
}

// หา process ที่ CPU% เปลี่ยนแรงจากรอบก่อน (ใช้กะพริบแถว) แล้วจำค่ารอบนี้ไว้เทียบรอบหน้า
function findCpuSpikes(procs) {
  const spikes = new Set();
  const next = new Map();
  for (const p of procs) {
    if (p.cpu_percent === null) continue;
    next.set(p.pid, p.cpu_percent);
    const before = prevCpu.get(p.pid);
    if (before !== undefined && Math.abs(p.cpu_percent - before) >= FLASH_DELTA) spikes.add(p.pid);
  }
  prevCpu = next;
  return spikes;
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

  updateSortIndicators(!useTree);
  // แถบ RAM เทียบกับ process ที่ใช้ RAM มากสุดในรอบนี้ (ถ้าเทียบกับ RAM ทั้งเครื่อง ส่วนใหญ่จะเล็กจนมองไม่เห็น)
  const maxRss = Math.max(1, ...state.processes.map(p => p.mem_rss || 0));

  const frag = document.createDocumentFragment();
  for (const { p, depth, hasChildren } of rows) {
    const tr = document.createElement("tr");
    tr.className = "state-" + p.state + (flashPids.has(p.pid) ? " flash" : "");
    cell(tr, fmt(p.pid), true);
    if (useTree) nameCell(tr, p, depth, hasChildren);
    else cell(tr, fmt(p.name));
    cell(tr, fmt(p.ppid), true);
    cell(tr, fmt(p.state));
    priorityCell(tr, fmt(p.priority));
    // แถบ CPU เป็นสัดส่วนจริงของ CPU ทั้งเครื่อง (0-100%)
    barCell(tr, fmt(p.cpu_percent, 1), (p.cpu_percent || 0) / 100, "cpu");
    barCell(tr, p.mem_rss === null ? null : (p.mem_rss / 1048576).toFixed(1), (p.mem_rss || 0) / maxRss, "ram");
    cell(tr, fmt(p.threads), true);
    actionCell(tr, p);
    frag.appendChild(tr);
  }
  rowsEl.replaceChildren(frag);
}

// ---------- กราฟ ----------

// rgb เป็นข้อความเช่น "88, 166, 255" (ใช้ทำทั้งสีเส้นและ gradient ใต้เส้น)
function drawChart(canvasId, values, rgb) {
  const canvas = document.getElementById(canvasId);
  const rect = canvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  // ปรับขนาด canvas ให้เท่าขนาดจริงบนจอ (คูณ devicePixelRatio) กราฟจะไม่เบลอหรือถูกยืด
  const dpr = window.devicePixelRatio || 1;
  const w = Math.round(rect.width * dpr), h = Math.round(rect.height * dpr);
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);

  const yOf = v => h - (Math.min(v, 100) / 100) * (h - 4 * dpr) - 2 * dpr;
  const xOf = i => (i / (HISTORY_LEN - 1)) * w;

  // เส้นกริด 0 / 50 / 100%
  ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
  ctx.lineWidth = dpr;
  for (const pct of [0, 50, 100]) {
    const y = yOf(pct);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  if (values.length < 2) return;
  ctx.beginPath();
  values.forEach((v, i) => {
    if (i === 0) ctx.moveTo(xOf(i), yOf(v)); else ctx.lineTo(xOf(i), yOf(v));
  });
  ctx.strokeStyle = `rgb(${rgb})`;
  ctx.lineWidth = 2 * dpr;
  ctx.lineJoin = "round";
  ctx.stroke();

  // พื้นที่ใต้เส้น: ไล่สีจากเข้มด้านบนไปจางด้านล่าง
  ctx.lineTo(xOf(values.length - 1), h);
  ctx.lineTo(xOf(0), h);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, `rgba(${rgb}, 0.35)`);
  grad.addColorStop(1, `rgba(${rgb}, 0)`);
  ctx.fillStyle = grad;
  ctx.fill();
}

function pushHistory(list, value) {
  list.push(value);
  if (list.length > HISTORY_LEN) list.shift();   // ทิ้งจุดเก่าสุด
}

function pill(label, value) {
  const el = document.createElement("span");
  el.className = "pill";
  const strong = document.createElement("b");
  strong.textContent = value;
  el.append(label + " ", strong);
  return el;
}

function renderSummary(s) {
  const hours = (s.uptime_s / 3600).toFixed(1);
  summaryEl.replaceChildren(
    pill("CPU", s.cpu_percent + "%"),
    pill("RAM", s.mem_percent + "%"),
    pill("Processes", s.process_count),
    pill("Uptime", hours + " ชม."),
  );

  const badge = document.getElementById("platform-badge");
  if (badge) {
    badge.textContent = PLATFORM_NAMES[s.platform] || s.platform;
    badge.hidden = false;
  }

  pushHistory(history.cpu, s.cpu_percent);
  pushHistory(history.ram, s.mem_percent);
  document.getElementById("cpu-now").textContent = s.cpu_percent + "%";
  document.getElementById("ram-now").textContent = s.mem_percent + "%";
  drawChart("cpu-chart", history.cpu, CHART_COLORS.cpu);
  drawChart("ram-chart", history.ram, CHART_COLORS.ram);
}

// ---------- ดึงข้อมูลเป็นรอบ ----------

async function refresh() {
  try {
    const res = await fetch("/api/snapshot");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const snap = await res.json();
    state.processes = snap.processes;
    flashPids = findCpuSpikes(snap.processes);
    // วาดตารางก่อน เพื่อให้กราฟที่พังไม่ลากตารางพังตาม
    // ไม่วาดตารางใหม่ขณะเปิดกล่องยืนยันหรือเลือก dropdown ค้างอยู่ ไม่งั้นจะหลุด
    const picking = document.activeElement && document.activeElement.tagName === "SELECT";
    if (!dialogEl.open && !picking) render();
    flashPids = new Set();   // กะพริบเฉพาะรอบที่ข้อมูลใหม่เข้ามา ไม่ให้ซ้ำตอนพิมพ์ค้นหา
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