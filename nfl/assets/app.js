// NFL Lines & Strategy hub — light UI helper.
// Adds a simple client-side filter box above each data table so reviewers can
// search rows by text without any server or manual input.
(function () {
  "use strict";

  function setup() {
    document.querySelectorAll("table.grid").forEach(function (table) {
      // Skip tables that are already wrapped with a filter.
      if (table.dataset.filtered) return;
      var wrapper = document.createElement("div");
      wrapper.className = "table-scroll";
      var search = document.createElement("input");
      search.type = "search";
      search.placeholder = "Filter this table…";
      search.className = "table-filter";
      search.style.cssText =
        "width:100%;margin:10px 0;padding:8px 12px;border-radius:8px;" +
        "background:var(--panel-2);color:var(--text);border:1px solid var(--line);font-size:14px;";
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(search);
      wrapper.appendChild(table);
      table.dataset.filtered = "1";

      search.addEventListener("input", function () {
        var q = search.value.trim().toLowerCase();
        var rows = table.querySelectorAll("tbody tr");
        rows.forEach(function (row) {
          var text = row.textContent.toLowerCase();
          row.style.display = q === "" || text.indexOf(q) !== -1 ? "" : "none";
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup);
  } else {
    setup();
  }
})();
