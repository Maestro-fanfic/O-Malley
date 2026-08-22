
(function () {
  var KEY = 'fanficFontScale';
  var MIN = 0.8, MAX = 1.7, STEP = 0.1;
  var saved = parseFloat(localStorage.getItem(KEY));
  var scale = isNaN(saved) ? 1 : saved;

  function apply() {
    document.documentElement.style.setProperty('--text-scale', scale);
  }
  apply();

  document.addEventListener('DOMContentLoaded', function () {
    var dec = document.getElementById('font-dec');
    var inc = document.getElementById('font-inc');
    if (dec) {
      dec.addEventListener('click', function () {
        scale = Math.max(MIN, Math.round((scale - STEP) * 100) / 100);
        apply();
        localStorage.setItem(KEY, scale);
      });
    }
    if (inc) {
      inc.addEventListener('click', function () {
        scale = Math.min(MAX, Math.round((scale + STEP) * 100) / 100);
        apply();
        localStorage.setItem(KEY, scale);
      });
    }

    var tocToggle = document.getElementById('toc-toggle');
    var tocPanel = document.getElementById('toc-panel');
    var tocClose = document.getElementById('toc-close');
    var tocBackdrop = document.getElementById('toc-backdrop');
    function openToc() {
      if (tocPanel) tocPanel.classList.add('open');
      if (tocBackdrop) tocBackdrop.classList.add('open');
    }
    function closeToc() {
      if (tocPanel) tocPanel.classList.remove('open');
      if (tocBackdrop) tocBackdrop.classList.remove('open');
    }
    if (tocToggle) tocToggle.addEventListener('click', openToc);
    if (tocClose) tocClose.addEventListener('click', closeToc);
    if (tocBackdrop) tocBackdrop.addEventListener('click', closeToc);
  });
})();
