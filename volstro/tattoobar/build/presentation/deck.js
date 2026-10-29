// Builds the TattooBar client presentation as a 16:9 PDF.
// Run: node deck.js <site dir> <deck dir> <out.pdf>
const { chromium } = require('playwright'); const path = require('path'); const fs = require('fs');
const [SITE, DIR, PDF] = process.argv.slice(2);
const shot = n => 'file://' + path.join(DIR, 'shots', n + '.jpg');
const img = n => 'file://' + path.join(SITE, 'img', n + '.jpg');

const URLS = { 'home': 'tattoo-bar.co.uk', 'tattoo': 'tattoo-bar.co.uk/tattoo', 'bar': 'tattoo-bar.co.uk/bar', 'events': 'tattoo-bar.co.uk/events',
  'learn': 'tattoo-bar.co.uk/learn', 'art': 'tattoo-bar.co.uk/art', 'aftercare': 'tattoo-bar.co.uk/aftercare' };
const screen = (name, url) => `<figure class="screen"><figcaption>${url}</figcaption><img src="${shot(name)}" alt=""></figure>`;
const phone = name => `<figure class="phone"><img src="${shot(name)}" alt=""></figure>`;

function screenSlide({ label, title, text, desk, page, ph }) {
  const media = ph
    ? `<div class="media c23">${screen(desk, URLS[page])}</div><div class="media c4 center">${phone(ph)}</div>`
    : `<div class="media c24">${screen(desk, URLS[page])}</div>`;
  return `<section class="slide grid">
  <div class="c1 copy"><p class="label">${label}</p><h2 class="big">${title}</h2>${text.map(t => `<p>${t}</p>`).join('')}</div>
  ${media}
</section>`;
}

const SLIDES = [];

// 1. Cover
SLIDES.push(`<section class="slide cover">
  <div class="logo big">Tattoo Bar</div>
  <div class="grid cover-row">
    <div class="c1 copy"><p class="lead">Your new website</p><p class="muted">Prepared by VOLSTRO for Vilma and the TattooBar team, October 2026</p></div>
    <img class="c2 cover-img" src="${img('work-realism-back-piece')}" alt="">
    <img class="c3 cover-img" src="${img('moon-room')}" alt="">
    <img class="c4 cover-img" src="${img('counter')}" alt="">
  </div>
</section>`);

// 2. What's new
SLIDES.push(`<section class="slide">
  <div class="grid head-row"><h2 class="big c12">What's new</h2><p class="c34 lead">The same TattooBar, with a new look and everything easier to find.</p></div>
  <div class="grid panels">
    <div class="panel"><h3>Everything in one place</h3><p>Tattoos, the bar, events, courses and the art each have their own page, one click from the top of every page.</p></div>
    <div class="panel"><h3>Booking in one tap</h3><p>Book sits at the top of every page and at the bottom of the screen on phones. Every button goes straight to the right booking page.</p></div>
    <div class="panel"><h3>The same details everywhere</h3><p>One set of opening hours, phone numbers and address on every page, plus a live line that says whether the studio and bar are open now.</p></div>
    <div class="panel ink"><h3>Easy to find on Google</h3><p>The full menu, prices and opening hours are written as real text, so Google can read them and show them in searches.</p></div>
  </div>
</section>`);

// 3. The look
SLIDES.push(`<section class="slide grid">
  <div class="c1 copy"><p class="label">The look</p><h2 class="big">Taken from your bar</h2>
    <p>The colours come from the concrete walls, the ink and the violet light in the room.</p>
    <p>The lettering is tall and narrow, like the TATTOO BAR letters cast into your counter.</p></div>
  <div class="c2 swatches">
    <div class="sw" style="background:#D5D6D2;box-shadow:inset 0 0 0 2px #B3B6B3"><b>Concrete</b><span>Backgrounds</span></div>
    <div class="sw" style="background:#17181A;color:#F3F3F0"><b>Ink</b><span>Text and panels</span></div>
    <div class="sw" style="background:#F3F3F0"><b>Paper</b><span>Price lists and forms</span></div>
    <div class="sw" style="background:#5536E8;color:#fff"><b>UV violet</b><span>Every booking button</span></div>
  </div>
  <div class="c3 type">
    <div><p class="spec big">Tattoo Bar</p><p class="muted">Big Shoulders, for the logo and big words</p></div>
    <div><p class="spec-text">Enthusiastic and skilled tattoo artist with 20 years of experience, creating unique and personalised tattoo designs.</p><p class="muted">Albert Sans, for everything else</p></div>
  </div>
  <img class="c4 tall-img" src="${img('counter')}" alt="">
</section>`);

// 4. The grid
SLIDES.push(`<section class="slide grid">
  <div class="c1 copy"><p class="label">The layout</p><h2 class="big">Everything lines up</h2>
    <p>Every page uses the same four columns as the squares on the home page.</p>
    <p>Text, photos and buttons line up from the top of each page to the bottom, on computers and phones.</p></div>
  <div class="media c24">${screen('grid', URLS.home)}</div>
</section>`);

SLIDES.push(screenSlide({ label: 'Home page', title: 'The first thing people see', page: 'home', desk: 'home-hero', ph: 'p-home',
  text: ['Your name across the top, your own words behind a photo of Vilma at work, and two buttons: book a tattoo or book a table.'] }));
SLIDES.push(screenSlide({ label: 'Home page', title: 'Eight ways in', page: 'home', desk: 'home-tiles', ph: 'p-tiles',
  text: ['Each square leads somewhere: the bar, Sip &amp; Ink, tattoos, happy hour, booking, the counter, courses and the Guardian.', 'The squares can be posted on Instagram too, so the website and your feed match.'] }));
SLIDES.push(screenSlide({ label: 'Home page', title: 'Meet Vilma', page: 'home', desk: 'home-vilma',
  text: ['Her story next to her photo, then four pieces of her work.', 'Work photos zoom in gently when you point at them.'] }));
SLIDES.push(screenSlide({ label: 'Home page', title: 'The bar, reviews and info', page: 'home', desk: 'home-bar',
  text: ['Happy hour, bar hours and booking, then real reviews from your clients.', 'At the bottom: opening hours, address, phone numbers and directions.'] }));
SLIDES.push(screenSlide({ label: 'Tattoo and piercing', title: 'Your work first', page: 'tattoo', desk: 'tattoo-top', ph: 'p-tattoo',
  text: ['The page opens with your tattoos, then Vilma and a big Book a tattoo button.'] }));
SLIDES.push(screenSlide({ label: 'Tattoo and piercing', title: 'Clear prices', page: 'tattoo', desk: 'tattoo-prices',
  text: ['Tattoo and piercing prices side by side, with a Book button underneath.', 'The Prices button at the top of every page comes straight here.', 'Below, more work people can filter by style: geometric, realism or fine line.'] }));
SLIDES.push(screenSlide({ label: 'The Bar', title: 'The bar', page: 'bar', desk: 'bar-top', ph: 'p-bar',
  text: ['A live line shows whether the bar is open, with happy hour and Book a table right underneath.'] }));
SLIDES.push(screenSlide({ label: 'The Bar', title: 'The full menu', page: 'bar', desk: 'bar-menu',
  text: ['Every drink and dish with its price, in three columns.', 'Buttons at the top jump straight to cocktails, wine, spirits, beer, soft drinks or food.'] }));
SLIDES.push(screenSlide({ label: 'Events', title: 'Sip &amp; Ink and private hire', page: 'events', desk: 'events-hire', ph: 'p-events',
  text: ['Sip &amp; Ink on the second Friday of every month, with tickets one tap away.', 'Private hire shows the minimum spend and has a form to plan an event.'] }));
SLIDES.push(screenSlide({ label: 'Learn', title: 'Learn to tattoo', page: 'learn', desk: 'learn-course', ph: 'p-learn',
  text: ['The 3-day beginner course day by day, a Book the course square, and answers to the questions people ask.', 'The free community programme follows underneath.'] }));
SLIDES.push(screenSlide({ label: 'The Art', title: 'The art and the place', page: 'art', desk: 'art-guardian',
  text: ['Vilma\'s story, then the Guardian, the counter and the Moon, each shown like a work in a gallery with its own label.'] }));
SLIDES.push(screenSlide({ label: 'Before and after', title: 'Before and after', page: 'aftercare', desk: 'aftercare-top',
  text: ['How to prepare for a session and how to look after a new tattoo.', 'Linked from the prices, so people read it before they book.'] }));

// Phones
SLIDES.push(`<section class="slide">
  <div class="grid head-row"><h2 class="big c12">On your phone</h2><p class="c34 lead">Every page is designed for phones. Book a tattoo and Book a table stay at the bottom of the screen.</p></div>
  <div class="grid phones">${['p-home', 'p-tiles', 'p-tattoo', 'p-bar'].map(p => `<div class="center">${phone(p)}</div>`).join('')}</div>
</section>`);

// Booking map
const BOOK = [
  ['Book a tattoo', 'Goldie, booking with Vilma'], ['Book a piercing', 'Goldie'], ['Book a table', 'Square'],
  ['Sip &amp; Ink tickets', 'DesignMyNight'], ['Book the course', 'Cademy'], ['Register for the community programme', 'Cademy'],
  ['Plan your event form', 'An email to vilma@tattoobar.co'],
];
SLIDES.push(`<section class="slide grid">
  <div class="c1 copy"><p class="label">Booking</p><h2 class="big">Every button goes to the right place</h2>
    <p>These are the booking pages your current site and Linktree use.</p></div>
  <div class="c24 table">
    <div class="row th"><span>Button on the website</span><span>Where it goes</span></div>
    ${BOOK.map(([a, b]) => `<div class="row"><span>${a}</span><span>${b}</span></div>`).join('')}
  </div>
</section>`);

// Questions
const QS = [
  ['Booking', 'Are Goldie (tattoos and piercing) and Square (tables) the tools you want people to use?'],
  ['Friday happy hour', 'Your old site says 12:00–18:00, but the bar opens at 15:00 on weekdays. Which is right?'],
  ['Experience', 'The website says 20 years. Your course page says over 24. Which should we use?'],
  ['Menu', 'Is it 1664 Blanc on draught? What goes in the Limoncello Spritz and the Pimm\'s?'],
  ['Logo', 'Do you have logo files, or should we keep the lettering shown here?'],
  ['Events', 'Are there other events to list, like fight nights or UV paint nights?'],
  ['TikTok', 'Is @tattoobar._ the right account?'],
  ['Going live', 'Who looks after the tattoo-bar.co.uk domain, and who will update the site?'],
];
SLIDES.push(`<section class="slide">
  <div class="grid head-row"><h2 class="big c12">A few things to check</h2><p class="c34 lead">Before the site goes live, please confirm these details.</p></div>
  <div class="grid qs">${QS.map(([t, q]) => `<div class="q"><h3>${t}</h3><p>${q}</p></div>`).join('')}</div>
</section>`);

// Next steps
SLIDES.push(`<section class="slide">
  <div class="grid head-row"><h2 class="big c12">Next steps</h2><p class="c34 lead">Three steps to get the new site live.</p></div>
  <div class="grid panels steps">
    <div class="panel"><p class="n big">1</p><h3>Your feedback</h3><p>Tell us what you'd like changed, and answer the questions on the page before this one.</p></div>
    <div class="panel"><p class="n big">2</p><h3>Final changes</h3><p>We make the changes and send you the finished site to check.</p></div>
    <div class="panel"><p class="n big">3</p><h3>Go live</h3><p>We put the new site live on tattoo-bar.co.uk, in place of the current one.</p></div>
    <div class="panel ink"><h3>VOLSTRO</h3><p>hello@volstro.co.uk</p></div>
  </div>
</section>`);

const total = SLIDES.length;
const html = `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Albert+Sans:wght@400;600&family=Big+Shoulders+Display:wght@900&display=swap">
<style>
@page { size: 1920px 1080px; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; }
body { font-family: "Albert Sans", Arial, sans-serif; color: #17181A; }
p, h2, h3, figure { margin: 0; }
.slide { width: 1920px; height: 1080px; background: #D5D6D2; padding: 72px 72px 96px; position: relative; overflow: hidden; break-after: page; }
.slide::after { content: attr(data-n); position: absolute; right: 72px; bottom: 36px; font-size: 18px; color: #4C5256; font-variant-numeric: tabular-nums; }
.slide::before { content: "TattooBar website"; position: absolute; left: 72px; bottom: 36px; font-size: 18px; color: #4C5256; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); column-gap: 12px; }
.c1 { grid-column: 1; } .c2 { grid-column: 2; } .c3 { grid-column: 3; } .c4 { grid-column: 4; }
.c12 { grid-column: 1 / 3; } .c23 { grid-column: 2 / 4; } .c24 { grid-column: 2 / 5; } .c34 { grid-column: 3 / 5; }
.slide.grid { align-items: start; height: 1080px; }
.big { font-family: "Big Shoulders Display", "Arial Narrow", sans-serif; font-weight: 900; text-transform: uppercase; line-height: .86; }
h2.big { font-size: 104px; }
.copy h2.big { font-size: 92px; }
.copy { display: flex; flex-direction: column; gap: 24px; padding-right: 32px; }
.copy p { font-size: 27px; line-height: 1.45; }
.copy .label { font-size: 22px; font-weight: 600; color: #5536E8; }
.lead { font-size: 34px; line-height: 1.35; }
.muted { color: #4C5256; font-size: 22px; line-height: 1.4; }
.media { display: flex; align-items: flex-start; }
.center { display: flex; justify-content: center; }
.screen { width: 100%; background: #F3F3F0; box-shadow: 0 0 0 2px #17181A; }
.screen figcaption { font-size: 17px; color: #4C5256; padding: 10px 16px; border-bottom: 2px solid #17181A; }
.screen img { display: block; width: 100%; }
.media.c23 .screen { margin-top: 0; }
.phone { width: 400px; padding: 14px; background: #17181A; border-radius: 44px; }
.phone img { display: block; width: 100%; border-radius: 32px; }
.media.c4 .phone { width: 100%; max-width: 420px; }
/* cover */
.cover { display: flex; flex-direction: column; justify-content: space-between; }
.logo { font-size: 330px; text-align: center; white-space: nowrap; line-height: .8; margin-top: 20px; }
.cover-row { align-items: end; }
.cover-row .copy { gap: 20px; }
.cover-img { width: 100%; height: 470px; object-fit: cover; filter: grayscale(1); }
/* panels */
.head-row { align-items: end; margin-bottom: 64px; }
.head-row .lead { padding-right: 40px; }
.panels .panel { background: #F3F3F0; padding: 40px; min-height: 560px; display: flex; flex-direction: column; gap: 20px; }
.panels .panel.ink { background: #17181A; color: #F3F3F0; }
.panel h3 { font-size: 34px; font-weight: 600; line-height: 1.2; }
.panel p { font-size: 26px; line-height: 1.45; }
.steps .panel { min-height: 520px; }
.steps .n { font-size: 150px; color: #5536E8; }
.steps .panel.ink { justify-content: flex-end; }
/* look */
.swatches { display: grid; gap: 12px; }
.sw { height: 205px; padding: 22px; display: flex; flex-direction: column; justify-content: flex-end; gap: 4px; font-size: 22px; }
.sw b { font-size: 26px; }
.type { display: grid; gap: 56px; padding: 8px 24px 0 16px; }
.spec { font-size: 150px; }
.spec-text { font-size: 30px; line-height: 1.45; margin-bottom: 12px; }
.type .muted { margin-top: 12px; }
.tall-img { width: 100%; height: 856px; object-fit: cover; filter: grayscale(1); }
/* table */
.table { display: grid; }
.row { display: grid; grid-template-columns: 1fr 1fr; column-gap: 12px; font-size: 28px; padding: 22px 0; border-top: 2px solid #B3B6B3; }
.row span:last-child { font-weight: 600; }
.row.th { font-size: 22px; color: #4C5256; border-top: 0; padding-top: 0; }
.row.th span:last-child { font-weight: 400; }
/* questions */
.qs { row-gap: 40px; }
.q { padding: 28px 32px 0 0; border-top: 2px solid #17181A; display: grid; gap: 12px; align-content: start; }
.q h3 { font-size: 30px; font-weight: 600; }
.q p { font-size: 25px; line-height: 1.45; }
.phones .phone { width: 330px; }
.phones { align-items: start; }
</style></head><body>
${SLIDES.map((s, i) => s.replace('<section class="slide', `<section data-n="${i + 1} / ${total}" class="slide`)).join('\n')}
</body></html>`;
fs.writeFileSync(path.join(DIR, 'deck.html'), html);

(async () => {
  const b = await chromium.launch();
  // grid overlay screen for slide 4
  const g = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
  await g.goto('file://' + path.join(SITE, 'index.html'), { waitUntil: 'networkidle' });
  await g.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 500) { scrollTo(0, y); await new Promise(r => setTimeout(r, 20)); }
    const page = document.querySelector('.page'); page.style.position = 'relative';
    const o = document.createElement('div');
    o.style.cssText = 'position:absolute;top:0;bottom:0;left:24px;right:24px;display:grid;grid-template-columns:repeat(4,1fr);gap:6px;pointer-events:none;z-index:99';
    for (let i = 0; i < 4; i++) { const c = document.createElement('div'); c.style.cssText = 'background:rgba(85,54,232,.07);border-left:1px solid rgba(85,54,232,.8);border-right:1px solid rgba(85,54,232,.8)'; o.appendChild(c); }
    page.appendChild(o);
    const t = document.querySelector('.tiles'); scrollTo(0, t.getBoundingClientRect().top + scrollY + 260);
  });
  await g.waitForTimeout(400);
  await g.screenshot({ path: path.join(DIR, 'shots', 'grid.jpg'), type: 'jpeg', quality: 84 });
  await g.close();

  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + path.join(DIR, 'deck.html'), { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: PDF, width: '1920px', height: '1080px', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await b.close();
  console.log('slides', total);
})();
