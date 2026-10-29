"""Writes the TattooBar static site. Run: python3 -I build.py <site dir>

Layout: every page sits on the same 4-column grid as the homepage tiles (6 px gaps).
On the homepage, section titles take column 1 and content starts at column 2.
On the other pages, titles take columns 1-2 and content sits in columns 3 and 4.
Column classes: c1..c4 for one column, c12, c23, c34, c24, c13 for spans, call for all.
"""
import sys, os, html, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from menu_data import MENU

OUT = sys.argv[1]
E = html.escape

TATTOO = 'https://book.heygoldie.com/c12bd355a12b'
PIERCING = 'https://book.heygoldie.com/c12bd355a12b'
TABLE = 'https://app.squareup.com/appointments/book/gette9ktfugri6/LAPMY1HNKH1NQ/start'
SIPINK = 'https://www.designmynight.com/london/whats-on/sip-paint/sip-ink?t=tickets'
COURSE = 'https://tattoobar.cademy.io/3-day-beginner-tattoo-course'
COMMUNITY = 'https://tattoobar.cademy.io/tattoobar-community-program'
EVENT_MENU = 'https://drive.google.com/file/d/1b_jLhJLdsS6knueKxkQjeogpOs86eWhY/view?usp=sharing'
MAP = 'https://www.google.com/maps/search/?api=1&query=TattooBar%2C+5+Cunningham+Avenue%2C+London+E16+2TN'
IG = 'https://www.instagram.com/tattoobar.co.uk/'
IG_VILMA = 'https://www.instagram.com/vilmatattoo/'
TIKTOK = 'https://www.tiktok.com/@tattoobar._'
FACEBOOK = 'https://www.facebook.com/profile.php?id=100063746405157'
EMAIL = 'vilma@tattoobar.co'
COMMUNITY_EMAIL = 'community.cic@tattoobar.co'
TEL_TATTOO = ('07747 744016', '+447747744016')
TEL_BAR = ('07737 744016', '+447737744016')
SITE = 'https://tattoo-bar.co.uk'

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Albert+Sans:wght@400;600&amp;family=Big+Shoulders+Display:wght@900&amp;display=swap">')
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%2317181A'/%3E"
           "%3Ctext x='32' y='46' font-family='Arial Narrow,Arial,sans-serif' font-weight='900' font-size='40' text-anchor='middle' fill='%23D5D6D2'%3ETB%3C/text%3E%3C/svg%3E")
STAR = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 1.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L10 14.9l-5.2 2.7 1-5.8L1.5 7.7l5.9-.9z"/></svg>'
STARS = '<span class="stars" role="img" aria-label="5 out of 5 stars">' + STAR * 5 + '</span>'


def ext(url, text, cls='btn'):
    return f'<a class="{cls}" href="{url}" target="_blank" rel="noopener">{text}</a>'


BOOK_ITEMS = [
    (TATTOO, 'A tattoo with Vilma', 'From £50'),
    (PIERCING, 'A piercing', 'From £25'),
    (TABLE, 'A table at the bar', 'Mon–Sat'),
    (SIPINK, 'Sip &amp; Ink tickets', 'Fridays, 19:30'),
    (COURSE, 'The 3-day beginner course', '£850'),
]
NAV = [
    ('tattoo.html', 'Tattoo &amp; piercing', 'tattoo'),
    ('bar.html', 'The bar', 'bar'),
    ('events.html', 'Events', 'events'),
    ('learn.html', 'Learn', 'learn'),
    ('art.html', 'The art', 'art'),
]


def head(title, desc, path, extra='', inner=True):
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE}/{'' if path == 'index.html' else path}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{SITE}/{'' if path == 'index.html' else path}">
<meta property="og:image" content="{SITE}/img/moon-room.jpg">
<meta name="theme-color" content="#D5D6D2">
<link rel="icon" href="{FAVICON}">
{FONTS}
<link rel="stylesheet" href="css/style.css">
{extra}</head>
<body{' class="inner"' if inner else ''}>
<a class="skip" href="#main">Skip to content</a>
<div class="page">
'''


def nav(page, big_logo):
    cur = ' aria-current="page"'
    links = '\n'.join(
        f'        <li><a href="{h}"{cur if key == page else ""}>{t}</a></li>' for h, t, key in NAV)
    menu_links = '\n'.join(f'          <a href="{h}">{t}</a>' for h, t, _ in NAV + [('tattoo.html#prices', 'Prices', '')])
    book_links = '\n'.join(
        f'          <a href="{u}" target="_blank" rel="noopener">{t}<small>{s}</small></a>' for u, t, s in BOOK_ITEMS)
    left = '' if big_logo else '      <a class="logo-small" href="index.html" aria-label="TattooBar home">Tattoo Bar</a>\n'
    logo = '  <a class="logo-full" href="index.html" aria-label="TattooBar home">Tattoo Bar</a>\n' if big_logo else ''
    return f'''<header class="head">
{logo}  <nav class="nav" aria-label="Main">
    <div class="nav-main">
{left}      <details class="drop menu">
        <summary class="menu-btn">Menu</summary>
        <div class="drop-panel menu-panel">
{menu_links}
        </div>
      </details>
      <ul class="nav-links">
{links}
      </ul>
    </div>
    <div class="nav-actions">
      <a class="btn ghost lg" href="tattoo.html#prices">Prices</a>
      <details class="drop">
        <summary class="btn lg">Book</summary>
        <div class="drop-panel">
{book_links}
        </div>
      </details>
    </div>
  </nav>
</header>
'''


def footer():
    return f'''<footer class="foot">
  <div class="foot-logo" aria-hidden="true">Tattoo Bar</div>
  <div class="foot-cols">
    <div>
      <h2>Visit</h2>
      <p>5 Cunningham Avenue<br>Royal Wharf, London E16 2TN</p>
      <a href="{MAP}" target="_blank" rel="noopener">Get directions</a>
    </div>
    <div>
      <h2>Call or email</h2>
      <a href="tel:{TEL_TATTOO[1]}">Tattoos {TEL_TATTOO[0]}</a>
      <a href="tel:{TEL_BAR[1]}">Bar {TEL_BAR[0]}</a>
      <a href="mailto:{EMAIL}">{EMAIL}</a>
    </div>
    <div>
      <h2>Opening hours</h2>
      <p>Tattoo studio: Mon–Sat 11:00–21:00</p>
      <p>Bar: Mon–Fri 15:00–23:00, Sat 12:00–00:00</p>
      <p>Sundays: private events only</p>
    </div>
    <div>
      <h2>Follow</h2>
      <a href="{IG}" target="_blank" rel="noopener">Instagram</a>
      <a href="{TIKTOK}" target="_blank" rel="noopener">TikTok</a>
      <a href="{FACEBOOK}" target="_blank" rel="noopener">Facebook</a>
    </div>
  </div>
  <div class="foot-base">
    <span>© 2026 TattooBar</span>
    <span><a href="aftercare.html">Before and after your tattoo</a></span>
  </div>
</footer>
</div>
<div class="book-bar">
  {ext(TATTOO, 'Book a tattoo')}
  {ext(TABLE, 'Book a table', 'btn ghost')}
</div>
<script src="js/site.js"></script>
</body>
</html>
'''


def rows(items):
    out = []
    for name, desc, price in items:
        d = f'<small>{E(desc)}</small>' if desc else ''
        out.append(f'<span>{E(name)}{d}</span><span>{E(price)}</span>')
    return '<div class="rows">' + ''.join(out) + '</div>'


def status_block(places=('studio', 'bar')):
    names = {'studio': 'Tattoo studio', 'bar': 'Bar'}
    return '<div class="status-list" aria-live="polite">' + ''.join(
        f'<p class="status" data-status="{p}"><i></i><span>{names[p]} hours below</span></p>' for p in places) + '</div>'


def enquiry_form(topic='Tattoo', event=False, idp='q'):
    topics = ['Tattoo', 'Piercing', 'Table booking', 'Event hire', 'Course', 'Something else']
    opts = ''.join(f'<option{" selected" if t == topic else ""}>{t}</option>' for t in topics)
    event_fields = f'''
      <div class="field"><label for="{idp}-date">Date</label><input id="{idp}-date" name="date" type="date"></div>
      <div class="field"><label for="{idp}-guests">Number of guests</label><input id="{idp}-guests" name="guests" type="number" min="1" inputmode="numeric"></div>''' if event else ''
    return f'''<form class="form" data-enquiry="{EMAIL}" novalidate>
      <div class="field"><label for="{idp}-name">Name</label><input id="{idp}-name" name="name" autocomplete="name" required></div>
      <div class="field"><label for="{idp}-email">Email</label><input id="{idp}-email" name="email" type="email" autocomplete="email" required></div>
      <div class="field"><label for="{idp}-phone">Phone (optional)</label><input id="{idp}-phone" name="phone" type="tel" autocomplete="tel"></div>
      <div class="field"><label for="{idp}-topic">What is it about?</label><select id="{idp}-topic" name="topic">{opts}</select></div>{event_fields}
      <div class="field"><label for="{idp}-message">Message</label><textarea id="{idp}-message" name="message" required placeholder="{'Tell us about your event and what you need' if event else 'Your idea, size and placement, or your question'}"></textarea></div>
      <div class="btns"><button class="btn" type="submit">Send enquiry</button></div>
      <p class="form-note">This opens your email app with your message ready to send to {EMAIL}.</p>
      <p class="form-done" hidden>Your email app should now be open with your message. If nothing happened, email {EMAIL} or call {TEL_TATTOO[0]}.</p>
    </form>'''


def ticks(items, cls='ticks'):
    return f'<ul class="{cls}">' + ''.join(f'<li>{i}</li>' for i in items) + '</ul>'


def write(name, content):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        f.write(content)


def sec(id_, title, body, extra='', cls=''):
    """A section: big title, then content. Its columns come from the page type (see the module docstring)."""
    return f'''<section class="sec{' ' + cls if cls else ''}" id="{id_}" aria-labelledby="{id_}-title">
  <h2 class="sec-title big" id="{id_}-title">{title}</h2>
  <div class="sec-body">{body}</div>{extra}
</section>
'''


def page_head(title, lead=None, media=None, meta=''):
    m = ''
    if media:
        src, alt, w, h, pos = media
        m = f'\n  <figure class="head-media"><img src="img/{src}" alt="{E(alt)}" width="{w}" height="{h}" style="object-position:{pos}"></figure>'
    side = f'\n  <div class="head-meta"><p class="lead">{lead}</p>{meta}</div>' if lead else ''
    return f'''<section class="page-head" aria-labelledby="page-title">
  <h1 class="big" id="page-title">{title}</h1>{side}{m}
</section>
'''


# ---------- Shared content ----------
WORK = [
    ('realism', 'work-realism-back-piece', 'Realism', 'Black and grey realism back piece with a skull-faced figure and a woman'),
    ('fine-line', 'work-fine-line-flower', 'Fine line', 'Fine line flower tattoo on the shoulder'),
    ('geometric', 'work-geometric-sleeve', 'Geometric', 'Geometric forearm tattoo of hexagons fading into dotwork'),
    ('realism', 'work-realism-cross', 'Realism', 'Realism tattoo of a woman holding a cross over her face'),
    ('fine-line', 'work-fine-line-lotus', 'Fine line', 'Fine line lotus ornament on the wrist'),
    ('geometric', 'work-geometric-shoulder', 'Geometric', 'Geometric shoulder tattoo with hexagons and dotwork'),
    ('realism', 'work-realism-skull-sleeve', 'Realism', 'Black and grey sleeve with skulls'),
    ('fine-line', 'work-fine-line-spine', 'Fine line', 'Fine line tattoo running down the spine'),
    ('geometric', 'work-geometric-wrist', 'Geometric', 'Geometric band tattoo around the wrist'),
    ('realism', 'work-realism-portrait', 'Realism', "Realism tattoo of a woman's face with clown make-up"),
    ('fine-line', 'work-fine-line-forearm', 'Fine line', 'Fine line ornamental tattoo on the forearm'),
    ('fine-line', 'work-fine-line-sternum', 'Fine line', 'Fine line ornament on the sternum'),
]
SIZES = {'work-realism-cross': (900, 1124)}
FEATURED = ['work-realism-back-piece', 'work-geometric-sleeve', 'work-fine-line-flower', 'work-realism-cross']
MORE = [w[1] for w in WORK if w[1] not in FEATURED]


def work_items(names, href=None):
    out = []
    for s, f, c, a in sorted((w for w in WORK if w[1] in names), key=lambda w: names.index(w[1])):
        w, h = SIZES.get(f, (800, 999))
        img = f'<img src="img/{f}.jpg" alt="{E(a)}" width="{w}" height="{h}" loading="lazy"><span class="cap">{c}</span>'
        if href:
            img = f'<a href="{href}">{img}</a>'
        out.append(f'      <li data-style="{s}">{img}</li>')
    return '\n'.join(out)


REVIEWS = [
    ('I would recommend this 100%! Piercing done to perfection! A very warm welcome! A big thank you!', 'Ilona'),
    ('Hands of gold! I recommend 100%, I am more than satisfied! Does the job so quickly and so unrealistically, advising, super!!', 'Ziedune'),
    ('The best tattoo artist! Very friendly and does your tattoo really nice. Recommend it!', 'Karolina'),
    ('Would definitely recommend this! I visited three times, everything chiki piki! Cover up well done!', 'Ernesta Liucija'),
    ('Had a ribbon tattoo done by Vilma this morning, fantastic work with great colours and shade. She went through everything very clearly with me before the tattoo to set my mind. Would definitely recommend to anyone, whether a first time or not.', 'Kristi'),
    ('I love my cover up! Thank you! Vilma is a great artist and very nice person too! Would definitely recommend!', 'Ausra'),
]
quotes = '\n'.join(
    f'      <li class="panel"><blockquote>{E(q)}</blockquote><p class="quote-by"><cite>{E(n)}</cite>{STARS}</p></li>' for q, n in REVIEWS)

TATTOO_PRICES = [
    ('Small', 'Up to 8 cm', 'from £50'),
    ('Medium', 'Up to 15 cm', 'from £140'),
    ('Large', 'Up to 25 cm', 'from £250'),
    ('By the hour', 'Individual sketch', '£85'),
]
PIERCING_PRICES = [
    ('Ear lobe, single', '', '£25'),
    ('Ear lobe, pair', '', '£40'),
    ('Helix, rook or tragus', '', '£35'),
    ('Nostril or septum', '', '£35'),
    ('Lip', '', '£35'),
    ('Belly button', '', '£35'),
]
STUDIO_HOURS = [('Monday to Saturday', '', '11:00–21:00'), ('Sunday', '', 'Closed')]
BAR_HOURS = [('Monday to Friday', '', '15:00–23:00'), ('Saturday', '', '12:00–00:00'), ('Sunday', '', 'Private events only')]

ld = {
    '@context': 'https://schema.org',
    '@type': ['TattooParlor', 'BarOrPub'],
    'name': 'TattooBar',
    'url': SITE,
    'image': f'{SITE}/img/moon-room.jpg',
    'email': EMAIL,
    'telephone': TEL_TATTOO[1],
    'address': {'@type': 'PostalAddress', 'streetAddress': '5 Cunningham Avenue', 'addressLocality': 'London',
                'postalCode': 'E16 2TN', 'addressCountry': 'GB'},
    'openingHoursSpecification': [
        {'@type': 'OpeningHoursSpecification', 'name': 'Tattoo studio',
         'dayOfWeek': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'], 'opens': '11:00', 'closes': '21:00'},
        {'@type': 'OpeningHoursSpecification', 'name': 'Bar',
         'dayOfWeek': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], 'opens': '15:00', 'closes': '23:00'},
        {'@type': 'OpeningHoursSpecification', 'name': 'Bar', 'dayOfWeek': 'Saturday', 'opens': '12:00', 'closes': '00:00'},
    ],
    'sameAs': [IG, TIKTOK, FACEBOOK],
}
LD = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + '</script>\n'


# ---------- Home ----------
band_rows = ''.join(
    f'    <div class="band-row{" lo" if i >= 3 else ""}">{w} &nbsp;{w} &nbsp;{w}</div>\n'
    for i, w in enumerate(['Ink &amp; drink', 'Pain &amp; pleasure'] * 3))

home = head('TattooBar | Tattoo studio and cocktail bar, Royal Wharf, London E16',
            'Custom tattoos and piercing by Vilma, a tattoo artist for 20 years, with a cocktail bar in the same room. 5 Cunningham Avenue, Royal Wharf, London E16 2TN.',
            'index.html', LD, inner=False) + nav('home', True) + f'''<main id="main">
<section class="hero" aria-labelledby="intro-title">
  <div class="band" aria-hidden="true">
{band_rows}    <img class="band-photo" src="img/hero-tattooing.jpg" alt="" width="1400" height="930">
  </div>
  <div class="intro on-ink">
    <div class="intro-text">
      <h1 id="intro-title">Tattoo studio and cocktail bar at Royal Wharf, London E16.</h1>
      <p>Where pain and pleasure meet.</p>
    </div>
    <div class="intro-actions">{ext(TATTOO, 'Book a tattoo', 'btn lg')}{ext(TABLE, 'Book a table', 'btn ghost lg')}</div>
  </div>
</section>

<nav class="tiles" aria-label="Explore TattooBar">
  <a class="tile" href="bar.html"><img src="img/moon-room.jpg" alt="" width="1600" height="1200"><span class="cap">The bar</span></a>
  <a class="tile uv" href="events.html#sip-and-ink"><span class="big">Sip &amp; Ink</span><p>Learn to tattoo on practice skin, drink included. Fridays 19:30–21:30, from £38.50.</p></a>
  <a class="tile" href="tattoo.html"><img src="img/work-realism-cross.jpg" alt="" width="900" height="1124"><span class="cap">Tattoos by Vilma</span></a>
  <a class="tile paper" href="bar.html#happy-hour"><span class="big">Happy hour</span><p>Any 2 cocktails for £15. Mon–Thu 15:00–19:00, Fri–Sat 12:00–18:00.</p></a>
  <a class="tile ink" href="{TATTOO}" target="_blank" rel="noopener"><span class="big">Book a tattoo</span><p>Small tattoos from £50. 20 years of experience.</p></a>
  <a class="tile" href="art.html#counter"><img src="img/counter.jpg" alt="" width="1600" height="1200"><span class="cap">24 machines, 20 years</span></a>
  <a class="tile conc" href="learn.html"><span class="big">Learn to tattoo</span><p>3-day beginner course, £850. Free 12-week community programme.</p></a>
  <a class="tile" href="art.html#guardian"><img src="img/guardian.jpg" alt="" width="1600" height="1200"><span class="cap">The Guardian</span></a>
</nav>

''' + sec('vilma', 'Vilma', f'''
    <div class="g3">
      <img class="c1 photo" src="img/vilma.jpg" alt="Vilma, the tattoo artist at TattooBar" width="1200" height="1349" loading="lazy">
      <div class="c23 cell prose top-align">
        <p class="lead">Hey, I'm Vilma, and my main inspiration is you.</p>
        <p>20 years of tattooing, from geometric and realism to fine line, with every design made for the person wearing it.</p>
        <p>Vilma started at art school, painting angels, demons and fantasy worlds. A tattoo artist saw the talent in her hands and suggested she try tattooing, and she has never stopped.</p>
        <p>She keeps to the highest standards of hygiene, and keeps learning through courses, workshops and conventions.</p>
        <p>The idea for TattooBar came from her clients. After a tattoo, they wanted a cocktail as a reward for the pain. So she put a bar in the studio.</p>
        <div class="btns"><a class="btn lg" href="tattoo.html">See Vilma's work</a></div>
      </div>
    </div>
  ''') + f'''
<section aria-label="Recent work">
  <ul class="work-grid">
{work_items(FEATURED, 'tattoo.html')}
  </ul>
</section>

''' + sec('the-bar', 'The bar', f'''
    <div class="g3"><p class="c12 cell lead">A bar inside the tattoo studio, with a wide choice of cocktails and drinks and Vilma's own artwork on the walls.</p></div>
    <div class="g3">
      <div class="c1 panel ink on-ink tall">
        <h3>Happy hour</h3>
        <p class="big">Any 2 cocktails £15</p>
        <p class="muted">Mon–Thu 15:00–19:00<br>Fri–Sat 12:00–18:00</p>
        <div class="btns push"><a class="btn ghost" href="bar.html#menu">See the menu</a></div>
      </div>
      <div class="c23 panel tall">
        <h3>Bar hours</h3>
        {rows(BAR_HOURS)}
        <p class="muted">Book the whole space for your event, from £25 a head.</p>
        <div class="g2 push">{ext(TABLE, 'Book a table', 'btn lg c1')}<a class="btn ghost lg c2" href="events.html#hire">Hire the space</a></div>
      </div>
    </div>
  ''') + sec('reviews', 'Reviews', f'''
    <ul class="g3 quotes">
{quotes}
    </ul>
  ''') + sec('info', 'Info', f'''
    <div class="g3">
      <div class="c1 cell stack-sm">
        {status_block()}
        <div><h3 class="list-title">Tattoo studio</h3>{rows(STUDIO_HOURS)}</div>
      </div>
      <div class="c2 cell">
        <h3 class="list-title">Bar</h3>{rows(BAR_HOURS)}
      </div>
      <div class="c3 cell stack-sm">
        <dl class="contact">
          <div><dt>Address</dt><dd>5 Cunningham Avenue, Royal Wharf, London E16 2TN</dd></div>
          <div><dt>Nearest station</dt><dd>Pontoon Dock (DLR)</dd></div>
          <div><dt>Tattoos and piercing</dt><dd><a href="tel:{TEL_TATTOO[1]}">{TEL_TATTOO[0]}</a></dd></div>
          <div><dt>Bar</dt><dd><a href="tel:{TEL_BAR[1]}">{TEL_BAR[0]}</a></dd></div>
          <div><dt>Email</dt><dd><a href="mailto:{EMAIL}">{EMAIL}</a></dd></div>
        </dl>
        <div class="btns">{ext(MAP, 'Get directions', 'btn ghost')}</div>
      </div>
    </div>
  ''') + '</main>\n' + footer()
write('index.html', home)


# ---------- Tattoo and piercing ----------
FILTERS = '''<div class="filters fill" role="group" aria-label="Filter by style">
      <button class="filter" type="button" data-filter="all" aria-pressed="true">All</button>
      <button class="filter" type="button" data-filter="geometric" aria-pressed="false">Geometric</button>
      <button class="filter" type="button" data-filter="realism" aria-pressed="false">Realism</button>
      <button class="filter" type="button" data-filter="fine-line" aria-pressed="false">Fine line</button>
    </div>'''

tattoo = head('Tattoo and piercing | TattooBar',
              'Custom tattoos and piercing by Vilma at TattooBar, Royal Wharf, London E16. Small tattoos from £50, piercing from £25.',
              'tattoo.html') + nav('tattoo', False) + f'''<main id="main">
<section class="page-head" aria-labelledby="page-title">
  <h1 class="big" id="page-title">Tattoo and piercing</h1>
  <ul class="work-grid head-media">
{work_items(FEATURED)}
  </ul>
</section>

<section class="split" id="vilma" aria-labelledby="vilma-title">
  <div class="split-text cell">
    <h2 class="big" id="vilma-title">Vilma</h2>
    <p class="lead">20 years of experience.</p>
    <p>Custom geometric, realism and fine line tattoos, and piercing, with the highest standards of hygiene.</p>
    <p><a class="link" href="art.html">The art and the place</a></p>
  </div>
  <div class="split-action">{ext(TATTOO, 'Book a tattoo', 'btn lg wide')}</div>
  <img class="split-media" src="img/hero-tattooing.jpg" alt="Vilma tattooing a client at TattooBar" width="1400" height="930" loading="lazy">
</section>

<section class="sec stacked" id="prices" aria-labelledby="prices-title">
  <h2 class="sec-title big" id="prices-title">Prices</h2>
  <div class="sec-wide">
    <div class="g4">
      <div class="c12 panel"><h3>Tattoo</h3>{rows(TATTOO_PRICES)}</div>
      <div class="c34 panel"><h3>Piercing</h3>{rows(PIERCING_PRICES)}</div>
      {ext(TATTOO, 'Book', 'btn lg call')}
    </div>
    <p class="muted price-note">Tattoo prices are starting prices. Read <a class="link" href="aftercare.html">how to prepare and how to look after your tattoo</a>.</p>
  </div>
</section>

<section class="sec ruled" id="more-work" aria-labelledby="more-title">
  <h2 class="sec-title big" id="more-title">More work</h2>
  <div class="sec-body sec-body-end">
    {FILTERS}
  </div>
  <div class="sec-wide">
    <ul class="work-grid">
{work_items(MORE)}
    </ul>
    <p class="work-more big-link"><a class="link" href="{IG}" target="_blank" rel="noopener">See more work on Instagram</a></p>
  </div>
</section>
</main>
''' + footer()
write('tattoo.html', tattoo)


# ---------- The art ----------
def artwork(id_, name, img, alt, w, h, title, lines, text):
    m = ''.join(f'<p class="m">{l}</p>' for l in lines)
    return f'''<section class="split art" id="{id_}" aria-labelledby="{id_}-title">
  <h2 class="split-text big" id="{id_}-title">{name}</h2>
  <div class="split-action label wide-label"><p class="t">{title}</p>{m}<p>{text}</p></div>
  <img class="split-media" src="img/{img}" alt="{E(alt)}" width="{w}" height="{h}" loading="lazy">
</section>
'''


art = head('The art and the place | TattooBar',
           "Vilma's story and the artworks inside TattooBar: the Guardian of the Bar, the counter sculpture made with 24 tattoo machines, and the Moon.",
           'art.html') + nav('art', False) + '<main id="main">\n' + page_head(
    'The art and the place',
    'When creating this interior, we aimed to break away from the ordinary and offer something unlike any other place. Every detail was chosen to make a visit memorable.',
    ('guardian-room.jpg', 'The bar room with the Guardian sculpture on the wall and tall windows', 1400, 1023, '50% 45%')) + sec(
    'vilma', 'Vilma', f'''<div class="cell prose">
      <p class="lead">Vilma began her artistic journey at art school, painting angels, demons and fantasy worlds.</p>
      <p>That theme has always stayed close to her heart and fills her work with magic and mysticism. Her real passion showed itself when she met a tattoo artist who recognised the talent in her hands. He suggested she try tattooing, and from that moment her life changed.</p>
      <p>Tattooing became her calling. She wants every client to leave with a unique piece of art made with love and skill. To her, a tattoo is more than an image on the skin: it is a form of self-expression that should bring joy.</p>
      <p><a class="link" href="{IG_VILMA}" target="_blank" rel="noopener">Vilma on Instagram</a></p>
    </div>''') + sec(
    'idea', 'The idea', '''<div class="cell prose">
      <p class="lead">The idea to combine a bar and a tattoo studio came from conversations with clients.</p>
      <p>Many said that after getting a tattoo they wanted a cocktail, a well-deserved reward for the pain. TattooBar brings both together in one cosy room: a place where pain and pleasure meet.</p>
    </div>''') + artwork(
    'guardian', 'The Guardian', 'guardian.jpg', 'The Guardian of the Bar, a pale sculpted female face emerging from the concrete wall', 1600, 1200,
    'The Guardian of the Bar', ['Vilma', 'Sculpture'],
    'As soon as Vilma saw the empty wall, she knew a Guardian belonged there. A figure of strength, calm and timeless femininity, she gazes into eternity and shields the bar from the hustle and bustle of the outside world.') + artwork(
    'counter', 'The counter', 'counter.jpg', 'The bar counter with TATTOO BAR cast in relief and tattoo machines set into it', 1600, 1200,
    'TattooBar counter sculpture', ['Vilma', '24 tattoo machines from 20 years of tattooing, set into the bar counter'],
    'The TattooBar inscription marks her years of dedication to tattooing. Every detail tells a story, and the counter holds her memories, her experience and her love for art.') + artwork(
    'moon', 'The Moon', 'moon-room.jpg', 'The glowing Moon artwork on the wall of the bar room', 1600, 1200,
    'The Moon', ['Vilma'],
    'The idea came when Vilma realised the room, in its cool tones, felt like a dive into space. The glowing Moon invites you to reach for the stars just by walking in, so every visit is a small journey to the Moon.') + '</main>\n' + footer()
write('art.html', art)


# ---------- The bar and menu ----------
def menu_section(id_, title, groups):
    """Title in column 1, the drinks in three columns across 2-4."""
    cols, load = [[], [], []], [0, 0, 0]
    if len(groups) == 1 and not groups[0][0]:
        items = groups[0][2]
        per = -(-len(items) // 3)
        for i in range(3):
            if items[i * per:(i + 1) * per]:
                cols[i].append(rows(items[i * per:(i + 1) * per]))
    else:
        for gt, sizes, items in groups:
            sz = f'<p class="group-sizes">{E(sizes)}</p>' if sizes else ''
            i = load.index(min(load))
            cols[i].append(f'<div><h3 class="list-title">{E(gt)}</h3>{sz}{rows(items)}</div>')
            load[i] += len(items) + 2
    body = '<div class="g3">' + ''.join(f'<div class="c{i + 1} cell menu-col">{"".join(c)}</div>' for i, c in enumerate(cols)) + '</div>'
    return sec(id_, title, body, cls='menu-sec')


jump = '<ul class="jump">' + ''.join(f'<li><a href="#{i}">{t}</a></li>' for i, t, _ in MENU) + '</ul>'
bar = head('The bar and menu | TattooBar',
           'Cocktails, wine, beer and food inside the TattooBar tattoo studio at Royal Wharf. Happy hour: any 2 cocktails for £15.',
           'bar.html') + nav('bar', False) + '<main id="main">\n' + page_head(
    'The bar',
    "Cocktails, wine, beer and food in the tattoo studio, with Vilma's artwork on the walls.",
    ('cocktails.jpg', 'Three cocktails in front of the glowing Moon artwork', 1000, 1333, '50% 30%'),
    f'{status_block(("bar",))}<div class="g2">{ext(TABLE, "Book a table", "btn lg c1")}<a class="btn ghost lg c2" href="#menu">See the menu</a></div>') + sec(
    'happy-hour', 'Happy hour', f'''<div class="g2">
      <div class="c1 panel ink on-ink tall"><p class="big">Any 2 cocktails £15</p><p class="muted">Monday to Thursday<br>15:00–19:00</p><p class="muted">Friday and Saturday<br>12:00–18:00</p></div>
      <div class="c2 panel tall"><h3>Bar hours</h3>{rows(BAR_HOURS)}</div>
      {ext(TABLE, 'Book a table', 'btn lg call')}
    </div>''') + sec('menu', 'Menu', f'<p class="lead">Jump to a section.</p>{jump}') + ''.join(
    menu_section(i, t, g) for i, t, g in MENU) + sec(
    'hire', 'Private hire', f'''<p class="lead">Book the whole space for your celebration, from £25 a head.</p>
    <div class="g2"><a class="btn lg c1" href="events.html#hire">Private hire details</a></div>''') + '</main>\n' + footer()
write('bar.html', bar)


# ---------- Events ----------
events = head('Events and private hire | TattooBar',
              'Sip & Ink on Fridays: learn to tattoo on practice skin with a drink in hand. Private hire of the TattooBar space from £25 a head.',
              'events.html') + nav('events', False) + '<main id="main">\n' + page_head(
    'Events',
    'Sip &amp; Ink on Fridays, and the whole space for your own celebration.',
    ('workshop.jpg', 'A group practising tattooing on synthetic skin at long tables in TattooBar', 1600, 900, '50% 50%')) + sec(
    'sip-and-ink', 'Sip &amp; Ink', f'''<p class="lead">Ever wondered what it's like to be a tattoo artist? Learn to tattoo on practice skin, guided step by step by a professional tattoo artist. No experience needed.</p>
    <div class="g2">
      <div class="c1 cell"><h3 class="list-title">The details</h3>{rows([('When', '', 'Fridays, 19:30–21:30'), ('Price', '', 'from £38.50'), ('Age', '', '18+')])}</div>
      <div class="c2 cell"><h3 class="list-title">Included</h3>{ticks(['A glass of house wine or a pint of beer', 'All tattooing materials and equipment', 'Expert instruction in a relaxed, creative atmosphere'])}</div>
      {ext(SIPINK, 'Get tickets', 'btn lg c1')}
    </div>''') + sec(
    'hire', 'Private hire', f'''<p class="lead">Send us the details of your event and the number of guests, and we will do everything we can to make your celebration unforgettable.</p>
    <div class="g2">
      <div class="c1 cell stack-sm"><h3 class="list-title">Minimum spend per person</h3>{rows([('Daytime', '11:00–17:00, for 2 hours', 'from £25'), ('Weekend evenings', '18:00–23:00, for 2 hours', 'from £35')])}
        <p class="muted">Sundays are kept for private events.</p>
        <p><a class="link" href="{EVENT_MENU}" target="_blank" rel="noopener">Event food and drinks menu</a></p>
      </div>
      <div class="c2 panel"><h3>Plan your event</h3>{enquiry_form('Event hire', True, 'e')}</div>
    </div>''') + '</main>\n' + footer()
write('events.html', events)


# ---------- Learn ----------
DAYS = [
    ('Day 1: Foundations', ['Machine setup', 'Needle knowledge', 'Hygiene and safety', 'Linework basics', 'Practice on fake skin']),
    ('Day 2: Technique', ['Shading techniques', 'Hand control', 'Fine line practice', 'Design placement', 'Real tattoo workflow']),
    ('Day 3: Professional practice', ['Full mini tattoo process', 'Client preparation', 'Aftercare guidance', 'Social media and branding', 'Portfolio content', 'Certificate ceremony']),
]
days = ('<div class="g4 call days">' + ''.join(f'<div class="c{i + 1} panel square"><h3>{t}</h3>{ticks(items)}</div>' for i, (t, items) in enumerate(DAYS))
        + f'<a class="c4 tile uv square" href="{COURSE}" target="_blank" rel="noopener"><span class="big">Book the course</span><p>3 days with Vilma, £850.</p></a></div>')
FAQ = [
    ('Do I need any experience?', 'No. This is a beginner course for complete newcomers with no tattooing experience.'),
    ('Will I tattoo real skin?', 'No. All practice is on synthetic practice skin, for training and safety.'),
    ('Do I get a certificate?', 'Yes. You receive a TattooBar Certificate of Completion when you finish the course.'),
    ('Do I need to bring anything?', 'All the essential training equipment is provided. You may be advised on optional personal items after booking.'),
    ('Are deposits refundable?', 'No. Deposits are non-refundable, as they secure your place and cover course resources.'),
    ('Is there an age limit?', 'Yes. You must be 18 or over.'),
]
faq = '<div class="faq">' + ''.join(f'<details><summary>{q}</summary><p>{a}</p></details>' for q, a in FAQ) + '</div>'

learn = head('Learn to tattoo | TattooBar',
             'A 3-day beginner tattoo course with Vilma for 2 to 5 students, £850, and the free 12-week Creative Connections community programme at TattooBar, London E16.',
             'learn.html') + nav('learn', False) + '<main id="main">\n' + page_head(
    'Learn to tattoo',
    'A 3-day beginner course with Vilma, and a free 12-week community programme.',
    ('studio-sign.jpg', 'The tattoo studio side of TattooBar with its wall sign and white tables', 1400, 1021, '50% 50%')) + sec(
    'course', 'Beginner course', f'''<p class="lead">Learn the fundamentals of tattooing with Vilma in a small group. The course is built for complete beginners who want strong technical foundations and the real workflow of a professional studio.</p>
    <div class="g2">
      <div class="c1 cell"><h3 class="list-title">The details</h3>{rows([('Price', 'Including VAT', '£850'), ('Length', '3 days in a row', '11:00–16:00'), ('Group', '', '2–5 students'), ('Age', '', '18+')])}</div>
      <div class="c2 cell"><h3 class="list-title">Included</h3>{ticks(['All materials and equipment', 'Drinks and refreshments', 'Completion certificate', '30 days of support after the course'])}</div>
    </div>''', extra=f'''
  {days}
  <div class="c23">{faq}</div>''') + sec(
    'community', 'Community programme', f'''<p class="lead">Creative Connections is a free 12-week programme for adults that brings people together through creativity, art and beginner tattoo design.</p>
    <p class="cell">Each week mixes creative wellbeing workshops with beginner tattoo design sessions. All practice is on paper and synthetic skin. Nobody gets tattooed.</p>
    <div class="g2">
      <div class="c1 cell"><h3 class="list-title">The details</h3>{rows([('Cost', '', 'Free'), ('When', 'Tuesdays and Fridays', '15:00–17:00'), ('Length', '', '12 weeks'), ('Group', '', 'Up to 10 people'), ('Age', '', '18+')])}</div>
      <div class="c2 cell"><h3 class="list-title">Included</h3>{ticks(['Creative wellbeing workshops', 'Beginner tattoo design classes', 'Drawing and illustration techniques', 'Practice on synthetic skin', 'Guidance from a professional artist', 'Certificate of participation'])}</div>
      <ul class="c1 quotes"><li class="panel"><blockquote>I started doing this free 12 week course with Vilma and I love it so much I even brought a friend and she enjoyed it too.</blockquote><p class="quote-by"><cite>Gabriella Dias</cite>{STARS}</p></li></ul>
    </div>
    <div class="g2">{ext(COMMUNITY, 'Register for a free place', 'btn lg c1')}<a class="btn ghost lg c2" href="mailto:{COMMUNITY_EMAIL}">Email us</a></div>
    <p class="muted">Places are limited to 10, so register early. Email <a class="link" href="mailto:{COMMUNITY_EMAIL}">{COMMUNITY_EMAIL}</a>.</p>''') + sec(
    'sip', 'Just curious?', '''<p class="lead">Try Sip &amp; Ink on a Friday night: two hours tattooing practice skin, with a drink.</p>
    <div class="g2"><a class="btn ghost lg c1" href="events.html#sip-and-ink">About Sip &amp; Ink</a></div>''') + '</main>\n' + footer()
write('learn.html', learn)


# ---------- Aftercare ----------
after = head('Before and after your tattoo | TattooBar',
             'How to prepare your skin for a tattoo session at TattooBar, and how to look after your new tattoo while it heals.',
             'aftercare.html') + nav('aftercare', False) + '<main id="main">\n' + page_head(
    'Before and after',
    'How to get your skin ready for your session, and how to look after your new tattoo.') + sec(
    'before', 'Before', ticks(['Get hydrated and moisturise', 'Shave and exfoliate', 'Eat before the session',
                              'Wear comfortable, suitable clothes', 'Avoid drugs and certain products before the session'])) + sec(
    'aftercare', 'Aftercare', '''<ol class="steps">
      <li>Remove the bandage after 1 to 3 hours.</li>
      <li>Wash with soap and water, using antibacterial soap.</li>
      <li>Apply a small amount of antibacterial ointment and pat dry with a towel.</li>
      <li>Do this at least 3 times a day for 3 days.</li>
      <li>After 3 days, use a non-perfumed hand lotion.</li>
    </ol>''') + sec(
    'healing', 'While it heals', ticks(["Don't swim or soak it in water", "Don't touch it except to wash it",
                                        "Don't let anyone else touch it", "Don't pick at any scabs",
                                        'Keep it out of the sun for 2 weeks'], 'ticks dont')) + sec(
    'dont-use', "Don't use", ticks(['Neosporin', 'Peroxide', 'Alcohol', 'Olive oil', 'Corn oil'], 'ticks dont') +
    f'<p class="muted">Questions while it heals? Call the studio on <a class="link" href="tel:{TEL_TATTOO[1]}">{TEL_TATTOO[0]}</a>.</p>') + '</main>\n' + footer()
write('aftercare.html', after)
print('built', sorted(os.listdir(OUT)))
