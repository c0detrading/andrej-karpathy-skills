# VOLSTRO

The VOLSTRO website as plain HTML, CSS and JavaScript. It's a static version of the React/Next.js site exported from ChatGPT, with the same design, content and pages. It needs no Node.js, no build step, no Cloudflare and no database.

## View it

Open `index.html` in a browser. Keep all the files and folders together.

## Put it online

Upload the whole `volstro` folder to any static host: Netlify (drag the folder onto app.netlify.com/drop), Vercel, Cloudflare Pages, GitHub Pages, or a regular `public_html` upload.

## Files

| File | What it is |
|---|---|
| `index.html` | Home |
| `work.html` | Work: the four concept projects |
| `services.html` | Website Design and pricing |
| `website-care.html` | Website Care plans |
| `contact.html` | Start a project: enquiry form |
| `styles.css` | All styling. Sections 1–3 are the original site's fonts and styles, unchanged; section 4 styles the menu, FAQ, form fields and project pop-up |
| `main.js` | Scroll animations, services menu, FAQ, project pop-up and the enquiry form |
| `fonts/` | Space Grotesk, self-hosted |
| `images/` | Concept project photography |
| `favicon.svg`, `image-credits.txt` | Site icon and photo credits |

## Differences from the original

- **Enquiry form.** The original saved enquiries to a Cloudflare D1 database (and sent no email). A static site has no server, so the form now opens the visitor's email app with the enquiry filled in, addressed to hello@volstro.co.uk. To receive submissions directly instead, connect a form service such as Formspree, or Netlify Forms if you host on Netlify.
- **Project pop-up fixed.** In the original, the "View project" pop-up was squashed into narrow columns, because the site's own `.grid` class clashed with a Tailwind class on the pop-up. It now shows the project properly.
- **Current page in the Services menu** is now highlighted, as the original CSS intended.
- Links use file names (`services.html`, `website-care.html`) instead of `/services` and `/services/website-care`, so the site also works when opened straight from a folder.

## Before going live

- The concept projects use reference photos from other businesses' websites (listed in `image-credits.txt`). Replace them with your own or licensed images before launch.
- Instagram and LinkedIn are marked "Coming soon" on the contact page.
