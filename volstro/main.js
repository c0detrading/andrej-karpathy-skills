(() => {
  const EMAIL = "hello@volstro.co.uk";

  // Home hero demo: map the animated frame width to a device width and switch the mock layout at breakpoints.
  const track = document.querySelector(".demo-track");
  const frame = document.querySelector(".demo-frame");
  if (track && frame && "ResizeObserver" in window) {
    const readout = frame.querySelector(".demo-width");
    const legend = document.querySelectorAll(".demo-legend [data-mode]");
    new ResizeObserver(() => {
      const ratio = frame.offsetWidth / track.clientWidth;
      const mode = ratio > 0.8 ? "desktop" : ratio > 0.45 ? "tablet" : "mobile";
      const px = Math.round(390 + (ratio - 0.32) / 0.68 * 1050);
      frame.dataset.mode = mode;
      readout.textContent = Math.min(1440, Math.max(390, px)) + " px";
      legend.forEach(el => el.classList.toggle("is-on", el.dataset.mode === mode));
    }).observe(frame);
  }

  // Copy the studio email, falling back to selecting it.
  const copyBtn = document.getElementById("copy-email");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const done = label => { copyBtn.textContent = label; setTimeout(() => { copyBtn.textContent = "Copy"; }, 1800); };
      const select = () => {
        const range = document.createRange();
        range.selectNodeContents(document.getElementById("studio-email"));
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        done("Selected");
      };
      if (navigator.clipboard) navigator.clipboard.writeText(EMAIL).then(() => done("Copied"), select);
      else select();
    });
  }

  // No backend yet: the form opens the visitor's email app with the enquiry filled in.
  const form = document.getElementById("enquiry");
  if (form) {
    const labels = {
      name: "Name",
      business: "Business name",
      email: "Email",
      phone: "Phone number",
      website: "Current website",
      need: "Looking for",
      budget: "Approximate budget"
    };
    form.addEventListener("submit", e => {
      e.preventDefault();
      const d = new FormData(form);
      const lines = Object.keys(labels).map(key => labels[key] + ": " + (d.get(key) || "-"));
      lines.push("", d.get("message"));
      const subject = "Website enquiry from " + d.get("name");
      document.getElementById("form-status").hidden = false;
      window.location.href = "mailto:" + EMAIL + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(lines.join("\n"));
    });
  }
})();
