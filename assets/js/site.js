/* NOTICE LAB — 공통 스크립트 (프레임워크 없음) */
(function () {
  "use strict";

  /* ------------------------------------------------------------ 모바일 메뉴 */
  var toggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    var closeNav = function () {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "메뉴 열기");
    };
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) closeNav();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeNav();
    });
  }

  /* ------------------------------------------------------------ 헤더 그림자 */
  var header = document.getElementById("site-header");
  if (header) {
    var onScroll = function () {
      header.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
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
