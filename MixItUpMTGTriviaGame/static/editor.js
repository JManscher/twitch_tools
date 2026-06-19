"use strict";

const LETTERS = ["A", "B", "C", "D"];
const INFO_REGIONS = ["rarity", "price"];

let META = { difficulties: ["Easy", "Medium", "Difficult"], hide_regions: [] };
let MODEL = [];
let selected = -1;
let dirty = false;

// Library state
let LISTS = [];
let currentSlug = null;   // the list being edited
let activeSlug = null;    // the list published to questions.json
let activeUnpublished = false;

const cardCache = new Map();     // `${name}|${set}` -> /api/card result
const printingsCache = new Map(); // name -> /api/printings result

const el = {
  status: document.getElementById("status"),
  save: document.getElementById("save-btn"),
  add: document.getElementById("add-btn"),
  count: document.getElementById("count"),
  list: document.getElementById("question-list"),
  empty: document.getElementById("empty-state"),
  form: document.getElementById("editor-form"),
  banner: document.getElementById("banner"),
  listSelect: document.getElementById("list-select"),
  activeTag: document.getElementById("active-tag"),
  unpublished: document.getElementById("unpublished"),
  publish: document.getElementById("publish-btn"),
  newList: document.getElementById("new-btn"),
  rename: document.getElementById("rename-btn"),
  delList: document.getElementById("del-list-btn"),
};

// ---------- helpers ----------
function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function imageRegions() { return META.hide_regions.filter((r) => !INFO_REGIONS.includes(r)); }
function infoRegions() { return META.hide_regions.filter((r) => INFO_REGIONS.includes(r)); }
function diffClass(d) {
  const l = (d || "").toLowerCase();
  return ["easy", "medium", "difficult"].includes(l) ? l : "unknown";
}
function setDirty(v) {
  dirty = v;
  el.save.disabled = !v;
  el.status.textContent = v ? "Unsaved changes" : "";
  el.status.className = "status" + (v ? " dirty" : "");
}
function showBanner(msg, ok) {
  el.banner.textContent = msg;
  el.banner.className = "banner" + (ok ? " ok" : "");
  el.banner.hidden = false;
}
function hideBanner() { el.banner.hidden = true; }

function uniqueId() {
  let max = 0;
  for (const q of MODEL) {
    const m = /^q-0*(\d+)$/.exec(q.id || "");
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return "q-" + String(max + 1).padStart(3, "0");
}
function blankQuestion() {
  const diff = META.difficulties.includes("Easy") ? "Easy" : (META.difficulties[0] || "Easy");
  return {
    id: uniqueId(),
    difficulty: diff,
    question: "",
    question_image: null,
    options: [0, 1, 2, 3].map(() => ({ text: "", card: null, set: null, hide: [] })),
    correct: 0,
    explanation: null,
  };
}

// ---------- debounce ----------
function debounce(fn, ms) {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ---------- sidebar ----------
function renderList() {
  el.count.textContent = `${MODEL.length} question${MODEL.length === 1 ? "" : "s"}`;
  el.list.innerHTML = "";
  MODEL.forEach((q, i) => {
    const li = document.createElement("li");
    li.className = "q-item" + (i === selected ? " active" : "");
    li.innerHTML = `
      <span class="q-badge ${diffClass(q.difficulty)}">${escapeHtml((q.difficulty || "?")[0])}</span>
      <span class="q-text">${escapeHtml(q.question) || "<em>(empty)</em>"}</span>
      <span class="q-id">${escapeHtml(q.id)}</span>`;
    li.addEventListener("click", () => selectQuestion(i));
    el.list.appendChild(li);
  });
}

function selectQuestion(i) {
  selected = i;
  renderList();
  renderForm();
}

// ---------- card editor (shared by question image + options) ----------
function buildHideGroup(holder, regions, label) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  wrap.innerHTML = `<span class="group-label">${escapeHtml(label)}</span>`;
  const grid = document.createElement("div");
  grid.className = "hide-grid";
  regions.forEach((r) => {
    const id = `hide-${Math.random().toString(36).slice(2)}`;
    const lab = document.createElement("label");
    lab.htmlFor = id;
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.checked = (holder.hide || []).includes(r);
    cb.addEventListener("change", () => {
      holder.hide = holder.hide || [];
      if (cb.checked) { if (!holder.hide.includes(r)) holder.hide.push(r); }
      else { holder.hide = holder.hide.filter((x) => x !== r); }
      setDirty(true);
    });
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(" " + r));
    grid.appendChild(lab);
  });
  wrap.appendChild(grid);
  return wrap;
}

// Returns a DOM element managing one card holder ({card,set,hide,[alt_text]}).
function buildCardEditor(holder, opts) {
  opts = opts || {};
  const block = document.createElement("div");
  block.className = "card-block";

  const preview = document.createElement("div");
  preview.className = "preview";
  preview.textContent = "No card";

  const fields = document.createElement("div");
  fields.className = "card-fields";

  // Card name
  const nameField = document.createElement("div");
  nameField.className = "field";
  nameField.innerHTML = `<label>Card name</label>`;
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.placeholder = "e.g. Lightning Bolt";
  nameInput.value = holder.card || "";
  nameField.appendChild(nameInput);

  // Printing picker
  const printField = document.createElement("div");
  printField.className = "field";
  printField.innerHTML = `<label>Printing</label>`;
  const printSelect = document.createElement("select");
  printSelect.innerHTML = `<option value="">Default (Scryfall's pick)</option>`;
  printField.appendChild(printSelect);
  const printHint = document.createElement("span");
  printHint.className = "hint";
  printField.appendChild(printHint);

  fields.appendChild(nameField);
  fields.appendChild(printField);

  // Alt text (question image only)
  let altInput = null;
  if (opts.showAlt) {
    const altField = document.createElement("div");
    altField.className = "field";
    altField.innerHTML = `<label>Caption / alt text (optional)</label>`;
    altInput = document.createElement("input");
    altInput.type = "text";
    altInput.value = holder.alt_text || "";
    altInput.addEventListener("input", () => { holder.alt_text = altInput.value; setDirty(true); });
    altField.appendChild(altInput);
    fields.appendChild(altField);
  }

  // Hide groups
  fields.appendChild(buildHideGroup(holder, imageRegions(), "Hide on the card image"));
  if (opts.showInfoHide) {
    fields.appendChild(buildHideGroup(holder, infoRegions(), "Hide as a quiz chip (reveals on answer)"));
  }

  block.appendChild(preview);
  block.appendChild(fields);

  function renderPreview(info) {
    if (!info || !info.ok) {
      preview.innerHTML = `<span>${info && info.error ? "Not found" : "No card"}</span>`;
      return;
    }
    const meta = [];
    if (info.rarity) meta.push(`<span class="rar">${escapeHtml(info.rarity)}</span>`);
    if (info.price_usd) meta.push(`$${escapeHtml(info.price_usd)}`);
    preview.innerHTML =
      (info.image_url ? `<img src="${escapeHtml(info.image_url)}" alt="" />` : `<span>${escapeHtml(info.name || "")}</span>`) +
      `<div class="preview-meta">${escapeHtml(info.name || "")}<br>${meta.join(" · ")}</div>`;
  }

  async function fetchCard() {
    const name = (holder.card || "").trim();
    if (!name) { preview.innerHTML = `<span>No card</span>`; return; }
    const setq = holder.set || "";
    const key = `${name}|${setq}`;
    if (cardCache.has(key)) { renderPreview(cardCache.get(key)); return; }
    preview.innerHTML = `<span>Loading…</span>`;
    try {
      const url = `/api/card?name=${encodeURIComponent(name)}` + (setq ? `&set=${encodeURIComponent(setq)}` : "");
      const info = await (await fetch(url)).json();
      cardCache.set(key, info);
      renderPreview(info);
    } catch (e) { preview.innerHTML = `<span>Preview failed</span>`; }
  }

  async function fetchPrintings() {
    const name = (holder.card || "").trim();
    printSelect.length = 1; // keep Default
    printHint.textContent = "";
    if (!name) return;
    printHint.textContent = "Loading printings…";
    let data;
    try {
      if (printingsCache.has(name.toLowerCase())) { data = printingsCache.get(name.toLowerCase()); }
      else {
        data = await (await fetch(`/api/printings?name=${encodeURIComponent(name)}`)).json();
        printingsCache.set(name.toLowerCase(), data);
      }
    } catch (e) { printHint.textContent = "Couldn't load printings"; return; }
    if (!data.ok) { printHint.textContent = data.error ? "No printings found" : ""; return; }
    printHint.textContent = `${data.printings.length} printing(s)`;
    let found = false;
    data.printings.forEach((p) => {
      if (!p.set) return;
      const o = document.createElement("option");
      o.value = p.set;
      const year = (p.released || "").slice(0, 4);
      o.textContent = `${p.set_name || p.set} · ${year} · ${p.rarity || ""}`.replace(/ · $/, "");
      if (holder.set && holder.set === p.set) { o.selected = true; found = true; }
      printSelect.appendChild(o);
    });
    // If the saved set isn't in the list, add it so the selection shows.
    if (holder.set && !found) {
      const o = document.createElement("option");
      o.value = holder.set;
      o.textContent = `${holder.set} (pinned)`;
      o.selected = true;
      printSelect.appendChild(o);
    }
  }

  const onName = debounce(() => { fetchCard(); fetchPrintings(); }, 400);
  nameInput.addEventListener("input", () => {
    holder.card = nameInput.value.trim() || "";
    setDirty(true);
    onName();
  });
  printSelect.addEventListener("change", () => {
    holder.set = printSelect.value || null;
    setDirty(true);
    fetchCard();
  });

  // Initial load
  if (holder.card) { fetchCard(); fetchPrintings(); }
  return block;
}

// ---------- main form ----------
function renderForm() {
  const q = MODEL[selected];
  if (!q) { el.form.hidden = true; el.empty.hidden = false; return; }
  el.empty.hidden = true;
  el.form.hidden = false;
  el.form.innerHTML = "";

  // Header: id + difficulty + delete/reorder
  const head = document.createElement("div");
  head.className = "form-row-head";
  head.innerHTML = `<span class="group-label">Editing ${escapeHtml(q.id)}</span>`;
  const headBtns = document.createElement("div");
  headBtns.className = "row";
  headBtns.style.flex = "0";
  const upBtn = document.createElement("button");
  upBtn.type = "button"; upBtn.className = "btn btn-ghost"; upBtn.textContent = "↑";
  upBtn.addEventListener("click", () => moveQuestion(-1));
  const downBtn = document.createElement("button");
  downBtn.type = "button"; downBtn.className = "btn btn-ghost"; downBtn.textContent = "↓";
  downBtn.addEventListener("click", () => moveQuestion(1));
  const delBtn = document.createElement("button");
  delBtn.type = "button"; delBtn.className = "btn btn-danger"; delBtn.textContent = "🗑 Delete";
  delBtn.addEventListener("click", deleteQuestion);
  headBtns.append(upBtn, downBtn, delBtn);
  head.appendChild(headBtns);
  el.form.appendChild(head);

  // Difficulty
  const diffField = document.createElement("div");
  diffField.className = "field";
  diffField.innerHTML = `<label>Difficulty</label>`;
  const diffSel = document.createElement("select");
  META.difficulties.forEach((d) => {
    const o = document.createElement("option");
    o.value = d; o.textContent = d; o.selected = d === q.difficulty;
    diffSel.appendChild(o);
  });
  diffSel.addEventListener("change", () => { q.difficulty = diffSel.value; setDirty(true); renderList(); });
  diffField.appendChild(diffSel);
  el.form.appendChild(diffField);

  // Question text
  const qField = document.createElement("div");
  qField.className = "field";
  qField.innerHTML = `<label>Question</label>`;
  const qInput = document.createElement("textarea");
  qInput.value = q.question || "";
  qInput.placeholder = "What is the question?";
  qInput.addEventListener("input", () => { q.question = qInput.value; setDirty(true); renderList(); });
  qField.appendChild(qInput);
  el.form.appendChild(qField);

  // Question image (optional toggle)
  const imgField = document.createElement("div");
  imgField.className = "field";
  const toggleLine = document.createElement("label");
  toggleLine.className = "toggle-line group-label";
  const toggle = document.createElement("input");
  toggle.type = "checkbox";
  toggle.checked = !!q.question_image;
  toggleLine.appendChild(toggle);
  toggleLine.appendChild(document.createTextNode(" Show a card alongside the question"));
  imgField.appendChild(toggleLine);
  const imgHolder = document.createElement("div");
  imgField.appendChild(imgHolder);
  function renderImgEditor() {
    imgHolder.innerHTML = "";
    if (q.question_image) {
      imgHolder.appendChild(buildCardEditor(q.question_image, { showAlt: true, showInfoHide: true }));
    }
  }
  toggle.addEventListener("change", () => {
    q.question_image = toggle.checked ? { card: "", set: null, alt_text: "", hide: [] } : null;
    setDirty(true);
    renderImgEditor();
  });
  renderImgEditor();
  el.form.appendChild(imgField);

  // Options
  const optsLabel = document.createElement("div");
  optsLabel.className = "group-label";
  optsLabel.textContent = "Answers (pick the correct one)";
  el.form.appendChild(optsLabel);

  q.options.forEach((opt, i) => {
    const block = document.createElement("div");
    block.className = "option-block" + (q.correct === i ? " correct" : "");

    const oh = document.createElement("div");
    oh.className = "option-head";
    const letter = document.createElement("span");
    letter.className = "option-letter";
    letter.textContent = LETTERS[i];
    const correctLab = document.createElement("label");
    correctLab.className = "correct-toggle";
    const radio = document.createElement("input");
    radio.type = "radio"; radio.name = "correct"; radio.checked = q.correct === i;
    radio.addEventListener("change", () => {
      q.correct = i; setDirty(true);
      el.form.querySelectorAll(".option-block").forEach((b, bi) => b.classList.toggle("correct", bi === i));
    });
    correctLab.appendChild(radio);
    correctLab.appendChild(document.createTextNode(" Correct"));
    oh.append(letter, correctLab);
    block.appendChild(oh);

    const textField = document.createElement("div");
    textField.className = "field";
    textField.innerHTML = `<label>Answer text</label>`;
    const textInput = document.createElement("input");
    textInput.type = "text";
    textInput.value = opt.text || "";
    textInput.addEventListener("input", () => { opt.text = textInput.value; setDirty(true); });
    textField.appendChild(textInput);
    block.appendChild(textField);

    const details = document.createElement("details");
    details.className = "card-toggle";
    if (opt.card) details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = "Card image for this answer (optional)";
    details.appendChild(summary);
    details.appendChild(buildCardEditor(opt, { showAlt: false, showInfoHide: false }));
    block.appendChild(details);

    el.form.appendChild(block);
  });

  // Explanation
  const expField = document.createElement("div");
  expField.className = "field";
  expField.innerHTML = `<label>Explanation (shown on reveal, optional)</label>`;
  const expInput = document.createElement("textarea");
  expInput.value = q.explanation || "";
  expInput.addEventListener("input", () => { q.explanation = expInput.value; setDirty(true); });
  expField.appendChild(expInput);
  el.form.appendChild(expField);
}

// ---------- CRUD actions ----------
function addQuestion() {
  MODEL.push(blankQuestion());
  setDirty(true);
  selectQuestion(MODEL.length - 1);
}
function deleteQuestion() {
  const q = MODEL[selected];
  if (!q) return;
  if (!confirm(`Delete ${q.id}? This can't be undone until you reload without saving.`)) return;
  MODEL.splice(selected, 1);
  setDirty(true);
  if (MODEL.length === 0) { selected = -1; renderList(); renderForm(); return; }
  selected = Math.min(selected, MODEL.length - 1);
  selectQuestion(selected);
}
function moveQuestion(dir) {
  const j = selected + dir;
  if (j < 0 || j >= MODEL.length) return;
  [MODEL[selected], MODEL[j]] = [MODEL[j], MODEL[selected]];
  selected = j;
  setDirty(true);
  renderList();
  renderForm();
}

// ---------- save ----------
function serialize() {
  return MODEL.map((q) => {
    const out = {
      id: q.id,
      difficulty: q.difficulty,
      question: (q.question || "").trim(),
      correct: q.correct,
    };
    const exp = (q.explanation || "").trim();
    out.explanation = exp || null;
    if (q.question_image && (q.question_image.card || "").trim()) {
      out.question_image = {
        card: q.question_image.card.trim(),
        set: q.question_image.set || null,
        alt_text: (q.question_image.alt_text || "").trim() || null,
        hide: q.question_image.hide || [],
      };
    } else {
      out.question_image = null;
    }
    out.options = q.options.map((o) => ({
      text: (o.text || "").trim(),
      card: (o.card || "").trim() || null,
      set: (o.card || "").trim() ? (o.set || null) : null,
      hide: (o.card || "").trim() ? (o.hide || []) : [],
    }));
    return out;
  });
}

function currentName() {
  const l = LISTS.find((x) => x.slug === currentSlug);
  return l ? l.name : currentSlug;
}

async function save() {
  if (!currentSlug) return;
  hideBanner();
  el.save.disabled = true;
  el.status.textContent = "Saving…";
  try {
    const resp = await fetch(`/api/lists/${encodeURIComponent(currentSlug)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions: serialize(), name: currentName() }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      showBanner("Could not save: " + (data.error || `HTTP ${resp.status}`), false);
      setDirty(true);
      return;
    }
    setDirty(false);
    await loadLists();
    const live = currentSlug === activeSlug;
    showBanner(
      `Saved “${currentName()}” ✓ (${data.count} questions).` +
      (live ? " Click 📢 Publish to push it to the live stream." : " Publish it when you're ready to use it live."),
      true
    );
  } catch (e) {
    showBanner("Could not save: " + e, false);
    setDirty(true);
  }
}

async function publish() {
  if (!currentSlug) return;
  if (dirty && !confirm("You have unsaved edits. Publish the last saved version anyway?")) return;
  try {
    const resp = await fetch(`/api/lists/${encodeURIComponent(currentSlug)}/activate`, { method: "POST" });
    const data = await resp.json();
    if (!resp.ok || !data.ok) { showBanner("Could not publish: " + (data.error || resp.status), false); return; }
    await loadLists();
    showBanner(`📢 Published “${currentName()}” to questions.json. Restart the trivia server to apply.`, true);
  } catch (e) { showBanner("Could not publish: " + e, false); }
}

async function newList() {
  if (!confirmDiscard()) return;
  const name = prompt("Name for the new list:");
  if (!name) return;
  const dup = confirm("OK = start from a copy of the current list.\nCancel = start with one blank question.");
  try {
    const resp = await fetch("/api/lists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, copy_from: dup ? currentSlug : null }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) { showBanner("Could not create list: " + (data.error || resp.status), false); return; }
    await loadLists();
    await loadList(data.slug);
    showBanner(`Created “${data.name}”. Edit it, then 📢 Publish to use it live.`, true);
  } catch (e) { showBanner("Could not create list: " + e, false); }
}

async function renameList() {
  if (!currentSlug) return;
  const name = prompt("Rename this list:", currentName());
  if (!name || name === currentName()) return;
  try {
    const resp = await fetch(`/api/lists/${encodeURIComponent(currentSlug)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) { showBanner("Could not rename: " + (data.error || resp.status), false); return; }
    await loadLists();
  } catch (e) { showBanner("Could not rename: " + e, false); }
}

async function deleteList() {
  if (!currentSlug) return;
  if (!confirm(`Delete the list “${currentName()}”? This removes its master file.`)) return;
  try {
    const resp = await fetch(`/api/lists/${encodeURIComponent(currentSlug)}`, { method: "DELETE" });
    const data = await resp.json();
    if (!resp.ok || !data.ok) { showBanner("Could not delete: " + (data.error || resp.status), false); return; }
    currentSlug = null;
    await loadLists();
    await loadList(activeSlug || (LISTS[0] && LISTS[0].slug));
    showBanner("List deleted.", true);
  } catch (e) { showBanner("Could not delete: " + e, false); }
}

function confirmDiscard() {
  return !dirty || confirm("You have unsaved changes. Discard them?");
}

function renderListBar() {
  el.listSelect.innerHTML = "";
  LISTS.forEach((l) => {
    const o = document.createElement("option");
    o.value = l.slug;
    o.textContent = l.name + (l.is_active ? "  ★ live" : "");
    o.selected = l.slug === currentSlug;
    el.listSelect.appendChild(o);
  });
  const isActive = currentSlug === activeSlug;
  el.activeTag.textContent = isActive ? "★ Live (questions.json)" : "Not live";
  el.activeTag.className = "active-tag" + (isActive ? "" : " inactive");
  el.publish.textContent = isActive ? "📢 Re-publish to stream" : "📢 Publish (make live)";
  el.unpublished.hidden = !(isActive && activeUnpublished);
}

// ---------- init / loading ----------
async function loadMeta() {
  try {
    const m = await (await fetch("/api/meta")).json();
    if (m.difficulties && m.difficulties.length) META.difficulties = m.difficulties;
    if (m.hide_regions) META.hide_regions = m.hide_regions;
  } catch (e) { /* keep defaults */ }
}

async function loadLists() {
  const data = await (await fetch("/api/lists")).json();
  LISTS = data.lists || [];
  activeSlug = data.active || null;
  activeUnpublished = !!data.active_unpublished;
  if (!currentSlug || !LISTS.some((l) => l.slug === currentSlug)) {
    currentSlug = activeSlug || (LISTS[0] && LISTS[0].slug) || null;
  }
  renderListBar();
}

async function loadList(slug) {
  if (!slug) { MODEL = []; selected = -1; renderList(); renderForm(); return; }
  currentSlug = slug;
  const data = await (await fetch(`/api/lists/${encodeURIComponent(slug)}`)).json();
  MODEL = data.questions || [];
  selected = MODEL.length ? 0 : -1;
  setDirty(false);
  renderListBar();
  renderList();
  renderForm();
}

el.save.addEventListener("click", save);
el.add.addEventListener("click", addQuestion);
el.publish.addEventListener("click", publish);
el.newList.addEventListener("click", newList);
el.rename.addEventListener("click", renameList);
el.delList.addEventListener("click", deleteList);
el.listSelect.addEventListener("change", () => {
  const slug = el.listSelect.value;
  if (slug === currentSlug) return;
  if (!confirmDiscard()) { el.listSelect.value = currentSlug; return; }
  hideBanner();
  loadList(slug);
});
window.addEventListener("beforeunload", (e) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });

(async function init() {
  await loadMeta();
  await loadLists();
  await loadList(currentSlug);
})();
