---
name: volstro-website
description: Build a full website for a VOLSTRO client, from the first questions to the client presentation. Use whenever the user gives a company or business and asks for a website, a redesign, a "new look", a brief, a mood board or a markup PDF, or says "make a website for…", even without saying VOLSTRO. Holds the user's house style (one 4-column grid on every page, two fonts, strict alignment), the feedback loop they like (one long markup PDF they draw on), and scripts that check alignment and make the PDFs.
---

# VOLSTRO websites

VOLSTRO is the user's London web design studio. The user designs with you: they approve a direction, sketch wireframes, then mark up every round on an iPad. This skill is what we learned building TattooBar (`volstro/tattoobar/`, eight rounds of feedback, October 2026). Following it should take a site from brief to sign-off in two or three rounds instead of eight.

Read `references/house-style.md` before designing anything. It lists the corrections the user made again and again. Read `references/tattoobar-feedback-log.md` when you want the reason behind a rule.

## Workflow

### 1. Intake (first reply)

Don't wait for answers before starting research. When the user names a company:

- Find their current website and public listings (Google, Fresha, Linktree, booking pages, DesignMyNight). Render pages with Playwright, since builders like Tilda and Wix need JavaScript. Pull every real detail: services, prices, hours, phone numbers, address, team story, reviews, photos, every booking link.
- List anything that contradicts itself (two sets of hours, two phone numbers, map pin at a different address). TattooBar had five of these.
- In the same reply, ask the user in one numbered list:
  1. **2–4 reference sites or Pinterest pins they like.** The user's own references beat invented concepts every time.
  2. **Do they have a homepage sketch?** They drew one for TattooBar. Building to it first saves a full round.
  3. **Social handles and links to confirm.** Scraped ones were wrong: the Instagram handle, the bar phone number and the Sip & Ink schedule all needed correcting.
  4. The contradictions you found, as questions.
  5. Anything only the client knows (logo files, booking tools they actually use).

Keep questions to one message. The user answers briefly, often several messages later, and sometimes just says "make it".

### 2. Approval pack (one private Artifact page)

Show: who the site is for, a mood board (Pinterest pins plus the client's own photos), colours with contrast ratios, **three font pairings as live specimens**, and the grid. Rules:

- Build layout options from the user's references, not from a clever concept. The "seam" layout from my own idea was rejected; the layout copied from their references was approved.
- Two fonts only, and offer them as choices. My first pairing was rejected; they picked Big Shoulders from the options.
- Show it on the real hero with real content, not abstract swatches alone.
- Then apply their tweaks (logo visibility, opacity, margins, spacing) on the same page until they say go.

### 3. Build

- Start from the TattooBar code instead of a blank page: `volstro/tattoobar/build/build.py` (page generator: header, footer, sections, tiles, price rows, forms) and `volstro/tattoobar/site/css/style.css` (the grid, tokens, components). Copy them into `volstro/<client>/`, swap the tokens and content, and keep the grid system.
- Keep the homepage short and link out to detail pages (see house style).
- Every booking button goes to the client's real booking page. Never invent details. Mark anything unconfirmed in the README's "To confirm" list.

### 4. Check before every send

Run the checker. It reports sideways scrolling, broken images, script errors and alignment near-misses, and saves screenshots with the column grid drawn on:

```bash
node .claude/skills/volstro-website/scripts/check_site.js volstro/<client>/site <scratchpad>/check --cols 4 --gutter 6 --margin 24
```

Then look at the grid screenshots yourself against the alignment checklist in `references/house-style.md`. Every near-miss the user caught on TattooBar would have shown up there.

### 5. Feedback rounds

Each round, send:

1. The preview link (publish the site as an Artifact, same file path every time so the link stays the same).
2. **One long PDF** of the whole site: desktop pages on the left, phone pages on the right, all on a single page. The user said: "one long pdf not different pages".

```bash
node .claude/skills/volstro-website/scripts/markup_pdf.js volstro/<client>/site <scratchpad>/<Client>-website-markup.pdf
```

When the markup comes back, list every mark you read before changing anything, then **apply each fix everywhere the same pattern appears**, not just where they drew it (divider lines on the menu also belonged on aftercare). Commit and push each round.

Don't offer Figma. The user couldn't import the plugin and asked for a PDF instead.

### 6. Client presentation

When the user is happy, make a 16:9 PDF presentation in the client's own colours, fonts and grid. Copy and edit the TattooBar one:

```bash
node volstro/tattoobar/build/presentation/capture.js volstro/<client>/site <deck dir>/shots
```

```bash
node volstro/tattoobar/build/presentation/deck.js volstro/<client>/site <deck dir> <deck dir>/<Client>-website-presentation.pdf
```

Slides: cover, what's new, the look, the grid, one slide per page (desktop screen, plus a phone where it helps), on your phone, where every booking button goes, a few things to check, next steps. Change the screen list in `capture.js` and the slide text in `deck.js`. Check every slide for overflow before sending.

## Working with this user

- They're a designer, not a developer. Keep deliverables to links and PDFs. Plain words, no setup steps.
- They write fast with typos ("fints", "ithe", "pfd"). Read for intent.
- They like a recommendation ("my pick"), but decide from their own references.
- "Make it look like what I uploaded" means follow the structure of their references closely.
- When they say "add or change anything if you think anything is off", do a full review pass with the checklist and list what you changed and why.

## Research

Pinterest works without logging in, but only shows the first page of results:

```bash
node .claude/skills/volstro-website/scripts/pinterest.js <scratchpad>/pins "tattoo studio website design" "cocktail menu design"
```

Download the pins at 736 px and make contact sheets with `montage` to look at them. Most "website design" pins are AI templates. Strong references came from posters, architecture, packaging and the trade itself, and the user's own picks were better than all of them.
