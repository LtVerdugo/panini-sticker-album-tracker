const API_BASE = window.location.origin;
const SPECIAL_TEAM_CODES = new Set(["FWC", "WP", "CCE", "HCC"]);

const TEAM_META = {
  ESP: { flag: "🇪🇸", name: "Spain" },
  NZL: { flag: "🇳🇿", name: "New Zealand" },
  UZB: { flag: "🇺🇿", name: "Uzbekistan" },
  MEX: { flag: "🇲🇽", name: "Mexico" },
};

const TEAM_FLAGS = {
  ALG: "🇩🇿", ARG: "🇦🇷", AUS: "🇦🇺", AUT: "🇦🇹",
  BEL: "🇧🇪", BIH: "🇧🇦", BOL: "🇧🇴", BRA: "🇧🇷",
  CAN: "🇨🇦", CHI: "🇨🇱", CHN: "🇨🇳", CIV: "🇨🇮",
  COD: "🇨🇩", COL: "🇨🇴", CPV: "🇨🇻", CRC: "🇨🇷",
  CRO: "🇭🇷", CZE: "🇨🇿", DEN: "🇩🇰", ECU: "🇪🇨",
  CUW: "🇨🇼", EGY: "🇪🇬", ENG: "🇬🇧", ESP: "🇪🇸", FRA: "🇫🇷",
  GER: "🇩🇪", GHA: "🇬🇭", GRE: "🇬🇷", HON: "🇭🇳",
  HUN: "🇭🇺", IDN: "🇮🇩", IRN: "🇮🇷", IRQ: "🇮🇶",
  IRL: "🇮🇪", ISL: "🇮🇸", ISR: "🇮🇱", ITA: "🇮🇹",
  JAM: "🇯🇲", JOR: "🇯🇴", JPN: "🇯🇵", KOR: "🇰🇷",
  KSA: "🇸🇦", MAR: "🇲🇦", MEX: "🇲🇽", MKD: "🇲🇰",
  MNE: "🇲🇪", NED: "🇳🇱", NGA: "🇳🇬", NOR: "🇳🇴",
  NZL: "🇳🇿", PAN: "🇵🇦", PAR: "🇵🇾", PER: "🇵🇪",
  POL: "🇵🇱", POR: "🇵🇹", QAT: "🇶🇦", ROU: "🇷🇴",
  RSA: "🇿🇦", SAU: "🇸🇦", SCO: "🇬🇧", SEN: "🇸🇳",
  SRB: "🇷🇸", SUI: "🇨🇭", SVK: "🇸🇰", SWE: "🇸🇪",
  THA: "🇹🇭", TUN: "🇹🇳", TUR: "🇹🇷", UKR: "🇺🇦",
  TRI: "🇹🇹", URU: "🇺🇾", USA: "🇺🇸", UZB: "🇺🇿", VEN: "🇻🇪",
  WAL: "🇬🇧", FWC: "🏆", WP: "🏅", CCE: "🥤",
  HCC: "🌎", ZAF: "🇿🇦"
};

const state = {
  stats: null,
  collection: [],
  missing: [],
  duplicates: [],
  sheetTouchStartY: 0,
  sheetMode: "missing",
  selectedFile: null,
  scanResult: null,
  reviewSlots: [],
  missingFilter: "All",
  collectionFilter: "All",
  swapFilter: "All",
  missingSearch: "",
  collectionSearch: "",
  tipIndex: 0,
  tipTimer: null,
  toastTimer: null,
};

const els = {
  pages: document.querySelectorAll(".page"),
  tabButtons: document.querySelectorAll(".tab-button"),
  openScanButton: document.querySelector("#openScanButton"),
  scanModal: document.querySelector("#scanModal"),
  closeScanButton: document.querySelector("#closeScanButton"),
  scanInput: document.querySelector("#scanInput"),
  scanPreview: document.querySelector("#scanPreview"),
  scanUploadView: document.querySelector("#scanUploadView"),
  analyzeButton: document.querySelector("#analyzeButton"),
  scanLoading: document.querySelector("#scanLoading"),
  scanError: document.querySelector("#scanError"),
  reviewView: document.querySelector("#reviewView"),
  reviewTeamBadge: document.querySelector("#reviewTeamBadge"),
  reviewGrid: document.querySelector("#reviewGrid"),
  confirmButton: document.querySelector("#confirmButton"),
  successOverlay: document.querySelector("#successOverlay"),
  successCount: document.querySelector("#successCount"),
  toast: document.querySelector("#toast"),
  homeCompletionPct: document.querySelector("#homeCompletionPct"),
  homeCompletionText: document.querySelector("#homeCompletionText"),
  homeCompletionBar: document.querySelector("#homeCompletionBar"),
  homeTotal: document.querySelector("#homeTotal"),
  homeOwned: document.querySelector("#homeOwned"),
  homeMissing: document.querySelector("#homeMissing"),
  tipText: document.querySelector("#tipText"),
  teamProgressRow: document.querySelector("#teamProgressRow"),
  seeAllTeams: document.querySelector("#seeAllTeams"),
  missingSearch: document.querySelector("#missingSearch"),
  missingFilters: document.querySelector("#missingFilters"),
  missingCounter: document.querySelector("#missingCounter"),
  missingList: document.querySelector("#missingList"),
  specialMissingSection: document.querySelector("#specialMissingSection"),
  specialMissingList: document.querySelector("#specialMissingList"),
  helpFab: document.querySelector("#help-fab"),
  howToOverlay: document.querySelector("#howToOverlay"),
  howToCloseButton: document.querySelector("#howToCloseButton"),
  howToCtaButton: document.querySelector("#howToCtaButton"),
  swapCount: document.querySelector("#swapCount"),
  swapFilters: document.querySelector("#swapFilters"),
  swapList: document.querySelector("#swapList"),
  shareSwapButton: document.querySelector("#shareSwapButton"),
  shareMissingButton: document.querySelector("#shareMissingButton"),
  statsCompletionPct: document.querySelector("#statsCompletionPct"),
  statsRing: document.querySelector("#statsRing"),
  statsTotal: document.querySelector("#statsTotal"),
  statsOwned: document.querySelector("#statsOwned"),
  statsMissing: document.querySelector("#statsMissing"),
  statsDuplicates: document.querySelector("#statsDuplicates"),
  teamStatsList: document.querySelector("#teamStatsList"),
};

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

function safeText(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function teamMeta(teamCode) {
  const code = String(teamCode || "UNK").toUpperCase();
  return TEAM_META[code] || { flag: TEAM_FLAGS[code] || "🏳️", name: code };
}

function codeFromSticker(sticker) {
  return sticker.code || sticker.display_code || sticker.sticker_id || "";
}

function nameFromSticker(sticker) {
  return sticker.name || sticker.player_name || "";
}

function teamFromSticker(sticker) {
  const code = codeFromSticker(sticker);
  return String(sticker.team_code || code.split(/[ _-]/)[0] || "UNK").toUpperCase();
}

function isSpecialSticker(sticker) {
  const directTeamCode = String(sticker.team_code || "").toUpperCase();
  return SPECIAL_TEAM_CODES.has(directTeamCode) || SPECIAL_TEAM_CODES.has(teamFromSticker(sticker));
}

function teamFilterMatches(sticker, activeTeam) {
  if (activeTeam === "All") return true;
  if (activeTeam === "Special") return isSpecialSticker(sticker);
  return !isSpecialSticker(sticker) && teamFromSticker(sticker) === activeTeam;
}

function slotNumberFromCode(code) {
  const match = String(code).match(/[A-Za-z]{3}[\s_-]*(\d{1,3})/);
  return match ? Number(match[1]) : null;
}

function normalizeDisplayCode(code) {
  const text = String(code || "").replaceAll("_", " ").replaceAll("-", " ").toUpperCase();
  const parts = text.split(/\s+/).filter(Boolean);
  if (parts.length < 2) return text.trim();
  const number = Number(parts[1]);
  return Number.isFinite(number) ? `${parts[0]} ${number}` : text.trim();
}

function progressColor(percent) {
  if (percent <= 25) return "#E63946";
  if (percent <= 50) return "#FF9800";
  if (percent <= 75) return "#2196F3";
  return "#2D9B6F";
}

function countUp(element, target, suffix = "") {
  const end = Number(target || 0);
  const duration = 1200;
  const started = performance.now();

  function frame(now) {
    const progress = Math.min(1, (now - started) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = `${Math.round(end * eased)}${suffix}`;
    if (progress < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

function setProgressBar(element, percent) {
  requestAnimationFrame(() => {
    element.style.width = `${Math.min(100, Math.max(0, Number(percent || 0)))}%`;
  });
}

function buildTeamProgress() {
  const teams = new Map();

  for (const sticker of [...state.collection, ...state.missing]) {
    const team = teamFromSticker(sticker);
    if (!teams.has(team)) {
      teams.set(team, { team, owned: 0, total: 0 });
    }
    const row = teams.get(team);
    row.total += 1;
    if (Number(sticker.quantity || 0) > 0) row.owned += 1;
  }

  return [...teams.values()].map((team) => {
    const total = team.total || 20;
    const percent = total ? Math.round((team.owned / total) * 100) : 0;
    return { ...team, total, percent };
  });
}

function updateStats(stats) {
  state.stats = stats;
  const total = Number(stats.total || 0);
  const owned = Number(stats.owned || 0);
  const missing = Number(stats.missing || 0);
  const duplicates = Number(stats.duplicates || 0);
  const pct = Number(stats.completion_pct || 0);

  countUp(els.homeCompletionPct, pct, "%");
  els.homeCompletionText.textContent = `${owned} stickers owned · ${missing} missing`;
  setProgressBar(els.homeCompletionBar, pct);
  countUp(els.homeTotal, total);
  countUp(els.homeOwned, owned);
  countUp(els.homeMissing, missing);

  countUp(els.statsCompletionPct, pct, "%");
  els.statsRing.style.strokeDashoffset = String(364.42 - (364.42 * pct) / 100);
  countUp(els.statsTotal, total);
  countUp(els.statsOwned, owned);
  countUp(els.statsMissing, missing);
  countUp(els.statsDuplicates, duplicates);
}

function renderTips() {
  const teams = buildTeamProgress();
  const mostOwned = [...teams].sort((a, b) => b.owned - a.owned)[0];
  const teamLabel = mostOwned ? teamMeta(mostOwned.team).name : "a team";
  const teamNeed = mostOwned ? Math.max(0, mostOwned.total - mostOwned.owned) : 0;
  const duplicateCount = Number(state.stats?.duplicates || 0);
  const pct = Number(state.stats?.completion_pct || 0);
  const tips = [
    `You need ${teamNeed} more stickers to complete ${teamLabel}!`,
    `You have ${duplicateCount} duplicate stickers ready to swap!`,
    `You're ${Math.max(0, Math.round(100 - pct))}% away from completing your album!`,
  ];

  els.tipText.style.opacity = "0";
  window.setTimeout(() => {
    els.tipText.textContent = tips[state.tipIndex % tips.length];
    els.tipText.style.opacity = "1";
  }, 180);

  if (!state.tipTimer) {
    state.tipTimer = window.setInterval(() => {
      state.tipIndex += 1;
      renderTips();
    }, 5000);
  }
}

function renderTeamProgress() {
  const teams = buildTeamProgress().sort((a, b) => b.percent - a.percent);
  if (!teams.length) {
    els.teamProgressRow.innerHTML = `<article class="team-card"><strong>No teams yet</strong><span>Scan a page to begin</span></article>`;
    els.teamStatsList.innerHTML = "";
    return;
  }

  els.teamProgressRow.innerHTML = teams
    .map((team) => {
      const meta = teamMeta(team.team);
      return `
        <article class="team-card">
          <div class="flag">${meta.flag}</div>
          <strong>${safeText(meta.name)}</strong>
          <span>${team.owned} / ${team.total}</span>
          <div class="team-progress"><div style="width:${team.percent}%;background:${progressColor(team.percent)}"></div></div>
        </article>
      `;
    })
    .join("");

  els.teamStatsList.innerHTML = teams
    .map((team) => {
      const meta = teamMeta(team.team);
      return `
        <article class="team-row">
          <div>
            <strong>${meta.flag} ${safeText(meta.name)}</strong>
            <span>${team.owned}/${team.total}</span>
          </div>
          <strong>${team.percent}%</strong>
          <div class="team-progress"><div style="width:${team.percent}%;background:${progressColor(team.percent)}"></div></div>
        </article>
      `;
    })
    .join("");
}

function ensureCollectionSection() {
  let section = document.getElementById("ownedCollectionSection");
  if (section) return section;

  section = document.createElement("section");
  section.id = "ownedCollectionSection";
  section.className = "section-block";
  section.innerHTML = `
    <div class="section-title">
      <h2>My Stickers</h2>
    </div>
    <div class="collection-controls">
      <label class="search-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <circle cx="11" cy="11" r="7"/>
          <path d="m20 20-3.5-3.5"/>
        </svg>
        <input id="collectionSearch" type="search" placeholder="Search owned stickers" />
      </label>
      <div id="collectionFilters" class="filter-row"></div>
    </div>
    <div id="ownedCollectionList" class="list-stack"></div>
  `;
  document.getElementById("albumPage").appendChild(section);
  section.querySelector("#collectionSearch").addEventListener("input", (event) => {
    state.collectionSearch = event.target.value.trim();
    renderCollection();
  });
  return section;
}

function renderCollection() {
  ensureCollectionSection();
  const list = document.getElementById("ownedCollectionList");
  const searchInput = document.getElementById("collectionSearch");
  const filterContainer = document.getElementById("collectionFilters");
  const teams = [...new Set(state.collection.filter((sticker) => !isSpecialSticker(sticker)).map(teamFromSticker))].sort();

  searchInput.value = state.collectionSearch;
  renderFilters(filterContainer, teams, state.collectionFilter, (team) => {
    state.collectionFilter = team;
    renderCollection();
  });

  if (!state.collection.length) {
    list.innerHTML = `
      <article class="empty-state compact">
        <div>📒</div>
        <h2>No stickers owned yet</h2>
        <p>Scan a page or mark stickers owned to build your album.</p>
      </article>
    `;
    return;
  }

  const query = state.collectionSearch.toLowerCase();
  const filtered = state.collection.filter((sticker) => {
    const text = `${codeFromSticker(sticker)} ${nameFromSticker(sticker)}`.toLowerCase();
    return teamFilterMatches(sticker, state.collectionFilter) && text.includes(query);
  });

  if (!filtered.length) {
    list.innerHTML = `
      <article class="empty-state compact">
        <div>🔎</div>
        <h2>No owned stickers found</h2>
        <p>Try another search or team filter.</p>
      </article>
    `;
    return;
  }

  list.innerHTML = filtered
    .map((sticker) => {
      const team = teamFromSticker(sticker);
      const meta = teamMeta(team);
      return `
        <article class="list-card collection-card ${isSpecialSticker(sticker) ? "special" : ""}">
          <div>
            <strong>${meta.flag} ${safeText(codeFromSticker(sticker))}</strong>
            <p>${safeText(nameFromSticker(sticker) || "To be completed")}</p>
          </div>
          <button
            class="duplicate-add-btn"
            type="button"
            aria-label="Add duplicate"
            data-code="${safeText(codeFromSticker(sticker))}"
            data-name="${safeText(nameFromSticker(sticker) || "To be completed")}"
            data-team="${safeText(team)}"
          >+</button>
        </article>
      `;
    })
    .join("");
}

function renderFilters(container, teams, activeTeam, onSelect) {
  container.innerHTML = "";
  const fragment = document.createDocumentFragment();
  const filterItems = ["All", ...teams];
  filterItems.push("Special");

  for (const team of filterItems) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `filter-pill ${team === activeTeam ? "active" : ""}`;
    button.textContent = team === "All"
      ? "All"
      : team === "Special"
        ? "✨ Special"
        : `${teamMeta(team).flag} ${team}`;
    button.addEventListener("click", () => onSelect(team));
    fragment.appendChild(button);
  }
  container.appendChild(fragment);
}

function renderMissingCard(sticker, extraClass = "") {
  const team = teamFromSticker(sticker);
  const meta = teamMeta(team);
  return `
    <article
      class="list-card missing-sticker-card ${extraClass}"
      data-sticker-id="${safeText(sticker.sticker_id || "")}"
      data-code="${safeText(codeFromSticker(sticker))}"
      data-name="${safeText(nameFromSticker(sticker) || "To be completed")}"
      data-team="${safeText(team)}"
      style="cursor: pointer;"
    >
      <div>
        <strong>${meta.flag} ${safeText(codeFromSticker(sticker))}</strong>
        <p>${safeText(nameFromSticker(sticker) || "To be completed")}</p>
      </div>
    </article>
  `;
}

function renderMissingTeamGroup(team, stickers) {
  const meta = teamMeta(team);
  const pageNumber = Number(stickers[0]?.page_number || 0);
  const pageMarkup = pageNumber > 0
    ? `
      <div class="team-page-indicator">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="11" height="11">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
        </svg>
        Page ${pageNumber}
      </div>
    `
    : "";

  return `
    <section class="team-group">
      <div class="team-group-header">
        <div class="team-group-left">
          <span class="team-flag">${meta.flag}</span>
          <span class="team-group-name">${safeText(meta.name)}</span>
          <span class="team-group-count">${stickers.length} missing</span>
        </div>
        ${pageMarkup}
      </div>
      <div class="list-stack">
        ${stickers.map((sticker) => renderMissingCard(sticker)).join("")}
      </div>
    </section>
  `;
}

function renderMissing() {
  const regularMissing = state.missing.filter((sticker) => !isSpecialSticker(sticker));
  const specialMissing = state.missing.filter(isSpecialSticker);
  const teams = [...new Set(regularMissing.map(teamFromSticker))].sort();
  renderFilters(els.missingFilters, teams, state.missingFilter, (team) => {
    state.missingFilter = team;
    renderMissing();
  });

  const query = state.missingSearch.toLowerCase();
  const matchesSearch = (sticker) => {
    const text = `${codeFromSticker(sticker)} ${nameFromSticker(sticker)}`.toLowerCase();
    return text.includes(query);
  };
  const filteredRegular = state.missingFilter === "Special"
    ? []
    : regularMissing.filter((sticker) => {
      const teamOk = state.missingFilter === "All" || teamFromSticker(sticker) === state.missingFilter;
      return teamOk && matchesSearch(sticker);
    });
  const filteredSpecial = specialMissing.filter(matchesSearch);
  const showSpecialSection = state.missingFilter === "All" || state.missingFilter === "Special";
  const counterCount = state.missingFilter === "Special"
    ? filteredSpecial.length
    : filteredRegular.length + (state.missingFilter === "All" ? filteredSpecial.length : 0);

  els.missingCounter.textContent = `${counterCount} stickers missing`;
  els.missingList.classList.toggle("hidden", state.missingFilter === "Special");
  const groupedRegular = filteredRegular.reduce((groups, sticker) => {
    const team = teamFromSticker(sticker);
    groups[team] = groups[team] || [];
    groups[team].push(sticker);
    return groups;
  }, {});
  els.missingList.innerHTML = Object.keys(groupedRegular)
    .sort()
    .map((team) => renderMissingTeamGroup(team, groupedRegular[team]))
    .join("");
  els.specialMissingSection.classList.toggle("hidden", !showSpecialSection);
  els.specialMissingList.innerHTML = filteredSpecial
    .map((sticker) => renderMissingCard(sticker, "special-sticker-card special"))
    .join("");
}

function updateMissingCounter() {
  if (state.missingFilter === "Special") {
    const query = state.missingSearch.toLowerCase();
    const count = state.missing.filter((sticker) => {
      const text = `${codeFromSticker(sticker)} ${nameFromSticker(sticker)}`.toLowerCase();
      return isSpecialSticker(sticker) && text.includes(query);
    }).length;
    els.missingCounter.textContent = `${count} stickers missing`;
    return;
  }

  const query = state.missingSearch.toLowerCase();
  const count = state.missing.filter((sticker) => {
    const specialOk = isSpecialSticker(sticker) && state.missingFilter === "All";
    const teamOk = specialOk || (
      !isSpecialSticker(sticker)
      && (state.missingFilter === "All" || teamFromSticker(sticker) === state.missingFilter)
    );
    const text = `${codeFromSticker(sticker)} ${nameFromSticker(sticker)}`.toLowerCase();
    return teamOk && text.includes(query);
  }).length;
  els.missingCounter.textContent = `${count} stickers missing`;
}

function renderSwap() {
  const teams = [...new Set(state.duplicates.filter((sticker) => !isSpecialSticker(sticker)).map(teamFromSticker))].sort();
  renderFilters(els.swapFilters, teams, state.swapFilter, (team) => {
    state.swapFilter = team;
    renderSwap();
  });

  const filtered = state.duplicates.filter((sticker) => teamFilterMatches(sticker, state.swapFilter));

  els.swapCount.textContent = String(filtered.length);
  if (!filtered.length) {
    els.swapList.innerHTML = `
      <article class="empty-state">
        <div>📭</div>
        <h2>No duplicates yet</h2>
        <p>Duplicates will appear here after confirmed scans.</p>
      </article>
    `;
    return;
  }

  els.swapList.innerHTML = filtered
    .map((sticker) => {
      const team = teamFromSticker(sticker);
      const meta = teamMeta(team);
      const quantity = Number(sticker.quantity || 2);
      return `
        <article
          class="list-card swap ${isSpecialSticker(sticker) ? "special" : ""}"
          data-sticker-id="${safeText(sticker.sticker_id || "")}"
          data-code="${safeText(codeFromSticker(sticker))}"
          data-name="${safeText(nameFromSticker(sticker) || "To be completed")}"
          data-team="${safeText(team)}"
          data-quantity="${quantity}"
        >
          <div>
            <strong>${meta.flag} ${safeText(codeFromSticker(sticker))}</strong>
            <p>${safeText(nameFromSticker(sticker) || "To be completed")}</p>
          </div>
          <div class="qty-control">
            <button class="qty-btn minus" type="button" aria-label="Decrease duplicate quantity">−</button>
            <span class="qty-value">${quantity}</span>
            <button class="qty-btn plus" type="button" aria-label="Increase duplicate quantity">+</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function showToast(message) {
  if (state.toastTimer) window.clearTimeout(state.toastTimer);
  els.toast.textContent = message;
  els.toast.classList.remove("hidden");
  state.toastTimer = window.setTimeout(() => {
    els.toast.classList.add("hidden");
  }, 2500);
}

function setScanLoading(message, visible = true) {
  const label = els.scanLoading.querySelector("strong");
  if (label) label.textContent = message;
  els.scanLoading.classList.toggle("hidden", !visible);
}

function injectStickerSheet() {
  if (document.getElementById("sticker-sheet-overlay")) return;

  document.body.insertAdjacentHTML(
    "beforeend",
    `
      <div id="sticker-sheet-overlay" class="sheet-overlay hidden">
        <div id="sticker-sheet" class="bottom-sheet">
          <div class="sheet-handle"></div>
          <div class="sheet-flag" id="sheet-flag"></div>
          <div class="sheet-code" id="sheet-code"></div>
          <div class="sheet-name" id="sheet-name"></div>
          <button class="sheet-confirm-btn" id="sheet-confirm">
            ✓ &nbsp;I got this sticker!
          </button>
          <button class="sheet-cancel-btn" id="sheet-cancel">
            Cancel
          </button>
        </div>
      </div>
    `
  );
}

function openStickerSheet(stickerId, code, name, teamCode) {
  state.sheetMode = "missing";
  const overlay = document.getElementById("sticker-sheet-overlay");
  const flagEl = document.getElementById("sheet-flag");
  const codeEl = document.getElementById("sheet-code");
  const nameEl = document.getElementById("sheet-name");
  const confirmBtn = document.getElementById("sheet-confirm");

  flagEl.textContent = TEAM_FLAGS[teamCode] || "🏳️";
  codeEl.textContent = code;
  nameEl.textContent = name || "Unknown player";
  confirmBtn.textContent = "✓  I got this sticker!";
  confirmBtn.classList.remove("duplicate");

  overlay.dataset.stickerId = stickerId;
  overlay.dataset.code = code;
  overlay.dataset.name = name || "";
  overlay.dataset.team = teamCode || "";

  overlay.classList.remove("hidden");
  requestAnimationFrame(() => overlay.classList.add("visible"));
}

function openDuplicateSheet(code, name, teamCode) {
  state.sheetMode = "duplicate";
  const overlay = document.getElementById("sticker-sheet-overlay");
  const flagEl = document.getElementById("sheet-flag");
  const codeEl = document.getElementById("sheet-code");
  const nameEl = document.getElementById("sheet-name");
  const confirmBtn = document.getElementById("sheet-confirm");

  flagEl.textContent = TEAM_FLAGS[teamCode] || "🏳️";
  codeEl.innerHTML = `Add duplicate?<br><span>${safeText(code)}</span>`;
  nameEl.innerHTML = `${safeText(name || "To be completed")}<br><small>Mark this sticker as duplicated</small>`;
  confirmBtn.textContent = "➕ Add duplicate";
  confirmBtn.classList.add("duplicate");

  overlay.dataset.code = code;
  overlay.dataset.name = name || "";
  overlay.dataset.team = teamCode || "";

  overlay.classList.remove("hidden");
  requestAnimationFrame(() => overlay.classList.add("visible"));
}

function closeStickerSheet() {
  const overlay = document.getElementById("sticker-sheet-overlay");
  overlay.classList.remove("visible");
  window.setTimeout(() => overlay.classList.add("hidden"), 300);
}

function openHowToModal() {
  els.howToOverlay.classList.remove("hidden");
  els.howToOverlay.setAttribute("aria-hidden", "false");
}

function closeHowToModal() {
  els.howToOverlay.classList.add("hidden");
  els.howToOverlay.setAttribute("aria-hidden", "true");
}

async function confirmStickerOwned(stickerId, code, name = "", teamCode = "") {
  try {
    const resolvedTeamCode = teamCode || String(code).split(" ")[0];
    const isSpecial = SPECIAL_TEAM_CODES.has(String(resolvedTeamCode).toUpperCase());
    const payload = {
      team_code: resolvedTeamCode,
      missing: [],
      owned: [{ sticker_id: stickerId, code, name }],
      raw_slots: [{ sticker_id: stickerId, code, name, readable: false }],
    };

    const response = await fetch(`${API_BASE}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error("Failed to save");

    closeStickerSheet();

    const escapeSelector = (value) => (
      window.CSS && CSS.escape ? CSS.escape(String(value || "")) : String(value || "").replaceAll('"', '\\"')
    );
    const card =
      document.querySelector(`[data-sticker-id="${escapeSelector(stickerId)}"]`) ||
      document.querySelector(`[data-code="${escapeSelector(code)}"]`);

    if (card) {
      card.style.transition = "all 0.3s ease";
      card.style.opacity = "0";
      card.style.transform = "translateX(60px)";
      const h = card.offsetHeight;
      card.style.maxHeight = `${h}px`;
      card.style.overflow = "hidden";
      setTimeout(() => {
        card.style.maxHeight = "0";
        card.style.marginBottom = "0";
        card.style.padding = "0";
        card.style.border = "none";
      }, 300);
      setTimeout(() => {
        card.remove();
        refreshAllData();
      }, 600);
    } else {
      refreshAllData();
    }

    state.missing = state.missing.filter((sticker) => sticker.sticker_id !== stickerId);
    updateMissingCounter();

    if (typeof confetti !== "undefined") {
      confetti({
        particleCount: 40,
        spread: 50,
        origin: { y: 0.7 },
        colors: ["#2D9B6F", "#D4AF37", "#ffffff"],
      });
    }

    showToast(isSpecial ? "✓ Special sticker marked as owned!" : "✓ Sticker marked as owned!");
  } catch (err) {
    showToast("Error saving. Please try again.");
    console.error(err);
  }
}

async function confirmDuplicateSticker(code, name, teamCode) {
  try {
    const payload = {
      team_code: teamCode,
      missing: [],
      owned: [{ code, name }],
      raw_slots: [{ code, name, readable: false }],
    };

    const response = await fetch(`${API_BASE}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error("Failed to save");

    closeStickerSheet();
    showToast("➕ Duplicate added! Check Swap tab");
    await Promise.all([loadCollection(), loadDuplicates()]);
    renderCollection();
  } catch (err) {
    showToast("Error saving. Please try again.");
    console.error(err);
  }
}

async function incrementDuplicateQuantity(card) {
  const code = card.dataset.code;
  const name = card.dataset.name || "";
  const teamCode = card.dataset.team || String(code).split(" ")[0];
  const quantityEl = card.querySelector(".qty-value");
  const currentQuantity = Number(card.dataset.quantity || quantityEl?.textContent || 1);
  const payload = {
    team_code: teamCode,
    missing: [],
    owned: [{ code, name }],
    raw_slots: [{ code, name, readable: false }],
  };

  const response = await fetch(`${API_BASE}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error("Failed to increase quantity");

  const nextQuantity = currentQuantity + 1;
  card.dataset.quantity = String(nextQuantity);
  if (quantityEl) quantityEl.textContent = String(nextQuantity);
  showToast("➕ Duplicate quantity updated");
  window.setTimeout(refreshAllData, 250);
}

async function decrementDuplicateQuantity(card) {
  const stickerId = card.dataset.stickerId;
  if (!stickerId) throw new Error("Missing sticker id");

  const response = await fetch(`${API_BASE}/sticker/${encodeURIComponent(stickerId)}/decrement`, {
    method: "POST",
  });

  if (!response.ok) throw new Error("Failed to decrease quantity");

  const result = await response.json();
  const nextQuantity = Number(result.quantity || 0);
  const quantityEl = card.querySelector(".qty-value");

  if (nextQuantity > 1) {
    card.dataset.quantity = String(nextQuantity);
    if (quantityEl) quantityEl.textContent = String(nextQuantity);
    showToast("Duplicate quantity updated");
    window.setTimeout(refreshAllData, 250);
    return;
  }

  card.style.transition = "all 0.3s ease";
  card.style.opacity = "0";
  card.style.transform = "translateX(60px)";
  card.style.maxHeight = `${card.offsetHeight}px`;
  window.setTimeout(() => {
    card.style.maxHeight = "0";
    card.style.marginBottom = "0";
    card.style.padding = "0";
  }, 300);
  window.setTimeout(() => {
    card.remove();
    refreshAllData();
  }, 600);
  showToast(nextQuantity === 0 ? "Moved to Missing" : "No longer a duplicate");
}

async function loadStats() {
  const stats = await apiFetch("/stats");
  updateStats(stats);
}

async function loadCollection() {
  state.collection = await apiFetch("/collection");
  renderCollection();
}

async function loadMissing() {
  state.missing = await apiFetch("/missing");
  renderMissing();
}

async function loadDuplicates() {
  state.duplicates = await apiFetch("/duplicates");
  renderSwap();
}

async function refreshAllData() {
  try {
    await Promise.all([loadStats(), loadCollection(), loadMissing(), loadDuplicates()]);
    renderTeamProgress();
    renderTips();
  } catch (error) {
    showToast(`Could not refresh data: ${error.message}`);
  }
}

function switchPage(pageId) {
  els.pages.forEach((page) => page.classList.toggle("active", page.id === pageId));
  els.tabButtons.forEach((button) => button.classList.toggle("active", button.dataset.page === pageId));
  els.shareSwapButton.classList.toggle("hidden", pageId !== "swapPage");
  els.shareMissingButton.classList.toggle("hidden", pageId !== "missingPage");
  if (pageId === "missingPage") loadMissing();
  if (pageId === "swapPage") loadDuplicates();
  if (pageId === "statsPage") Promise.all([loadStats(), loadCollection()]).then(renderTeamProgress);
}

function resetScanFlow() {
  state.selectedFile = null;
  state.scanResult = null;
  state.reviewSlots = [];
  els.scanInput.value = "";
  els.scanPreview.removeAttribute("src");
  els.scanPreview.classList.remove("visible");
  els.analyzeButton.disabled = true;
  els.analyzeButton.innerHTML = "⚡ Analyze Page";
  els.scanUploadView.classList.remove("hidden");
  els.scanLoading.classList.add("hidden");
  els.reviewView.classList.add("hidden");
  els.reviewGrid.innerHTML = "";
  els.scanError.classList.add("hidden");
  els.scanError.textContent = "";
}

function openScanModal() {
  resetScanFlow();
  els.scanModal.classList.add("open");
  els.scanModal.setAttribute("aria-hidden", "false");
}

function closeScanModal() {
  els.scanModal.classList.remove("open");
  els.scanModal.setAttribute("aria-hidden", "true");
  resetScanFlow();
}

function buildReviewSlots(result) {
  const slots = Array.isArray(result.raw_slots) ? result.raw_slots : [];
  if (slots.length) {
    return slots.map((slot, index) => ({
      id: `${slot.code || "slot"}-${index}`,
      code: String(slot.code || "").trim(),
      name: String(slot.name || "").trim(),
      status: slot.readable ? "missing" : "owned",
    }));
  }

  return [
    ...(result.missing || []).map((slot, index) => ({
      id: `missing-${index}`,
      code: String(slot.code || "").trim(),
      name: String(slot.name || "").trim(),
      status: "missing",
    })),
    ...(result.owned || []).map((slot, index) => ({
      id: `owned-${index}`,
      code: String(slot.code || "").trim(),
      name: String(slot.name || "").trim(),
      status: "owned",
    })),
  ];
}

function hasStickerData(data) {
  return Boolean(
    data
    && (
      Array.isArray(data.slots)
      || Array.isArray(data.raw_slots)
      || Array.isArray(data.missing)
      || Array.isArray(data.owned)
    )
  );
}

function showScanError(message) {
  els.scanError.textContent = message;
  els.scanError.classList.remove("hidden");
}

function getReviewCounts() {
  const owned = state.reviewSlots.filter((slot) => slot.status === "owned").length;
  return {
    owned,
    missing: state.reviewSlots.length - owned,
    total: state.reviewSlots.length || 20,
  };
}

function updateReviewCounter(animate = false) {
  const counter = document.getElementById("reviewCounter");
  if (!counter) return;

  const counts = getReviewCounts();
  const ownedEl = document.getElementById("reviewOwnedCount");
  const totalEl = document.getElementById("reviewTotalCount");
  const missingEl = document.getElementById("reviewMissingCount");
  const fillEl = document.getElementById("reviewCounterFill");
  const total = counts.total || 20;

  ownedEl.textContent = String(counts.owned);
  totalEl.textContent = `${counts.owned} / ${total}`;
  missingEl.textContent = String(counts.missing);
  fillEl.style.width = `${Math.min(100, (counts.owned / total) * 100)}%`;

  if (animate) {
    counter.classList.remove("pulse");
    void counter.offsetWidth;
    counter.classList.add("pulse");
  }
}

function renderReview() {
  const counts = getReviewCounts();
  const total = counts.total || 20;
  const counter = `
    <div id="reviewCounter" class="review-counter">
      <div class="review-counter-row">
        <div>
          <strong id="reviewOwnedCount" class="owned-count">${counts.owned}</strong>
          <span>owned</span>
        </div>
        <div class="review-total" id="reviewTotalCount">${counts.owned} / ${total}</div>
        <div>
          <strong id="reviewMissingCount" class="missing-count">${counts.missing}</strong>
          <span>missing</span>
        </div>
      </div>
      <div class="review-counter-track">
        <div id="reviewCounterFill" style="width:${Math.min(100, (counts.owned / total) * 100)}%"></div>
      </div>
    </div>
  `;
  const quickActions = `
    <div class="quick-action-row">
      <button class="quick-btn quick-missing" data-quick-action="missing" type="button">✗ All Missing</button>
      <button class="quick-btn quick-owned" data-quick-action="owned" type="button">✓ All Owned</button>
    </div>
  `;
  const cards = state.reviewSlots
    .map((slot, index) => `
      <button class="review-card ${slot.status}" data-index="${index}" type="button">
        <strong>${safeText(slot.code)}</strong>
        <span class="name">${safeText(slot.name || "To be completed")}</span>
        <span class="state-badge">${slot.status === "owned" ? "✓ Owned" : "✗ Missing"}</span>
      </button>
    `)
    .join("");
  els.reviewGrid.innerHTML = counter + quickActions + cards;
}

function setAllReviewSlots(status) {
  state.reviewSlots = state.reviewSlots.map((slot) => ({ ...slot, status }));
  renderReview();
  updateReviewCounter(true);
}

function buildConfirmPayload() {
  const owned = [];
  const missing = [];
  for (const slot of state.reviewSlots) {
    const row = { code: slot.code, name: slot.name || "" };
    if (slot.status === "owned") owned.push(row);
    else missing.push(row);
  }

  return {
    ...state.scanResult,
    owned,
    missing,
    raw_slots: state.reviewSlots.map((slot) => ({
      code: slot.code,
      name: slot.name || "",
      readable: slot.status === "missing",
    })),
  };
}

async function analyzeScan() {
  if (!state.selectedFile) return;

  const formData = new FormData();
  formData.append("file", state.selectedFile);
  els.analyzeButton.disabled = true;
  els.analyzeButton.innerHTML = `<span class="spinner"></span> Analyzing with AI...`;
  setScanLoading("Analyzing with AI...", true);
  els.scanError.classList.add("hidden");

  try {
    const result = await apiFetch("/scan", { method: "POST", body: formData });
    try {
      if (!hasStickerData(result)) {
        console.error("Unexpected scan response:", result);
        showScanError("No stickers detected. Try a clearer photo.");
        return;
      }

      const detectedItems = [
        ...(Array.isArray(result.raw_slots) ? result.raw_slots : []),
        ...(Array.isArray(result.slots) ? result.slots : []),
        ...(Array.isArray(result.missing) ? result.missing : []),
        ...(Array.isArray(result.owned) ? result.owned : []),
      ];

      if (!detectedItems.length) {
        console.error("Empty scan response:", result);
        showScanError("Could not detect stickers. Please try again.");
        return;
      }

      state.scanResult = result;
      state.reviewSlots = buildReviewSlots(result);
      if (!state.reviewSlots.length) {
        console.error("No review slots built from scan response:", result);
        showScanError("Could not detect stickers. Please try again.");
        return;
      }

      els.reviewTeamBadge.textContent = result.team_code || "TEAM";
      els.scanUploadView.classList.add("hidden");
      els.scanLoading.classList.add("hidden");
      els.reviewView.classList.remove("hidden");
      renderReview();
    } catch (parseError) {
      console.error("Failed to handle scan response:", parseError, result);
      showScanError("Analysis failed. Please retake the photo.");
    }
  } catch (error) {
    console.error("Scan request failed:", error);
    showScanError("Analysis failed. Please retake the photo.");
  } finally {
    els.analyzeButton.disabled = false;
    els.analyzeButton.innerHTML = "⚡ Analyze Page";
    setScanLoading("", false);
  }
}

function fireConfetti() {
  if (typeof confetti !== "function") return;
  const end = Date.now() + 3000;
  const colors = ["#E63946", "#D4AF37", "#ffffff", "#2196F3"];
  const timer = window.setInterval(() => {
    confetti({ particleCount: 40, spread: 80, origin: { y: 0.6 }, colors });
    if (Date.now() > end) window.clearInterval(timer);
  }, 300);
  confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 }, colors });
}

async function confirmScan() {
  if (!state.reviewSlots.length) return;

  els.confirmButton.disabled = true;
  try {
    const result = await apiFetch("/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildConfirmPayload()),
    });

    if (result.stats) updateStats(result.stats);
    fireConfetti();
    els.successCount.textContent = String(result.saved || 0);
    els.successOverlay.classList.remove("hidden");
    const refreshPromise = refreshAllData();
    await wait(2000);
    els.successOverlay.classList.add("hidden");
    closeScanModal();
    await refreshPromise;
  } catch (error) {
    els.scanError.textContent = `Save failed: ${error.message}`;
    els.scanError.classList.remove("hidden");
  } finally {
    els.confirmButton.disabled = false;
  }
}

async function shareSwapList() {
  const items = state.duplicates.map((sticker) => {
    return `${codeFromSticker(sticker)} - ${nameFromSticker(sticker) || "To be completed"}`;
  });
  const text = `🔄 My Panini WC 2026 duplicates:\n\n${items.join("\n")}\n\nInterested in swapping? Let me know! 🏆`;

  if (navigator.share) {
    try {
      await navigator.share({ text });
      return;
    } catch (error) {
      if (error.name === "AbortError") return;
    }
  }

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      showToast("📋 Copied to clipboard!");
      return;
    } catch {
      // Fall through to the textarea copy fallback for non-HTTPS browsers.
    }
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();

    if (copied) {
      showToast("📋 Copied to clipboard!");
      return;
    }
  } catch {
    // Final fallback below shows the text for manual copy.
  }

  window.alert(text);
}

async function shareMissingList() {
  const items = state.missing.map((sticker) => {
    return `${codeFromSticker(sticker)} - ${nameFromSticker(sticker) || "To be completed"}`;
  });
  const text = `⭐ My Panini WC 2026 missing stickers:\n\n${items.join("\n")}\n\nDo you have any of these? Let me know! 🏆`;

  if (navigator.share) {
    try {
      await navigator.share({ text });
      return;
    } catch (error) {
      if (error.name === "AbortError") return;
    }
  }

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      showToast("📋 Copied to clipboard!");
      return;
    } catch {
      // Fall through to the textarea copy fallback for non-HTTPS browsers.
    }
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();

    if (copied) {
      showToast("📋 Copied to clipboard!");
      return;
    }
  } catch {
    // Final fallback below shows the text for manual copy.
  }

  window.alert(text);
}

function bindEvents() {
  injectStickerSheet();

  els.tabButtons.forEach((button) => {
    button.addEventListener("click", () => switchPage(button.dataset.page));
  });
  els.seeAllTeams.addEventListener("click", () => switchPage("statsPage"));
  els.helpFab.addEventListener("click", openHowToModal);
  els.howToCloseButton.addEventListener("click", () => closeHowToModal());
  els.howToCtaButton.addEventListener("click", () => closeHowToModal());
  els.howToOverlay.addEventListener("click", (event) => {
    if (event.target === els.howToOverlay) closeHowToModal();
  });
  els.openScanButton.addEventListener("click", openScanModal);
  els.closeScanButton.addEventListener("click", closeScanModal);
  els.scanInput.addEventListener("change", () => {
    const file = els.scanInput.files[0];
    state.selectedFile = file || null;
    els.analyzeButton.disabled = !file;
    els.scanError.classList.add("hidden");
    els.scanError.textContent = "";
    if (!file) {
      els.scanPreview.classList.remove("visible");
      els.scanPreview.removeAttribute("src");
      return;
    }
    els.scanPreview.src = URL.createObjectURL(file);
    els.scanPreview.classList.add("visible");
  });
  els.analyzeButton.addEventListener("click", analyzeScan);
  els.reviewGrid.addEventListener("click", (event) => {
    const quickButton = event.target.closest("[data-quick-action]");
    if (quickButton) {
      setAllReviewSlots(quickButton.dataset.quickAction);
      return;
    }

    const card = event.target.closest(".review-card");
    if (!card) return;
    const index = Number(card.dataset.index);
    const slot = state.reviewSlots[index];
    if (!slot) return;
    slot.status = slot.status === "owned" ? "missing" : "owned";
    card.classList.toggle("owned", slot.status === "owned");
    card.classList.toggle("missing", slot.status === "missing");
    card.querySelector(".state-badge").textContent = slot.status === "owned" ? "✓ Owned" : "✗ Missing";
    updateReviewCounter(true);
  });
  els.confirmButton.addEventListener("click", confirmScan);
  els.missingSearch.addEventListener("input", () => {
    state.missingSearch = els.missingSearch.value.trim();
    renderMissing();
  });
  els.missingList.addEventListener("click", (event) => {
    const card = event.target.closest(".missing-sticker-card");
    if (!card) return;

    openStickerSheet(
      card.dataset.stickerId,
      card.dataset.code,
      card.dataset.name,
      card.dataset.team
    );
  });
  els.specialMissingList.addEventListener("click", (event) => {
    const card = event.target.closest(".missing-sticker-card");
    if (!card) return;

    openStickerSheet(
      card.dataset.stickerId,
      card.dataset.code,
      card.dataset.name,
      card.dataset.team
    );
  });
  els.shareSwapButton.addEventListener("click", () => {
    shareSwapList().catch((error) => showToast(error.message));
  });
  els.shareMissingButton.addEventListener("click", () => {
    shareMissingList().catch((error) => showToast(error.message));
  });
  els.swapList.addEventListener("click", (event) => {
    const button = event.target.closest(".qty-btn");
    if (!button) return;

    const card = event.target.closest(".list-card");
    if (!card) return;

    button.disabled = true;
    const update = button.classList.contains("plus")
      ? incrementDuplicateQuantity(card)
      : decrementDuplicateQuantity(card);
    update
      .catch((error) => {
        showToast(error.message || "Could not update quantity");
        console.error(error);
      })
      .finally(() => {
        button.disabled = false;
      });
  });
  document.getElementById("albumPage").addEventListener("click", (event) => {
    const button = event.target.closest(".duplicate-add-btn");
    if (!button) return;
    event.stopPropagation();
    openDuplicateSheet(button.dataset.code, button.dataset.name, button.dataset.team);
  });

  const overlay = document.getElementById("sticker-sheet-overlay");
  const sheet = document.getElementById("sticker-sheet");
  document.getElementById("sheet-confirm").addEventListener("click", () => {
    if (state.sheetMode === "duplicate") {
      confirmDuplicateSticker(overlay.dataset.code, overlay.dataset.name, overlay.dataset.team);
      return;
    }
    confirmStickerOwned(
      overlay.dataset.stickerId,
      overlay.dataset.code,
      overlay.dataset.name,
      overlay.dataset.team
    );
  });
  document.getElementById("sheet-cancel").addEventListener("click", closeStickerSheet);
  overlay.addEventListener("click", (event) => {
    if (event.target.id === "sticker-sheet-overlay") {
      closeStickerSheet();
    }
  });
  sheet.addEventListener("touchstart", (event) => {
    state.sheetTouchStartY = event.changedTouches[0].clientY;
  });
  sheet.addEventListener("touchend", (event) => {
    const touchEndY = event.changedTouches[0].clientY;
    if (touchEndY - state.sheetTouchStartY > 80) {
      closeStickerSheet();
    }
  });
}

bindEvents();
refreshAllData();
