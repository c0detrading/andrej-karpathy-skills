# VOLSTRO house style

These are the rules behind the user's corrections on TattooBar. Use them by default on every site unless the user or the brief says otherwise. Values in brackets are what TattooBar used.

## Grid and alignment (the user's biggest issue)

The user draws column lines over every page and checks that everything sits on them. "The 4 grid system, you kinda forgot about it, make sure you keep it the same for all the pages."

- **One column grid on every page**: header, hero, sections, forms, footer. [4 columns, 6 px gutter, 24 px outside margin on desktop, 20 px on phones.] On phones, text stacks to one column and photos and tiles go two across.
- **Where content starts**:
  - Homepage: section title in column 1, content from column 2.
  - Inner pages: title in columns 1–2, content in columns 3–4.
  - Long lists such as menus start at column 2 and run three across.
- **Text inside a block lines up with text inside the blocks above it.** Use one inset token for tile and panel padding, and use the same inset on free text that sits under tiles. (Vilma's text had to line up with "Learn to tattoo" inside the tile above.)
- **Tops line up** with the neighbouring block's top. **A button that ends a text column sits level with the bottom of the photo beside it.**
- **The gap between stacked items in one group equals the column gutter**: boxes then their button, panels then their button. [6 px]
- **Buttons fill whole columns**: one column, two columns, or the full width. Make them big [56 px tall] and the same size as the buttons beside them. Filter and chip rows stretch to fill their columns.
- **No empty space.** If a column sits empty next to content:
  - Stretch the content into it: form across two columns, wall labels across two, Book button full width.
  - Or move secondary text under the section title.
  - Or split long lists into more columns.
- **Section spacing is one value everywhere** [80 px desktop, 60 px phone]. The user asked for 60–100 px between sections and 20–30 px outside margins.

## Alignment checklist (run before every send)

For each page, on the grid screenshot:

1. Does every block's left and right edge sit on a column line?
2. Does text inside tiles and panels line up with text in the block above or below?
3. Do neighbouring blocks share a top edge, and do buttons share a bottom edge with the photo beside them?
4. Is every gap inside a group the gutter, and every gap between sections the section spacing?
5. Is any column empty while its neighbour is crowded?
6. Is each fix you made on one page applied to the same pattern on every page?

## Type

- **Two fonts only.** A condensed, heavy display face for the logo and big words, and a clean sans for everything else. [Big Shoulders Display 900, Albert Sans 400/600.] Offer three pairings first, as specimens on the real hero.
- **The logo is big, solid and clearly visible.** The subtle pressed-in version was too faint.
- Repeated text behind a photo sits at low opacity [22%] so the photo leads.
- Navigation labels are in Title Case ("Tattoo & Piercing", "The Bar").
- Sub-headings in lists are clearly bigger than the items under them [22 px against 16 px].
- Body copy is short and plain. Section titles are the big words.

## Structure

- **Short homepage.** The user's TattooBar sketch was:
  1. Logo and page links.
  2. Hero with two booking buttons.
  3. 8 tiles as ways in.
  4. About, with a button to the work.
  5. 4 work photos.
  6. A short service or bar section.
  7. Reviews.
  8. Info.

  Details belong on their own pages.
- **Header**: page links, a **Prices** button that jumps to the prices section, and a **Book** button that opens every booking option. No "Visit" link; the info sits at the bottom of the homepage and in the footer.
- **A dedicated page per offer** (tattoo and piercing, bar and menu, events, courses, the art, aftercare), each built like the user's sketch: title, work photos, about beside a big photo, prices, more work with style filters.
- **Divider lines** between repeated sections (menu sections, aftercare steps), the same colour as the list lines.
- Reviews show **five stars**.
- Links go to **the exact section** they mention (`page.html#section`). Pages without a hash open at the top.
- Phones get a fixed bottom bar with the two main booking buttons.

## Motion

- One subtle hover zoom on portfolio photos [scale 1.04, 0.45 s, clipped by its frame]. Turn it off for reduced motion.
- Nothing else moves. No fade-ins and no scroll effects.

## Facts

- Scraped details are often wrong. On TattooBar the Instagram handle, the bar phone number and the event schedule were all corrected by the user.
- Keep a "To confirm" list in the client README and on a presentation slide until the user or client signs each item off.
