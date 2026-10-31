/* БРО — поведение сайта: корзина, фасовки, фильтры каталога, оформление в WhatsApp. Без зависимостей. */
(function () {
  'use strict';
  var BRO = window.BRO || { products: {}, site: { delivery: {} } };
  var ROOT = document.body.getAttribute('data-root') || '';
  var KEY = 'bro_cart_v1';

  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); }
  function rub(n) { return Math.round(n).toLocaleString('ru-RU') + ' ₽'; }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  /* ---------- cart store ---------- */
  var mem = [];
  /* Firefox и ряд браузеров изолируют localStorage у каждого file://-файла, поэтому при открытии сайта
     с диска корзина дополнительно живёт в window.name — он сохраняется при переходах внутри вкладки. */
  var FILE = location.protocol === 'file:', NAME_PREFIX = KEY + ':';
  function fromName() {
    if (!FILE || window.name.indexOf(NAME_PREFIX) !== 0) return null;
    try { var v = JSON.parse(window.name.slice(NAME_PREFIX.length)); return Array.isArray(v) ? v : null; } catch (e) { return null; }
  }
  function load() {
    var named = fromName();
    if (named) return named;
    try { var v = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(v) ? v : []; }
    catch (e) { return mem; }
  }
  function save(items) {
    mem = items;
    try { localStorage.setItem(KEY, JSON.stringify(items)); } catch (e) { /* приватный режим — живём в памяти */ }
    if (FILE) window.name = NAME_PREFIX + JSON.stringify(items);
    renderBadge(true);
  }
  function optPrice(slug, label) {
    var p = BRO.products[slug]; if (!p) return null;
    for (var i = 0; i < p.o.length; i++) if (p.o[i][0] === label) return p.o[i][1];
    return null;
  }
  function addToCart(slug, opt, qty) {
    var items = load(), found = false;
    items.forEach(function (it) { if (it.s === slug && it.o === opt) { it.q = Math.min(99, it.q + qty); found = true; } });
    if (!found) items.push({ s: slug, o: opt, q: qty });
    save(items);
  }
  function count() { return load().reduce(function (a, it) { return a + it.q; }, 0); }
  function total() {
    return load().reduce(function (a, it) {
      var p = BRO.products[it.s], pr = optPrice(it.s, it.o);
      return a + (p && p.s === 1 && pr !== null ? pr * it.q : 0);
    }, 0);
  }
  function freeLeft() { return Math.max(0, (BRO.site.delivery.free_from || 0) - total()); }
  function plural(n, one, few, many) {
    var m10 = n % 10, m100 = n % 100;
    return n + ' ' + (m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many);
  }
  /* нижняя панель корзины на телефоне */
  var bar = $('#cartbar');
  function renderBar() {
    if (!bar) return;
    var n = count(), onCart = !!$('#cartApp');
    bar.hidden = n === 0 || onCart;
    document.body.classList.toggle('has-cartbar', !bar.hidden);
    if (bar.hidden) return;
    var left = freeLeft(), free = BRO.site.delivery.free_from || 1;
    $('[data-bar-count]', bar).textContent = plural(n, 'товар', 'товара', 'товаров');
    $('[data-bar-sum]', bar).textContent = rub(total());
    $('[data-bar-free]', bar).textContent = left ? 'до бесплатной доставки ' + rub(left) : 'доставка бесплатно';
    $('[data-bar-progress]', bar).style.width = Math.min(100, 100 * (free - left) / free) + '%';
  }
  function renderBadge(bump) {
    var n = count();
    renderBar(); syncAddButtons();
    $$('[data-cart-count]').forEach(function (b) {
      b.textContent = n; b.hidden = n === 0;
      if (bump && n) { b.classList.remove('bump'); void b.offsetWidth; b.classList.add('bump'); }
    });
  }

  /* ---------- toast ---------- */
  var toastTimer;
  function toast(html) {
    var t = $('#toast'); if (!t) return;
    t.innerHTML = html; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 3200);
  }

  /* ---------- nav ---------- */
  var navToggle = $('#navToggle'), mainNav = $('#mainNav');
  if (navToggle && mainNav) {
    navToggle.addEventListener('click', function () {
      var open = mainNav.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* ---------- слайдер на главной ---------- */
  /* Листается нативной прокруткой со scroll-snap (свайп работает и без JS); JS добавляет точки, стрелки,
     автопрокрутку. Автопрокрутка стоит на паузе под курсором, при фокусе, в скрытой вкладке и при «меньше движения». */
  var slider = $('#heroSlider');
  if (slider) (function () {
    var track = $('#heroSlides', slider), ui = $('.slider-ui', slider);
    var today = new Date().toISOString().slice(0, 10);
    $$('.slide[data-until]', track).forEach(function (s) { if (s.getAttribute('data-until') < today) s.remove(); });
    var slides = $$('.slide', track), dots = $$('.dot', slider), DELAY = 7000;
    $$('.dot', slider).forEach(function (d, i) { if (i >= slides.length) d.remove(); });
    dots = $$('.dot', slider);
    if (slides.length < 2 || !ui) return;
    ui.hidden = false;
    slider.style.setProperty('--slide-ms', DELAY + 'ms');
    var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    var cur = 0, timer = null, paused = reduce, hold = false;

    function mark(i) {
      cur = i;
      slider.classList.toggle('on-dark', /slide-(olive|burgundy)/.test(slides[i].className));
      slides.forEach(function (s, k) {
        s.setAttribute('aria-label', (k + 1) + ' из ' + slides.length);
        if (k === i) s.removeAttribute('inert'); else s.setAttribute('inert', '');
      });
      dots.forEach(function (d, k) {
        if (k === i) d.setAttribute('aria-current', 'true'); else d.removeAttribute('aria-current');
      });
    }
    function go(i) {
      i = (i + slides.length) % slides.length;
      track.scrollTo({ left: i * track.clientWidth, behavior: reduce ? 'auto' : 'smooth' });
      mark(i); schedule();
    }
    function schedule() {
      clearTimeout(timer);
      slider.classList.toggle('is-playing', !paused);
      slider.classList.toggle('is-hold', hold);
      if (paused || hold || document.hidden) return;
      var f = dots[cur].firstChild; f.style.animation = 'none'; void f.offsetWidth; f.style.animation = '';  // заливка точки с нуля
      timer = setTimeout(function () { go(cur + 1); }, DELAY);
    }
    var scrollT;
    track.addEventListener('scroll', function () {  // свайп пальцем или колёсиком
      clearTimeout(scrollT);
      scrollT = setTimeout(function () {
        var i = Math.round(track.scrollLeft / track.clientWidth);
        if (i !== cur) { mark(i); schedule(); }
      }, 90);
    }, { passive: true });
    window.addEventListener('resize', function () { track.scrollLeft = cur * track.clientWidth; });
    dots.forEach(function (d, i) { d.addEventListener('click', function () { go(i); }); });
    $('[data-prev]', slider).addEventListener('click', function () { go(cur - 1); });
    $('[data-next]', slider).addEventListener('click', function () { go(cur + 1); });
    var pauseBtn = $('[data-pause]', slider);
    function setPaused(p) {
      paused = p;
      slider.classList.toggle('is-paused', p);
      pauseBtn.setAttribute('aria-label', p ? 'Включить прокрутку' : 'Остановить прокрутку');
      schedule();
    }
    pauseBtn.addEventListener('click', function () { setPaused(!paused); });
    slider.addEventListener('mouseenter', function () { hold = true; schedule(); });
    slider.addEventListener('mouseleave', function () { hold = false; schedule(); });
    slider.addEventListener('focusin', function () { hold = true; schedule(); });
    slider.addEventListener('focusout', function (e) { if (!slider.contains(e.relatedTarget)) { hold = false; schedule(); } });
    slider.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { go(cur + 1); e.preventDefault(); }
      if (e.key === 'ArrowLeft') { go(cur - 1); e.preventDefault(); }
    });
    document.addEventListener('visibilitychange', schedule);
    mark(0); setPaused(paused);
  })();

  /* ---------- options, qty, add ---------- */
  /* Цена на экране = цена выбранной фасовки (из админки) × количество. Сами цены не меняются:
     в корзину уходят фасовка и количество, сумму заказа сервер считает заново по products.json. */
  function renderPrice(card) {
    var po = $('[data-price-out]', card), uo = $('[data-unit-out]', card), add = $('[data-add]', card);
    if (!po || !add) return;
    var slug = add.getAttribute('data-add'), label = add.getAttribute('data-opt');
    var price = optPrice(slug, label); if (price === null) return;
    var qi = $('[data-qty-input]', card), q = qi ? Math.max(1, Math.min(99, parseInt(qi.value, 10) || 1)) : 1;
    po.textContent = rub(price * q);
    if (uo) uo.textContent = q > 1 ? q + ' × ' + label + ' · по ' + rub(price) : 'за ' + label;
  }
  document.addEventListener('input', function (e) {
    var qi = e.target.closest('[data-qty-input]');
    if (qi && !qi.closest('.cart-item')) renderPrice(qi.closest('.pcard'));
  });
  document.addEventListener('change', function (e) {
    var qi = e.target.closest('[data-qty-input]');
    if (qi && !qi.closest('.cart-item')) { qi.value = Math.max(1, Math.min(99, parseInt(qi.value, 10) || 1)); renderPrice(qi.closest('.pcard')); }
  });
  document.addEventListener('click', function (e) {
    var opt = e.target.closest('.opt');
    if (opt) {
      var card = opt.closest('.pcard');
      $$('.opt', card).forEach(function (b) { b.setAttribute('aria-pressed', b === opt ? 'true' : 'false'); });
      var po = $('[data-price-out]', card), uo = $('[data-unit-out]', card), add = $('[data-add]', card);
      if (add) { add.setAttribute('data-opt', opt.getAttribute('data-opt')); syncAddButtons(); renderPrice(card); }
      else {  // нет кнопки «В корзину» (нет в наличии) — показываем цену фасовки как есть
        if (po) po.textContent = rub(+opt.getAttribute('data-price'));
        if (uo) uo.textContent = 'за ' + opt.getAttribute('data-opt');
      }
      return;
    }
    var step = e.target.closest('[data-qty-dec],[data-qty-inc]');
    if (step && step.closest('[data-qty]') && !step.closest('.cart-item')) {
      var input = $('[data-qty-input]', step.closest('[data-qty]'));
      var v = (parseInt(input.value, 10) || 1) + (step.hasAttribute('data-qty-inc') ? 1 : -1);
      input.value = Math.max(1, Math.min(99, v));
      renderPrice(step.closest('.pcard'));
      return;
    }
    var addBtn = e.target.closest('[data-add]');
    if (addBtn) {
      var c = addBtn.closest('.pcard'), qi = c && $('[data-qty-input]', c);
      var q = qi ? Math.max(1, Math.min(99, parseInt(qi.value, 10) || 1)) : 1;
      var slug = addBtn.getAttribute('data-add'), o = addBtn.getAttribute('data-opt');
      addToCart(slug, o, q);
      var name = BRO.products[slug] ? BRO.products[slug].n : '';
      var left = freeLeft();
      toast('<span>Добавлено: ' + esc(name) + ', ' + esc(o) + (q > 1 ? ' × ' + q : '') +
        '<small>' + (left ? 'До бесплатной доставки ' + rub(left) : 'Доставка по Москве — бесплатно') + '</small></span>' +
        '<a href="' + ROOT + 'cart.html">В корзину →</a>');
    }
  });

  /* Кнопка «В корзину» остаётся оливковой «В корзине · N», пока выбранная фасовка лежит в корзине; нажатие добавляет ещё. */
  function syncAddButtons() {
    var inCart = {};
    load().forEach(function (it) { inCart[it.s + '|' + it.o] = (inCart[it.s + '|' + it.o] || 0) + it.q; });
    $$('[data-add]').forEach(function (b) {
      if (!b.hasAttribute('data-label')) b.setAttribute('data-label', b.textContent);
      var n = inCart[b.getAttribute('data-add') + '|' + b.getAttribute('data-opt')] || 0;
      b.classList.toggle('is-added', n > 0);
      b.textContent = n ? 'В корзине · ' + n + ' шт' : b.getAttribute('data-label');
      b.setAttribute('aria-label', n ? 'В корзине ' + n + ' шт, добавить ещё' : b.getAttribute('data-label'));
    });
  }
  window.addEventListener('pageshow', function () { renderBadge(false); });  // возврат кнопкой «Назад»

  /* ---------- catalog ---------- */
  var grid = $('#catalogGrid');
  if (grid) {
    var cards = $$('.pcard', grid), chips = $$('#chips .chip');
    var search = $('#search'), sort = $('#sort'), inStock = $('#inStock'), found = $('#found'), empty = $('#catalogEmpty');
    var params = new URLSearchParams(location.search);
    var state = { cat: params.get('cat') || 'all', q: params.get('q') || '' };
    if (!chips.some(function (c) { return c.getAttribute('data-filter') === state.cat; })) state.cat = 'all';
    search.value = state.q;

    function plural(n) {
      var m10 = n % 10, m100 = n % 100;
      return n + ' ' + (m10 === 1 && m100 !== 11 ? 'позиция' : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? 'позиции' : 'позиций');
    }
    function apply() {
      var q = state.q.trim().toLowerCase(), shown = 0;
      chips.forEach(function (c) {
        var on = c.getAttribute('data-filter') === state.cat;
        c.classList.toggle('is-active', on); c.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      var words = q.split(/\s+/).filter(Boolean);
      cards.forEach(function (card) {
        var tags = card.getAttribute('data-tags').split(' ');
        var catOk = state.cat === 'all' || tags.indexOf(state.cat) !== -1;
        var text = card.getAttribute('data-name') + ' ' + (card.textContent || '').toLowerCase();
        var qOk = words.every(function (w) { return text.indexOf(w) !== -1; });
        var stOk = !inStock.checked || card.getAttribute('data-stock') === '1';
        var ok = catOk && qOk && stOk;
        card.hidden = !ok; if (ok) shown++;
      });
      var mode = sort.value;
      cards.slice().sort(function (a, b) {
        var sa = +b.getAttribute('data-stock') - +a.getAttribute('data-stock');
        if (sa) return sa;
        if (mode === 'asc') return +a.getAttribute('data-price') - +b.getAttribute('data-price');
        if (mode === 'desc') return +b.getAttribute('data-price') - +a.getAttribute('data-price');
        if (mode === 'name') return a.getAttribute('data-name').localeCompare(b.getAttribute('data-name'), 'ru');
        return +a.getAttribute('data-pop') - +b.getAttribute('data-pop');
      }).forEach(function (c) { grid.appendChild(c); });
      found.textContent = plural(shown);
      var soon = $('#catsSoon'), catsEmpty = state.cat === 'cats' && shown === 0;
      if (soon) soon.hidden = !catsEmpty;
      empty.hidden = shown > 0 || catsEmpty;
      var p = new URLSearchParams();
      if (state.cat !== 'all') p.set('cat', state.cat);
      if (state.q) p.set('q', state.q);
      var qs = p.toString();
      try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash); } catch (e) { }
    }
    chips.forEach(function (c) { c.addEventListener('click', function () { state.cat = c.getAttribute('data-filter'); apply(); }); });
    var t;
    search.addEventListener('input', function () { clearTimeout(t); t = setTimeout(function () { state.q = search.value; apply(); }, 120); });
    sort.addEventListener('change', apply);
    inStock.addEventListener('change', apply);
    apply();
    if (location.hash === '#search') search.focus();
  }

  /* ---------- cart page ---------- */
  var app = $('#cartApp');
  if (app) {
    var D = BRO.site.delivery, list = $('#cartList'), form = $('#checkout');

    function lines() {
      return load().map(function (it) {
        var p = BRO.products[it.s], price = optPrice(it.s, it.o);
        return { it: it, p: p, price: price, ok: !!p && price !== null && p.s === 1 };
      });
    }
    function calc() {
      var ls = lines().filter(function (l) { return l.ok; });
      var items = ls.reduce(function (a, l) { return a + l.price * l.it.q; }, 0);
      var zone = (form.querySelector('[name=zone]:checked') || {}).value;
      var fee = items >= D.free_from ? 0 : D.fee;
      return { items: items, fee: fee, out: zone === 'out', total: items + fee, min: D.min_order, lines: ls };
    }
    function renderTotals() {
      var c = calc();
      $('#tItems').textContent = rub(c.items);
      $('#tDelivery').textContent = (c.fee ? rub(c.fee) : 'бесплатно') + (c.out ? ' + ' + D.outside_per_km + ' ₽/км' : '');
      $('#tTotal').textContent = (c.out ? 'от ' : '') + rub(c.total);
      var hint = $('#minHint'), send = $('#sendOrder'), short = c.items < c.min;
      if (!send.getAttribute('data-label')) send.setAttribute('data-label', send.innerHTML);
      if (short) {
        hint.hidden = false; hint.className = 'hint warn';
        hint.innerHTML = 'Минимальный заказ — ' + rub(c.min) + ' (без учёта доставки). <a href="' + ROOT + 'catalog.html">Добавить товары →</a>';
        send.textContent = 'Добавьте ещё на ' + rub(c.min - c.items);
      } else {
        send.innerHTML = send.getAttribute('data-label');
        if (c.fee) {
          hint.hidden = false; hint.className = 'hint';
          hint.textContent = 'До бесплатной доставки осталось ' + rub(D.free_from - c.items) + '.';
        } else hint.hidden = true;
      }
      send.disabled = short;
    }
    function render() {
      var ls = lines();
      $('#cartEmpty').hidden = ls.length > 0;
      app.hidden = ls.length === 0;
      list.innerHTML = ls.map(function (l, i) {
        var p = l.p || { n: 'Товар больше не продаётся', i: '' };
        var img = p.i ? '<img src="' + ROOT + 'static/img/products/' + esc(p.i) + '" alt="" loading="lazy">' : '';
        var note = !l.ok ? '<span class="meta" style="color:var(--pomegranate)">нет в наличии — уберите из заказа</span>' :
          '<span class="meta">' + esc(l.it.o) + ' · ' + rub(l.price) + '</span>';
        return '<li class="cart-item" data-i="' + i + '">' +
          '<a class="thumb" href="' + ROOT + 'p/' + esc(l.it.s) + '.html">' + img + '</a>' +
          '<div><div class="name"><a href="' + ROOT + 'p/' + esc(l.it.s) + '.html">' + esc(p.n) + '</a></div>' + note + '</div>' +
          '<div class="sum">' + (l.ok ? rub(l.price * l.it.q) : '—') + '</div>' +
          '<div class="controls"><div class="qty" data-qty><button type="button" data-qty-dec aria-label="Меньше">−</button>' +
          '<input type="number" min="1" max="99" value="' + l.it.q + '" aria-label="Количество" data-qty-input>' +
          '<button type="button" data-qty-inc aria-label="Больше">+</button></div>' +
          '<button type="button" class="remove" aria-label="Удалить">✕</button></div></li>';
      }).join('');
      if (ls.length) renderTotals();
      if (typeof renderRepeat === 'function') renderRepeat();
    }
    function setQty(i, q) {
      var items = load();
      if (!items[i]) return;
      if (q <= 0) items.splice(i, 1); else items[i].q = Math.min(99, q);
      save(items); render();
    }
    list.addEventListener('click', function (e) {
      var li = e.target.closest('.cart-item'); if (!li) return;
      var i = +li.getAttribute('data-i'), items = load();
      if (e.target.closest('.remove')) setQty(i, 0);
      else if (e.target.closest('[data-qty-inc]')) setQty(i, items[i].q + 1);
      else if (e.target.closest('[data-qty-dec]')) setQty(i, items[i].q - 1);
    });
    list.addEventListener('change', function (e) {
      if (e.target.matches('[data-qty-input]')) setQty(+e.target.closest('.cart-item').getAttribute('data-i'), parseInt(e.target.value, 10) || 1);
    });
    $('#cartClear').addEventListener('click', function () {
      var b = this;
      if (b.getAttribute('data-confirm')) { save([]); render(); b.removeAttribute('data-confirm'); b.textContent = 'Очистить корзину'; return; }
      b.setAttribute('data-confirm', '1'); b.textContent = 'Точно очистить? Нажмите ещё раз';
      setTimeout(function () { b.removeAttribute('data-confirm'); b.textContent = 'Очистить корзину'; }, 3500);
    });
    form.addEventListener('change', renderTotals);

    /* Телефон строго +7 и 10 цифр: +7 подставляется сам, 8 или 7 в начале вставленного номера отбрасывается. */
    function phoneDigits(v) { return '+' + v.replace(/\D/g, ''); }
    function formatPhone(d) {  // d — 10 цифр номера без +7
      var out = '+7 ';
      if (d.length) out += '(' + d.slice(0, 3);
      if (d.length >= 3) out += ')';
      if (d.length > 3) out += ' ' + d.slice(3, 6);
      if (d.length > 6) out += '-' + d.slice(6, 8);
      if (d.length > 8) out += '-' + d.slice(8, 10);
      return out;
    }
    var phone = form.elements.phone, prevDigits = '';
    phone.addEventListener('focus', function () { if (!phone.value) phone.value = '+7 '; });
    phone.addEventListener('blur', function () { if (!prevDigits) phone.value = ''; });
    phone.addEventListener('input', function (e) {
      var raw = phone.value, rest = raw.indexOf('+7') === 0 ? raw.slice(2) : raw;
      var d = rest.replace(/\D/g, '');
      if (d.length === 11 && /^[78]/.test(d)) d = d.slice(1);                 // вставили 8XXXXXXXXXX или +7XXXXXXXXXX
      else if (!prevDigits && d.length === 1 && /[78]/.test(d)) d = '';        // начали набирать с 8 или +7
      if (e.inputType && e.inputType.indexOf('delete') === 0 && d === prevDigits) d = d.slice(0, -1);  // стёрли скобку/дефис
      prevDigits = d.slice(0, 10);
      phone.value = formatPhone(prevDigits);
    });

    /* ---------- «как в прошлый раз»: имя, телефон и адреса живут только в браузере покупателя ---------- */
    var ME_KEY = 'bro_me_v1', LAST_KEY = 'bro_last_v1';
    function loadMe() { try { var v = JSON.parse(localStorage.getItem(ME_KEY) || 'null'); return v && v.phone ? v : null; } catch (e) { return null; } }
    function rememberMe() {
      try {
        if (!$('#f-remember').checked) { localStorage.removeItem(ME_KEY); localStorage.removeItem(LAST_KEY); return; }
        var now = new Date();
        localStorage.setItem(LAST_KEY, JSON.stringify({ d: ('0' + now.getDate()).slice(-2) + '.' + ('0' + (now.getMonth() + 1)).slice(-2),
          items: calc().lines.map(function (l) { return { s: l.it.s, o: l.it.o, q: l.it.q }; }) }));
        var f = form.elements, me = loadMe() || { addresses: [] };
        var addr = f.address.value.trim(), zone = (form.querySelector('[name=zone]:checked') || {}).value || 'mkad';
        me.name = f.name.value.trim(); me.phone = prevDigits;
        me.addresses = [{ a: addr, z: zone }].concat((me.addresses || []).filter(function (x) { return x.a.toLowerCase() !== addr.toLowerCase(); })).slice(0, 3);
        localStorage.setItem(ME_KEY, JSON.stringify(me));
      } catch (e) { /* приватный режим — просто не запоминаем */ }
    }
    function fillAddress(x) {
      form.elements.address.value = x.a;
      var r = form.querySelector('[name=zone][value="' + x.z + '"]'); if (r) { r.checked = true; renderTotals(); }
    }
    function fillMe(me, x) {
      form.elements.name.value = me.name || '';
      prevDigits = me.phone; phone.value = formatPhone(prevDigits);
      fillAddress(x || me.addresses[0]);
      ['name', 'phone', 'address'].forEach(function (n) { form.elements[n].setAttribute('aria-invalid', 'false'); });
    }
    function renderRemember() {
      var me = loadMe(), box = $('#remember'), sug = $('#addrSuggest');
      if (!me) { box.hidden = true; sug.innerHTML = ''; return; }
      box.innerHTML = '<p><b>' + (me.name ? 'С возвращением, ' + esc(me.name) + '!' : 'Вы уже заказывали у нас') + '</b> Заполнить как в прошлый раз:</p>' +
        me.addresses.map(function (x, i) {
          return '<button type="button" class="remember-fill" data-i="' + i + '"><span>' + esc(formatPhone(me.phone)) + '</span>' + esc(x.a) + (x.z === 'out' ? ' · за МКАД' : '') + '</button>';
        }).join('') + '<button type="button" class="remember-forget">Забыть мои данные</button>';
      box.hidden = false;
      sug.innerHTML = me.addresses.map(function (x, i) { return '<li role="option" tabindex="-1" data-i="' + i + '">' + esc(x.a) + '</li>'; }).join('');
    }
    $('#remember').addEventListener('click', function (e) {
      var me = loadMe(); if (!me) return;
      var b = e.target.closest('.remember-fill');
      if (b) { fillMe(me, me.addresses[+b.dataset.i]); $('#f-consent').focus(); return; }
      if (e.target.closest('.remember-forget')) { try { localStorage.removeItem(ME_KEY); localStorage.removeItem(LAST_KEY); } catch (err) { } renderRemember(); renderRepeat(); toast('<span>Готово: ваши данные удалены с этого устройства</span>'); }
    });

    /* ---------- повтор прошлого заказа: состав (без имени/телефона) хранится только в браузере ---------- */
    function loadLast() { try { var v = JSON.parse(localStorage.getItem(LAST_KEY) || 'null'); return v && v.items && v.items.length ? v : null; } catch (e) { return null; } }
    function checkLast(last) {  // что из прошлого заказа можно купить сейчас — по текущим ценам и наличию из админки
      var ok = [], gone = [];
      last.items.forEach(function (it) {
        var p = BRO.products[it.s], pr = optPrice(it.s, it.o);
        if (p && p.s === 1 && pr !== null) ok.push({ it: it, p: p, price: pr }); else gone.push((p ? p.n : 'товар') + ', ' + it.o);
      });
      return { ok: ok, gone: gone };
    }
    function repeatLast() {
      var last = loadLast(); if (!last) return;
      var r = checkLast(last);
      r.ok.forEach(function (x) { addToCart(x.it.s, x.it.o, x.it.q); });
      render();
      toast('<span>Добавлено из прошлого заказа: ' + r.ok.length + ' ' + plural(r.ok.length, 'позиция', 'позиции', 'позиций').replace(/^\d+ /, '') +
        (r.gone.length ? '<small>Нет в наличии: ' + esc(r.gone.join('; ')) + '</small>' : '') + '</span>');
    }
    function renderRepeat() {
      var box = $('#repeatBox'), last = loadLast(), empty = !load().length;
      var rb = $('#remember .remember-repeat'); if (rb) rb.remove();
      if (!last) { box.hidden = true; return; }
      var r = checkLast(last);
      if (empty) {
        var sum = r.ok.reduce(function (a, x) { return a + x.price * x.it.q; }, 0);
        box.innerHTML = '<h2>Ваш прошлый заказ от ' + esc(last.d) + '</h2><ul>' +
          r.ok.map(function (x) { return '<li><span>' + esc(x.p.n) + ' — ' + esc(x.it.o) + ' × ' + x.it.q + '</span><b>' + rub(x.price * x.it.q) + '</b></li>'; }).join('') +
          r.gone.map(function (g) { return '<li class="gone"><span>' + esc(g) + '</span><b>нет в наличии</b></li>'; }).join('') + '</ul>' +
          (r.ok.length ? '<button type="button" class="btn btn-primary" data-repeat>Повторить заказ · ' + rub(sum) + '</button><p class="hint">Цены — сегодняшние. Состав можно поменять в корзине.</p>'
                       : '<p class="hint">Этих товаров сейчас нет в наличии.</p>');
        box.hidden = false;
      } else {
        box.hidden = true;
        var rem = $('#remember');
        if (r.ok.length && !rem.hidden) rem.insertAdjacentHTML('beforeend', '<button type="button" class="remember-repeat" data-repeat>+ Добавить товары из прошлого заказа (' + esc(last.d) + ')</button>');
      }
    }
    document.addEventListener('click', function (e) { if (e.target.closest('[data-repeat]')) repeatLast(); });
    var addrInput = form.elements.address, sug = $('#addrSuggest');
    function showSug(on) { sug.hidden = !on || !sug.children.length; }
    addrInput.addEventListener('focus', function () { if (!addrInput.value) showSug(true); });
    addrInput.addEventListener('input', function () { showSug(!addrInput.value); });
    addrInput.addEventListener('blur', function () { setTimeout(function () { showSug(false); }, 150); });
    sug.addEventListener('mousedown', function (e) {
      var li = e.target.closest('li'); if (!li) return;
      e.preventDefault(); fillAddress(loadMe().addresses[+li.dataset.i]); showSug(false);
    });
    renderRemember(); renderRepeat();

    function orderText() {
      var c = calc(), f = form.elements, out = ['Здравствуйте! Заказ с сайта:', ''];
      c.lines.forEach(function (l, i) {
        out.push((i + 1) + '. ' + l.p.n + ' — ' + l.it.o + ' × ' + l.it.q + ' = ' + rub(l.price * l.it.q));
      });
      out.push('', 'Товары: ' + rub(c.items));
      out.push('Доставка: ' + (c.fee ? rub(c.fee) : 'бесплатно') + (c.out ? ' + ' + D.outside_per_km + ' ₽/км за МКАД' : ''));
      out.push('Итого: ' + (c.out ? 'от ' : '') + rub(c.total), '');
      out.push('Имя: ' + f.name.value.trim());
      out.push('Телефон: ' + f.phone.value.trim());
      out.push('Адрес: ' + f.address.value.trim() + (c.out ? ' (за МКАД)' : ''));
      out.push('Оплата: наличными после получения');
      if (f.comment.value.trim()) out.push('Комментарий: ' + f.comment.value.trim());
      return out.join('\n').replace(/ /g, ' ');
    }
    function validate() {
      var bad = null;
      ['name', 'phone', 'address'].forEach(function (n) {
        var el = form.elements[n], v = el.value.trim();
        var ok = n === 'phone' ? /^\+7\d{10}$/.test(phoneDigits(v)) : v.length >= 2;
        el.setAttribute('aria-invalid', ok ? 'false' : 'true');
        if (!ok && !bad) bad = el;
      });
      var err = $('#formError'), consent = $('#f-consent');
      if (bad) {
        err.hidden = false;
        err.textContent = bad.name === 'phone' && bad.value.trim().length > 2 ? 'Проверьте телефон: +7 и ещё 10 цифр, например +7 (900) 123-45-67.' : 'Заполните имя, телефон и адрес, чтобы мы могли доставить заказ.';
        bad.focus(); return false;
      }
      if (consent && !consent.checked) { err.hidden = false; err.textContent = 'Отметьте согласие на обработку персональных данных — без него мы не можем принять заказ.'; consent.focus(); return false; }
      err.hidden = true; return true;
    }
    function sendWhatsApp() {
      rememberMe();
      var url = 'https://wa.me/' + BRO.site.whatsapp + '?text=' + encodeURIComponent(orderText());
      var w = window.open(url, '_blank', 'noopener');
      if (!w) location.href = url;
      toast('<span>Открываем WhatsApp — нажмите «Отправить» в чате</span>');
    }
    /* Заказ на сервер (цены он пересчитает сам). Не вышло — показываем ошибку и запасную кнопку WhatsApp. */
    function sendToServer() {
      var c = calc(), f = form.elements, send = $('#sendOrder'), err = $('#formError');
      var label = send.innerHTML;
      send.disabled = true; send.textContent = 'Отправляем заказ…';
      fetch(BRO.site.order_api, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-BRO': '1' },
        body: JSON.stringify({
          items: c.lines.map(function (l) { return { s: l.it.s, o: l.it.o, q: l.it.q }; }),
          name: f.name.value, phone: f.phone.value, address: f.address.value, comment: f.comment.value,
          zone: c.out ? 'out' : 'mkad', consent: $('#f-consent').checked, website: f.website.value, total: c.total
        })
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, d: d }; });
      }).then(function (res) {
        if (!res.ok) throw res.d;
        var d = res.d;
        rememberMe(); save([]);  // сначала запомнить состав для «Повторить заказ», потом очистить корзину
        app.hidden = true; $('#cartEmpty').hidden = true;
        var done = $('#orderDone');
        done.innerHTML = '<p class="eyebrow">Заказ принят</p><h2>Спасибо за заказ!</h2>' +
          '<p>Сумма: <b>' + (d.out ? 'от ' : '') + rub(d.total) + '</b>, оплата наличными после получения. ' +
          'Мы перезвоним по номеру <b>' + esc(f.phone.value.trim()) + '</b>, чтобы подтвердить заказ и время доставки.</p>' +
          '<a class="btn btn-primary" href="' + ROOT + 'catalog.html">Вернуться в каталог</a>';
        done.hidden = false; done.focus(); window.scrollTo(0, 0);
      }).catch(function (d) {
        d = d || {};
        send.disabled = false; send.innerHTML = label;
        err.hidden = false;
        err.innerHTML = esc(d.error || 'Не получилось отправить заказ — нет связи с сервером.') +
          (d.error && !d.fallback ? '' : ' <button type="button" class="btn-ghost" id="waFallback">Отправить через WhatsApp</button>');
        var fb = $('#waFallback'); if (fb) fb.addEventListener('click', sendWhatsApp);
      });
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!validate()) return;
      if (BRO.site.order_api) sendToServer(); else sendWhatsApp();
    });
    render();
  }

  /* ---------- cookie: счётчик посещаемости — только после согласия ---------- */
  var CK = 'bro_cookie_v1';
  function cookieChoice() { try { return localStorage.getItem(CK); } catch (e) { return null; } }
  function loadMetrika() {
    var id = window.BRO_METRIKA; if (!id || window.ym) return;
    (function (m, e, t, r, i, k, a) { m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); }; m[i].l = 1 * new Date(); k = e.createElement(t), a = e.getElementsByTagName(t)[0], k.async = 1, k.src = r, a.parentNode.insertBefore(k, a); })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js', 'ym');
    window.ym(id, 'init', { clickmap: true, trackLinks: true, accurateTrackBounce: true });
  }
  function clearMetrikaCookies() {  // при отказе убираем то, что счётчик мог сохранить раньше
    document.cookie.split(';').forEach(function (c) {
      var n = c.split('=')[0].trim();
      if (/^_ym|^yandexuid|^yabs-sid|^i$/.test(n)) document.cookie = n + '=; Max-Age=0; path=/';
    });
  }
  function cookieBanner() {
    var old = $('#cookieBar'); if (old) old.remove();
    var bar = document.createElement('div');
    bar.id = 'cookieBar'; bar.className = 'cookie-bar'; bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', 'Файлы cookie');
    bar.innerHTML = '<p>Мы используем файлы cookie, чтобы сайт работал удобнее. Подробнее — в <a href="' + ROOT + 'privacy.html#cookie">политике</a>.</p>' +
      '<div class="cookie-btns"><button type="button" class="cookie-yes">Принять</button><button type="button" class="cookie-no">Отказаться</button></div>';
    document.body.appendChild(bar);
    bar.addEventListener('click', function (e) {
      var yes = e.target.closest('.cookie-yes'), no = e.target.closest('.cookie-no');
      if (!yes && !no) return;
      try { localStorage.setItem(CK, yes ? 'yes' : 'no'); } catch (err) { }
      if (yes) loadMetrika(); else clearMetrikaCookies();
      bar.remove();
    });
  }
  if (cookieChoice() === 'yes') loadMetrika();
  else if (!cookieChoice()) cookieBanner();
  document.addEventListener('click', function (e) { if (e.target.closest('[data-cookie-settings]')) cookieBanner(); });

  renderBadge(false);
  window.addEventListener('storage', function (e) { if (e.key === KEY) renderBadge(false); });
})();
