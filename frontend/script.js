/* ============================================================
   TelsonBase Landing Page — Script
   Control Your Claw — Governed Agent Security Platform
   v7.4.0CC
   ============================================================ */

(function () {
  'use strict';

  // --- DOM Ready ---
  document.addEventListener('DOMContentLoaded', init);

  function init() {
    initNavScroll();
    initHamburger();
    initSmoothScroll();
    initCarousel();
    initCounters();
    initFadeIn();
    initModal();
    initHubSpotForms();
  }

  // --- Sticky Nav Scroll Effect ---
  function initNavScroll() {
    var nav = document.querySelector('.nav');
    if (!nav) return;

    function onScroll() {
      if (window.scrollY > 40) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // --- Mobile Hamburger Menu ---
  function initHamburger() {
    var btn = document.querySelector('.hamburger');
    var links = document.querySelector('.nav-links');
    if (!btn || !links) return;

    btn.addEventListener('click', function () {
      btn.classList.toggle('active');
      links.classList.toggle('open');
      document.body.style.overflow = links.classList.contains('open') ? 'hidden' : '';
    });

    // Close on link click
    var navAnchors = links.querySelectorAll('a');
    for (var i = 0; i < navAnchors.length; i++) {
      navAnchors[i].addEventListener('click', function () {
        btn.classList.remove('active');
        links.classList.remove('open');
        document.body.style.overflow = '';
      });
    }
  }

  // --- Smooth Scroll ---
  function initSmoothScroll() {
    var anchors = document.querySelectorAll('a[href^="#"]');
    for (var i = 0; i < anchors.length; i++) {
      anchors[i].addEventListener('click', function (e) {
        var targetId = this.getAttribute('href');
        if (targetId === '#') return;
        var target = document.querySelector(targetId);
        if (!target) return;
        e.preventDefault();
        var navHeight = document.querySelector('.nav').offsetHeight;
        var top = target.getBoundingClientRect().top + window.pageYOffset - navHeight;
        window.scrollTo({ top: top, behavior: 'smooth' });
      });
    }
  }

  // --- Carousel ---
  function initCarousel() {
    var track = document.querySelector('.carousel-track');
    var slides = document.querySelectorAll('.carousel-slide');
    var dots = document.querySelectorAll('.carousel-dot');
    var prevBtn = document.querySelector('.carousel-btn.prev');
    var nextBtn = document.querySelector('.carousel-btn.next');

    if (!track || slides.length === 0) return;

    var current = 0;
    var total = slides.length;
    var autoPlayInterval = null;
    var autoPlayDelay = 5000;

    function goTo(index) {
      if (index < 0) index = total - 1;
      if (index >= total) index = 0;
      current = index;
      track.style.transform = 'translateX(-' + (current * 100) + '%)';
      updateDots();
    }

    function updateDots() {
      for (var i = 0; i < dots.length; i++) {
        dots[i].classList.toggle('active', i === current);
      }
    }

    function next() { goTo(current + 1); }
    function prev() { goTo(current - 1); }

    if (nextBtn) nextBtn.addEventListener('click', function () { next(); resetAutoPlay(); });
    if (prevBtn) prevBtn.addEventListener('click', function () { prev(); resetAutoPlay(); });

    for (var i = 0; i < dots.length; i++) {
      (function (idx) {
        dots[idx].addEventListener('click', function () {
          goTo(idx);
          resetAutoPlay();
        });
      })(i);
    }

    function startAutoPlay() {
      autoPlayInterval = setInterval(next, autoPlayDelay);
    }

    function resetAutoPlay() {
      clearInterval(autoPlayInterval);
      startAutoPlay();
    }

    // Touch/swipe support
    var startX = 0;
    var endX = 0;

    track.addEventListener('touchstart', function (e) {
      startX = e.touches[0].clientX;
    }, { passive: true });

    track.addEventListener('touchend', function (e) {
      endX = e.changedTouches[0].clientX;
      var diff = startX - endX;
      if (Math.abs(diff) > 50) {
        if (diff > 0) next();
        else prev();
        resetAutoPlay();
      }
    }, { passive: true });

    updateDots();
    startAutoPlay();
  }

  // --- Animated Counters ---
  function initCounters() {
    // Handle both .counter-value and .stat-value elements
    var counters = document.querySelectorAll('.counter-value, .stat-value');
    if (counters.length === 0) return;

    var animated = new Set();

    function animateCounter(el) {
      var targetStr = el.getAttribute('data-target');
      if (!targetStr) return; // Skip non-numeric stat values like "1-Click"

      var target = parseInt(targetStr, 10);
      if (isNaN(target)) return;

      var duration = 2000;
      var startTime = null;

      function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
      }

      function step(timestamp) {
        if (!startTime) startTime = timestamp;
        var progress = Math.min((timestamp - startTime) / duration, 1);
        var easedProgress = easeOutCubic(progress);
        var currentValue = Math.floor(easedProgress * target);
        el.textContent = currentValue.toLocaleString();

        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          el.textContent = target.toLocaleString();
        }
      }

      requestAnimationFrame(step);
    }

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !animated.has(entry.target)) {
            animated.add(entry.target);
            // Only animate numeric counters
            if (entry.target.getAttribute('data-target')) {
              animateCounter(entry.target);
            }
          }
        });
      }, { threshold: 0.3 });

      counters.forEach(function (el) {
        if (el.getAttribute('data-target')) {
          el.textContent = '0';
        }
        observer.observe(el);
      });
    } else {
      // Fallback: just show the numbers
      counters.forEach(function (el) {
        var target = parseInt(el.getAttribute('data-target'), 10);
        if (!isNaN(target)) el.textContent = target.toLocaleString();
      });
    }
  }

  // --- Info Modals ---
  function initModal() {
    var modals = document.querySelectorAll('.cyc-modal-overlay');
    if (modals.length === 0) return;

    // Close on overlay click (outside the modal card)
    modals.forEach(function (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) {
          modal.classList.remove('open');
        }
      });
    });

    // Close on Escape key — closes whichever modal is open
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        modals.forEach(function (modal) {
          modal.classList.remove('open');
        });
      }
    });
  }

  // --- Fade-In on Scroll ---
  function initFadeIn() {
    var elements = document.querySelectorAll('.fade-in');
    if (elements.length === 0) return;

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

      elements.forEach(function (el) {
        observer.observe(el);
      });
    } else {
      // Fallback: show everything
      elements.forEach(function (el) {
        el.classList.add('visible');
      });
    }
  }

  // --- HubSpot Email Capture ---
  var HS_PORTAL_ID = '245465324';
  var HS_FORM_GUID = 'f70f2ed0-84bb-43eb-b56e-5d1dafa62d32';

  function initHubSpotForms() {
    var forms = document.querySelectorAll('.hs-capture');
    for (var i = 0; i < forms.length; i++) {
      bindHSForm(forms[i]);
    }
  }

  function bindHSForm(form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = form.querySelector('input[type="email"]').value;
      var btn = form.querySelector('button[type="submit"]');
      var originalText = btn.textContent;

      btn.disabled = true;
      btn.textContent = 'Sending\u2026';

      fetch(
        'https://api.hsforms.com/submissions/v3/integration/submit/' +
          HS_PORTAL_ID + '/' + HS_FORM_GUID,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fields: [{ objectTypeId: '0-1', name: 'email', value: email }],
            context: { pageUri: window.location.href, pageName: document.title }
          })
        }
      )
        .then(function (r) {
          if (r.ok) {
            form.innerHTML =
              '<p class="hs-success">You\'re on the list. We\'ll be in touch when it matters.</p>';
          } else {
            btn.disabled = false;
            btn.textContent = originalText;
            form.insertAdjacentHTML(
              'beforeend',
              '<p class="hs-error">Something went wrong. Email <a href="mailto:support@telsonbase.com">support@telsonbase.com</a> directly.</p>'
            );
          }
        })
        .catch(function () {
          btn.disabled = false;
          btn.textContent = originalText;
        });
    });
  }

})();
