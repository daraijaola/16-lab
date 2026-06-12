/* ==========================================================================
   16 Lab — Lab page logic
   API layer is isolated below: MOCK=true runs the page fully offline today;
   when the FastAPI backend lands, set MOCK=false and the same UI drives
   the real endpoints. Nothing outside the API object touches the network.
   ========================================================================== */

(() => {
  "use strict";

  const CONFIG = {
    MOCK: true,
    API_BASE: "/api",
    MAX_FILE_BYTES: 50 * 1024 * 1024,
    ACCEPTED_EXT: ["mp3", "wav", "m4a", "webm"],
    POLL_MS: 1200,
  };

  /* Pipeline step definitions per analysis path. `sponsor` renders the
     small uppercase label so judges see which API powers each stage. */
  const PIPELINES = {
    upload: [
      { key: "isolate", name: "Isolate vocals", sponsor: "LALAL.AI" },
      { key: "transcribe", name: "Transcribe the bars", sponsor: "ElevenLabs Scribe" },
      { key: "match", name: "Match on Musixmatch", sponsor: "Musixmatch Pro" },
      { key: "decode", name: "Decode & score", sponsor: "Claude" },
    ],
    track: [
      { key: "lyrics", name: "Fetch lyrics", sponsor: "Musixmatch Pro" },
      { key: "decode", name: "Decode the bars", sponsor: "Claude" },
      { key: "score", name: "Score the pen", sponsor: "16 Lab engine" },
    ],
  };

  /* ------------------------------------------------------------------ */
  /* API layer                                                           */
  /* ------------------------------------------------------------------ */

  const MOCK_TRACKS = [
    {
      id: "mxm-starlight",
      title: "Starlight",
      artist: "Dave",
      album: "Single",
      hasLyrics: true,
      cover: "./assets/tracks/starlight-cover.jpg",
    },
    {
      id: "mxm-sprinter",
      title: "Sprinter",
      artist: "Dave & Central Cee",
      album: "Split Decision EP",
      hasLyrics: true,
      cover: null,
    },
    {
      id: "mxm-vossi",
      title: "Vossi Bop",
      artist: "Stormzy",
      album: "Heavy Is the Head",
      hasLyrics: true,
      cover: null,
    },
  ];

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const API = {
    async searchTracks(query) {
      if (CONFIG.MOCK) {
        await sleep(900);
        const q = query.trim().toLowerCase();
        return MOCK_TRACKS.filter(
          (t) =>
            t.title.toLowerCase().includes(q) ||
            t.artist.toLowerCase().includes(q)
        );
      }
      const res = await fetch(
        `${CONFIG.API_BASE}/search?q=${encodeURIComponent(query)}`
      );
      if (!res.ok) throw new Error(`Search failed (${res.status})`);
      return res.json();
    },

    /* Returns { jobId }. payload: {type:'track', trackId} | {type:'upload', file} */
    async startAnalysis(payload) {
      if (CONFIG.MOCK) {
        await sleep(400);
        return { jobId: `mock-${payload.type}-${Date.now()}` };
      }
      if (payload.type === "upload") {
        const form = new FormData();
        form.append("file", payload.file);
        const res = await fetch(`${CONFIG.API_BASE}/analyze/upload`, {
          method: "POST",
          body: form,
        });
        if (!res.ok) throw new Error(`Upload failed (${res.status})`);
        return res.json();
      }
      const res = await fetch(`${CONFIG.API_BASE}/analyze/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_id: payload.trackId }),
      });
      if (!res.ok) throw new Error(`Analysis failed (${res.status})`);
      return res.json();
    },

    /* Yields {stepKey, status:'active'|'done'|'error', result?} until done.
       Mock mode walks the pipeline on timers; upload resolves NO MATCH
       (the demo moment), track search resolves MATCH. */
    async *watchJob(jobId, pipelineType) {
      const steps = PIPELINES[pipelineType];
      if (CONFIG.MOCK) {
        for (const step of steps) {
          yield { stepKey: step.key, status: "active" };
          await sleep(1400 + Math.random() * 900);
          yield { stepKey: step.key, status: "done" };
        }
        yield {
          stepKey: null,
          status: "complete",
          result:
            pipelineType === "upload"
              ? {
                  match: false,
                  trackId: "upload-demo",
                  title: "Untitled freestyle",
                }
              : { match: true, trackId: "mxm-starlight", title: "Starlight" },
        };
        return;
      }
      // Real mode: poll the jobs endpoint until terminal state.
      while (true) {
        const res = await fetch(`${CONFIG.API_BASE}/jobs/${jobId}`);
        if (!res.ok) throw new Error(`Job poll failed (${res.status})`);
        const job = await res.json();
        for (const s of job.steps) {
          yield { stepKey: s.key, status: s.status };
        }
        if (job.status === "complete") {
          yield { stepKey: null, status: "complete", result: job.result };
          return;
        }
        if (job.status === "error") {
          throw new Error(job.error || "Analysis failed");
        }
        await sleep(CONFIG.POLL_MS);
      }
    },
  };

  /* ------------------------------------------------------------------ */
  /* DOM refs                                                            */
  /* ------------------------------------------------------------------ */

  const $ = (id) => document.getElementById(id);

  const els = {
    form: $("searchForm"),
    input: $("searchInput"),
    searchBtn: $("searchButton"),
    hint: $("searchHint"),
    loading: $("searchLoading"),
    results: $("searchResults"),
    empty: $("searchEmpty"),
    searchError: $("searchError"),
    emptyToUpload: $("emptyToUpload"),
    dropzone: $("dropzone"),
    fileInput: $("fileInput"),
    filePreview: $("filePreview"),
    fileName: $("fileName"),
    fileInfo: $("fileInfo"),
    runBtn: $("runButton"),
    clearFile: $("clearFile"),
    uploadError: $("uploadError"),
    pipelineSection: $("pipelineSection"),
    pipelineTitle: $("pipelineTitle"),
    pipelineSubject: $("pipelineSubject"),
    pipelineSteps: $("pipelineSteps"),
    verdict: $("verdict"),
    verdictBadge: $("verdictBadge"),
    verdictTitle: $("verdictTitle"),
    verdictText: $("verdictText"),
    verdictCta: $("verdictCta"),
  };

  let selectedFile = null;
  let jobRunning = false;

  /* ------------------------------------------------------------------ */
  /* Search                                                              */
  /* ------------------------------------------------------------------ */

  function setSearchState(state) {
    els.hint.hidden = state !== "idle";
    els.loading.hidden = state !== "loading";
    els.results.hidden = state !== "results";
    els.empty.hidden = state !== "empty";
    els.searchError.hidden = state !== "error";
  }

  function renderResults(tracks) {
    els.results.textContent = "";
    for (const track of tracks) {
      const li = document.createElement("li");
      li.className = "lab-result";

      const cover = track.cover
        ? Object.assign(document.createElement("img"), {
            src: track.cover,
            alt: `${track.title} cover art`,
          })
        : Object.assign(document.createElement("div"), {
            className: "lab-cover-tile",
            textContent: track.title.slice(0, 1).toUpperCase(),
          });

      const info = document.createElement("div");
      info.className = "lab-result-info";
      const title = document.createElement("strong");
      title.textContent = track.title;
      const meta = document.createElement("p");
      meta.textContent = `${track.artist} · ${track.album}`;
      info.append(title, meta);
      if (track.hasLyrics) {
        const badge = document.createElement("span");
        badge.className = "lab-has-lyrics";
        badge.textContent = "Lyrics available";
        info.append(badge);
      }

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "lab-analyze";
      btn.setAttribute("aria-label", `Analyze ${track.title} by ${track.artist}`);
      btn.append(document.createElement("span"));
      btn.addEventListener("click", () =>
        runPipeline("track", {
          trackId: track.id,
          subject: `${track.title} — ${track.artist}`,
        })
      );

      li.append(cover, info, btn);
      els.results.append(li);
    }
  }

  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = els.input.value.trim();
    if (query.length < 2) return;

    els.searchBtn.disabled = true;
    setSearchState("loading");
    try {
      const tracks = await API.searchTracks(query);
      if (tracks.length === 0) {
        setSearchState("empty");
      } else {
        renderResults(tracks);
        setSearchState("results");
      }
    } catch (err) {
      els.searchError.textContent = `Search hit a snag: ${err.message}. Try again.`;
      setSearchState("error");
    } finally {
      els.searchBtn.disabled = false;
    }
  });

  els.emptyToUpload.addEventListener("click", () => {
    els.dropzone.focus();
    els.dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  /* ------------------------------------------------------------------ */
  /* Upload                                                              */
  /* ------------------------------------------------------------------ */

  function fileExt(name) {
    return name.includes(".") ? name.split(".").pop().toLowerCase() : "";
  }

  function formatBytes(bytes) {
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  function showUploadError(msg) {
    els.uploadError.textContent = msg;
    els.uploadError.hidden = false;
  }

  function clearUploadError() {
    els.uploadError.hidden = true;
  }

  function acceptFile(file) {
    clearUploadError();
    if (!CONFIG.ACCEPTED_EXT.includes(fileExt(file.name))) {
      showUploadError(
        `"${file.name}" isn't a supported format. Use MP3, WAV, M4A, or WEBM.`
      );
      return;
    }
    if (file.size > CONFIG.MAX_FILE_BYTES) {
      showUploadError(
        `That file is ${formatBytes(file.size)} — the lab takes up to 50 MB. Trim the clip and retry.`
      );
      return;
    }

    selectedFile = file;
    els.fileName.textContent = file.name;
    els.fileInfo.textContent = formatBytes(file.size);
    els.filePreview.hidden = false;

    /* Read duration off the audio element; purely informational. */
    const url = URL.createObjectURL(file);
    const probe = new Audio();
    probe.preload = "metadata";
    probe.src = url;
    probe.addEventListener("loadedmetadata", () => {
      if (Number.isFinite(probe.duration)) {
        const m = Math.floor(probe.duration / 60);
        const s = String(Math.round(probe.duration % 60)).padStart(2, "0");
        els.fileInfo.textContent = `${formatBytes(file.size)} · ${m}:${s}`;
      }
      URL.revokeObjectURL(url);
    });
    probe.addEventListener("error", () => URL.revokeObjectURL(url));
  }

  function clearFile() {
    selectedFile = null;
    els.fileInput.value = "";
    els.filePreview.hidden = true;
    clearUploadError();
  }

  els.dropzone.addEventListener("click", () => els.fileInput.click());
  els.dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      els.fileInput.click();
    }
  });

  els.fileInput.addEventListener("change", () => {
    if (els.fileInput.files.length) acceptFile(els.fileInput.files[0]);
  });

  /* dragenter/dragleave fire on children too — count to avoid flicker. */
  let dragDepth = 0;
  els.dropzone.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dragDepth += 1;
    els.dropzone.classList.add("is-dragover");
  });
  els.dropzone.addEventListener("dragover", (e) => e.preventDefault());
  els.dropzone.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) els.dropzone.classList.remove("is-dragover");
  });
  els.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dragDepth = 0;
    els.dropzone.classList.remove("is-dragover");
    if (e.dataTransfer.files.length) acceptFile(e.dataTransfer.files[0]);
  });

  els.clearFile.addEventListener("click", clearFile);

  els.runBtn.addEventListener("click", () => {
    if (!selectedFile || jobRunning) return;
    runPipeline("upload", {
      file: selectedFile,
      subject: selectedFile.name,
    });
  });

  /* ------------------------------------------------------------------ */
  /* Pipeline                                                            */
  /* ------------------------------------------------------------------ */

  function renderSteps(pipelineType) {
    els.pipelineSteps.textContent = "";
    const stepEls = new Map();
    PIPELINES[pipelineType].forEach((step, i) => {
      const li = document.createElement("li");
      li.className = "lab-step";

      const num = document.createElement("span");
      num.className = "lab-step-num";
      num.textContent = String(i + 1);

      const info = document.createElement("div");
      info.className = "lab-step-info";
      const name = document.createElement("strong");
      name.textContent = step.name;
      const sponsor = document.createElement("span");
      sponsor.textContent = step.sponsor;
      info.append(name, sponsor);

      const state = document.createElement("span");
      state.className = "lab-step-state";
      state.textContent = "Queued";

      li.append(num, info, state);
      els.pipelineSteps.append(li);
      stepEls.set(step.key, { li, state });
    });
    return stepEls;
  }

  function showVerdict(result) {
    const isMatch = result.match;
    els.verdictBadge.className = `lab-verdict-badge ${isMatch ? "is-match" : "is-nomatch"}`;
    els.verdictBadge.textContent = isMatch ? "Catalog match" : "No match found";
    els.verdictTitle.textContent = isMatch
      ? `This is ${result.title}.`
      : "These bars aren't written down anywhere.";
    els.verdictText.textContent = isMatch
      ? "Matched on Musixmatch — licensed lyrics, metadata, and the full decode are ready."
      : "We checked the Musixmatch catalog and nothing matches. 16 Lab just transcribed and decoded bars no lyrics platform covers.";
    els.verdictCta.href = `./track.html?src=${isMatch ? "musixmatch" : "upload"}&id=${encodeURIComponent(result.trackId)}`;
    els.verdict.hidden = false;
    els.verdict.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function runPipeline(type, payload) {
    if (jobRunning) return;
    jobRunning = true;
    els.runBtn.disabled = true;

    els.verdict.hidden = true;
    els.pipelineTitle.textContent =
      type === "upload" ? "Running the lab" : "Pulling the track apart";
    els.pipelineSubject.textContent = payload.subject;
    const stepEls = renderSteps(type);
    els.pipelineSection.hidden = false;
    els.pipelineSection.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      const { jobId } = await API.startAnalysis({ type, ...payload });
      for await (const update of API.watchJob(jobId, type)) {
        if (update.status === "complete") {
          showVerdict(update.result);
          break;
        }
        const step = stepEls.get(update.stepKey);
        if (!step) continue;
        if (update.status === "active") {
          step.li.className = "lab-step is-active";
          step.state.textContent = "Running";
        } else if (update.status === "done") {
          step.li.className = "lab-step is-done";
          step.state.textContent = "Done";
        } else if (update.status === "error") {
          step.li.className = "lab-step is-error";
          step.state.textContent = "Failed";
        }
      }
    } catch (err) {
      els.pipelineSubject.textContent = `Something broke mid-scan: ${err.message}`;
    } finally {
      jobRunning = false;
      els.runBtn.disabled = false;
    }
  }
})();
