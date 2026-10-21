const state = {
  sites: [],
  mode: "title",
  lastInfer: null,
  editingId: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    data = null;
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `خطای ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

let toastTimer = null;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("err", isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3800);
}

function formatSize(bytes) {
  if (!bytes || bytes < 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

/* ------------------------------------------------------------------ tabs */
function showTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${name}`));
  if (name === "history") loadHistory();
}

$$(".tab").forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));

/* ----------------------------------------------------------------- sites */
async function loadSites() {
  try {
    const data = await api("/api/sites");
    state.sites = data.sites || [];
  } catch (err) {
    toast(err.message, true);
    state.sites = [];
  }
  renderChips();
  renderSiteList();
}

function renderChips() {
  const box = $("#site-chips");
  if (!state.sites.length) {
    box.innerHTML = '<span class="muted small">هنوز سایتی اضافه نشده — از تب «سایت‌ها» شروع کن.</span>';
    return;
  }
  box.innerHTML = state.sites
    .map(
      (s) => `
      <label class="chip on" data-id="${escapeHtml(s.id)}">
        <input type="checkbox" checked value="${escapeHtml(s.id)}" />
        ${escapeHtml(s.name || s.id)}
      </label>`
    )
    .join("");
  box.querySelectorAll(".chip input").forEach((input) => {
    input.addEventListener("change", () => {
      input.closest(".chip").classList.toggle("on", input.checked);
    });
  });
}

function selectedSiteIds() {
  return $$("#site-chips input:checked").map((i) => i.value);
}

function renderSiteList() {
  const box = $("#site-list");
  if (!state.sites.length) {
    box.innerHTML = '<div class="empty">سایتی ثبت نشده است.</div>';
    return;
  }
  box.innerHTML = state.sites
    .map(
      (s) => `
      <div class="site-item" data-id="${escapeHtml(s.id)}">
        <div class="meta">
          <strong>${escapeHtml(s.name || s.id)} ${s.enabled ? "" : '<span class="badge warn">غیرفعال</span>'}</strong>
          <small>${escapeHtml(s.search_url)}</small>
          <small>نتیجه: <code>${escapeHtml(s.result_selector || "—")}</code> · دانلود: <code>${escapeHtml(s.download_selector || "خودکار")}</code> · ${s.download_on === "result" ? "صفحهٔ نتایج" : "صفحهٔ آهنگ"}</small>
        </div>
        <div class="actions">
          <button class="ghost small" data-act="test">تست</button>
          <button class="ghost small" data-act="edit">ویرایش</button>
          <button class="ghost small danger" data-act="delete">حذف</button>
        </div>
      </div>`
    )
    .join("");

  box.querySelectorAll(".site-item").forEach((row) => {
    const id = row.dataset.id;
    const site = state.sites.find((s) => s.id === id);
    row.querySelector('[data-act="edit"]').addEventListener("click", () => fillForm(site));
    row.querySelector('[data-act="delete"]').addEventListener("click", () => deleteSite(id));
    row.querySelector('[data-act="test"]').addEventListener("click", () => testSite(site));
  });
}

function fillForm(site) {
  const form = $("#site-form");
  state.editingId = site.id;
  form.id.value = site.id;
  form.name.value = site.name || "";
  form.base.value = site.base || "";
  form.search_url.value = site.search_url || "";
  form.result_selector.value = site.result_selector || "";
  form.title_selector.value = site.title_selector || "";
  form.artist_selector.value = site.artist_selector || "";
  form.detail_link_selector.value = site.detail_link_selector || "";
  form.download_selector.value = site.download_selector || "";
  form.download_on.value = site.download_on || "detail";
  form.charset.value = site.charset || "";
  form.render.value = site.render || "http";
  form.enabled.checked = site.enabled !== false;
  $("#form-title").textContent = `ویرایش سایت: ${site.name || site.id}`;
  form.scrollIntoView({ behavior: "smooth", block: "center" });
}

function resetForm() {
  const form = $("#site-form");
  form.reset();
  form.enabled.checked = true;
  form.download_on.value = "detail";
  form.render.value = "http";
  state.editingId = null;
  $("#form-title").textContent = "افزودن سایت";
}

$("#form-reset").addEventListener("click", resetForm);

$("#site-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {
    id: form.id.value.trim(),
    name: form.name.value.trim(),
    base: form.base.value.trim(),
    search_url: form.search_url.value.trim(),
    result_selector: form.result_selector.value.trim(),
    title_selector: form.title_selector.value.trim(),
    artist_selector: form.artist_selector.value.trim(),
    detail_link_selector: form.detail_link_selector.value.trim(),
    download_selector: form.download_selector.value.trim(),
    download_on: form.download_on.value,
    charset: form.charset.value.trim(),
    render: form.render.value,
    enabled: form.enabled.checked,
    notes: "",
  };
  try {
    await api("/api/sites", { method: "POST", body: JSON.stringify(payload) });
    toast("سایت ذخیره شد");
    resetForm();
    await loadSites();
  } catch (err) {
    toast(err.message, true);
  }
});

async function deleteSite(id) {
  if (!confirm(`سایت «${id}» حذف شود؟`)) return;
  try {
    await api(`/api/sites/${encodeURIComponent(id)}`, { method: "DELETE" });
    toast("حذف شد");
    if (state.editingId === id) resetForm();
    await loadSites();
  } catch (err) {
    toast(err.message, true);
  }
}

async function testSite(site) {
  const query = prompt(`عبارت تست برای «${site.name || site.id}»:`, "hello");
  if (!query) return;
  toast("در حال تست…");
  try {
    const data = await api(`/api/sites/${encodeURIComponent(site.id)}/test`, {
      method: "POST",
      body: JSON.stringify({ query, verify: false }),
    });
    if (data.error) throw new Error(data.error);
    renderResults(data.results || [], { query, guesses: [], searched_queries: [query] });
    showTab("search");
    toast(`${(data.results || []).length} نتیجه از این سایت`);
  } catch (err) {
    toast(err.message, true);
  }
}

/* ----------------------------------------------------------------- infer */
$("#infer-btn").addEventListener("click", async () => {
  const searchUrl = $("#infer-search-url").value.trim();
  const detailUrl = $("#infer-detail-url").value.trim();
  const hint = $("#infer-query-hint").value.trim();
  if (!searchUrl) {
    toast("آدرس صفحهٔ نتایج را وارد کن", true);
    return;
  }
  const btn = $("#infer-btn");
  btn.disabled = true;
  btn.textContent = "در حال بررسی…";
  try {
    const data = await api("/api/sites/infer", {
      method: "POST",
      body: JSON.stringify({ search_url: searchUrl, detail_url: detailUrl, query_hint: hint }),
    });
    state.lastInfer = data;
    $("#infer-apply").classList.remove("hidden");
    renderInfer(data);
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "استنباط سلکتورها";
  }
});

function renderInfer(data) {
  const notes = data.notes || [];
  $("#infer-notes").innerHTML = notes.map((n) => `<div>⚠ ${escapeHtml(n)}</div>`).join("");

  const preview = data.preview || [];
  const downloads = data.download_candidates || [];
  let html = "";
  if (preview.length) {
    html += `<div>نمونهٔ نتایج استخراج‌شده (${preview.length}):</div><ol>`;
    html += preview
      .slice(0, 5)
      .map((p) => `<li>${escapeHtml(p.title)}</li>`)
      .join("");
    html += "</ol>";
  }
  if (downloads.length) {
    html += `<div style="margin-top:.5rem">لینک‌های دانلود پیدا‌شده در صفحهٔ نمونه (${downloads.length}):</div><ol>`;
    html += downloads
      .slice(0, 4)
      .map((d) => `<li>${escapeHtml(d.label || "لینک")} — ${escapeHtml(d.url)}</li>`)
      .join("");
    html += "</ol>";
  }
  $("#infer-preview").innerHTML = html;
}

$("#infer-apply").addEventListener("click", () => {
  const data = state.lastInfer;
  if (!data) return;
  const form = $("#site-form");
  form.search_url.value = data.search_url || form.search_url.value;
  form.base.value = data.base || form.base.value;
  form.result_selector.value = data.result_selector || form.result_selector.value;
  form.title_selector.value = data.title_selector || form.title_selector.value;
  form.artist_selector.value = data.artist_selector || form.artist_selector.value;
  form.detail_link_selector.value = data.detail_link_selector || form.detail_link_selector.value;
  form.download_selector.value = data.download_selector || form.download_selector.value;
  form.download_on.value = data.download_on || "detail";

  if (!form.id.value) {
    let host = "";
    try {
      host = new URL(data.base || data.search_url).hostname;
    } catch (_) {
      host = "mysite";
    }
    form.id.value = host.replace(/^www\./, "").replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "mysite";
  }
  if (!form.name.value) {
    form.name.value = form.id.value;
  }
  toast("سلکتورها روی فرم اعمال شد — یک بار تست کن");
  form.scrollIntoView({ behavior: "smooth", block: "center" });
});

/* ---------------------------------------------------------------- search */
$$(".mode").forEach((btn) =>
  btn.addEventListener("click", () => {
    state.mode = btn.dataset.mode;
    $$(".mode").forEach((b) => b.classList.toggle("active", b === btn));
    $("#query").placeholder =
      state.mode === "lyrics" ? "بخشی از متن آهنگ را بنویس…" : "اسم آهنگ را بنویس…";
  })
);

$("#search-btn").addEventListener("click", runSearch);
$("#query").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    runSearch();
  }
});

async function runSearch() {
  const query = $("#query").value.trim();
  if (!query) {
    toast("عبارت جست‌وجو خالی است", true);
    return;
  }
  const siteIds = selectedSiteIds();
  if (!siteIds.length) {
    toast("حداقل یک سایت انتخاب کن", true);
    return;
  }
  const btn = $("#search-btn");
  btn.disabled = true;
  btn.textContent = "در حال جست‌وجو…";
  $("#results").innerHTML = '<div class="loading">در حال جست‌وجو در سایت‌ها…</div>';
  $("#empty-state").classList.add("hidden");
  $("#guess-banner").classList.add("hidden");
  $("#search-errors").classList.add("hidden");

  try {
    const data = await api("/api/search", {
      method: "POST",
      body: JSON.stringify({
        query,
        mode: state.mode,
        site_ids: siteIds,
        verify: $("#verify").checked,
        limit_per_site: 4,
      }),
    });
    renderResults(data.results || [], data);
  } catch (err) {
    $("#results").innerHTML = "";
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "جست‌وجو";
  }
}

function renderResults(results, payload = {}) {
  const guesses = payload.guesses || [];
  if (guesses.length) {
    const text = guesses
      .slice(0, 3)
      .map(
        (g) =>
          `<strong>${escapeHtml(g.artist)} — ${escapeHtml(g.title)}</strong> (تطابق متن ${Math.round((g.lyrics_match || 0) * 100)}٪)`
      )
      .join(" · ");
    $("#guess-banner").innerHTML = `از روی متن حدس زدم: ${text}`;
    $("#guess-banner").classList.remove("hidden");
  }

  const errors = payload.errors || [];
  if (errors.length) {
    $("#search-errors").innerHTML = errors
      .map((e) => `⚠ ${escapeHtml(e.site_id)}: ${escapeHtml(e.message)}`)
      .join("<br />");
    $("#search-errors").classList.remove("hidden");
  }

  const box = $("#results");
  if (!results.length) {
    box.innerHTML = "";
    $("#empty-state").textContent = "نتیجه‌ای پیدا نشد. سلکتورهای سایت را با دکمهٔ «تست» بررسی کن.";
    $("#empty-state").classList.remove("hidden");
    return;
  }
  $("#empty-state").classList.add("hidden");
  box.innerHTML = results.map(renderCard).join("");
  box.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        toast("لینک کپی شد");
      } catch (_) {
        toast("کپی نشد؛ دستی انتخاب کن", true);
      }
    });
  });
  box.querySelectorAll("[data-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.toggle);
      if (target) target.classList.toggle("hidden");
    });
  });
}

function renderCard(item, index) {
  const score = Math.round((item.score || 0) * 100);
  const verified = item.verified || null;
  const kind = item.link_kind === "direct" ? "لینک مستقیم" : item.link_kind === "page" ? "صفحهٔ واسط" : "";
  const kindClass = item.link_kind === "direct" ? "ok" : item.link_kind === "page" ? "warn" : "";

  const metaBadges = [];
  if (kind) metaBadges.push(`<span class="badge ${kindClass}">${kind}</span>`);
  if (verified && verified.ok) {
    metaBadges.push('<span class="badge ok">لینک پاسخ می‌دهد</span>');
    if (verified.content_type) metaBadges.push(`<span class="badge">${escapeHtml(verified.content_type)}</span>`);
    if (verified.size) metaBadges.push(`<span class="badge">${formatSize(verified.size)}</span>`);
  } else if (verified && !verified.ok) {
    metaBadges.push('<span class="badge warn">بررسی لینک ناموفق</span>');
  }

  const candidates = item.candidates || [];
  const candidateId = `cand-${index}-${Math.random().toString(36).slice(2, 8)}`;
  const candidatesHtml = candidates.length > 1
    ? `<button class="ghost small" data-toggle="${candidateId}">${candidates.length} لینک دیگر</button>
       <ul id="${candidateId}" class="candidates hidden">
         ${candidates.map((c) => `<li><a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.label || c.url)}</a> (${c.kind === "direct" ? "مستقیم" : "صفحه"})</li>`).join("")}
       </ul>`
    : "";

  const downloadBtn = item.download_url
    ? `<a class="primary" style="padding:.5rem 1rem;border-radius:10px;display:inline-block" href="${escapeHtml(item.download_url)}" target="_blank" rel="noopener">باز کردن لینک دانلود</a>`
    : '<span class="badge warn">لینک دانلودی پیدا نشد</span>';

  const note = item.note ? `<div class="muted small">${escapeHtml(item.note)}</div>` : "";

  return `
    <article class="result">
      <div class="result-head">
        <div>
          <div class="result-title">${escapeHtml(item.title || "بدون عنوان")}</div>
          <div class="result-artist">${escapeHtml(item.artist || "")}</div>
          <div class="badges" style="margin-top:.35rem">
            <span class="badge info">${escapeHtml(item.site_name || item.site_id)}</span>
            ${metaBadges.join("")}
          </div>
        </div>
        <div class="score">
          <div class="score-bar"><i style="width:${score}%"></i></div>
          <span>${score}٪</span>
        </div>
      </div>
      <div class="actions">
        ${downloadBtn}
        ${item.download_url ? `<button class="ghost small" data-copy="${escapeHtml(item.download_url)}">کپی لینک</button>` : ""}
        ${item.detail_url ? `<a class="ghost small" style="text-decoration:none" href="${escapeHtml(item.detail_url)}" target="_blank" rel="noopener">صفحهٔ آهنگ</a>` : ""}
        ${candidatesHtml}
      </div>
      ${note}
    </article>`;
}

/* --------------------------------------------------------------- history */
async function loadHistory() {
  try {
    const data = await api("/api/history");
    const rows = data.history || [];
    const box = $("#history-list");
    if (!rows.length) {
      box.innerHTML = '<div class="empty">تاریخچه خالی است.</div>';
      return;
    }
    box.innerHTML = rows
      .map(
        (h) => `
        <div class="history-item" data-query="${escapeHtml(h.query)}" data-mode="${escapeHtml(h.mode)}">
          <div>
            <strong>${escapeHtml(h.query)}</strong>
            <div class="muted small">${h.mode === "lyrics" ? "متن آهنگ" : "نام آهنگ"} · ${h.result_count} نتیجه</div>
          </div>
          <span class="muted small">${escapeHtml(h.created_at)}</span>
        </div>`
      )
      .join("");
    box.querySelectorAll(".history-item").forEach((row) => {
      row.addEventListener("click", () => {
        $("#query").value = row.dataset.query;
        const mode = row.dataset.mode;
        state.mode = mode;
        $$(".mode").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
        showTab("search");
        runSearch();
      });
    });
  } catch (err) {
    toast(err.message, true);
  }
}

$("#clear-history").addEventListener("click", async () => {
  if (!confirm("تاریخچه پاک شود؟")) return;
  await api("/api/history", { method: "DELETE" });
  loadHistory();
});

$("#clear-cache").addEventListener("click", async () => {
  await api("/api/cache/clear", { method: "POST" });
  toast("کش صفحات پاک شد");
});

/* ------------------------------------------------------- import / export */
function importMode() {
  const checked = document.querySelector('input[name="import-mode"]:checked');
  return checked ? checked.value : "merge";
}

$("#export-yaml").addEventListener("click", () => {
  window.location.href = "/api/sites/export?format=yaml";
});

$("#export-json").addEventListener("click", () => {
  window.location.href = "/api/sites/export?format=json";
});

$("#export-copy").addEventListener("click", async () => {
  try {
    const res = await fetch("/api/sites/export?format=yaml");
    const text = await res.text();
    await navigator.clipboard.writeText(text);
    toast("کانفیگ کپی شد");
  } catch (err) {
    toast("کپی نشد", true);
  }
});

$("#import-btn").addEventListener("click", async () => {
  const input = $("#import-file");
  if (!input.files || !input.files.length) {
    toast("اول یک فایل YAML/JSON انتخاب کن", true);
    return;
  }
  const file = input.files[0];
  const content = await file.text();
  const btn = $("#import-btn");
  btn.disabled = true;
  btn.textContent = "در حال ورود…";
  try {
    const data = await api("/api/sites/import", {
      method: "POST",
      body: JSON.stringify({ content, mode: importMode() }),
    });
    const skipped = (data.skipped || []).map((s) => escapeHtml(s)).join("<br />");
    $("#import-report").innerHTML =
      `<div>✔ ${data.imported} پروفایل وارد شد (${data.mode === "replace" ? "جایگزینی" : "افزودن"})؛ مجموع: ${data.total}</div>` +
      (skipped ? `<div style="margin-top:.4rem">رد شده:<br />${skipped}</div>` : "");
    toast(`${data.imported} پروفایل وارد شد`);
    input.value = "";
    await loadSites();
  } catch (err) {
    $("#import-report").innerHTML = `<div>✖ ${escapeHtml(err.message)}</div>`;
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "ورود از فایل";
  }
});

/* ------------------------------------------------------------------ init */
loadSites();
