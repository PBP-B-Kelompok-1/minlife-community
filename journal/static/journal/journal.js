(() => {
  const root = document.getElementById("journal");
  if (!root) return;

  const entries = JSON.parse(document.getElementById("jr-entries").textContent);
  const entryUrl = root.dataset.entryUrl;
  const csrf = root.dataset.csrf;
  const today = root.dataset.today;
  const monthPrefix = `${root.dataset.year}-${root.dataset.month.padStart(2, "0")}`;

  const DAYS = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
  const MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
  const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  const HINTS = {
    private: "Hanya kamu yang bisa melihat entry ini.",
    public: "Entry ini bisa dilihat user lain di profile-mu.",
  };

  const $ = (id) => document.getElementById(id);
  const grid = $("jr-grid");
  const popup = $("jr-popup");
  const summary = $("jr-summary");
  const editor = $("jr-editor");
  const body = $("jr-body");
  const status = $("jr-status");
  const saveBtn = $("jr-save");
  const deleteBtn = $("jr-delete");

  let current = null;
  let visibility = "private";
  let showAll = false;
  let loadId = 0;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function parseDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  function dateLabel(iso, withYear = true) {
    const d = parseDate(iso);
    const text = `${DAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]}`;
    return withYear ? `${text} ${d.getFullYear()}` : text;
  }

  const cellFor = (iso) => grid.querySelector(`[data-date="${iso}"]`);

  async function request(method, iso, payload) {
    const options = { method, headers: { "X-CSRFToken": csrf }, credentials: "same-origin" };
    if (payload) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    const res = await fetch(entryUrl.replace("0000-00-00", iso), options);
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, data };
  }

  // SweetAlert2 udah di-load di base.html tim
  function toast(title) {
    if (!window.Swal) return;
    Swal.fire({ toast: true, position: "top-end", icon: "success", title, showConfirmButton: false, timer: 2000 });
  }

  async function confirmDelete() {
    if (!window.Swal) return window.confirm("Hapus entry ini?");
    const result = await Swal.fire({
      title: "Hapus entry ini?",
      text: "Entry yang sudah dihapus tidak bisa dikembalikan.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Hapus",
      cancelButtonText: "Batal",
      confirmButtonColor: "#c0475a",
    });
    return result.isConfirmed;
  }

  function setStatus(message) {
    status.textContent = message || "";
  }

  // ringkasan bulan
  function chip(vis) {
    return el("span", vis === "public" ? "jr-chip is-public" : "jr-chip", vis === "public" ? "Public" : "Private");
  }

  function summaryRow(entry) {
    const d = parseDate(entry.date);
    const row = el("button", entry.date === current ? "jr-row is-current" : "jr-row");
    row.type = "button";
    row.dataset.date = entry.date;

    const badge = el("span", "jr-badge");
    badge.append(el("b", "", d.getDate()), el("small", "", MONTHS_SHORT[d.getMonth()]));

    const text = el("span", "jr-row-text");
    text.append(el("span", "jr-row-snippet", entry.snippet), el("small", "", `${DAYS[d.getDay()]} · ${entry.updated}`));

    row.append(badge, text, chip(entry.visibility));
    return row;
  }

  function renderSummary() {
    const list = Object.values(entries)
      .filter((e) => e.date.startsWith(monthPrefix))
      .sort((a, b) => b.date.localeCompare(a.date));
    const publicCount = list.filter((e) => e.visibility === "public").length;

    $("jr-total").textContent = list.length;
    $("jr-private").textContent = list.length - publicCount;
    $("jr-public").textContent = publicCount;

    const shown = showAll ? list : list.slice(0, 5);
    $("jr-list").replaceChildren(...shown.map(summaryRow));
    $("jr-empty").hidden = list.length > 0;

    const more = $("jr-more");
    more.hidden = list.length <= 5;
    more.textContent = showAll ? "Tampilkan lebih sedikit" : `Lihat ${list.length - 5} entri lainnya →`;

    const hasToday = Boolean(entries[today]);
    $("jr-new-icon").className = hasToday ? "fa-solid fa-pen" : "fa-solid fa-plus";
    $("jr-new-label").textContent = hasToday ? "Edit hari ini" : "Tulis entry";
  }

  function showSummary() {
    editor.hidden = true;
    summary.hidden = false;
    document.body.classList.remove("jr-lock");
    renderSummary();
  }

  // editor
  function setVisibility(value) {
    visibility = value === "public" ? "public" : "private";
    document.querySelectorAll(".jr-seg-btn").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.vis === visibility);
    });
    $("jr-hint").textContent = HINTS[visibility];
  }

  function markSelected() {
    grid.querySelectorAll(".is-selected").forEach((c) => c.classList.remove("is-selected"));
    cellFor(current)?.classList.add("is-selected");
  }

  function fillEditor(data) {
    $("jr-meta").textContent = data.exists ? `Tersimpan · diperbarui ${data.updated}` : "Belum ada entry untuk tanggal ini.";
    body.innerHTML = data.content; // sudah dibersihkan di server
    setVisibility(data.visibility);
    deleteBtn.hidden = !data.exists;
  }

  async function openEditor(iso) {
    hidePopup();
    current = iso;
    markSelected();
    setStatus("");

    $("jr-title").textContent = dateLabel(iso);
    $("jr-meta").textContent = "Memuat...";
    body.innerHTML = "";
    deleteBtn.hidden = true;
    summary.hidden = true;
    editor.hidden = false;
    document.body.classList.add("jr-lock");

    const id = ++loadId;
    try {
      const { ok, data } = await request("GET", iso);
      if (id !== loadId) return;
      if (!ok) throw new Error(data.error);
      fillEditor(data);
    } catch (err) {
      setStatus(err.message || "Gagal memuat entry.");
    }
  }

  async function save() {
    if (!body.textContent.trim()) {
      setStatus("Isi entry tidak boleh kosong.");
      return;
    }
    saveBtn.disabled = true;
    setStatus("");
    try {
      const { ok, data } = await request("POST", current, { content: body.innerHTML, visibility });
      if (!ok) {
        setStatus(data.error || "Gagal menyimpan.");
        return;
      }
      entries[current] = { date: data.date, snippet: data.snippet, visibility: data.visibility, updated: data.updated };
      cellFor(current)?.classList.add("has-entry");
      toast("Entry tersimpan");
      showSummary();
    } catch {
      setStatus("Tidak bisa terhubung ke server.");
    } finally {
      saveBtn.disabled = false;
    }
  }

  async function remove() {
    if (!(await confirmDelete())) return;
    try {
      const { ok, data } = await request("DELETE", current);
      if (!ok) {
        setStatus(data.error || "Gagal menghapus.");
        return;
      }
      delete entries[current];
      cellFor(current)?.classList.remove("has-entry");
      toast("Entry dihapus");
      showSummary();
    } catch {
      setStatus("Tidak bisa terhubung ke server.");
    }
  }

  // popup saat kursor di atas tanggal
  const canHover = window.matchMedia("(hover: hover)").matches;

  function hidePopup() {
    popup.hidden = true;
  }

  function showPopup(cell) {
    const iso = cell.dataset.date;
    const entry = entries[iso];

    const head = el("div", "jr-popup-head");
    head.append(el("strong", "", dateLabel(iso, false)));
    if (entry) head.append(chip(entry.visibility));

    const text = el("p", entry ? "jr-popup-text" : "jr-popup-text is-empty", entry ? entry.snippet : "Belum ada entry di tanggal ini.");

    const foot = el("div", "jr-popup-foot");
    if (entry) foot.append(el("span", "", `diperbarui ${entry.updated}`));
    foot.append(el("span", "jr-popup-hint", entry ? "klik untuk buka →" : "klik untuk mulai menulis"));

    popup.replaceChildren(head, text, foot);
    popup.classList.remove("is-below");
    popup.hidden = false;

    const rect = cell.getBoundingClientRect();
    const width = popup.offsetWidth;
    const height = popup.offsetHeight;
    const left = Math.max(8, Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width - 8));
    let top = rect.top - height - 12;
    if (top < 8) {
      top = rect.bottom + 12;
      popup.classList.add("is-below");
    }
    popup.style.left = `${left}px`;
    popup.style.top = `${top}px`;
    popup.style.setProperty("--arrow", `${rect.left + rect.width / 2 - left}px`);
  }

  if (canHover) {
    grid.addEventListener("mouseover", (e) => {
      const cell = e.target.closest(".jr-day");
      if (cell) showPopup(cell);
      else hidePopup();
    });
    grid.addEventListener("mouseleave", hidePopup);
    grid.addEventListener("focusin", (e) => e.target.closest(".jr-day") && showPopup(e.target));
    grid.addEventListener("focusout", hidePopup);
    window.addEventListener("scroll", hidePopup, true);
  }

  // event
  grid.addEventListener("click", (e) => {
    const cell = e.target.closest(".jr-day");
    if (cell) openEditor(cell.dataset.date);
  });

  $("jr-list").addEventListener("click", (e) => {
    const row = e.target.closest(".jr-row");
    if (row) openEditor(row.dataset.date);
  });

  $("jr-new").addEventListener("click", () => openEditor(today));
  $("jr-back").addEventListener("click", showSummary);
  $("jr-more").addEventListener("click", () => {
    showAll = !showAll;
    renderSummary();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !editor.hidden) showSummary();
  });

  document.querySelectorAll(".jr-tool").forEach((btn) => {
    // mousedown dicegah supaya teks yang diblok nggak kehilangan seleksi
    btn.addEventListener("mousedown", (e) => e.preventDefault());
    btn.addEventListener("click", () => {
      body.focus();
      document.execCommand(btn.dataset.cmd, false, btn.dataset.arg || null);
    });
  });

  document.querySelectorAll(".jr-seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => setVisibility(btn.dataset.vis));
  });

  saveBtn.addEventListener("click", save);
  deleteBtn.addEventListener("click", remove);

  renderSummary();
})();
