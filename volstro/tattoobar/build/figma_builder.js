// Draws DATA (written by figma_export.js) into the current Figma file as editable layers.

var WEIGHT_NAMES = {
  100: ['thin', 'hairline'], 200: ['extralight', 'ultralight'], 300: ['light'], 400: ['regular', 'normal', 'book'],
  500: ['medium'], 600: ['semibold', 'demibold'], 700: ['bold'], 800: ['extrabold', 'ultrabold'], 900: ['black', 'heavy']
};
var FAMILY_ALIASES = {
  'Big Shoulders Display': ['Big Shoulders Display', 'Big Shoulders'],
  'Albert Sans': ['Albert Sans']
};

function norm(s) { return s.toLowerCase().replace(/[\s_-]/g, ''); }

function hexToColor(hex) {
  var h = hex.replace('#', '');
  return {
    r: parseInt(h.slice(0, 2), 16) / 255,
    g: parseInt(h.slice(2, 4), 16) / 255,
    b: parseInt(h.slice(4, 6), 16) / 255,
    a: h.length > 6 ? parseInt(h.slice(6, 8), 16) / 255 : 1
  };
}

function solid(hex) {
  var c = hexToColor(hex);
  return { type: 'SOLID', color: { r: c.r, g: c.g, b: c.b }, opacity: c.a };
}

function main() {
  return figma.listAvailableFontsAsync().then(function (available) {
    var byFamily = {};
    available.forEach(function (f) {
      if (!byFamily[f.fontName.family]) byFamily[f.fontName.family] = [];
      byFamily[f.fontName.family].push(f.fontName.style);
    });

    var missing = {};
    var cache = {};
    function pickStyle(styles, weight) {
      var order = [weight];
      for (var d = 100; d <= 800; d += 100) { order.push(weight + d); order.push(weight - d); }
      for (var i = 0; i < order.length; i++) {
        var names = WEIGHT_NAMES[order[i]];
        if (!names) continue;
        for (var j = 0; j < names.length; j++) {
          for (var k = 0; k < styles.length; k++) if (norm(styles[k]) === names[j]) return styles[k];
        }
        for (var j2 = 0; j2 < names.length; j2++) {
          for (var k2 = 0; k2 < styles.length; k2++) {
            var n = norm(styles[k2]);
            if (n.indexOf('italic') < 0 && n.slice(-names[j2].length) === names[j2]) return styles[k2];
          }
        }
      }
      return null;
    }
    function resolveFont(family, weight) {
      var key = family + '|' + weight;
      if (cache[key]) return cache[key];
      var fams = FAMILY_ALIASES[family] || [family];
      for (var i = 0; i < fams.length; i++) {
        var styles = byFamily[fams[i]];
        if (!styles) continue;
        var st = pickStyle(styles, weight);
        if (st) { cache[key] = { family: fams[i], style: st }; return cache[key]; }
      }
      missing[family] = true;
      var interStyle = pickStyle(byFamily['Inter'] || ['Regular'], weight) || 'Regular';
      cache[key] = { family: 'Inter', style: interStyle };
      return cache[key];
    }

    // Work out and load every font before drawing
    var needed = { 'Inter|Regular': { family: 'Inter', style: 'Regular' } };
    function scanFonts(n) {
      if (n.t === 'text') n.runs.forEach(function (r) { var f = resolveFont(r.st.f, r.st.wt); needed[f.family + '|' + f.style] = f; });
      (n.children || []).forEach(scanFonts);
    }
    DATA.frames.forEach(function (fr) { fr.children.forEach(scanFonts); });
    var fontList = Object.keys(needed).map(function (k) { return needed[k]; });
    return Promise.all(fontList.map(function (f) { return figma.loadFontAsync(f); })).then(function () {
      return draw(resolveFont, Object.keys(missing));
    });
  });
}

function draw(resolveFont, missing) {
  // Colour styles, so one colour can be changed everywhere
  var styleIds = {};
  Object.keys(DATA.tokens).forEach(function (name) {
    var s = figma.createPaintStyle();
    s.name = 'TattooBar/' + name;
    s.paints = [solid(DATA.tokens[name])];
    styleIds[DATA.tokens[name].toUpperCase()] = s.id;
  });

  var imageHashes = {};
  function imageHash(src) {
    if (!imageHashes[src]) imageHashes[src] = figma.createImage(figma.base64Decode(DATA.images[src])).hash;
    return imageHashes[src];
  }

  var page = figma.createPage();
  page.name = 'TattooBar website';
  var pending = [];

  function paints(list) {
    return (list || []).map(function (p) {
      if (p.type === 'solid') return solid(p.c);
      return {
        type: 'GRADIENT_LINEAR',
        gradientTransform: [[0, 1, 0], [-1, 0, 1]],
        gradientStops: p.stops.map(function (s) { return { position: s[0], color: hexToColor(s[1]) }; })
      };
    });
  }
  function bindFill(node, list) {
    if (list && list.length === 1 && list[0].type === 'solid' && styleIds[list[0].c]) {
      pending.push(function () { return node.setFillStyleIdAsync(styleIds[list[0].c]); });
    }
  }
  function corners(node, r) {
    if (!r) return;
    if (r[0] === r[1] && r[1] === r[2] && r[2] === r[3]) node.cornerRadius = r[0];
    else { node.topLeftRadius = r[0]; node.topRightRadius = r[1]; node.bottomRightRadius = r[2]; node.bottomLeftRadius = r[3]; }
  }

  function build(n, parent, ox, oy) {
    if (n.t === 'frame') {
      var f = figma.createFrame();
      parent.appendChild(f);
      f.name = n.name;
      f.resize(Math.max(n.w, 0.01), Math.max(n.h, 0.01));
      f.x = n.x - ox; f.y = n.y - oy;
      f.fills = paints(n.fill);
      bindFill(f, n.fill);
      f.clipsContent = !!n.clip;
      if (n.stroke) {
        f.strokes = [solid(n.stroke.c)];
        f.strokeAlign = n.stroke.align;
        var w = n.stroke.w;
        if (w[0] === w[1] && w[1] === w[2] && w[2] === w[3]) f.strokeWeight = w[0];
        else { f.strokeTopWeight = w[0]; f.strokeRightWeight = w[1]; f.strokeBottomWeight = w[2]; f.strokeLeftWeight = w[3]; }
      }
      corners(f, n.radius);
      if (n.opacity !== undefined) f.opacity = n.opacity;
      n.children.forEach(function (c) { build(c, f, n.x, n.y); });
      return;
    }
    if (n.t === 'image') {
      var r = figma.createRectangle();
      parent.appendChild(r);
      r.name = n.name;
      r.resize(Math.max(n.w, 0.01), Math.max(n.h, 0.01));
      r.x = n.x - ox; r.y = n.y - oy;
      var fill = { type: 'IMAGE', imageHash: imageHash(n.src), scaleMode: 'FILL' };
      var centred = Math.abs(n.pos[0] - 0.5) < 0.01 && Math.abs(n.pos[1] - 0.5) < 0.01;
      if (!centred && n.nw && n.nh) {
        // object-fit: cover with an off-centre object-position
        var s = Math.max(n.w / n.nw, n.h / n.nh);
        var sw = n.w / (n.nw * s), sh = n.h / (n.nh * s);
        fill.scaleMode = 'CROP';
        fill.imageTransform = [[sw, 0, (1 - sw) * n.pos[0]], [0, sh, (1 - sh) * n.pos[1]]];
      }
      if (n.gray) fill.filters = { saturation: -1 };
      r.fills = [fill];
      corners(r, n.radius);
      return;
    }
    if (n.t === 'svg') {
      var v = figma.createNodeFromSvg(n.svg);
      parent.appendChild(v);
      v.name = n.name;
      v.x = n.x - ox; v.y = n.y - oy;
      v.fills = [];
      return;
    }
    if (n.t === 'text') {
      var t = figma.createText();
      parent.appendChild(t);
      var first = n.runs[0].st;
      t.fontName = resolveFont(first.f, first.wt);
      t.characters = n.runs.map(function (r) { return r.s; }).join('');
      var at = 0;
      n.runs.forEach(function (run) {
        var st = run.st, end = at + run.s.length;
        if (end > at) {
          t.setRangeFontName(at, end, resolveFont(st.f, st.wt));
          t.setRangeFontSize(at, end, Math.max(st.sz, 1));
          t.setRangeFills(at, end, [solid(st.c)]);
          t.setRangeLineHeight(at, end, st.lh ? { unit: 'PIXELS', value: st.lh } : { unit: 'AUTO' });
          t.setRangeLetterSpacing(at, end, { unit: 'PIXELS', value: st.ls || 0 });
          t.setRangeTextCase(at, end, st.tc);
          if (st.u) t.setRangeTextDecoration(at, end, 'UNDERLINE');
          var id = styleIds[st.c];
          if (id) {
            (function (s0, e0, sid) { pending.push(function () { return t.setRangeFillStyleIdAsync(s0, e0, sid); }); })(at, end, id);
          }
        }
        at = end;
      });
      if (n.single && n.align === 'LEFT' && !n.fixed) {
        t.textAutoResize = 'WIDTH_AND_HEIGHT';
      } else {
        t.resize(Math.max(n.w, 1), Math.max(t.height, 1));
        t.textAutoResize = 'HEIGHT';
        t.textAlignHorizontal = n.align;
      }
      t.x = n.x - ox; t.y = n.y - oy;
      return;
    }
  }

  var x = 0, rowY = { Desktop: 0, Phone: 0 }, colX = { Desktop: 0, Phone: 0 };
  var desktopHeight = 0;
  DATA.frames.forEach(function (fr) { if (fr.view === 'Desktop') desktopHeight = Math.max(desktopHeight, fr.h); });
  rowY.Phone = desktopHeight + 600;
  var made = [];
  DATA.frames.forEach(function (fr) {
    var f = figma.createFrame();
    page.appendChild(f);
    f.name = fr.name;
    f.resize(fr.w, fr.h);
    f.x = colX[fr.view]; f.y = rowY[fr.view];
    colX[fr.view] += fr.w + (fr.view === 'Desktop' ? 200 : 120);
    f.fills = [solid(fr.bg)];
    bindFill(f, [{ type: 'solid', c: fr.bg }]);
    f.clipsContent = true;
    f.layoutGrids = [{
      pattern: 'COLUMNS', alignment: 'STRETCH', count: fr.grid.count, gutterSize: fr.grid.gutter, offset: fr.grid.offset,
      visible: true, color: { r: 1, g: 0.1, b: 0.1, a: 0.08 }
    }];
    fr.children.forEach(function (c) { build(c, f, 0, 0); });
    made.push(f);
  });

  return figma.setCurrentPageAsync(page).then(function () {
    var chain = Promise.resolve();
    var failed = 0;
    pending.forEach(function (fn) { chain = chain.then(fn).catch(function () { failed++; }); });
    return chain.then(function () {
      figma.viewport.scrollAndZoomIntoView(made);
      var msg = 'TattooBar website imported: ' + made.length + ' frames.';
      if (missing.length) msg += ' Missing fonts (Inter used instead): ' + missing.join(', ') + '.';
      figma.closePlugin(msg);
    });
  });
}

figma.notify('Drawing the TattooBar website…', { timeout: 4000 });
main().catch(function (e) { figma.closePlugin('Import failed: ' + (e && e.message ? e.message : e)); });
