/* Liquid sine-wave hover for .wave-btn — kingscottishDEV N.A.S */
(function () {
  const buttons = new WeakMap();

  function attach(btn) {
    if (buttons.has(btn)) return;
    const canvas = document.createElement("canvas");
    btn.prepend(canvas);
    const ctx = canvas.getContext("2d");
    const state = { amp: 0, phase: 0, hover: false, raf: 0, canvas, ctx };
    buttons.set(btn, state);

    const resize = () => {
      const r = btn.getBoundingClientRect();
      canvas.width = Math.max(2, Math.floor(r.width * devicePixelRatio));
      canvas.height = Math.max(2, Math.floor(r.height * devicePixelRatio));
    };
    resize();
    new ResizeObserver(resize).observe(btn);

    btn.addEventListener("pointerenter", () => { state.hover = true; });
    btn.addEventListener("pointerleave", () => { state.hover = false; });
    btn.addEventListener("pointermove", (ev) => {
      const r = btn.getBoundingClientRect();
      state.mx = (ev.clientX - r.left) / r.width;
    });

    const tick = () => {
      state.phase += 0.085;
      state.amp += ((state.hover ? 1 : 0) - state.amp) * 0.12;
      draw(state, btn.classList.contains("gold"));
      state.raf = requestAnimationFrame(tick);
    };
    tick();
  }

  function draw(state, gold) {
    const { ctx, canvas, amp, phase } = state;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (amp < 0.01) return;
    const mid = h * 0.62;
    const waves = [
      { color: gold ? "rgba(255,255,255,0.22)" : "rgba(225,29,46,0.42)", len: 1.6, y: 0 },
      { color: gold ? "rgba(0,0,0,0.22)" : "rgba(255,80,80,0.38)", len: 2.3, y: 6 },
    ];
    waves.forEach((wave, i) => {
      ctx.beginPath();
      ctx.moveTo(0, h);
      for (let x = 0; x <= w; x += 4) {
        const t = x / w;
        const y =
          mid +
          Math.sin(t * Math.PI * wave.len * 2 + phase + i) * 10 * amp * devicePixelRatio +
          Math.sin(t * Math.PI * 6 - phase * 1.4) * 4 * amp * devicePixelRatio +
          wave.y * devicePixelRatio;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(w, h);
      ctx.closePath();
      ctx.fillStyle = wave.color;
      ctx.fill();
    });
    if (state.mx != null && amp > 0.2) {
      const gx = state.mx * w;
      const g = ctx.createRadialGradient(gx, h * 0.4, 4, gx, h * 0.4, w * 0.35);
      g.addColorStop(0, gold ? "rgba(255,255,255,0.32)" : "rgba(255,50,50,0.32)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    }
  }

  function scan(root) {
    (root || document).querySelectorAll("[data-wave]").forEach(attach);
  }
  window.FrameGeniusWaves = { scan, attach };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => scan());
  } else {
    scan();
  }
})();
