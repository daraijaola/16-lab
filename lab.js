/* ==========================================================================
   16 Lab — The Lab app shell
   Hash router + seeded demo data. The dashboard ships pre-loaded (a lab
   that's been cooking, never an empty shell). When the backend lands,
   SEED_DECODES is replaced by a fetch to /api/decodes and the mode chip
   flips off — nothing else changes.
   ========================================================================== */

(() => {
  "use strict";

  /* Demo seed — mirrors the three curated Musicathon demo clips. */
  const SEED_DECODES = [
    {
      id: "mxm-starlight",
      title: "Starlight",
      artist: "Dave",
      source: "match",
      score: 87,
      bars: 96,
      cover: "./assets/tracks/starlight-cover.jpg",
      when: "Today",
    },
    {
      id: "upload-fs-001",
      title: "Untitled freestyle 001",
      artist: "Unmatched on Musixmatch",
      source: "nomatch",
      score: 84,
      bars: 24,
      cover: null,
      when: "Today",
    },
    {
      id: "mxm-vossi",
      title: "Vossi Bop",
      artist: "Stormzy",
      source: "match",
      score: 81,
      bars: 88,
      cover: null,
      when: "Yesterday",
    },
  ];

  const SECTIONS = ["overview", "analyze", "decodes", "artists"];
  const TITLES = {
    overview: "Overview",
    analyze: "Analyze",
    decodes: "Decodes",
    artists: "Artists",
  };

  const $ = (id) => document.getElementById(id);

  /* ---------------- Router ---------------- */

  function currentSection() {
    const hash = location.hash.replace("#", "");
    return SECTIONS.includes(hash) ? hash : "overview";
  }

  function route() {
    const section = currentSection();
    for (const name of SECTIONS) {
      const el = $(`section-${name}`);
      if (el) el.hidden = name !== section;
    }
    document.querySelectorAll(".lab-nav a").forEach((a) => {
      const active = a.dataset.section === section;
      a.classList.toggle("is-active", active);
      if (active) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    $("appbarTitle").textContent = TITLES[section];
  }

  window.addEventListener("hashchange", route);

  /* ---------------- Decode rows ---------------- */

  function decodeRow(d) {
    const row = document.createElement("a");
    row.className = "lab-decode";
    row.href = `./track.html?src=${d.source === "match" ? "musixmatch" : "upload"}&id=${encodeURIComponent(d.id)}`;

    let cover;
    if (d.cover) {
      cover = document.createElement("img");
      cover.src = d.cover;
      cover.alt = `${d.title} cover art`;
    } else {
      cover = document.createElement("div");
      cover.className = `lab-cover-tile${d.source === "nomatch" ? " is-freestyle" : ""}`;
      cover.textContent = d.title.slice(0, 1).toUpperCase();
    }

    const info = document.createElement("div");
    info.className = "lab-decode-info";
    const title = document.createElement("strong");
    title.textContent = d.title;
    const meta = document.createElement("span");
    meta.textContent = `${d.artist} · ${d.bars} bars · ${d.when}`;
    info.append(title, meta);

    const chip = document.createElement("span");
    chip.className = `lab-source-chip ${d.source === "match" ? "is-match" : "is-nomatch"}`;
    chip.textContent = d.source === "match" ? "Catalog match" : "No match";

    const score = document.createElement("span");
    score.className = "lab-decode-score";
    score.innerHTML = `${d.score}<small>/100</small>`;

    row.append(cover, info, chip, score);
    return row;
  }

  function renderDecodes() {
    const recent = $("recentList");
    const all = $("decodeList");
    recent.textContent = "";
    all.textContent = "";
    SEED_DECODES.forEach((d, i) => {
      const li = document.createElement("li");
      li.append(decodeRow(d));
      all.append(li);
      if (i < 3) {
        const li2 = document.createElement("li");
        li2.append(decodeRow(d));
        recent.append(li2);
      }
    });
    $("decodesCount").textContent = String(SEED_DECODES.length);
  }

  /* ---------------- Stats ---------------- */

  function renderStats() {
    const tracks = SEED_DECODES.length;
    const bars = SEED_DECODES.reduce((n, d) => n + d.bars, 0);
    const avg = Math.round(
      SEED_DECODES.reduce((n, d) => n + d.score, 0) / Math.max(1, tracks)
    );
    const unmatchedBars = SEED_DECODES.filter((d) => d.source === "nomatch")
      .reduce((n, d) => n + d.bars, 0);

    $("statTracks").textContent = String(tracks);
    $("statBars").textContent = String(bars);
    $("statScore").textContent = String(avg);
    $("statUnmatched").textContent = String(unmatchedBars);
  }

  /* ---------------- Init ---------------- */

  renderDecodes();
  renderStats();
  route();
})();
