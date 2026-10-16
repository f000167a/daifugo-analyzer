const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Exercise the actual inline script while keeping Node tests independent of a DOM.
function loadApp(file = process.env.ANALYZER_HTML || path.join(__dirname, '..', 'index.html')) {
  const html = fs.readFileSync(file, 'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^buildGrid\(\);$/m, '')
    .replace(/^buildPosOpts\(\);$/m, '');
  const context = vm.createContext({
    document: {getElementById: () => ({addEventListener() {}})},
    console, performance, setTimeout, clearTimeout,
  });
  vm.runInContext(script, context);
  return context;
}
function hand(cards) {
  const result = Object.fromEntries(Array.from({length:14}, (_, i) => [i + 3, 0]));
  for (const card of cards) result[card]++;
  return result;
}
function seeded(seed) {
  return () => {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const plain = value => JSON.parse(JSON.stringify(value));
module.exports = {loadApp, hand, seeded, plain};
