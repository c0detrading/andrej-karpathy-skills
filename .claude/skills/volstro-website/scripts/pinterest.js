// Searches Pinterest (no login) and saves the first page of pins for each query.
// usage: node pinterest.js <outdir> "<query>" ["<query>" ...]
// Then download the 736px images listed in <outdir>/pins.json and make contact sheets with montage to look at them.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [out, ...queries] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch();
  const results = {};
  for (const q of queries) {
    const p = await b.newPage({ viewport: { width: 1400, height: 1000 }, userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36' });
    await p.goto('https://www.pinterest.com/search/pins/?q=' + encodeURIComponent(q), { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
    await p.waitForTimeout(5000);
    // apply the "Less AI" filter chip when Pinterest offers it
    const chip = p.getByText('Less AI', { exact: true });
    let lessAi = false;
    if (await chip.count()) { await chip.first().click({ force: true }).catch(() => {}); await p.waitForTimeout(5000); lessAi = true; }
    const pins = await p.$$eval('img', imgs => imgs.filter(i => /\/(236|474|564)x\//.test(i.src)).map(i => ({ img: i.src.replace(/\/\d+x\//, '/736x/'), alt: i.alt })));
    const uniq = [...new Map(pins.map(x => [x.img, x])).values()];
    results[q] = { lessAi, pins: uniq };
    console.log(`${q}: ${uniq.length} pins${lessAi ? ' (Less AI)' : ''}`);
    await p.close();
  }
  fs.writeFileSync(out + '/pins.json', JSON.stringify(results, null, 1));
  await b.close();
})();
