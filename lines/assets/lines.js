/* NFL lines lab: client-side filtering for the bet ledger */
(function () {
  var table = document.getElementById('bets');
  if (!table) return;
  var tbody = table.querySelector('tbody');
  var q = document.getElementById('q');
  var sSel = document.getElementById('strategy');
  var seasonSel = document.getElementById('season');
  var placedSel = document.getElementById('placed');
  var count = document.getElementById('count');
  var csvBtn = document.getElementById('csv');
  var rows = [];

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fmt(v, d) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return v.toFixed(d === undefined ? 3 : d);
    return v;
  }

  fetch('../data/lines/strategies.json')
    .then(function (r) { return r.json(); })
    .then(function (doc) {
      rows = doc.bets || [];
      var strategies = {}, seasons = {};
      rows.forEach(function (b) {
        strategies[b.strategy] = true;
        seasons[b.season] = true;
      });
      Object.keys(strategies).sort().forEach(function (s) {
        var o = document.createElement('option'); o.value = s; o.textContent = s; sSel.appendChild(o);
      });
      Object.keys(seasons).sort().forEach(function (s) {
        var o = document.createElement('option'); o.value = s; o.textContent = s; seasonSel.appendChild(o);
      });
      render();
    })
    .catch(function (e) {
      tbody.innerHTML = '<tr><td colspan="11">The bet ledger could not be loaded from ' +
        'data/lines/strategies.json (' + esc(e) + '). The same data is summarised on the Strategies page.</td></tr>';
    });

  function visible() {
    var term = (q.value || '').toLowerCase().trim();
    var st = sSel.value, se = seasonSel.value, pl = placedSel.value;
    return rows.filter(function (b) {
      if (st && b.strategy !== st) return false;
      if (se && String(b.season) !== se) return false;
      if (pl === 'placed' && !b.placed) return false;
      if (!term) return true;
      var hay = [b.strategy, b.market, b.side, b.team, b.opponent, b.gameId, b.playerDisplay]
        .join(' ').toLowerCase();
      return hay.indexOf(term) !== -1;
    });
  }

  function render() {
    var list = visible();
    tbody.innerHTML = list.map(function (b) {
      return '<tr>' +
        '<td>' + esc(b.date) + '</td>' +
        '<td>' + esc(b.strategy) + '</td>' +
        '<td>' + esc(b.market) + '</td>' +
        '<td>' + esc(b.side) + '</td>' +
        '<td>' + fmt(b.line, 1) + '</td>' +
        '<td>' + fmt(b.p, 3) + '</td>' +
        '<td>' + fmt(b.pNaive, 3) + '</td>' +
        '<td>' + (b.outcome === 1 ? 'won' : 'lost') + '</td>' +
        '<td>' + (b.placed ? 'yes' : 'no') + '</td>' +
        '<td>' + fmt(b.units, 3) + '</td>' +
        '<td><a href="' + esc(b.sourceUrl) + '" target="_blank" rel="noopener">official</a></td>' +
        '</tr>';
    }).join('');
    count.textContent = list.length + ' of ' + rows.length + ' candidate bets shown';
  }

  if (q) q.addEventListener('input', render);
  if (sSel) sSel.addEventListener('change', render);
  if (seasonSel) seasonSel.addEventListener('change', render);
  if (placedSel) placedSel.addEventListener('change', render);

  if (csvBtn) csvBtn.addEventListener('click', function () {
    var list = visible();
    var head = ['date', 'strategy', 'market', 'side', 'line', 'model_p', 'naive_p', 'outcome', 'placed', 'units', 'source'];
    var out = [head.join(',')];
    list.forEach(function (b) {
      out.push([b.date, b.strategy, b.market, b.side, b.line, b.p, b.pNaive, b.outcome, b.placed, b.units, b.sourceUrl]
        .map(function (v) {
          var s = v === null || v === undefined ? '' : String(v);
          return /[",
]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
        }).join(','));
    });
    var blob = new Blob([out.join('\n')], { type: 'text/csv' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'nfl-lines-bets.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  });
})();
