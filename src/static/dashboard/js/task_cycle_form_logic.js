/**
 * Portage web (quasi verbatim) du moteur de conditionnalité / calculs /
 * obligatoires mobile : node_modules/tcomb-form-native/lib/cdd-form-logic.js
 * (cdd-frontend). Même contrat, mêmes noms de fonctions — SEULE différence :
 * exposé en global navigateur (`window.TCFormLogic`) au lieu de
 * `module.exports` (ce dashboard n'a pas de bundler CommonJS/ESM), et
 * `cloneDeepKeepFns` ne préserve plus les fonctions React (aucun `factory`
 * ici côté web) mais reste inoffensif à garder tel quel.
 *
 * Aucune dépendance externe, pas d'`eval`. Ne PAS dupliquer cette logique
 * ailleurs si un jour un vrai bundler est introduit — reprendre le fichier
 * mobile tel quel à ce moment-là.
 */
(function (window) {
  'use strict';

  /* ============================================================= utilitaires */

  function isEmpty(v) {
    return (
      v === undefined ||
      v === null ||
      v === '' ||
      (Array.isArray(v) && v.length === 0)
    );
  }

  function toNumber(v) {
    if (typeof v === 'number') return v;
    var n = parseFloat(v);
    return isNaN(n) ? NaN : n;
  }

  function resolvePath(root, path) {
    if (!path) return undefined;
    var parts = String(path).split('.');
    var cur = root;
    for (var i = 0; i < parts.length; i++) {
      if (cur == null) return undefined;
      cur = cur[parts[i]];
    }
    return cur;
  }

  function setPath(root, path, value) {
    var parts = String(path).split('.');
    var cur = root;
    for (var k = 0; k < parts.length - 1; k++) {
      if (cur[parts[k]] == null || typeof cur[parts[k]] !== 'object') cur[parts[k]] = {};
      cur = cur[parts[k]];
    }
    cur[parts[parts.length - 1]] = value;
  }

  function cloneDeepKeepFns(v) {
    if (v == null || typeof v !== 'object') return v;
    if (typeof v === 'function') return v;
    if (Array.isArray(v)) {
      var arr = new Array(v.length);
      for (var i = 0; i < v.length; i++) arr[i] = cloneDeepKeepFns(v[i]);
      return arr;
    }
    var out = {};
    for (var k in v) {
      if (!Object.prototype.hasOwnProperty.call(v, k)) continue;
      if ((k === 'dataset' || k === 'options') && Array.isArray(v[k])) {
        out[k] = v[k];
        continue;
      }
      out[k] = cloneDeepKeepFns(v[k]);
    }
    return out;
  }

  function hasDeclarativeLogic(page) {
    return !!(
      page &&
      ((Array.isArray(page.rules) && page.rules.length) ||
        (Array.isArray(page.calculate) && page.calculate.length))
    );
  }

  function _anyDatasetInFields(fields) {
    var keys = Object.keys(fields || {});
    for (var i = 0; i < keys.length; i++) {
      var f = fields[keys[i]];
      if (!f || typeof f !== 'object') continue;
      if (Array.isArray(f.dataset)) return true;
      if (f.fields && _anyDatasetInFields(f.fields)) return true;
      if (f.item && f.item.fields && _anyDatasetInFields(f.item.fields)) return true;
    }
    return false;
  }
  function _anyOrderInFields(fields) {
    var keys = Object.keys(fields || {});
    for (var i = 0; i < keys.length; i++) {
      var f = fields[keys[i]];
      if (!f || typeof f !== 'object') continue;
      if (Array.isArray(f.order)) return true;
      if (f.fields && _anyOrderInFields(f.fields)) return true;
      if (f.item && (Array.isArray(f.item.order) || _anyOrderInFields(f.item.fields))) return true;
    }
    return false;
  }
  function hasDynamicOptions(page) {
    if (hasDeclarativeLogic(page)) return true;
    var o = page && page.options;
    if (!o) return false;
    return Array.isArray(o.order) || _anyDatasetInFields(o.fields) || _anyOrderInFields(o.fields);
  }

  function applyFieldOrder(options, srcOptions) {
    if (!options || !srcOptions || typeof srcOptions !== 'object') return options;
    if (Array.isArray(srcOptions.order) && !Array.isArray(options.order)) {
      options.order = srcOptions.order.slice();
    }
    if (options.fields && srcOptions.fields) {
      Object.keys(options.fields).forEach(function (k) {
        if (srcOptions.fields[k]) applyFieldOrder(options.fields[k], srcOptions.fields[k]);
      });
    }
    if (options.item && srcOptions.item) applyFieldOrder(options.item, srcOptions.item);
    return options;
  }

  /* ================================ mise en forme valeur -> schéma courant */

  function _coerceToSchema(schema, val) {
    if (!schema || typeof schema !== 'object') return val;
    var tp = schema.type;
    if (tp === 'object' && schema.properties) {
      if (val == null || typeof val !== 'object' || Array.isArray(val)) return val;
      var out = null;
      Object.keys(schema.properties).forEach(function (k) {
        var cv = _coerceToSchema(schema.properties[k], val[k]);
        if (cv !== val[k]) {
          if (!out) out = Object.assign({}, val);
          out[k] = cv;
        }
      });
      return out || val;
    }
    if (tp === 'array') {
      if (Array.isArray(val)) return val;
      if (val == null || val === '') return undefined;
      return [val];
    }
    if (Array.isArray(val)) return val.length ? val[0] : undefined;
    return val;
  }
  function coerceValueToSchema(page, value) {
    return page && page.page ? _coerceToSchema(page.page, value) : value;
  }

  /* ============================================================== conditions */

  function resolveField(field, values, allResponses) {
    if (typeof field === 'string' && field.charAt(0) === '$') {
      var dot = field.indexOf('.');
      var idx = parseInt(field.slice(1, dot === -1 ? undefined : dot), 10);
      var rest = dot === -1 ? '' : field.slice(dot + 1);
      var pageValues = (allResponses || [])[idx] || {};
      return rest ? resolvePath(pageValues, rest) : pageValues;
    }
    return resolvePath(values || {}, field);
  }

  function evaluateCondition(cond, values, allResponses) {
    if (!cond || typeof cond !== 'object') return true;
    if (Array.isArray(cond.all)) {
      return cond.all.every(function (c) { return evaluateCondition(c, values, allResponses); });
    }
    if (Array.isArray(cond.any)) {
      return cond.any.some(function (c) { return evaluateCondition(c, values, allResponses); });
    }

    var actual = resolveField(cond.field, values, allResponses);
    var expected = cond.value;

    switch (cond.op) {
      case 'eq': return String(actual) === String(expected);
      case 'ne': return String(actual) !== String(expected);
      case 'gt': return toNumber(actual) > toNumber(expected);
      case 'gte': return toNumber(actual) >= toNumber(expected);
      case 'lt': return toNumber(actual) < toNumber(expected);
      case 'lte': return toNumber(actual) <= toNumber(expected);
      case 'in':
        return Array.isArray(actual)
          ? actual.map(String).indexOf(String(expected)) !== -1
          : String(actual) === String(expected);
      case 'nin':
        return Array.isArray(actual)
          ? actual.map(String).indexOf(String(expected)) === -1
          : String(actual) !== String(expected);
      case 'contains':
        return String(actual == null ? '' : actual).indexOf(String(expected)) !== -1;
      case 'empty': return isEmpty(actual);
      case 'notEmpty': return !isEmpty(actual);
      default: return true;
    }
  }

  /* ====================================================== options dynamiques */

  function optionNodeAtPath(options, path) {
    var parts = String(path).split('.');
    var node = options;
    for (var i = 0; i < parts.length; i++) {
      if (!node.fields) node.fields = {};
      if (!node.fields[parts[i]]) node.fields[parts[i]] = {};
      node = node.fields[parts[i]];
    }
    return node;
  }

  function buildDynamicOptions(page, values, allResponses, baseOptions) {
    var options = cloneDeepKeepFns(
      baseOptions && Object.keys(baseOptions).length
        ? baseOptions
        : (page && page.options) || {}
    );
    if (!page) return options;

    function markCalculatedTargetsDisabled() {
      calculatedTargets(page).forEach(function (target) {
        var node = optionNodeAtPath(options, target);
        node.editable = false;
        node.disabled = true;
      });
    }

    if (!Array.isArray(page.rules) || !page.rules.length) {
      markCalculatedTargetsDisabled();
      return applyDatasets(applyFieldOrder(options, page && page.options), values, allResponses);
    }

    var agg = {};
    page.rules.forEach(function (rule) {
      var met = evaluateCondition(rule.when, values, allResponses);
      (rule.then || []).forEach(function (act) {
        if (!act || !act.target || !act.action) return;
        var bucket = agg[act.target] || (agg[act.target] = {});
        (bucket[act.action] || (bucket[act.action] = [])).push(!!met);
      });
    });

    var some = function (a) { return Array.isArray(a) && a.some(Boolean); };
    var has = function (b, k) { return Array.isArray(b[k]) && b[k].length > 0; };

    Object.keys(agg).forEach(function (target) {
      var b = agg[target];
      var node = optionNodeAtPath(options, target);

      if (has(b, 'show') || has(b, 'hide')) {
        var hiddenByHide = has(b, 'hide') && some(b.hide);
        var hiddenByShow = has(b, 'show') && !some(b.show);
        node.hidden = hiddenByHide || hiddenByShow;
      }

      if (has(b, 'require') || has(b, 'optional')) {
        node.__ruleRequired =
          has(b, 'require') && some(b.require) &&
          !(has(b, 'optional') && some(b.optional));
        if (node.__ruleRequired && !(has(b, 'hide') && some(b.hide))) {
          node.hidden = false;
        }
      }

      if (has(b, 'enable') || has(b, 'disable')) {
        var disabled =
          (has(b, 'disable') && some(b.disable)) ||
          (has(b, 'enable') && !some(b.enable));
        node.editable = !disabled;
        node.disabled = disabled;
      }
    });

    markCalculatedTargetsDisabled();

    return applyDatasets(applyFieldOrder(options, page && page.options), values, allResponses);
  }

  /* ============================================ sources dynamiques / cascade */

  function _cascadePath(prefix, cascadeFrom) {
    if (!cascadeFrom) return null;
    if (cascadeFrom.charAt(0) === '$' || cascadeFrom.indexOf('.') !== -1) return cascadeFrom;
    return prefix ? prefix + '.' + cascadeFrom : cascadeFrom;
  }

  function _datasetToOptions(node, values, allResponses, prefix) {
    var ds = Array.isArray(node.dataset) ? node.dataset : [];
    var pPath = _cascadePath(prefix, node.cascadeFrom);
    var list = ds;
    if (pPath) {
      var pv = resolveField(pPath, values, allResponses);
      if (isEmpty(pv)) return [];
      list = ds.filter(function (r) { return String(r.p) === String(pv); });
    }
    return list.map(function (r) {
      return { value: r.v, text: (r.l != null && r.l !== '') ? r.l : String(r.v) };
    });
  }

  function applyDatasets(options, values, allResponses) {
    if (!options || !options.fields) return options;
    (function walk(fields, prefix) {
      Object.keys(fields).forEach(function (key) {
        var f = fields[key];
        if (!f || typeof f !== 'object') return;
        var path = prefix ? prefix + '.' + key : key;
        if (Array.isArray(f.dataset)) {
          var opts = _datasetToOptions(f, values, allResponses, prefix);
          f.options = opts;
          f.item = (f.item && typeof f.item === 'object') ? f.item : {};
          f.item.options = opts;
        }
        if (f.fields) walk(f.fields, path);
        if (f.item && f.item.fields) walk(f.item.fields, path);
      });
    })(options.fields, '');
    return options;
  }

  function pruneStaleCascadeValues(options, values) {
    if (!options || !options.fields) return values;
    var out = null;
    (function walk(fields, prefix) {
      Object.keys(fields).forEach(function (key) {
        var f = fields[key];
        if (!f || typeof f !== 'object') return;
        var path = prefix ? prefix + '.' + key : key;
        if (Array.isArray(f.dataset) && Array.isArray(f.options)) {
          var cur = resolvePath(out || values, path);
          if (!isEmpty(cur) && !Array.isArray(cur)) {
            var ok = f.options.some(function (o) { return String(o.value) === String(cur); });
            if (!ok) {
              if (!out) { try { out = JSON.parse(JSON.stringify(values || {})); } catch (e) { out = Object.assign({}, values || {}); } }
              setPath(out, path, undefined);
            }
          }
        }
        if (f.fields) walk(f.fields, path);
      });
    })(options.fields, '');
    return out || values;
  }

  /* ===================================================== obligatoires vides */

  function collectRuleRequired(fields, prefix, acc) {
    Object.keys(fields || {}).forEach(function (key) {
      var f = fields[key] || {};
      if (f.hidden) return;
      var path = prefix ? prefix + '.' + key : key;
      if (f.__ruleRequired) acc.push(path);
      if (f.fields) collectRuleRequired(f.fields, path, acc);
    });
    return acc;
  }

  function validateRuleRequired(dynamicOptions, values) {
    var paths = collectRuleRequired((dynamicOptions || {}).fields, '', []);
    return paths.filter(function (p) { return isEmpty(resolvePath(values || {}, p)); });
  }

  function walkSchemaRequired(objSchema, val, opts, prefix, missing) {
    var props = (objSchema && objSchema.properties) || {};
    var req = (objSchema && objSchema.required) || [];
    Object.keys(props).forEach(function (key) {
      var p = props[key] || {};
      var o = (opts && opts[key]) || {};
      var path = prefix ? prefix + '.' + key : key;
      if (o.hidden) return;

      if (p.type === 'object') {
        walkSchemaRequired(p, (val && val[key]) || {}, o.fields || {}, path, missing);
      } else if (p.type === 'array' && p.items && p.items.type === 'object') {
        // Répétable : validation ligne par ligne hors périmètre v1.
      } else if (req.indexOf(key) !== -1) {
        if (isEmpty(val ? val[key] : undefined)) missing.push(path);
      }
    });
    return missing;
  }

  function validateSchemaRequired(page, values, dynamicOptions) {
    var schema = page && page.page;
    if (!schema || !schema.properties) return [];
    return walkSchemaRequired(
      schema, values || {}, (dynamicOptions || {}).fields || {}, '', []
    );
  }

  function checkPageRequired(page, values, dynamicOptions) {
    if (!hasDeclarativeLogic(page)) return [];
    return validateRuleRequired(dynamicOptions, values)
      .concat(validateSchemaRequired(page, values, dynamicOptions));
  }

  /* ============================================== marquage visuel « en rouge » */

  function _leafKey(path) {
    var p = String(path).split('.');
    return p[p.length - 1];
  }

  function markRequiredErrors(options, paths, page, fallbackMsg) {
    if (!options || !Array.isArray(paths) || !paths.length) return options;
    var messages = (page && page.messages) || {};
    paths.forEach(function (p) {
      var node = optionNodeAtPath(options, p);
      node.hasError = true;
      if (node.error == null) {
        var perField = messages[_leafKey(p)] && messages[_leafKey(p)].required;
        node.error = perField || fallbackMsg || 'Ce champ est obligatoire';
      }
    });
    return options;
  }

  /* ============================================================== calculs */

  var FUNCTIONS = {
    sum: function (a) { return a.reduce(function (x, y) { return x + y; }, 0); },
    min: function (a) { return a.length ? Math.min.apply(null, a) : 0; },
    max: function (a) { return a.length ? Math.max.apply(null, a) : 0; },
    round: function (a) { return Math.round(a[0] || 0); },
    abs: function (a) { return Math.abs(a[0] || 0); },
    floor: function (a) { return Math.floor(a[0] || 0); },
    ceil: function (a) { return Math.ceil(a[0] || 0); },
    int: function (a) { return parseInt(a[0] || 0, 10) || 0; },
    float: function (a) { return parseFloat(a[0] || 0) || 0; }
  };

  var BINOPS = {
    '+': function (a, b) { return a + b; },
    '-': function (a, b) { return a - b; },
    '*': function (a, b) { return a * b; },
    '/': function (a, b) { return b === 0 ? 0 : a / b; },
    '%': function (a, b) { return b === 0 ? 0 : a % b; }
  };

  function tokenize(expr) {
    var tokens = [];
    var re = /\s*([A-Za-z_][\w.]*|\d+\.\d+|\d+|[()+\-*/%,])\s*/g;
    var m;
    var last = 0;
    while ((m = re.exec(expr)) !== null) {
      if (m.index !== last) return null;
      tokens.push(m[1]);
      last = re.lastIndex;
    }
    return last === expr.length ? tokens : null;
  }

  function parse(tokens) {
    var i = 0;
    function peek() { return tokens[i]; }
    function next() { return tokens[i++]; }

    function parseExpr() {
      var node = parseTerm();
      while (peek() === '+' || peek() === '-') {
        node = { t: 'bin', op: next(), l: node, r: parseTerm() };
      }
      return node;
    }
    function parseTerm() {
      var node = parseFactor();
      while (peek() === '*' || peek() === '/' || peek() === '%') {
        node = { t: 'bin', op: next(), l: node, r: parseFactor() };
      }
      return node;
    }
    function parseFactor() {
      var tok = peek();
      if (tok === '-') { next(); return { t: 'neg', v: parseFactor() }; }
      if (tok === '+') { next(); return parseFactor(); }
      if (tok === '(') {
        next();
        var node = parseExpr();
        if (next() !== ')') throw new Error('paren');
        return node;
      }
      if (/^\d+(\.\d+)?$/.test(tok)) { next(); return { t: 'num', v: parseFloat(tok) }; }
      if (/^[A-Za-z_][\w.]*$/.test(tok)) {
        next();
        if (peek() === '(') {
          next();
          var args = [];
          if (peek() !== ')') {
            args.push(parseExpr());
            while (peek() === ',') { next(); args.push(parseExpr()); }
          }
          if (next() !== ')') throw new Error('paren');
          return { t: 'call', name: tok, args: args };
        }
        return { t: 'var', name: tok };
      }
      throw new Error('token ' + tok);
    }

    var ast = parseExpr();
    if (i !== tokens.length) throw new Error('trailing');
    return ast;
  }

  function numValue(v) {
    if (typeof v === 'number') return v;
    if (v == null || v === '') return 0;
    var n = parseFloat(String(v).replace(',', '.'));
    return isNaN(n) ? 0 : n;
  }

  function evalNode(node, values) {
    switch (node.t) {
      case 'num': return node.v;
      case 'var': return numValue(resolvePath(values, node.name));
      case 'neg': return -evalNode(node.v, values);
      case 'bin': return BINOPS[node.op](evalNode(node.l, values), evalNode(node.r, values));
      case 'call': {
        var fn = FUNCTIONS[node.name];
        if (!fn) return 0;
        return fn(node.args.map(function (a) { return evalNode(a, values); }));
      }
      default: return 0;
    }
  }

  var _astCache = {};
  function compileExpr(expr) {
    if (Object.prototype.hasOwnProperty.call(_astCache, expr)) return _astCache[expr];
    var ast = null;
    try {
      var tokens = tokenize(expr);
      if (tokens) ast = parse(tokens);
    } catch (e) {
      ast = null;
    }
    _astCache[expr] = ast;
    return ast;
  }

  function applyCalculations(page, values) {
    if (!page || !Array.isArray(page.calculate) || !page.calculate.length) return values;
    var out;
    try {
      out = JSON.parse(JSON.stringify(values || {}));
    } catch (e) {
      out = Object.assign({}, values || {});
    }
    var items = page.calculate.filter(function (c) { return c && c.target && c.expr; });
    var passes = Math.min(Math.max(items.length, 1), 6);
    for (var p = 0; p < passes; p++) {
      var changed = false;
      for (var k = 0; k < items.length; k++) {
        var ast = compileExpr(items[k].expr);
        if (!ast) continue;
        var res = evalNode(ast, out);
        if (res == null || isNaN(res) || !isFinite(res)) continue;
        var rounded = Math.round(res * 1e6) / 1e6;
        if (numValue(resolvePath(out, items[k].target)) !== rounded) {
          setPath(out, items[k].target, rounded);
          changed = true;
        }
      }
      if (!changed) break;
    }
    return out;
  }

  function calculatedTargets(page) {
    if (!page || !Array.isArray(page.calculate)) return [];
    return page.calculate
      .filter(function (c) { return c && c.target; })
      .map(function (c) { return c.target; });
  }

  /* ================================================================ export */

  window.TCFormLogic = {
    hasDeclarativeLogic: hasDeclarativeLogic,
    hasDynamicOptions: hasDynamicOptions,
    evaluateCondition: evaluateCondition,
    buildDynamicOptions: buildDynamicOptions,
    applyDatasets: applyDatasets,
    pruneStaleCascadeValues: pruneStaleCascadeValues,
    validateRuleRequired: validateRuleRequired,
    validateSchemaRequired: validateSchemaRequired,
    checkPageRequired: checkPageRequired,
    markRequiredErrors: markRequiredErrors,
    applyCalculations: applyCalculations,
    calculatedTargets: calculatedTargets,
    cloneDeepKeepFns: cloneDeepKeepFns,
    coerceValueToSchema: coerceValueToSchema,
    resolvePath: resolvePath,
    setPath: setPath,
    isEmpty: isEmpty
  };
})(typeof window !== 'undefined' ? window : this);
