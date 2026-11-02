/* Free-time calendar: day navigation, scope filters, timeline. */
const S = {
  analysis: null, events: {}, scope: "all", date: null,
  years: [2026, 2027, 2028, 2029, 2030],
};
const SCOPE_TAGS = {
  radio: ["mlb-giants", "mlb-athletics", "nfl-49ers", "ncaaf-stanford", "ncaaf-cal", "westwoodone"],
};
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const toMin = (h) => { const [a, b] = h.split(":").map(Number); return a * 60 + b; };
const fmt = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const addDays = (iso, n) => {
  const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};
const prettyDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-US",
  { weekday: "long", year: "numeric", month: "long", day: "numeric" });

const TBD = [720, 1410]; // 12:00-23:30 PT conservative block for a TBD kickoff
function evIntervals(e) {
  if (!e.start) {
    if (e.startWindow) {
      const [a, b] = e.startWindow.split("-");
      return [[toMin(a), toMin(b)]];
    }
    return [TBD];
  }
  const out = [[toMin(e.start), toMin(e.start) + e.durationMin]];
  if (e.altWindow) out.push([toMin(e.altWindow.start), toMin(e.altWindow.start) + e.altWindow.durationMin]);
  if (e.startWindow) {
    const [a, b] = e.startWindow.split("-");
    out.push([toMin(a), toMin(b)]);
  }
  return out;
}
function merge(ivs) {
  const s = ivs.slice().sort((a, b) => a[0] - b[0]);
  const out = [];
  for (const [a, b] of s) {
    if (out.length && a <= out[out.length - 1][1]) out[out.length - 1][1] = Math.max(out[out.length - 1][1], b);
    else out.push([a, b]);
  }
  return out;
}
function inScope(e, scope) {
  if (scope === "all") return true;
  if (scope === "high") return e.priority === "high";
  return (e.tags || []).some((t) => SCOPE_TAGS.radio.includes(t));
}

const V = () => window.DATA_VERSION || "v0";
async function loadYear(y) {
  if (S.events[y]) return S.events[y];
  const r = await fetch(`data/events-${y}.json?v=${V()}`);
  S.events[y] = await r.json();
  return S.events[y];
}
async function eventsFor(iso, scope) {
  const y = +iso.slice(0, 4);
  if (!S.years.includes(y)) return [];
  const pack = await loadYear(y);
  return pack.events.filter((e) => e.date === iso && inScope(e, scope));
}

function srcUrl(pack, e) {
  return e.sourceUrl || (pack.meta.sources[e.s] || {}).url || "#";
}
function basisText(pack, e) {
  return (pack.meta.basis || {})[e.b] || e.timeBasis || "";
}

function timeline(intervals, scope) {
  const merged = merge(intervals.filter((i) => i[1] > 0)).map(([a, b]) => [Math.max(0, a), Math.min(1440, b)]);
  const bar = $("#bar"); bar.innerHTML = "";
  let cursor = 0;
  const freeSegs = [];
  for (const [a, b] of merged) {
    if (a > cursor) freeSegs.push([cursor, a]);
    cursor = Math.max(cursor, b);
  }
  if (cursor < 1440) freeSegs.push([cursor, 1440]);
  // free background
  for (const [a, b] of freeSegs) {
    const d = document.createElement("div");
    d.className = "seg free"; d.style.left = `${(a / 1440) * 100}%`; d.style.width = `${((b - a) / 1440) * 100}%`;
    bar.appendChild(d);
  }
  for (const [a, b] of merged) {
    const d = document.createElement("div");
    d.className = "seg busy"; d.style.left = `${(a / 1440) * 100}%`; d.style.width = `${((b - a) / 1440) * 100}%`;
    d.title = `${fmt(a)}–${fmt(b)} busy`;
    bar.appendChild(d);
  }
  const free = freeSegs.filter(([a, b]) => b - a >= 30);
  $("#freewin").innerHTML = free.length
    ? free.map(([a, b]) => `<span class="tag ver">${fmt(a)}–${fmt(b)} free (${((b - a) / 60).toFixed(1)}h)</span>`).join(" ")
    : `<span class="tag flag">No free window of 30 minutes or more</span>`;
  const busyH = merged.reduce((t, [a, b]) => t + (b - a), 0) / 60;
  $("#hours").textContent = busyH.toFixed(1);
  $("#freehrs").textContent = (24 - busyH).toFixed(1);
}

async function render(iso) {
  S.date = iso;
  history.replaceState(null, "", `#${iso}`);
  const [y, m, d] = iso.split("-");
  $("#dayhead").textContent = prettyDate(iso);
  $("#dateinput").value = iso;
  const evs = (await eventsFor(iso, S.scope)).sort((a, b) => (a.start || "99") < (b.start || "99") ? -1 : 1);
  const pack = S.events[+y];
  timeline(evs.flatMap(evIntervals), S.scope);

  const body = $("#gamelist");
  if (!evs.length) {
    body.innerHTML = `<tr><td colspan="6" class="free"><strong>No qualifying games.</strong> The whole day is free.</td></tr>`;
  } else {
    body.innerHTML = evs.map((e) => {
      const lg = e.league === "MLB" ? "mlb" : e.league === "NFL" ? "nfl" : "ncaaf";
      const status = e.status === "verified" ? `<span class="tag ver">verified</span>`
        : e.status === "estimated" || e.timeStatus === "estimated" ? `<span class="tag est">estimated</span>`
          : `<span class="tag flag">${e.status || "unconfirmed"}</span>`;
      const when = e.start ? `<span class="mono">${e.start}</span> <small>PT</small>` : `<small>TBD</small>`;
      const radio = e.radio && e.radio.length ? e.radio.join(" · ") : (e.nationalRadio || "");
      return `<tr>
        <td>${when}</td>
        <td><span class="tag ${lg}">${e.league}</span></td>
        <td>${e.title}${e.note ? `<br><small>${e.note}</small>` : ""}</td>
        <td>${e.priority === "high" ? '<span class="tag high">high</span>' : '<small>normal</small>'}</td>
        <td><small>${radio || "—"}</small></td>
        <td>${status} <a href="${srcUrl(pack, e)}" target="_blank" rel="noopener">source</a></td>
      </tr>`;
    }).join("");
  }
  const note = evs.find((e) => e.b);
  $("#basis").textContent = note ? basisText(pack, note) : "No estimated times for this day.";

  // week strip
  const strip = $("#strip"); strip.innerHTML = "";
  for (let i = 0; i < 7; i++) {
    const ds = addDays(iso, i);
    const pack2 = S.years.includes(+ds.slice(0, 4)) ? await loadYear(+ds.slice(0, 4)) : { events: [] };
    const dEv = pack2.events.filter((e) => e.date === ds && inScope(e, S.scope));
    const h = merge(dEv.flatMap(evIntervals)).reduce((t, [a, b]) => t + (b - a), 0) / 60;
    const cls = h === 0 ? "ver" : h < 3 ? "est" : "flag";
    const dt = new Date(ds + "T12:00:00");
    strip.insertAdjacentHTML("beforeend", `<a class="chip ${ds === iso ? "on" : ""}" href="#${ds}" data-day="${ds}">
      ${dt.toLocaleDateString("en-US", { weekday: "short" })} ${dt.getDate()}
      <span class="tag ${cls}">${h === 0 ? "free" : h.toFixed(1) + "h"}</span></a>`);
  }
  $$("#strip .chip").forEach((el) => el.addEventListener("click", (ev) => {
    ev.preventDefault(); render(el.dataset.day);
  }));
}

async function init() {
  S.analysis = await (await fetch("data/derived/analysis.json")).json();
  const today = S.analysis.meta.today;
  const h = location.hash.replace("#", "");
  const start = /^\d{4}-\d{2}-\d{2}$/.test(h) ? h : today;
  $("#today").textContent = new Date(today + "T12:00:00").toLocaleDateString("en-US",
    { month: "short", day: "numeric", year: "numeric" });
  $("#prev").onclick = () => render(addDays(S.date, -1));
  $("#next").onclick = () => render(addDays(S.date, 1));
  $("#tomorrow").onclick = () => render(addDays(S.analysis.meta.today, 1));
  $("#tobay").onclick = () => render(today);
  $("#dateinput").onchange = (e) => render(e.target.value);
  $$(".chip[data-scope]").forEach((el) => el.addEventListener("click", () => {
    S.scope = el.dataset.scope;
    $$(".chip[data-scope]").forEach((x) => x.classList.toggle("on", x === el));
    render(S.date);
  }));
  window.addEventListener("hashchange", () => {
    const d = location.hash.replace("#", "");
    if (/^\d{4}-\d{2}-\d{2}$/.test(d) && d !== S.date) render(d);
  });
  await render(start);
}
document.addEventListener("DOMContentLoaded", init);
