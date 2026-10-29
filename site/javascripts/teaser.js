(function () {
  function settle() {
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.querySelectorAll("video.teaser").forEach(function (video) {
      if (still) {
        video.pause();
        video.removeAttribute("autoplay");
        video.currentTime = 0;
        video.controls = true;
      }
    });
  }
  if (window.document$) window.document$.subscribe(settle);
  else document.addEventListener("DOMContentLoaded", settle);
})();
