# VOLSTRO

Four-page website for VOLSTRO, a London digital design studio. Plain HTML, CSS and JavaScript: no build step, and the only outside dependency is Google Fonts.

| File | Page |
|---|---|
| `index.html` | Home: hero, the problem, services preview, selected work, process, why VOLSTRO, final call to action |
| `services.html` | Website design packages, ecommerce, website care, additional services, FAQ |
| `work.html` | The four projects, each with a large website mockup |
| `contact.html` | Enquiry form and contact details |
| `styles.css` | Shared styles for every page |
| `main.js` | Home hero demo, the contact form and the copy-email button |

## View it

Open `index.html` in a browser.

## Before going live

- **Email.** The site uses `hello@volstro.co.uk`. It won't receive mail until the domain and mailbox are set up. The address appears in every page footer, on the contact page and in the `EMAIL` constant in `main.js`.
- **Contact form.** There's no backend yet, so the form opens the visitor's email app with the enquiry filled in. To receive enquiries directly, point the form at a form service such as Formspree or Netlify Forms.
- **Instagram and LinkedIn** on the contact page are placeholders with no links. Add each profile URL as the `href` on its `<a>` in `contact.html`.
- **Work.** All four projects are concepts and are labelled "Concept project". Their "View project" links show "Coming soon" until they have somewhere to go: add an `href` to each `arrow-link` in `work.html` and delete its `<span class="soon">`. When you have real clients, replace the concepts with client name, industry, challenge, solution and result.

## Hosting

Any static host works: Netlify, Vercel, GitHub Pages or Cloudflare Pages. Upload the whole `volstro` folder.
