(() => {
  "use strict";
  const STORAGE_KEY = "korea5.nfl-lines-lab.decisions.v1";
  const selects = Array.from(document.querySelectorAll("select[data-decision]"));
  const status = document.getElementById("decision-status");
  const exportButton = document.getElementById("export-decisions");
  const clearButton = document.getElementById("clear-decisions");

  function readSaved() {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
      return parsed && typeof parsed === "object" && parsed.decisions && typeof parsed.decisions === "object"
        ? parsed
        : { version: 1, decisions: {} };
    } catch (_error) {
      return { version: 1, decisions: {} };
    }
  }

  function updateRow(select) {
    const itemId = select.dataset.decision;
    const rowStatus = Array.from(document.querySelectorAll("[data-decision-status]"))
      .find((element) => element.dataset.decisionStatus === itemId);
    if (!rowStatus) return;
    if (!select.value) {
      rowStatus.textContent = "awaiting your choice";
      rowStatus.className = "pending";
      return;
    }
    const option = Array.from(select.options).find((candidate) => candidate.value === select.value);
    rowStatus.textContent = `selected ${select.value}${option ? ` — ${option.textContent.replace(/^\S+\s+—\s+/, "")}` : ""} (local only)`;
    rowStatus.className = "local-choice";
  }

  function save() {
    const decisions = {};
    selects.forEach((select) => {
      decisions[select.dataset.decision] = select.value;
      updateRow(select);
    });
    const record = { version: 1, decisions, savedAt: new Date().toISOString(), storage: "this browser only" };
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
      if (status) status.textContent = "Choices saved in this browser only. Export JSON to share; nothing was sent.";
    } catch (_error) {
      if (status) status.textContent = "Browser storage is unavailable. Use Export choices to download the current selections.";
    }
    return record;
  }

  const saved = readSaved();
  selects.forEach((select) => {
    const prior = saved.decisions[select.dataset.decision];
    if (typeof prior === "string" && Array.from(select.options).some((option) => option.value === prior)) {
      select.value = prior;
    }
    updateRow(select);
    select.addEventListener("change", save);
  });
  if (status && selects.some((select) => select.value)) {
    status.textContent = "Saved choices restored from this browser. Export JSON to share; nothing was sent.";
  }

  if (exportButton) {
    exportButton.addEventListener("click", () => {
      const record = save();
      const blob = new Blob([JSON.stringify(record, null, 2) + "\n"], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "nfl-lines-lab-decisions.json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      if (status) status.textContent = "Decision JSON downloaded. No selection was sent to a server.";
    });
  }

  if (clearButton) {
    clearButton.addEventListener("click", () => {
      selects.forEach((select) => {
        select.value = "";
        updateRow(select);
      });
      try {
        window.localStorage.removeItem(STORAGE_KEY);
        if (status) status.textContent = "Local review choices cleared.";
      } catch (_error) {
        if (status) status.textContent = "Selections cleared from this page; browser storage was unavailable.";
      }
    });
  }
})();
