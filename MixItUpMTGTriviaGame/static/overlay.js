"use strict";

const POLL_MS = 500;
const CHOICE_LETTERS = ["A", "B", "C", "D"];

const root = document.getElementById("root");

let lastState = null;
let lastRenderedKey = null;
let phaseEndsAtMs = 0;
let phaseLabel = "";
let phaseTotalMs = 0;
let countdownRunning = false;

function difficultyClass(d) {
  const allowed = ["easy", "medium", "difficult"];
  const lower = (d || "").toLowerCase();
  return allowed.includes(lower) ? lower : "unknown";
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function imagePath(p) {
  if (!p) return null;
  return "/static/" + p;
}

// Regions that censor a part of the card image. Other regions in the hide
// list (rarity, price) drive separate info chips.
const CARD_IMAGE_REGIONS = new Set(["name", "mana_cost", "art", "type", "text", "pt", "artist", "set", "collector"]);

// Hiding the rarity must also blank the card's own rarity tells: the set
// symbol (its colour encodes rarity) and the bottom collector line (which
// prints the rarity letter C/U/R/M). Otherwise the answer is on the card.
const RARITY_TELL_REGIONS = ["set", "collector"];

function imageRegionsFor(hide) {
  const regions = hide.filter((r) => CARD_IMAGE_REGIONS.has(r));
  if (hide.includes("rarity")) {
    for (const r of RARITY_TELL_REGIONS) {
      if (!regions.includes(r)) regions.push(r);
    }
  }
  return regions;
}

function renderCardFrame(imagePath_, hideRegions, variant, alt) {
  // variant: "thumb" for option chips, "side-card" for the big question card.
  const hide = Array.isArray(hideRegions) ? hideRegions : [];
  const url = imagePath(imagePath_);
  if (!url) return "";

  const imageCensors = imageRegionsFor(hide)
    .map((r) => `<div class="censor censor-${escapeHtml(r)}"></div>`)
    .join("");

  if (variant === "thumb") {
    return `<div class="thumb card-frame" style="background-image: url('${escapeHtml(url)}')">${imageCensors}</div>`;
  }

  // side-card: real <img> so the natural aspect ratio is preserved, with
  // absolutely-positioned censors over it.
  return `
    <div class="card-frame side-card">
      <img src="${escapeHtml(url)}" alt="${escapeHtml(alt || "")}" />
      ${imageCensors}
    </div>
  `;
}

function formatRarity(rarity) {
  if (!rarity) return "Unknown";
  if (rarity === "mythic") return "Mythic Rare";
  return rarity.charAt(0).toUpperCase() + rarity.slice(1);
}

function formatPrice(usd) {
  if (usd === null || usd === undefined || usd === "") return "Not tracked";
  const n = Number(usd);
  if (!isFinite(n)) return "Not tracked";
  return "$" + n.toFixed(2);
}

function renderInfoChips(hide, rarity, priceUsd, isReveal) {
  const wantRarity = hide.includes("rarity");
  const wantPrice = hide.includes("price");
  if (!wantRarity && !wantPrice) return "";

  const chips = [];
  if (wantRarity) {
    const value = isReveal ? formatRarity(rarity) : "?";
    const cls = isReveal ? "info-chip rarity" + (rarity ? " r-" + escapeHtml(rarity) : "") : "info-chip rarity censored";
    chips.push(`<div class="${cls}"><span class="info-icon">&#9733;</span><span class="info-value">${escapeHtml(value)}</span></div>`);
  }
  if (wantPrice) {
    const value = isReveal ? formatPrice(priceUsd) : "?";
    const cls = isReveal ? "info-chip price" : "info-chip price censored";
    chips.push(`<div class="${cls}"><span class="info-icon">$</span><span class="info-value">${escapeHtml(value)}</span></div>`);
  }
  return `<div class="card-info-chips">${chips.join("")}</div>`;
}

const RANK_MEDAL = { 1: "🥇", 2: "🥈", 3: "🥉" };

// The leaderboard shows one board at a time and rotates between these.
let scoreboardMode = "session";

function renderScoreRows(board, isReveal) {
  if (!board || !board.length) {
    return `<div class="score-empty">No points yet</div>`;
  }
  return board.map((e) => {
    const medal = RANK_MEDAL[e.rank] || ("#" + e.rank);
    const award = isReveal && e.awarded > 0
      ? `<span class="award">+${e.awarded}</span>`
      : "";
    return `
      <div class="score-row${e.rank === 1 ? " leader" : ""}">
        <span class="rank">${medal}</span>
        <span class="score-name">${escapeHtml(e.name)}</span>
        ${award}
        <span class="score-pts">${e.score}</span>
      </div>`;
  }).join("");
}

// Resolve which board to actually show: never flip to an empty board while the
// other has entries, so early on it parks on whichever is populated.
function resolveScoreboardMode(state, mode) {
  const session = state.scoreboard || [];
  const total = state.total_scoreboard || [];
  if (!session.length && !total.length) return "session";
  if (mode === "total" && !total.length) return "session";
  if (mode === "session" && !session.length) return "total";
  return mode;
}

function scoreboardBodyHtml(state, isReveal) {
  const mode = resolveScoreboardMode(state, scoreboardMode);
  const isSession = mode === "session";
  const board = isSession ? (state.scoreboard || []) : (state.total_scoreboard || []);
  const label = isSession ? "This Session" : "All-Time";
  const other = isSession ? "All-Time" : "This Session";
  return `
    <div class="score-section-label">
      <span class="active">${label}</span>
      <span class="next">${other} &rsaquo;</span>
    </div>
    ${renderScoreRows(board, isReveal)}`;
}

function renderScoreboard(state, isReveal) {
  if (!state.show_scoreboard) return "";
  return `
    <div class="scoreboard">
      <div class="scoreboard-title"><span class="trophy">🏆</span> Leaderboard</div>
      <div class="scoreboard-body fade">${scoreboardBodyHtml(state, isReveal)}</div>
    </div>`;
}

// Rotate the visible board in place, without a full re-render (keeps the
// countdown and tally stable). Driven by a self-scheduling timer so the
// interval can honour the server-configured rotation period.
function refreshScoreboardBody() {
  if (!lastState || !lastState.show_scoreboard) return;
  const bodyEl = document.querySelector(".scoreboard-body");
  if (!bodyEl) return;
  const isReveal = lastState.phase === "REVEAL";
  bodyEl.innerHTML = scoreboardBodyHtml(lastState, isReveal);
  // Re-trigger the fade animation.
  bodyEl.classList.remove("fade");
  void bodyEl.offsetWidth;
  bodyEl.classList.add("fade");
}

function scheduleScoreboardRotation() {
  const ms = (lastState && lastState.scoreboard_rotate_ms) || 6000;
  setTimeout(() => {
    scoreboardMode = scoreboardMode === "session" ? "total" : "session";
    refreshScoreboardBody();
    scheduleScoreboardRotation();
  }, ms);
}

function renderIdle() {
  root.innerHTML = `<div id="loading">Waiting for the first question...</div>`;
}

function renderState(state) {
  const q = state.question;
  if (!q) {
    renderIdle();
    return;
  }

  const isReveal = state.phase === "REVEAL";
  const tally = state.tally || {};
  const totalVotes = state.total_votes || 0;
  const correct = q.correct;
  const diffClass = difficultyClass(q.difficulty);

  const hasQImage = !!q.question_image;
  const hasSidebar = hasQImage || !!state.show_scoreboard;
  const panelClasses = ["panel"];
  if (hasSidebar) panelClasses.push("has-sidebar");
  if (isReveal) panelClasses.push("reveal");

  const optionsHtml = q.options.map((opt, i) => {
    const count = tally[String(i)] || 0;
    const pct = totalVotes > 0 ? (count / totalVotes) * 100 : 0;
    const classes = ["option"];
    if (opt.image) classes.push("has-image");
    if (isReveal && i === correct) classes.push("correct");
    if (isReveal && i !== correct && count === 0) classes.push("dim");
    // Reveal lifts the censors so viewers see the full card with the answer.
    const optHide = isReveal ? [] : (opt.hide || []);
    const thumb = opt.image
      ? renderCardFrame(opt.image, optHide, "thumb")
      : "";
    return `
      <div class="${classes.join(" ")}">
        <div class="letter">${CHOICE_LETTERS[i]}</div>
        ${thumb}
        <div class="text">${escapeHtml(opt.text)}</div>
        <div class="count">${count}</div>
        <div class="bar" style="width: ${pct.toFixed(1)}%"></div>
      </div>
    `;
  }).join("");

  // Reveal lifts the question-image censors AND replaces info-chip "?" placeholders
  // with the real rarity / price values.
  const qHide = isReveal ? [] : (q.question_image_hide || []);
  const chipsHide = q.question_image_hide || [];
  const sideCardHtml = hasQImage
    ? `
      <div class="side">
        ${renderInfoChips(chipsHide, q.question_image_rarity, q.question_image_price, isReveal)}
        ${renderCardFrame(q.question_image, qHide, "side-card", q.question_image_alt)}
        ${q.question_image_alt ? `<div class="caption">${escapeHtml(q.question_image_alt)}</div>` : ""}
      </div>
    `
    : "";
  const sidebarHtml = hasSidebar
    ? `<div class="sidebar">${sideCardHtml}${renderScoreboard(state, isReveal)}</div>`
    : "";

  const explanationHtml = isReveal && q.explanation
    ? `<div class="explanation">${escapeHtml(q.explanation)}</div>`
    : "";

  const tallyFooter = isReveal
    ? (totalVotes === 0
        ? `<div class="no-votes">No votes this round</div>`
        : `<div>${totalVotes} vote${totalVotes === 1 ? "" : "s"} tallied</div>`)
    : `<div>Type <strong>!vote A</strong>, B, C, or D to answer</div>`;

  root.innerHTML = `
    <div class="${panelClasses.join(" ")}">
      <div>
        <div class="header">
          <div class="title">MTG Trivia &middot; Round ${state.round_number}</div>
          <div class="badge ${diffClass}">${escapeHtml(q.difficulty || "?")}</div>
        </div>
        <div class="question">${escapeHtml(q.text)}</div>
        <div class="options">${optionsHtml}</div>
        ${explanationHtml}
        <div class="timer">
          <div class="label">${isReveal ? "Answer" : "Time"}</div>
          <div class="value" id="timer-value">--</div>
          <div class="track"><div class="fill" id="timer-fill" style="width: 100%"></div></div>
        </div>
        <div class="footer">${tallyFooter}</div>
      </div>
      ${sidebarHtml}
    </div>
  `;
}

function tickCountdown() {
  const fillEl = document.getElementById("timer-fill");
  const valueEl = document.getElementById("timer-value");
  if (!fillEl || !valueEl) {
    countdownRunning = false;
    return;
  }
  const remainingMs = Math.max(0, phaseEndsAtMs - Date.now());
  const seconds = Math.ceil(remainingMs / 1000);
  valueEl.textContent = `${seconds}s`;
  const pct = phaseTotalMs > 0 ? (remainingMs / phaseTotalMs) * 100 : 0;
  fillEl.style.width = `${pct.toFixed(2)}%`;
  if (remainingMs > 0) {
    requestAnimationFrame(tickCountdown);
  } else {
    countdownRunning = false;
  }
}

function startCountdownIfNeeded(state) {
  const newLabel = `${state.phase}:${state.round_number}:${state.phase_ends_at_ms}`;
  if (newLabel === phaseLabel) return;
  phaseLabel = newLabel;
  // Compensate for clock skew between server and client by using the offset
  // provided in this snapshot.
  const skew = Date.now() - (state.server_now_ms || Date.now());
  phaseEndsAtMs = state.phase_ends_at_ms + skew;
  phaseTotalMs = Math.max(1, phaseEndsAtMs - Date.now());
  if (!countdownRunning) {
    countdownRunning = true;
    requestAnimationFrame(tickCountdown);
  }
}

async function poll() {
  try {
    const resp = await fetch("/state", { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const state = await resp.json();
    lastState = state;

    // Re-render only when the structural fingerprint changes — keeps the DOM
    // stable so the local countdown animation doesn't restart on each poll.
    // Tally + total_votes can change between polls without requiring a full
    // re-render: update those in place when present.
    const fingerprint = JSON.stringify({
      phase: state.phase,
      round: state.round_number,
      qid: state.question && state.question.id,
      ends: state.phase_ends_at_ms,
      // Re-render when standings change (e.g. a mid-round /reset) so the
      // leaderboard never shows stale scores.
      sb: state.scoreboard,
      tsb: state.total_scoreboard,
    });

    if (fingerprint !== lastRenderedKey) {
      lastRenderedKey = fingerprint;
      renderState(state);
      startCountdownIfNeeded(state);
    } else if (state.question) {
      updateTallyInPlace(state);
    }
  } catch (e) {
    // Stay silent on stream. Keep showing the last rendered state.
    // Optional: console.debug(e) for local debugging.
  }
}

function updateTallyInPlace(state) {
  const tally = state.tally || {};
  const totalVotes = state.total_votes || 0;
  const options = document.querySelectorAll(".option");
  options.forEach((el, i) => {
    const count = tally[String(i)] || 0;
    const pct = totalVotes > 0 ? (count / totalVotes) * 100 : 0;
    const countEl = el.querySelector(".count");
    const barEl = el.querySelector(".bar");
    if (countEl) countEl.textContent = String(count);
    if (barEl) barEl.style.width = `${pct.toFixed(1)}%`;
  });
}

renderIdle();
poll();
setInterval(poll, POLL_MS);
scheduleScoreboardRotation();
