(function () {
  function system() {
    const agent = navigator.userAgent || "";
    const data = navigator.userAgentData;
    const platform = (data && data.platform) || navigator.platform || "";
    const touchMac = /Mac/i.test(platform) && navigator.maxTouchPoints > 1;
    if ((data && data.mobile) || touchMac || /Android|iPhone|iPad|iPod|Mobile/i.test(agent)) {
      return "mobile";
    }
    if (/Win/i.test(platform) || /Windows/i.test(agent)) return "windows";
    if (/Mac/i.test(platform) || /Mac OS X/i.test(agent)) return "mac";
    if (/CrOS/i.test(agent)) return null;
    if (/Linux|X11/i.test(platform) || /Linux|X11/i.test(agent)) return "linux";
    return null;
  }

  function graphics() {
    try {
      const gl = document.createElement("canvas").getContext("webgl");
      const info = gl && gl.getExtension("WEBGL_debug_renderer_info");
      return info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "";
    } catch (error) {
      return "";
    }
  }

  function intelMac() {
    const data = navigator.userAgentData;
    if (data && data.getHighEntropyValues) {
      return data.getHighEntropyValues(["architecture"])
        .then(function (found) { return found.architecture === "x86"; })
        .catch(function () { return false; });
    }
    const renderer = graphics();
    return Promise.resolve(/Intel|AMD|Radeon/i.test(renderer) && !/Apple M/i.test(renderer));
  }

  function show(key) {
    const panels = document.querySelectorAll(".get[data-os]");
    let shown = false;
    panels.forEach(function (panel) {
      panel.hidden = panel.dataset.os !== key;
      shown = shown || !panel.hidden;
    });
    document.querySelectorAll(".file[data-os]").forEach(function (row) {
      row.classList.toggle("is-yours", shown && row.dataset.os === key);
    });
  }

  const NAMES = { windows: "Windows", linux: "Linux", mac: "Mac" };

  function offer(button, key) {
    if (!button.dataset.page) {
      button.dataset.page = button.getAttribute("href");
      button.dataset.text = button.textContent;
    }
    const file = key && button.dataset[key];
    const note = document.querySelector(".get-app-note");
    button.setAttribute("href", file || button.dataset.page);
    button.textContent = file ? "Download for " + NAMES[key] : button.dataset.text;
    if (note) note.classList.toggle("is-shown", Boolean(file));
  }

  function choose() {
    const button = document.querySelector("a.get-app");
    const page = document.querySelector(".get[data-os]");
    if (!button && !page) return;
    const key = system();
    if (page) show(key);
    if (button) offer(button, key);
    if (key === "mac") {
      intelMac().then(function (intel) {
        if (!intel) return;
        if (page) show("mac-intel");
        if (button) offer(button, null);
      });
    }
  }

  if (window.document$) window.document$.subscribe(choose);
  else document.addEventListener("DOMContentLoaded", choose);
})();
