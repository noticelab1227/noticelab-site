/* NOTICE LAB — 공통 스크립트 (프레임워크 없음) */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------------------ 메뉴 오버레이 */
  var toggle = document.getElementById("nav-toggle");
  var overlay = document.getElementById("site-nav");
  var body = document.body;

  function setMenu(open) {
    if (!toggle || !overlay) return;
    overlay.classList.toggle("is-open", open);
    body.classList.toggle("nav-open", open);
    body.classList.toggle("is-locked", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    if (open) {
      var first = overlay.querySelector(".nav-link");
      if (first) first.focus({ preventScroll: true });
    } else {
      toggle.focus({ preventScroll: true });
    }
  }

  if (toggle && overlay) {
    toggle.addEventListener("click", function () {
      setMenu(!overlay.classList.contains("is-open"));
    });
    overlay.addEventListener("click", function (event) {
      if (event.target.closest("a")) setMenu(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && overlay.classList.contains("is-open")) setMenu(false);
    });
  }

  /* ------------------------------------------------------------ 헤더 상태 */
  var header = document.getElementById("site-header");

  function onScrollHeader() {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 24);
  }

  /* ------------------------------------------------------------ 히어로 패럴랙스 */
  var hero = document.getElementById("hero");

  function onScrollHero() {
    if (!hero) return;
    var shift = Math.min(window.scrollY, window.innerHeight) * 0.12;
    hero.style.setProperty("--hero-shift", shift.toFixed(1) + "px");
  }

  /* ------------------------------------------------------------ 섹션 인디케이터 */
  var indicator = document.getElementById("section-indicator");
  var currentLabel = document.getElementById("section-current");
  var stops = [];

  if (indicator) {
    ["hero", "structure", "services", "latest", "region"].forEach(function (id) {
      var node = document.getElementById(id);
      if (node) stops.push(node);
    });

    var updateIndicator = function () {
      var mark = window.innerHeight * 0.42;
      var active = 0;
      stops.forEach(function (node, index) {
        if (node.getBoundingClientRect().top <= mark) active = index;
      });
      var label = Math.max(1, Math.min(active, 4));
      if (currentLabel) currentLabel.textContent = label < 10 ? "0" + label : String(label);

      if (stops[active].classList.contains("section--paper")) {
        indicator.classList.add("is-light");
      } else {
        indicator.classList.remove("is-light");
      }

      var probeX = Math.max(8, window.innerWidth - 12);
      var probeY = Math.max(8, window.innerHeight - 26);
      var probe = document.elementFromPoint(probeX, probeY);
      var lightBox = probe && probe.closest(".section--paper, .archive, .post-paper, .closing");
      indicator.classList.toggle("is-light", Boolean(lightBox));
    };

    var goTo = function (direction) {
      var mark = window.innerHeight * 0.42;
      var active = 0;
      stops.forEach(function (node, index) {
        if (node.getBoundingClientRect().top <= mark) active = index;
      });
      var target = Math.min(stops.length - 1, Math.max(0, active + direction));
      if (target === 0) {
        window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
      } else {
        stops[target].scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      }
    };

    var prev = document.getElementById("section-prev");
    var next = document.getElementById("section-next");
    if (prev) prev.addEventListener("click", function () { goTo(-1); });
    if (next) next.addEventListener("click", function () { goTo(1); });

    updateIndicator();
    window.addEventListener("scroll", updateIndicator, { passive: true });
    window.addEventListener("resize", updateIndicator);
  }

  /* ------------------------------------------------------------ 스크롤 반응 묶음 */
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () {
      onScrollHeader();
      if (!reduceMotion) onScrollHero();
      ticking = false;
    });
  }
  onScrollHeader();
  if (!reduceMotion) onScrollHero();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* ------------------------------------------------------------ 등장 모션 */
  var revealNodes = Array.prototype.slice.call(document.querySelectorAll("[data-reveal]"));
  if (revealNodes.length) {
    if (reduceMotion || !("IntersectionObserver" in window)) {
      revealNodes.forEach(function (node) { node.classList.add("is-in"); });
    } else {
      var revealObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry, index) {
          if (!entry.isIntersecting) return;
          entry.target.style.setProperty("--reveal-delay", index * 90 + "ms");
          entry.target.classList.add("is-in");
          revealObserver.unobserve(entry.target);
        });
      }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
      revealNodes.forEach(function (node) { revealObserver.observe(node); });
    }
  }

  /* ------------------------------------------------------------ 글 목록 필터 */
  var list = document.getElementById("post-list");
  if (list) {
    var chips = Array.prototype.slice.call(document.querySelectorAll(".chip[data-filter]"));
    var status = document.getElementById("filter-status");
    var empty = document.getElementById("empty-state");
    var moreButton = document.getElementById("load-more");
    var cards = Array.prototype.slice.call(list.querySelectorAll(".card"));
    var PAGE = 9;
    var shown = PAGE;
    var current = "all";

    var matches = function (card, filter) {
      return filter === "all" || card.getAttribute("data-category") === filter;
    };

    var apply = function (resetPage) {
      if (resetPage) shown = PAGE;
      var visible = 0;
      cards.forEach(function (card) {
        var hit = matches(card, current);
        var keep = hit && visible < shown;
        if (hit) visible += 1;
        card.hidden = !keep;
      });
      var total = cards.filter(function (card) { return matches(card, current); }).length;
      if (status) {
        status.textContent = (current === "all" ? "전체 " : current + " ") + total + "편";
      }
      if (empty) empty.hidden = total !== 0;
      if (moreButton) moreButton.hidden = total <= shown;
    };

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        current = chip.getAttribute("data-filter");
        chips.forEach(function (other) {
          var active = other === chip;
          other.classList.toggle("is-active", active);
          other.setAttribute("aria-pressed", active ? "true" : "false");
        });
        apply(true);
      });
    });

    if (moreButton) {
      moreButton.addEventListener("click", function () {
        shown += PAGE;
        apply(false);
      });
    }

    apply(true);
  }

  /* ------------------------------------------------------------ 목차 현재 위치 */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc-list a"));
  var article = document.querySelector(".article");
  if (tocLinks.length && article && "IntersectionObserver" in window) {
    var headings = Array.prototype.slice.call(article.querySelectorAll("h2[id]"));
    var byId = {};
    tocLinks.forEach(function (link) {
      byId[link.getAttribute("href").slice(1)] = link;
    });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        tocLinks.forEach(function (link) { link.classList.remove("is-active"); });
        var active = byId[entry.target.id];
        if (active) active.classList.add("is-active");
      });
    }, { rootMargin: "-90px 0px -70% 0px", threshold: 0 });
    headings.forEach(function (heading) { observer.observe(heading); });
  }
})();
