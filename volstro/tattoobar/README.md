# TattooBar website

A new website for TattooBar, the tattoo studio and cocktail bar at 5 Cunningham Avenue, Royal Wharf, London E16 2TN. It replaces the look of their current Tilda site at tattoo-bar.co.uk; every business detail comes from that site, their Linktree, Cademy and DesignMyNight pages (October 2026).

Design: the approved "Cast" direction. Concrete, ink and one UV violet accent. Two fonts: Big Shoulders Display for the logo and big words, Albert Sans for everything else. 12-column grid, 24 px outside margins (20 px on phones), 80 px between every section (60 px on phones).

## Pages

| File | Page |
| --- | --- |
| `site/index.html` | Home: logo, hero, tiles, Vilma, 4 work photos, the bar, reviews and info |
| `site/tattoo.html` | Tattoo and piercing: work, Vilma, prices and more work. The Prices button in the header links to its prices section |
| `site/art.html` | The art and the place: Vilma's story, the Guardian, the counter, the Moon |
| `site/bar.html` | The bar: happy hour, hours and the full drinks and food menu |
| `site/events.html` | Sip & Ink and private hire, with an event enquiry form |
| `site/learn.html` | The 3-day beginner course and the free community programme |
| `site/aftercare.html` | Before the session and tattoo aftercare |

## Preview locally

```bash
cd volstro/tattoobar/site
```

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Editing

The pages are plain HTML, written by `build/build.py`. Booking links, phone numbers, hours, prices and page copy are at the top of that file or in its page sections, and the menu is in `build/menu_data.py`. After a change, rebuild all pages:

```bash
python3 -I volstro/tattoobar/build/build.py volstro/tattoobar/site
```

Opening hours for the "open now" line live in `site/js/site.js`.

## Going live

The site is static, so it runs on any static host (Netlify, Cloudflare Pages, GitHub Pages). Upload the `site` folder, then point the tattoo-bar.co.uk domain at the host instead of Tilda.

The enquiry forms open the visitor's email app with the message filled in. To receive form submissions directly, connect the forms to a form service (for example Netlify Forms or Formspree) when the site is hosted.

## To confirm with the client

1. Booking: tattoos and piercing go to Goldie (the link on their Linktree), tables to the Square page their current "Book a table" button uses. Confirm these are the tools they use.
2. Happy hour on Fridays: their site says 12:00–18:00, but the bar opens at 15:00 on weekdays.
3. Experience: their site says 20 years; the Cademy course page says over 24. The new site says "over 20 years".
4. Menu fixes: "1644 Blanc" is shown as 1664 Blanc; the Pimm's description was a copy of the Whiskey Sour, so it was removed; the Limoncello Spritz has no ingredients listed.
5. The community programme now uses the studio number 07747 744016, which the client confirmed as correct.
6. TikTok links to @tattoobar._ (from Linktree). The old site linked to @vilma_tattoo.
7. UTMA Fight Night and the UV glow sip & paint night are left out because they are past or unconfirmed. Add current events to `events.html` when known.
8. Logo: the wordmark is set in Big Shoulders Display. Swap in their logo files if they have them.
