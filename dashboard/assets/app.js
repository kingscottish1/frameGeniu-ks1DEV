(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = {
    csrf: "",
    user: "",
    timer: null,
    active: null,
    busy: false,
    chat: [],
    files: [],
    thoughtTimer: null,
  };

  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (state.csrf && opts.method && opts.method !== "GET") headers["X-CSRF-Token"] = state.csrf;
    const res = await fetch(path, Object.assign({}, opts, { headers, credentials: "same-origin" }));
    if (res.status === 401) throw new Error("auth");
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail;
      const msg = (detail && detail.error) || (typeof detail === "string" ? detail : res.statusText);
      throw new Error(msg || "request failed");
    }
    return data;
  }

  function showApp() {
    const gate = $("#gate");
    if (gate) gate.hidden = true;
    const app = $("#app");
    if (app) app.hidden = false;
    if (window.FrameGeniusWaves) window.FrameGeniusWaves.scan();
  }

  async function boot() {
    drawGrid();
    tickClock();
    setInterval(tickClock, 1000);
    showApp();
    try {
      const me = await api("/api/v1/auth/me");
      state.csrf = me.csrf || "dev";
      state.user = me.username || "studio";
      if ($("#who")) $("#who").textContent = "studio";
    } catch (_) {
      state.csrf = "dev";
    }
    try {
      await refreshAll();
      await loadPreflight();
    } catch (_) { /* still show the studio */ }
    state.timer = setInterval(refreshQuiet, 4000);
  }

  $$(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".nav-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const view = btn.dataset.view;
      $$(".view").forEach((el) => { el.hidden = el.id !== `view-${view}`; });
      const titles = {
        overview: ["Command", "Overview"],
        generate: ["Create", "Generate"],
        agent: ["Crown AI", "Crown"],
        reskin: ["Clean", "Upload"],
        factory: ["Print", "Factory"],
        queue: ["Monitor", "Queue"],
        library: ["Archive", "Library"],
        vault: ["Security", "Vault"],
        settings: ["Control", "Settings"],
      };
      $("#view-kicker").textContent = titles[view][0];
      $("#view-title").textContent = titles[view][1];
      if (view === "queue" || view === "library") refreshQuiet();
      if (view === "settings") loadSettings();
      if (view === "factory") loadFactory();
      if (view === "agent" && window.FrameGeniusWaves) window.FrameGeniusWaves.scan($("#view-agent"));
    });
  });

  const CRIME_HINT = /kingpin|murder|mafia|cartel|crime|killer|detective|prison|gangster|heist|homicide|mobster|kinahan|narco|hitman|kidnap/i;
  if ($("#template")) {
    $("#template").addEventListener("change", () => { state.templateTouched = true; });
  }
  if ($("#topic")) {
    $("#topic").addEventListener("input", () => {
      const t = $("#template");
      if (!t || state.templateTouched) return;
      if (CRIME_HINT.test($("#topic").value || "")) t.value = "crime";
    });
  }

  if ($("#dur-pills")) {
    $("#dur-pills").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-sec]");
      if (!btn) return;
      $$("#dur-pills button").forEach((b) => b.classList.toggle("on", b === btn));
      $("#duration").value = btn.dataset.sec;
      if (window.FrameGeniusWaves) window.FrameGeniusWaves.scan($("#dur-pills"));
    });
  }

  if ($("#gen-form")) $("#gen-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (state.busy) return;
    const payload = {
      topic: $("#topic").value.trim(),
      script_text: $("#script").value.trim() || null,
      template: $("#template").value,
      aspect_ratio: $("#aspect").value,
      voice: $("#voice").value,
      duration: Number($("#duration").value),
      subtitle_enabled: $("#subs").checked,
      bgm_enabled: $("#bgm").checked,
      research_enabled: !$("#research") || $("#research").checked,
      llm_provider: ($("#llm-provider") && $("#llm-provider").value) || "auto",
      ollama_model: ($("#ollama-model") && $("#ollama-model").value) || null,
      cut_shorts: !$("#shorts") || $("#shorts").checked,
      dual_export: !$("#dual") || $("#dual").checked,
      hook_lock: !$("#hooklock") || $("#hooklock").checked,
      series_name: ($("#series-name") && $("#series-name").value.trim()) || null,
      series_part: ($("#series-part") && $("#series-part").value) ? Number($("#series-part").value) : null,
      series_total: ($("#series-total") && $("#series-total").value) ? Number($("#series-total").value) : null,
    };
    const box = $("#gen-status");
    const btn = $("#render-btn");
    box.hidden = false;
    box.innerHTML = `<p>Queueing a real render…</p><div class="bar"><i style="width:4%"></i></div>`;
    state.busy = true;
    if (btn) btn.disabled = true;
    try {
      const rec = await api("/api/v1/videos", { method: "POST", body: JSON.stringify(payload) });
      state.active = rec.task_id;
      await pollTask(rec.task_id, $("#gen-status"));
    } catch (err) {
      box.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    } finally {
      state.busy = false;
      if (btn) btn.disabled = false;
    }
  });

  if ($("#agent-form")) $("#agent-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    sendAgent(false);
  });
  if ($("#agent-draw")) $("#agent-draw").addEventListener("click", () => sendAgent(true));
  if ($("#agent-attach")) $("#agent-attach").addEventListener("click", () => $("#agent-file") && $("#agent-file").click());
  if ($("#agent-file")) $("#agent-file").addEventListener("change", () => {
    ingestFiles($("#agent-file").files);
    $("#agent-file").value = "";
  });
  const desk = $("#agent-desk");
  if (desk) {
    desk.addEventListener("dragover", (ev) => { ev.preventDefault(); desk.classList.add("drop"); });
    desk.addEventListener("dragleave", () => desk.classList.remove("drop"));
    desk.addEventListener("drop", (ev) => {
      ev.preventDefault();
      desk.classList.remove("drop");
      ingestFiles(ev.dataTransfer && ev.dataTransfer.files);
    });
  }

  const THOUGHTS = ["thinking", "still working", "give me a sec"];

  async function ingestFiles(list) {
    if (!list || !list.length) return;
    for (const file of [...list].slice(0, 4)) {
      try {
        const body = new FormData();
        body.append("file", file);
        const headers = {};
        if (state.csrf) headers["X-CSRF-Token"] = state.csrf;
        const res = await fetch("/api/v1/agent/upload", { method: "POST", body, headers, credentials: "same-origin" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error((data.detail && data.detail.error) || data.detail || "upload failed");
        state.files.push(data);
      } catch (err) {
        state.chat.push({ role: "assistant", content: err.message || "Couldn't take that file." });
      }
    }
    renderChips();
    renderChat();
  }

  function renderChips() {
    const row = $("#agent-chips");
    if (!row) return;
    if (!state.files.length) {
      row.hidden = true;
      row.innerHTML = "";
      return;
    }
    row.hidden = false;
    row.innerHTML = state.files.map((f, i) =>
      `<span class="chip-file">${esc(f.filename || "file")} <button type="button" data-i="${i}">×</button></span>`
    ).join("");
    row.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.files.splice(Number(btn.dataset.i), 1);
        renderChips();
      });
    });
  }

  function startThoughts() {
    stopThoughts();
    let n = 0;
    const tick = () => {
      const el = $("#ghost-letters");
      if (!el) return;
      const phrase = n > 12 ? "still working — long answers take a bit" : THOUGHTS[n % THOUGHTS.length];
      el.innerHTML = [...phrase].map((ch) => `<span>${ch === " " ? "&nbsp;" : esc(ch)}</span>`).join("");
      n += 1;
    };
    tick();
    state.thoughtTimer = setInterval(tick, 2200);
  }

  function stopThoughts() {
    if (state.thoughtTimer) {
      clearInterval(state.thoughtTimer);
      state.thoughtTimer = null;
    }
  }

  async function sendAgent(draw) {
    const input = $("#agent-input");
    const text = (input.value || "").trim();
    const attachments = state.files.slice();
    if (!text && !attachments.length && !draw) return;
    input.value = "";
    const shown = text || (draw ? "Make a picture" : attachments.map((f) => f.filename).join(", "));
    const userImages = attachments.filter((f) => f.kind === "image" && f.url).map((f) => ({ url: f.url, prompt: f.filename }));
    state.chat.push({ role: "user", content: shown, images: userImages });
    state.files = [];
    renderChips();
    state.chat.push({ role: "assistant", pending: true, content: "" });
    renderChat();
    startThoughts();
    const sendBtn = $("#agent-send");
    if (sendBtn) sendBtn.disabled = true;
    try {
      const data = await api("/api/v1/agent/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text || (draw ? "a picture" : ""),
          draw: !!draw,
          history: state.chat.filter((item) => !item.pending).slice(0, -1).slice(-16),
          attachments,
        }),
      });
      stopThoughts();
      state.chat = state.chat.filter((item) => !item.pending);
      state.chat.push({
        role: "assistant",
        content: data.reply || "Here.",
        images: data.images || [],
      });
      renderChat();
    } catch (err) {
      stopThoughts();
      state.chat = state.chat.filter((item) => !item.pending);
      state.chat.push({ role: "assistant", content: err.message || "Couldn't answer." });
      renderChat();
    } finally {
      if (sendBtn) sendBtn.disabled = false;
      input.focus();
    }
  }

  function renderChat() {
    const log = $("#agent-log");
    if (!log) return;
    log.innerHTML = state.chat.map((item) => {
      if (item.pending) {
        return `<div class="bubble agent thought">
          <div class="thought-pills"><i>working</i><i>looking</i><i>one sec</i></div>
          <div class="ghost-letters" id="ghost-letters"></div>
        </div>`;
      }
      const who = item.role === "user" ? "user" : "agent";
      const pics = (item.images || []).map((img) =>
        `<a href="${esc(img.url)}" target="_blank"><img src="${esc(img.url)}" alt="${esc(img.prompt || "picture")}" /></a>`
      ).join("");
      return `<div class="bubble ${who}">${esc(item.content)}${pics}</div>`;
    }).join("");
    log.scrollTop = log.scrollHeight;
    if (window.FrameGeniusWaves) window.FrameGeniusWaves.scan($("#view-agent"));
  }


  let reskinFile = null;
  const drop = $("#reskin-drop");
  const fileInput = $("#reskin-file");
  if (drop && fileInput) {
    drop.addEventListener("click", () => fileInput.click());
    const take = (list) => {
      const f = list && list[0];
      if (!f) return;
      reskinFile = f;
      if ($("#reskin-name")) $("#reskin-name").textContent = f.name + " · " + Math.round(f.size / 1048576) + " MB";
    };
    fileInput.addEventListener("change", () => take(fileInput.files));
    drop.addEventListener("dragover", (ev) => { ev.preventDefault(); drop.classList.add("hot"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("hot"));
    drop.addEventListener("drop", (ev) => {
      ev.preventDefault();
      drop.classList.remove("hot");
      take(ev.dataTransfer && ev.dataTransfer.files);
    });
  }
  if ($("#reskin-form")) $("#reskin-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const box = $("#reskin-status");
    const btn = $("#reskin-btn");
    if (!reskinFile) {
      if (box) { box.hidden = false; box.innerHTML = `<p class="error">Drop a video first.</p>`; }
      return;
    }
    if (reskinFile.size > 400 * 1048576) {
      if (box) { box.hidden = false; box.innerHTML = `<p class="error">400 MB max.</p>`; }
      return;
    }
    const body = new FormData();
    body.append("file", reskinFile);
    body.append("topic", ($("#reskin-topic") && $("#reskin-topic").value.trim()) || "");
    body.append("aspect_ratio", ($("#reskin-aspect") && $("#reskin-aspect").value) || "9:16");
    body.append("bleep", ($("#reskin-bleep") && $("#reskin-bleep").checked) ? "1" : "0");
    if (box) { box.hidden = false; box.innerHTML = `<p>Uploading…</p><div class="bar"><i style="width:6%"></i></div>`; }
    if (btn) btn.disabled = true;
    try {
      const headers = {};
      if (state.csrf) headers["X-CSRF-Token"] = state.csrf;
      const res = await fetch("/api/v1/reskin", { method: "POST", body, headers, credentials: "same-origin" });
      const rec = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = rec.detail;
        const msg = (detail && detail.error) || (typeof detail === "string" ? detail : res.statusText);
        throw new Error(msg || "upload failed");
      }
      state.active = rec.task_id;
      await pollTask(rec.task_id, box);
    } catch (err) {
      if (box) box.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  async function pollTask(id, boxEl) {
    const box = boxEl || $("#gen-status");
    if (!box) return;
    const seconds = Number($("#duration")?.value || 30);
    const maxPolls = Math.max(2000, Math.ceil(seconds * 12));
    for (let i = 0; i < maxPolls; i++) {
      const rec = await api(`/api/v1/tasks/${id}`);
      const pct = rec.progress || 0;
      const stage = rec.stage || "working";
      const msg = rec.message || "";
      box.innerHTML = `
        <p><b>${esc(stage)}</b> · ${pct}%</p>
        <p class="muted">${esc(msg)}</p>
        <div class="bar"><i style="width:${pct}%"></i></div>`;
      if (rec.state === "completed") {
        const stream = `/api/v1/videos/${id}/stream`;
        const dl = `/api/v1/videos/${id}/download`;
        const kit = `/api/v1/videos/${id}/kit`;
        const caps = `/api/v1/videos/${id}/captions`;
        const tagsUrl = `/api/v1/videos/${id}/tags`;
        const file = rec.result?.filename || `${id}.mp4`;
        const secs = rec.result?.duration ? rec.result.duration.toFixed(1) : "—";
        const tags = rec.result?.hashtags || rec.result?.tags || [];
        const tagLine = tags.map(esc).join(" ");
        const titles = rec.result?.titles || rec.result?.postkit?.titles || [];
        const hook = rec.result?.hook || "";
        const shortsN = rec.result?.shorts_count || 0;
        const shortsBtn = shortsN
          ? `<a class="wave-btn" data-wave href="/api/v1/videos/${id}/shorts" download><span>Shorts (${shortsN})</span></a>`
          : "";
        const wideBtn = rec.result?.companion_url
          ? `<a class="wave-btn" data-wave href="${rec.result.companion_url}" download><span>Wide cut</span></a>`
          : "";
        const today = rec.result?.today_folder
          ? `<p class="muted path">TODAY folder · ${esc(rec.result.today_folder)}</p>`
          : "";
        box.innerHTML = `
          <p class="ok">Ready to post · ${esc(file)} · ${secs}s</p>
          ${hook ? `<p class="muted">${esc(hook)}</p>` : ""}
          ${titles.length ? `<ul class="titles">${titles.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}
          <div class="bar"><i style="width:100%"></i></div>
          <div class="result-actions">
            <a class="wave-btn gold" data-wave href="${dl}" download="${esc(file)}"><span>Download MP4</span></a>
            <a class="wave-btn" data-wave href="${caps}" download="${id}.srt"><span>Captions</span></a>
            <a class="wave-btn" data-wave href="${tagsUrl}" download="${id}_tags.txt"><span>Tags</span></a>
            ${shortsBtn}
            ${wideBtn}
            <a class="wave-btn" data-wave href="${kit}" download><span>Post kit</span></a>
            <button type="button" class="wave-btn" data-wave data-pub="youtube" data-id="${id}"><span>YouTube</span></button>
            <button type="button" class="wave-btn" data-wave data-pub="tiktok" data-id="${id}"><span>TikTok</span></button>
            <a class="wave-btn" data-wave href="${stream}" target="_blank"><span>Open file</span></a>
          </div>
          ${tagLine ? `<p class="tagline" id="tag-line">${tagLine}</p>
            <button type="button" class="wave-btn" id="copy-tags" data-wave><span>Copy tags</span></button>` : ""}
          <img src="/api/v1/videos/${id}/thumbnail" alt="" style="width:100%;max-height:280px;object-fit:cover;border-radius:14px;margin-top:10px" onerror="this.remove()" />
          <video src="${stream}" controls playsinline style="width:100%;margin-top:12px;border-radius:14px;background:#000"></video>
          <p class="muted path">${esc(rec.result?.video_path || "")}</p>
          ${today}`;
        const copy = $("#copy-tags");
        if (copy) copy.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(tags.join(" "));
            copy.querySelector("span").textContent = "Copied";
          } catch (_) {
            copy.querySelector("span").textContent = "Select the tags above";
          }
        });
        bindPublish(box);
        if (window.FrameGeniusWaves) window.FrameGeniusWaves.scan(box);
        refreshQuiet();
        return;
      }
      if (rec.state === "failed") {
        box.innerHTML += `<p class="error">${esc(rec.error || rec.message || "Render failed")}</p>
          <button class="wave-btn" type="button" id="retry-btn" data-wave><span>Try again</span></button>`;
        const retry = $("#retry-btn");
        if (retry) retry.addEventListener("click", () => $("#gen-form").requestSubmit());
        if (window.FrameGeniusWaves) window.FrameGeniusWaves.scan(box);
        return;
      }
      await sleep(1200);
    }
    box.innerHTML += `<p class="error">Timed out waiting for the render. Check Queue.</p>`;
  }

  async function loadFactory(niche) {
    const box = $("#trends");
    if (!box) return;
    box.innerHTML = `<p class="muted">Scanning…</p>`;
    try {
      const data = await api(`/api/v1/factory/trends?niche=${encodeURIComponent(niche || "all")}`);
      box.innerHTML = (data.items || []).map((item) =>
        `<button type="button" class="trend" data-topic="${esc(item.title)}"><b>${esc(item.title)}</b><small>${esc(item.source || "")}</small></button>`
      ).join("") || empty("No trends right now.");
      box.querySelectorAll(".trend").forEach((btn) => {
        btn.addEventListener("click", () => {
          const topic = btn.dataset.topic || btn.textContent;
          if ($("#topic")) $("#topic").value = topic;
          const gen = document.querySelector('[data-view="generate"]');
          if (gen) gen.click();
        });
      });
    } catch (err) {
      box.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    }
    if (window.FrameGeniusWaves) window.FrameGeniusWaves.scan($("#view-factory"));
  }

  if ($("#trend-niches")) {
    $("#trend-niches").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-niche]");
      if (!btn) return;
      $$("#trend-niches button").forEach((b) => b.classList.toggle("on", b === btn));
      loadFactory(btn.dataset.niche);
    });
  }

  if ($("#batch-form")) $("#batch-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const raw = ($("#batch-topics").value || "").split(/\n+/).map((s) => s.trim()).filter(Boolean);
    const box = $("#batch-status");
    box.hidden = false;
    if (!raw.length) {
      box.innerHTML = `<p class="error">Paste at least one topic.</p>`;
      return;
    }
    const body = {
      topics: raw,
      template: ($("#template") && $("#template").value) || "auto",
      aspect_ratio: ($("#aspect") && $("#aspect").value) || "9:16",
      voice: ($("#voice") && $("#voice").value) || "en-GB-LibbyNeural",
      duration: Number($("#duration") && $("#duration").value) || 30,
      subtitle_enabled: !$("#subs") || $("#subs").checked,
      bgm_enabled: !$("#bgm") || $("#bgm").checked,
      research_enabled: !$("#research") || $("#research").checked,
      llm_provider: ($("#llm-provider") && $("#llm-provider").value) || "auto",
      ollama_model: ($("#ollama-model") && $("#ollama-model").value) || null,
      cut_shorts: !$("#shorts") || $("#shorts").checked,
      dual_export: !$("#dual") || $("#dual").checked,
      hook_lock: !$("#hooklock") || $("#hooklock").checked,
      series_name: ($("#batch-series") && $("#batch-series").value.trim()) || null,
    };
    try {
      const rec = await api("/api/v1/factory/batch", { method: "POST", body: JSON.stringify(body) });
      box.innerHTML = `<p class="ok">Queued ${rec.count} films. Watch Queue.</p>`;
      const q = document.querySelector('[data-view="queue"]');
      if (q) q.click();
    } catch (err) {
      box.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    }
  });

  if ($("#channel-form")) $("#channel-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = {
      name: $("#ch-name").value.trim(),
      handle: $("#ch-handle").value.trim(),
      cta_text: $("#ch-cta").value.trim(),
      intro_enabled: $("#ch-intro").checked,
      cta_enabled: $("#ch-end").checked,
      watermark: $("#ch-mark").checked,
    };
    try {
      await api("/api/v1/factory/channel", { method: "PUT", body: JSON.stringify(body) });
      alert("Channel saved.");
    } catch (err) {
      alert(err.message);
    }
  });

  function freshSecret(el) {
    const v = ((el && el.value) || "").trim();
    if (!v || v.includes("****")) return "";
    return v;
  }

  async function connectYouTube() {
    try {
      const rec = await api("/api/v1/publish/youtube/auth");
      if (rec.auth_url) window.open(rec.auth_url, "yt-oauth", "width=560,height=740");
    } catch (err) {
      alert(err.message);
    }
  }

  async function refreshPublishStatus() {
    const el = $("#yt-status");
    try {
      const s = await api("/api/v1/publish/status");
      if (!el) return;
      const bits = [];
      if (s.youtube_connected) bits.push("YouTube connected");
      else if (s.youtube_configured) bits.push("YouTube client saved — click Connect YouTube");
      else bits.push("YouTube: paste OAuth client, Save, then Connect");
      bits.push(s.pexels ? "Pexels on" : "Pexels optional");
      bits.push("Coverr B-roll on");
      bits.push(s.whisper && s.whisper.ready ? "Speech-to-text ready (bleeps)" : "Bleeps: pip install vosk in .venv");
      el.textContent = bits.join(" · ");
    } catch (_) { /* optional */ }
  }

  async function publishFilm(id, platform) {
    if (!id) return;
    try {
      const rec = await api(`/api/v1/publish/${id}`, {
        method: "POST",
        body: JSON.stringify({ platform, privacy: "unlisted" }),
      });
      if (rec.need_client) {
        alert(rec.message || "Paste a free Google OAuth client id + secret in Settings first.");
        const btn = document.querySelector('[data-view="settings"]');
        if (btn) btn.click();
        return;
      }
      if (rec.need_auth) {
        await connectYouTube();
        return;
      }
      if (rec.watch_url) {
        window.open(rec.watch_url, "_blank");
        return;
      }
      if (rec.studio_url) {
        try { await navigator.clipboard.writeText(rec.caption || ""); } catch (_) { /* ignore */ }
        window.open(rec.studio_url, "_blank");
        alert(rec.message || "Caption copied. Drop the MP4 in TikTok Studio.");
        return;
      }
      if (rec.ok) alert(rec.message || "Posted.");
      else alert(rec.message || "Publish failed.");
    } catch (err) {
      alert(err.message);
    }
  }

  function bindPublish(root) {
    if (!root) return;
    root.querySelectorAll("[data-pub]").forEach((btn) => {
      btn.addEventListener("click", () => publishFilm(btn.dataset.id, btn.dataset.pub));
    });
  }

  if ($("#yt-connect")) $("#yt-connect").addEventListener("click", (ev) => {
    ev.preventDefault();
    connectYouTube();
  });

  if ($("#cfg-form")) $("#cfg-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = {
      llm: { provider: $("#cfg-llm").value },
      tts: { provider: $("#cfg-tts").value },
      media: { provider: $("#cfg-media").value },
    };
    if ($("#cfg-ollama-model") && $("#cfg-ollama-model").value) body.llm.ollama_model = $("#cfg-ollama-model").value;
    if ($("#cfg-ollama-url") && $("#cfg-ollama-url").value) body.llm.ollama_base_url = $("#cfg-ollama-url").value;
    const openai = freshSecret($("#cfg-openai"));
    if (openai) body.llm.openai_api_key = openai;
    const pexels = freshSecret($("#cfg-pexels"));
    if (pexels) body.media.pexels_api_keys = [pexels];
    const ytId = (($("#cfg-yt-id") && $("#cfg-yt-id").value) || "").trim();
    if (ytId && !ytId.includes("****")) {
      body.upload = body.upload || {};
      body.upload.youtube_client_id = ytId;
    }
    const ytSec = freshSecret($("#cfg-yt-secret"));
    if (ytSec) {
      body.upload = body.upload || {};
      body.upload.youtube_client_secret = ytSec;
    }
    try {
      await api("/api/v1/config", { method: "PUT", body: JSON.stringify(body) });
      alert("Saved.");
      loadPreflight();
      refreshPublishStatus();
    } catch (err) {
      alert(err.message);
    }
  });

  async function refreshAll() {
    await Promise.all([loadStats(), loadVoices(), refreshQuiet()]);
  }

  async function refreshQuiet() {
    try {
      const data = await api("/api/v1/tasks");
      renderQueue(data.items || []);
      renderLibrary(data.items || []);
    } catch (_) { /* ignore */ }
  }

  async function loadStats() {
    try {
      await api("/api/v1/studio/stats");
    } catch (_) { /* optional */ }
  }

  async function loadPreflight() {
    const el = $("#preflight");
    try {
      const s = await api("/api/v1/studio/preflight");
      const pills = [
        pill("FFmpeg", s.ffmpeg),
        pill(s.ollama ? `Ollama · ${(s.ollama_model || "ready")}` : "Ollama offline", s.ollama),
        pill(`Voice · ${s.tts || "edge"}`, true),
        pill(s.whisper ? "Bleeps ready" : "Bleeps: pip install vosk", s.whisper),
        pill("Coverr B-roll", true),
      ];
      if (s.pexels) pills.push(pill("Pexels", true));
      if (s.youtube) pills.push(pill("YouTube connected", true));
      else if (s.youtube_configured) pills.push(pill("YouTube — Connect", false));
      pills.push(pill(`Disk ${s.disk_free_mb} MB`, s.disk_free_mb > 400));
      if (el) el.innerHTML = pills.join("");
      const label = $("#ready-label");
      if (label) label.textContent = s.ffmpeg ? "ready" : "need ffmpeg";
    } catch (_) {
      if (el) el.innerHTML = "";
    }
  }

  function pill(text, ok) {
    return `<span class="pill ${ok ? "on" : "off"}">${esc(text)}</span>`;
  }

  async function loadSettings() {
    const [cfg, opt] = await Promise.all([api("/api/v1/config"), api("/api/v1/config/options")]);
    fillSelect($("#cfg-llm"), opt.llm_providers, cfg.llm?.provider);
    fillSelect($("#cfg-tts"), opt.tts_providers, cfg.tts?.provider);
    fillSelect($("#cfg-media"), opt.media_providers, cfg.media?.provider);
    const ollamaList = (opt.ollama_models && opt.ollama_models.length)
      ? opt.ollama_models
      : (opt.suggested_models || ["gemma4:latest"]);
    if ($("#cfg-ollama-model")) fillSelect($("#cfg-ollama-model"), ollamaList, cfg.llm?.ollama_model || opt.ollama_model);
    if ($("#cfg-ollama-url")) $("#cfg-ollama-url").value = cfg.llm?.ollama_base_url || "http://127.0.0.1:11434";
    if ($("#cfg-yt-id")) $("#cfg-yt-id").value = (cfg.upload && cfg.upload.youtube_client_id) || "";
    refreshPublishStatus();
    if ($("#ollama-model")) fillSelect($("#ollama-model"), ollamaList, cfg.llm?.ollama_model || ollamaList[0]);
      if ($("#llm-provider") && cfg.llm?.provider) {
      const mapped = cfg.llm.provider === "demo" ? "studio" : cfg.llm.provider;
      $("#llm-provider").value = mapped;
    }
    try {
      const ch = await api("/api/v1/factory/channel");
      if ($("#ch-name")) $("#ch-name").value = ch.name || "";
      if ($("#ch-handle")) $("#ch-handle").value = ch.handle || "";
      if ($("#ch-cta")) $("#ch-cta").value = ch.cta_text || "";
      if ($("#ch-intro")) $("#ch-intro").checked = ch.intro_enabled !== false;
      if ($("#ch-end")) $("#ch-end").checked = ch.cta_enabled !== false;
      if ($("#ch-mark")) $("#ch-mark").checked = !!ch.watermark;
    } catch (_) { /* optional */ }
  }

  async function loadVoices() {
    try {
      const opt = await api("/api/v1/config/options");
      fillSelect($("#voice"), opt.voices, "en-GB-LibbyNeural");
      const ollamaList = (opt.ollama_models && opt.ollama_models.length)
        ? opt.ollama_models
        : (opt.suggested_models || ["gemma4:latest"]);
      if ($("#ollama-model")) fillSelect($("#ollama-model"), ollamaList, opt.ollama_model || ollamaList[0]);
    } catch (_) {
      fillSelect($("#voice"), ["en-GB-LibbyNeural"], "en-GB-LibbyNeural");
    }
  }

  function renderQueue(items) {
    $("#queue").innerHTML = items.map((item) => {
      const st = item.state;
      return `<div class="row"><div><b>${esc(item.params?.topic || item.task_id)}</b><br><small>${esc(item.stage)} · ${esc(st)}</small></div><div>${item.progress}%</div></div>`;
    }).join("") || empty("Queue is clear");
  }

  function renderLibrary(items) {
    const done = items.filter((i) => i.state === "completed");
    const lib = $("#library");
    if (!lib) return;
    lib.innerHTML = done.map((item) => {
      const file = item.result?.filename || `${item.task_id}.mp4`;
      return `
      <article class="card">
        <img src="/api/v1/videos/${item.task_id}/thumbnail" alt="" onerror="this.replaceWith(document.createElement('div'))" />
        <div class="pad">
          <b>${esc(item.result?.title || item.params?.topic)}</b>
          <p class="muted">${esc(file)}</p>
          <div class="result-actions">
            <a class="wave-btn gold" data-wave href="/api/v1/videos/${item.task_id}/download" download="${esc(file)}"><span>Download</span></a>
            <a class="wave-btn" data-wave href="/api/v1/videos/${item.task_id}/captions" download><span>Captions</span></a>
            <a class="wave-btn" data-wave href="/api/v1/videos/${item.task_id}/tags" download><span>Tags</span></a>
            ${item.result?.shorts_count ? `<a class="wave-btn" data-wave href="/api/v1/videos/${item.task_id}/shorts" download><span>Shorts</span></a>` : ""}
            <a class="wave-btn" data-wave href="/api/v1/videos/${item.task_id}/kit" download><span>Kit</span></a>
            <button type="button" class="wave-btn" data-wave data-pub="youtube" data-id="${item.task_id}"><span>YouTube</span></button>
            <button type="button" class="wave-btn" data-wave data-pub="tiktok" data-id="${item.task_id}"><span>TikTok</span></button>
            <a class="wave-btn" data-wave href="/api/v1/videos/${item.task_id}/stream" target="_blank"><span>Play</span></a>
          </div>
        </div>
      </article>`;
    }).join("") || empty("Nothing in the archive yet.");
    bindPublish(lib);
    if (window.FrameGeniusWaves) window.FrameGeniusWaves.scan($("#library"));
  }

  function empty(text) { return `<p class="muted">${esc(text)}</p>`; }
  function fillSelect(el, items, current) {
    if (!el) return;
    el.innerHTML = items.map((v) => `<option ${v === current ? "selected" : ""}>${esc(v)}</option>`).join("");
  }
  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
  function tickClock() {
    const el = $("#clock");
    if (el) el.textContent = new Date().toLocaleTimeString();
  }

  function drawGrid() {
    const canvas = $("#grid");
    const ctx = canvas.getContext("2d");
    const paint = () => {
      canvas.width = innerWidth * devicePixelRatio;
      canvas.height = innerHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      ctx.strokeStyle = "rgba(225,29,46,0.10)";
      ctx.lineWidth = 1;
      const step = 42;
      for (let x = 0; x < innerWidth; x += step) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, innerHeight); ctx.stroke();
      }
      for (let y = 0; y < innerHeight; y += step) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(innerWidth, y); ctx.stroke();
      }
    };
    paint();
    addEventListener("resize", paint);
  }

  boot();
})();
