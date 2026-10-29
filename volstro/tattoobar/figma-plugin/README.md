# TattooBar website in Figma

This plugin draws the TattooBar website into a Figma file as normal, editable layers.

## Import it

1. Use the Figma desktop app (free). Plugins you add yourself only run in the desktop app, not in the browser.
2. Open a design file, or create a new one.
3. Go to **Plugins → Development → Import plugin from manifest…** and choose `manifest.json` from this folder.
4. Run it from **Plugins → Development → TattooBar website import**. It takes a minute and adds a page called **TattooBar website**.

## What you get

- 14 frames: the 7 pages at desktop size (1440 px) on the top row, and the same 7 at phone size (390 px) underneath.
- Each frame has the 4-column layout grid: 6 px gutters with 24 px margins on desktop, and 2 columns with 20 px margins on phones. Turn it on or off from **View → Layout grids**.
- Real text layers in Big Shoulders Display and Albert Sans, the photos, buttons, panels and lists, all named.
- Colour styles under **TattooBar/** (Concrete, Formwork, Ink, Steel, Paper, UV, White). Change one and it updates everywhere it is used.

If Figma doesn't have one of the fonts, the plugin uses Inter instead and says which font was missing when it finishes.

## Good to know

- Layers are placed where they sit on the website. They don't use auto layout, so moving one thing doesn't push the rest along.
- Hover states, the Book dropdown and the "open now" line are shown in one fixed state.
- Changes made in Figma don't update the website by themselves.

## Regenerate it after the site changes

```bash
node volstro/tattoobar/build/figma_export.js volstro/tattoobar/site volstro/tattoobar/figma-plugin
```
