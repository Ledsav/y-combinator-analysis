// Single source of truth for the nav header: builds the markup and
// injects it into each page's <div id="site-nav"></div> mount point,
// with the current page's link marked aria-current. Avoids duplicating
// the header HTML verbatim across all 3 pages.
(function () {
  const NAV_LINKS = [
    { href: "index", label: "Overview" },
    { href: "dashboard", label: "Dashboard" },
    { href: "pipeline", label: "Pipeline" },
  ];

  function renderNav() {
    const mount = document.getElementById("site-nav");
    if (!mount) return;
    const path = window.location.pathname.split("/").pop().replace(/\.html$/, "") || "index";

    const links = NAV_LINKS.map((link) => {
      const current = link.href === path ? ' aria-current="page"' : "";
      return `<li><a href="${link.href}"${current}>${link.label}</a></li>`;
    }).join("");

    mount.outerHTML = `
<header class="site-nav">
  <div class="wrap">
    <a class="site-nav__mark" href="index">
      <svg width="20" height="14" viewBox="0 0 20 14" aria-hidden="true">
        <rect x="0" y="4" width="12" height="6" fill="#3A5A96" />
        <rect x="12" y="4" width="8" height="6" fill="#C08A2E" />
      </svg>
      YC Complexity Index
    </a>
    <nav>
      <ul class="site-nav__links">${links}</ul>
    </nav>
  </div>
</header>`;
  }

  renderNav();
})();
