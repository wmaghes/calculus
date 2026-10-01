/*
 * Persistent top nav, injected into <div id="siteNav"></div>.
 * Each page sets window.SITE_NAV = { base: "relative/path/to/dashboard/root/", active: "scanner" | "research" | "simulator" | "guide" }
 * before loading this script.
 */
(function () {
  function themeIconSVG(isLight) {
    if (isLight) {
      return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2.5v2.5M12 19v2.5M4.5 12H2M22 12h-2.5M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8"/></svg>';
    }
    return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 14.7A8.5 8.5 0 1 1 9.3 3.5a7 7 0 0 0 11.2 11.2z"/></svg>';
  }
  function logoSVG() {
    return '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
      '<defs><linearGradient id="navLogoGrad" x1="0" y1="24" x2="24" y2="0">' +
      '<stop offset="0" stop-color="var(--accent)"/><stop offset="1" stop-color="var(--accent-2)"/></linearGradient></defs>' +
      '<path d="M3 18 L9 10 L14 15 L21 5" stroke="url(#navLogoGrad)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' +
      '<circle cx="21" cy="5" r="2.4" fill="url(#navLogoGrad)"/></svg>';
  }

  const cfg = window.SITE_NAV || { base: "", active: "" };
  const base = cfg.base || "";
  const LINKS = [
    { key: "scanner", label: "Scanner", href: base + "index.html" },
    { key: "research", label: "Research", href: base + "research/index.html" },
    { key: "simulator", label: "Simulator", href: base + "simulator/index.html" },
    { key: "guide", label: "Guide", href: base + "guide/index.html" },
  ];
  const linksHtml = LINKS.map(function (l) {
    return '<a href="' + l.href + '" class="' + (l.key === cfg.active ? "active" : "") + '">' + l.label + "</a>";
  }).join("");

  const mount = document.getElementById("siteNav");
  if (!mount) return;

  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  mount.outerHTML =
    '<nav class="site-nav">' +
    '<a class="brand" href="' + base + 'index.html">' + logoSVG() + '<span class="wordmark">VANTAGE</span></a>' +
    '<div class="links">' + linksHtml + "</div>" +
    '<button class="theme-toggle" id="themeToggleBtn" aria-label="Toggle light/dark theme" title="Toggle light/dark theme">' + themeIconSVG(isLight) + "</button>" +
    "</nav>";

  const btn = document.getElementById("themeToggleBtn");
  if (btn) {
    btn.addEventListener("click", function () {
      const html = document.documentElement;
      const goingLight = html.getAttribute("data-theme") !== "light";
      if (goingLight) html.setAttribute("data-theme", "light");
      else html.removeAttribute("data-theme");
      try { localStorage.setItem("siteTheme", goingLight ? "light" : "dark"); } catch (e) {}
      btn.innerHTML = themeIconSVG(goingLight);
    });
  }
})();
