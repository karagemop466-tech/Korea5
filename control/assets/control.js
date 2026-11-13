/* NFL Control Room — suggestion review board.
 * Selections live in localStorage only. Nothing is sent anywhere and no source file is
 * modified: the export is for pasting into COORDINATION.md or a PR description.
 */
(function () {
  "use strict";
  var KEY = "korea5.control.choices.v1";

  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; }
  }
  function write(obj) {
    try { localStorage.setItem(KEY, JSON.stringify(obj)); } catch (e) { /* private mode */ }
  }
  function note(msg) {
    var s = document.getElementById("status");
    if (s) { s.textContent = msg; }
  }

  var inputs = Array.prototype.slice.call(document.querySelectorAll('input[type=radio]'));
  if (!inputs.length) { return; }

  var saved = read();
  inputs.forEach(function (el) {
    if (saved[el.name] === el.value) { el.checked = true; }
    el.addEventListener("change", function () {
      var all = read();
      all[el.name] = el.value;
      write(all);
      var n = Object.keys(all).length;
      note(n + " of " + countItems() + " decided in this browser");
    });
  });

  function countItems() {
    var names = {};
    inputs.forEach(function (el) { names[el.name] = 1; });
    return Object.keys(names).length;
  }

  var exportBtn = document.getElementById("export");
  if (exportBtn) {
    exportBtn.addEventListener("click", function () {
      var all = read();
      var rows = [];
      Object.keys(all).sort().forEach(function (k) {
        rows.push({ suggestion: k, option: all[k] });
      });
      var payload = {
        generatedUTC: new Date().toISOString(),
        note: "Local choices only. Not submitted anywhere. Paste into COORDINATION.md to make binding.",
        choices: rows
      };
      var blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "control-room-choices.json";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      note("exported " + rows.length + " choice(s)");
    });
  }

  var clearBtn = document.getElementById("clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
      inputs.forEach(function (el) { el.checked = false; });
      note("cleared");
    });
  }

  var initial = Object.keys(read()).length;
  if (initial) { note(initial + " of " + countItems() + " decided in this browser"); }
}());
