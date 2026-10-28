// TattooBar: open-now status, portfolio filter, enquiry form, menus.
(function () {
  // Opening hours in minutes after midnight, London time. null = closed.
  var HOURS = {
    studio: { Mon: [660, 1260], Tue: [660, 1260], Wed: [660, 1260], Thu: [660, 1260], Fri: [660, 1260], Sat: [660, 1260], Sun: null },
    bar: { Mon: [900, 1380], Tue: [900, 1380], Wed: [900, 1380], Thu: [900, 1380], Fri: [900, 1380], Sat: [720, 1440], Sun: null }
  };
  var NAMES = { studio: 'Tattoo studio', bar: 'Bar' };

  function londonNow() {
    var parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/London', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(new Date());
    var get = function (type) {
      for (var i = 0; i < parts.length; i++) if (parts[i].type === type) return parts[i].value;
      return '';
    };
    return { day: get('weekday'), mins: parseInt(get('hour'), 10) * 60 + parseInt(get('minute'), 10) };
  }

  function time(m) {
    if (m >= 1440) return 'midnight';
    return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  }

  function status(place, now) {
    var h = HOURS[place][now.day];
    var name = NAMES[place];
    if (!h) return { open: false, text: name + ' closed today' };
    if (now.mins < h[0]) return { open: false, text: name + ' opens at ' + time(h[0]) };
    if (now.mins < h[1]) return { open: true, text: name + ' open until ' + time(h[1]) };
    return { open: false, text: name + ' closed for today' };
  }

  function renderStatus() {
    var now = londonNow();
    document.querySelectorAll('[data-status]').forEach(function (el) {
      var s = status(el.getAttribute('data-status'), now);
      el.querySelector('i').className = s.open ? 'open' : '';
      el.querySelector('span').textContent = s.text;
    });
  }
  try { renderStatus(); setInterval(renderStatus, 60000); } catch (e) { /* hours stay as printed */ }

  // Portfolio filter
  var filters = document.querySelectorAll('.filter');
  filters.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var style = btn.getAttribute('data-filter');
      filters.forEach(function (b) { b.setAttribute('aria-pressed', String(b === btn)); });
      document.querySelectorAll('.work-grid li').forEach(function (li) {
        li.hidden = style !== 'all' && li.getAttribute('data-style') !== style;
      });
    });
  });

  // Enquiry form: opens the visitor's email app with the message filled in.
  document.querySelectorAll('form[data-enquiry]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!form.reportValidity()) return;
      var d = new FormData(form);
      var topic = d.get('topic') || 'Enquiry';
      var lines = [
        'Name: ' + d.get('name'),
        'Email: ' + d.get('email'),
        d.get('phone') ? 'Phone: ' + d.get('phone') : '',
        d.get('date') ? 'Date: ' + d.get('date') : '',
        d.get('guests') ? 'Guests: ' + d.get('guests') : '',
        '',
        d.get('message')
      ].filter(function (l, i) { return l !== '' || i === 5; });
      var to = form.getAttribute('data-enquiry');
      window.location.href = 'mailto:' + to + '?subject=' + encodeURIComponent(topic + ' enquiry from ' + d.get('name')) +
        '&body=' + encodeURIComponent(lines.join('\n'));
      var done = form.querySelector('.form-done');
      if (done) done.hidden = false;
    });
  });

  // Close open menus on Escape or a click elsewhere
  function closeMenus(except) {
    document.querySelectorAll('details.drop[open]').forEach(function (d) { if (d !== except) d.removeAttribute('open'); });
  }
  document.addEventListener('click', function (e) {
    var inside = e.target.closest('details.drop');
    closeMenus(inside);
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenus(null); });
})();
