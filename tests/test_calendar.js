// Pure calendar helpers are exercised in multiple browser time zones.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('assets/app.js', 'utf8');
const context = {document: {addEventListener() {}}};
vm.createContext(context);
vm.runInContext(code, context);
for (const tz of ['Pacific/Kiritimati', 'America/Los_Angeles', 'Pacific/Honolulu']) {
  process.env.TZ = tz;
  assert.equal(vm.runInContext('addDays("2027-12-31", 1)', context), '2028-01-01');
  assert.equal(vm.runInContext('addDays("2028-03-01", -1)', context), '2028-02-29');
}
assert.equal(vm.runInContext('fmt(1440)', context), '24:00');
console.log('Calendar helper tests passed');
