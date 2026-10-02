(() => {
  const EMAIL = "hello@volstro.co.uk";

  document.querySelectorAll("[data-year]").forEach(el => { el.textContent = new Date().getFullYear(); });

  // Scroll reveals, the process timeline and image parallax. All content stays visible without JavaScript.
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const items = [...document.querySelectorAll("[data-reveal], [data-rule]")];
  const timelines = [...document.querySelectorAll("[data-timeline]")];
  const images = [...document.querySelectorAll("[data-parallax]")];
  let observer;
  let frame = 0;
  const update = () => {
    frame = 0;
    const h = window.innerHeight;
    timelines.forEach(el => {
      const rect = el.getBoundingClientRect();
      const progress = Math.min(1, Math.max(0, (h * 0.82 - rect.top) / (rect.height + h * 0.25)));
      el.style.setProperty("--progress", reduced.matches ? "1" : String(progress));
    });
    if (!reduced.matches) {
      images.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.bottom > 0 && rect.top < h) {
          el.style.setProperty("--parallax", `${Math.max(-14, Math.min(14, (rect.top + rect.height / 2 - h / 2) * -0.025))}px`);
        }
      });
    }
  };
  const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
  const setup = () => {
    if (observer) observer.disconnect();
    items.forEach(el => el.classList.remove("reveal-pending"));
    if (!reduced.matches && "IntersectionObserver" in window) {
      observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.07, rootMargin: "0px 0px -30px 0px" });
      items.forEach(el => {
        if (el.getBoundingClientRect().top > window.innerHeight * 0.75) {
          el.classList.add("reveal-pending");
          observer.observe(el);
        } else {
          el.classList.add("is-visible");
        }
      });
    } else {
      items.forEach(el => el.classList.add("is-visible"));
      images.forEach(el => el.style.setProperty("--parallax", "0px"));
    }
    update();
  };
  setup();
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  reduced.addEventListener("change", setup);

  // Services dropdown: opens on hover with a mouse, on click or tap otherwise.
  const menu = document.querySelector(".services-menu");
  if (menu) {
    const trigger = menu.querySelector(".services-trigger");
    const dropdown = menu.querySelector(".services-dropdown");
    let timer;
    let openedByHover = false;
    const set = open => {
      clearTimeout(timer);
      dropdown.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      trigger.dataset.state = open ? "open" : "closed";
      if (!open) openedByHover = false;
    };
    trigger.addEventListener("click", () => {
      if (openedByHover) { openedByHover = false; return; }
      set(dropdown.hidden);
    });
    menu.addEventListener("pointerenter", e => {
      if (e.pointerType !== "mouse") return;
      clearTimeout(timer);
      timer = setTimeout(() => { set(true); openedByHover = true; }, 100);
    });
    menu.addEventListener("pointerleave", e => {
      if (e.pointerType !== "mouse") return;
      clearTimeout(timer);
      timer = setTimeout(() => set(false), 150);
    });
    menu.addEventListener("focusout", e => { if (!menu.contains(e.relatedTarget)) set(false); });
    document.addEventListener("click", e => { if (!menu.contains(e.target)) set(false); });
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && !dropdown.hidden) { set(false); trigger.focus(); }
    });
  }

  // FAQ: one answer open at a time, also in browsers without <details name> support.
  document.querySelectorAll(".faq").forEach(faq => {
    faq.addEventListener("toggle", e => {
      if (!e.target.open) return;
      faq.querySelectorAll("details[open]").forEach(d => { if (d !== e.target) d.open = false; });
    }, true);
  });

  // Concept project dialog, filled from the project that was clicked.
  const dialog = document.querySelector(".project-dialog");
  if (dialog && typeof dialog.showModal === "function") {
    document.querySelectorAll("[data-open-project]").forEach(button => {
      button.addEventListener("click", () => {
        const project = button.closest(".project");
        const art = project.querySelector(".artwork").cloneNode(true);
        art.querySelectorAll("[data-parallax]").forEach(el => el.style.removeProperty("--parallax"));
        dialog.querySelector(".dialog-number").textContent = project.querySelector(".project-number").textContent;
        dialog.querySelector("#dialog-title").textContent = project.querySelector("h3").textContent;
        dialog.querySelector("#dialog-description").textContent =
          project.querySelector(".project-desc").textContent + " Independent design concept, not a commissioned client project.";
        dialog.querySelector(".dialog-art").replaceChildren(art);
        dialog.showModal();
        document.body.classList.add("dialog-open");
      });
    });
    dialog.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => document.body.classList.remove("dialog-open"));
    dialog.addEventListener("click", e => {
      if (e.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close();
    });
  }

  // Enquiry form. There's no server, so it opens the visitor's email app with the enquiry filled in.
  const form = document.getElementById("enquiry");
  if (form) {
    const status = document.getElementById("form-status");
    const preset = new URLSearchParams(window.location.search).get("service");
    if (preset && [...form.elements.service.options].some(o => o.value === preset)) form.elements.service.value = preset;
    const labels = [
      ["Name", "name"], ["Business name", "business"], ["Email", "email"], ["Phone number", "phone"],
      ["Current website", "website"], ["Looking for", "service"], ["Approximate budget", "budget"]
    ];
    form.addEventListener("submit", e => {
      e.preventDefault();
      const d = new FormData(form);
      const body = labels.map(([label, key]) => `${label}: ${d.get(key) || "-"}`).concat("", d.get("message")).join("\n");
      const subject = `Website enquiry from ${d.get("name")}`;
      status.textContent = `Your email app should open with your enquiry ready to send. If it doesn’t, email us at ${EMAIL}.`;
      status.hidden = false;
      window.location.href = `mailto:${EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    });
  }
})();
