/* NFL Lines & Strategy Lab - progressive enhancement only.
   Tables are fully readable without this file; it adds filtering and sorting. */
(function () {
  "use strict";

  function wrapTables() {
    document.querySelectorAll("table.data-table").forEach(function (t) {
      if (t.parentElement && t.parentElement.classList.contains("tw")) return;
      var d = document.createElement("div");
      d.className = "tw";
      t.parentNode.insertBefore(d, t);
      d.appendChild(t);
    });
  }

  function addFilter(t) {
    var head = t.tHead;
    if (!head) return;
    var bar = document.createElement("div");
    bar.className = "filterbar";
    var input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Filter rows…";
    input.setAttribute("aria-label", "Filter rows");
    var count = document.createElement("span");
    count.className = "count";
    bar.appendChild(input);
    bar.appendChild(count);
    t.parentNode.insertBefore(bar, t);

    var rows = Array.prototype.slice.call(t.tBodies[0].rows);
    var total = rows.length;

    function apply() {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (r) {
        // keep nested option tables visible with their parent row
        var hit = !q || r.textContent.toLowerCase().indexOf(q) !== -1;
        r.style.display = hit ? "" : "none";
        if (hit) shown++;
      });
      count.textContent = q ? shown + " of " + total + " rows" : total + " rows";
    }
    input.addEventListener("input", apply);
    apply();
  }

  function addSorting(t) {
    var head = t.tHead;
    if (!head) return;
    var ths = Array.prototype.slice.call(head.rows[0].cells);
    ths.forEach(function (th, idx) {
      th.classList.add("sortable");
      th.setAttribute("scope", "col");
      var dir = 0;
      th.addEventListener("click", function () {
        dir = dir === 0 ? 1 : dir === 1 ? -1 : 0;
        ths.forEach(function (o) { o.classList.remove("asc", "desc"); });
        var body = t.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows);
        if (dir === 0) {
          rows.sort(function (a, b) {
            return Array.prototype.indexOf.call(body.rows, a) -
                   Array.prototype.indexOf.call(body.rows, b);
          });
        } else {
          th.classList.add(dir === 1 ? "asc" : "desc");
          rows.sort(function (a, b) {
            var x = (a.cells[idx] || {}).textContent || "";
            var y = (b.cells[idx] || {}).textContent || "";
            x = x.trim(); y = y.trim();
            var nx = parseFloat(x.replace(/[^0-9eE+\-.]/g, ""));
            var ny = parseFloat(y.replace(/[^0-9eE+\-.]/g, ""));
            var num = !isNaN(nx) && !isNaN(ny) && x !== "" && y !== "";
            if (num) return (nx - ny) * dir;
            return x.localeCompare(y, undefined, { numeric: true }) * dir;
          });
        }
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wrapTables();
    document.querySelectorAll("table.data-table").forEach(function (t) {
      if (!t.tBodies.length || t.tBodies[0].rows.length < 6) return;
      addFilter(t);
      addSorting(t);
    });
  });
})();
