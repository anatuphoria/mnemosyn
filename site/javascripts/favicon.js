(function () {
  const KEY = [[6,34],[6,6],[34,6],[34,30],[14,30],[14,14],[26,14],[26,22],[20,22]];
  const BOX = 40, STROKE = 3.2;
  const DELAY = 0.4, SECONDS = 1.8, LENGTH = 0.16;
  const INK = "#16161d", BLUE = "#3d6fd6", LIGHT = "#e8e6df";

  function bezier(x1, y1, x2, y2) {
    const at = (a, b, t) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3;
    return function (x) {
      if (x <= 0) return 0;
      if (x >= 1) return 1;
      let low = 0, high = 1;
      for (let i = 0; i < 40; i++) {
        const mid = (low + high) / 2;
        if (at(x1, x2, mid) < x) low = mid; else high = mid;
      }
      return at(y1, y2, (low + high) / 2);
    };
  }
  const EASE = bezier(0.45, 0, 0.25, 1);

  function state(t) {
    const raw = Math.min(Math.max((t - DELAY) / SECONDS, 0), 1);
    let opacity;
    if (raw <= 0 || raw >= 1) opacity = 0;
    else if (raw < 0.08) opacity = EASE(raw / 0.08);
    else if (raw < 0.85) opacity = 1;
    else opacity = 1 - EASE((raw - 0.85) / 0.15);
    const offset = LENGTH + (-1 - LENGTH) * EASE(raw);
    return [opacity, -offset];
  }

  function trace(context, size) {
    const inset = size * 6 / BOX, scale = (size - 2 * inset) / BOX;
    context.beginPath();
    KEY.forEach(([x, y], n) => {
      const px = inset + x * scale, py = inset + y * scale;
      if (n) context.lineTo(px, py); else context.moveTo(px, py);
    });
    context.lineWidth = STROKE * scale;
    context.lineCap = "square";
    context.lineJoin = "miter";
    let length = 0;
    for (let n = 1; n < KEY.length; n++) {
      length += Math.hypot(KEY[n][0] - KEY[n - 1][0], KEY[n][1] - KEY[n - 1][1]) * scale;
    }
    return length;
  }

  function draw(context, size, t) {
    context.clearRect(0, 0, size, size);
    const radius = size * 52 / 256;
    context.fillStyle = INK;
    context.beginPath();
    context.roundRect(0, 0, size, size, radius);
    context.fill();
    context.setLineDash([]);
    context.globalAlpha = 1;
    context.strokeStyle = BLUE;
    trace(context, size);
    context.stroke();
    const [opacity, start] = state(t);
    const from = Math.max(start, 0), shown = start + LENGTH - from;
    if (opacity <= 0 || shown <= 0) return;
    const length = trace(context, size);
    context.setLineDash([shown * length, length * 3]);
    context.lineDashOffset = -from * length;
    context.globalAlpha = opacity;
    context.strokeStyle = LIGHT;
    context.stroke();
    context.globalAlpha = 1;
  }

  if (typeof module !== "undefined") {
    module.exports = { state, bezier, draw };
    return;
  }
  window.mnemosynFavicon = { state, draw };
  try {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (sessionStorage.getItem("mnemosyn-favicon")) return;
    sessionStorage.setItem("mnemosyn-favicon", "played");
  } catch (error) {
    return;
  }
  const link = document.querySelector("link[rel~='icon']");
  if (!link) return;
  const still = link.href, size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context || !context.roundRect) return;
  let began = null, shown = -1;
  function step(now) {
    if (began === null) began = now;
    const t = (now - began) / 1000;
    if (t > DELAY + SECONDS) {
      link.href = still;
      return;
    }
    const frame = Math.floor(t * 30);
    if (frame !== shown) {
      shown = frame;
      draw(context, size, t);
      link.href = canvas.toDataURL("image/png");
    }
    requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
})();
