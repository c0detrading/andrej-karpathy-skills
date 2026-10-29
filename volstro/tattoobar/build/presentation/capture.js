// Viewport screenshots of the site for the client presentation.
// usage: node capture.js <site dir> <deck dir>/shots   (then run deck.js)
// Edit DESK and PHONE: [shot name, page file without .html, selector to scroll to or null for the top].
const { chromium } = require('playwright'); const path = require('path');
const [SITE, OUT] = process.argv.slice(2);
const DESK = [
  ['home-hero', 'index', null], ['home-tiles', 'index', '.tiles'], ['home-vilma', 'index', '#vilma'], ['home-bar', 'index', '#the-bar'], ['home-info', 'index', '#reviews'],
  ['tattoo-top', 'tattoo', null], ['tattoo-prices', 'tattoo', '#prices'],
  ['bar-top', 'bar', null], ['bar-menu', 'bar', '#menu'],
  ['events-top', 'events', null], ['events-hire', 'events', '#hire'],
  ['learn-course', 'learn', '#course'], ['art-guardian', 'art', '#guardian'], ['aftercare-top', 'aftercare', null],
];
const PHONE = [['p-home', 'index', null], ['p-tiles', 'index', '.tiles'], ['p-tattoo', 'tattoo', '#prices'], ['p-bar', 'bar', '#happy-hour'], ['p-events', 'events', '#hire'], ['p-learn', 'learn', '#course']];
(async () => {
  const b = await chromium.launch();
  for (const [list, w, h, dsf] of [[DESK, 1440, 900, 1.5], [PHONE, 390, 844, 2.5]]) for (const [name, page, sel] of list) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: dsf });
    await p.goto('file://' + path.join(SITE, page + '.html'), { waitUntil: 'networkidle' });
    await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 500) { scrollTo(0, y); await new Promise(r => setTimeout(r, 20)); } await Promise.all([...document.images].map(i => i.decode().catch(() => {}))); });
    await p.evaluate(() => {
      document.querySelectorAll('[data-status]').forEach(el => { el.querySelector('i').className = 'open'; el.querySelector('span').textContent = el.dataset.status === 'bar' ? 'Bar open until 23:00' : 'Tattoo studio open until 21:00'; });
    });
    await p.evaluate(s => { const el = s && document.querySelector(s); scrollTo(0, el ? el.getBoundingClientRect().top + scrollY - (innerWidth > 600 ? 48 : 24) : 0); }, sel);
    await p.waitForTimeout(400);
    await p.screenshot({ path: path.join(OUT, name + '.jpg'), type: 'jpeg', quality: 84 });
    await p.close(); console.log(name);
  }
  await b.close();
})();
