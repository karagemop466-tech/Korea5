// NFL Lines Lab: row filter and column sort for data tables. No external dependencies.
(function () {
  function rowsOf(t) { return Array.prototype.slice.call(t.tBodies[0].rows); }
  function updateCount(t) {
    var rows = rowsOf(t), shown = rows.filter(function (r) { return r.style.display !== "none"; }).length;
    var c = document.querySelector('[data-count-for="' + t.id + '"]');
    if (c) c.textContent = "Showing " + shown + " of " + rows.length + " rows";
  }
  document.querySelectorAll("input.filter").forEach(function (inp) {
    var t = document.getElementById(inp.getAttribute("data-target"));
    if (!t) return;
    inp.addEventListener("input", function () {
      var q = inp.value.toLowerCase();
      rowsOf(t).forEach(function (r) {
        r.style.display = r.textContent.toLowerCase().indexOf(q) === -1 ? "none" : "";
      });
      updateCount(t);
    });
    updateCount(t);
  });
  document.querySelectorAll("table.data[data-sort='1']").forEach(function (t) {
    var ths = t.tHead ? t.tHead.rows[0].cells : [];
    Array.prototype.forEach.call(ths, function (th, idx) {
      th.title = "Click to sort";
      th.addEventListener("click", function () {
        var asc = th.getAttribute("data-asc") !== "1";
        Array.prototype.forEach.call(ths, function (o) { o.removeAttribute("data-asc"); });
        th.setAttribute("data-asc", asc ? "1" : "0");
        var body = t.tBodies[0];
        var rows = rowsOf(t).sort(function (a, b) {
          var x = a.cells[idx] ? a.cells[idx].textContent.trim() : "";
          var y = b.cells[idx] ? b.cells[idx].textContent.trim() : "";
          var nx = parseFloat(x.replace(/[%,+]/g, "")), ny = parseFloat(y.replace(/[%,+]/g, ""));
          var r = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : x.localeCompare(y);
          return asc ? r : -r;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  });
})();
