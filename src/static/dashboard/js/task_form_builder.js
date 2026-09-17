/* Form builder pour Task.form (Cycle d'investissement > Tâches).
 *
 * Modèle interne d'édition -> compilé vers le format stocké consommé par
 * tcomb-json-schema / tcomb-form-native côté mobile :
 *   form = [ { options:{fields}, page:{type,properties,required}, rules?, calculate?, messages? } ]
 *
 * Le décompilateur (format stocké -> modèle interne) permet de rouvrir un
 * formulaire existant, y compris collé dans l'onglet JSON.
 */
(function () {
  "use strict";

  var CFG = JSON.parse(document.getElementById("tfb-config").textContent);
  var T = CFG.i18n || {};
  function t(k, d) { return T[k] || d || k; }

  var FIELD_TYPES = [
    ["text", t("type_text", "Texte")],
    ["note", t("type_note", "Note / libellé")],
    ["integer", t("type_integer", "Entier")],
    ["decimal", t("type_decimal", "Décimal")],
    ["select_one", t("type_select_one", "Choix unique")],
    ["select_multiple", t("type_select_multiple", "Choix multiple (liste)")],
    ["select_multiple_check", t("type_select_multiple_check", "Choix multiple (cases à cocher)")],
    ["date", t("type_date", "Date")],
    ["datetime", t("type_datetime", "Date + heure")],
    ["time", t("type_time", "Heure")],
    ["geopoint", t("type_geopoint", "Coordonnées GPS")],
    ["group", t("type_group", "Groupe")],
    ["repeat", t("type_repeat", "Groupe répétable")]
  ];
  var DEFAULT_GPS_ACCURACY = 20;
  var CONTAINER_TYPES = { group: 1, repeat: 1 };
  var OPS = [
    ["eq", "="], ["ne", "≠"], ["gt", ">"], ["gte", "≥"], ["lt", "<"], ["lte", "≤"],
    ["in", t("op_in", "dans la liste")], ["nin", t("op_nin", "hors liste")],
    ["contains", t("op_contains", "contient")],
    ["empty", t("op_empty", "est vide")], ["notEmpty", t("op_not_empty", "est renseigné")]
  ];
  var ACTIONS = [
    ["show", t("act_show", "Afficher")], ["hide", t("act_hide", "Masquer")],
    ["require", t("act_require", "Rendre obligatoire")], ["optional", t("act_optional", "Rendre facultatif")],
    ["enable", t("act_enable", "Activer")], ["disable", t("act_disable", "Désactiver")]
  ];

  var uid = (function () { var n = 0; return function () { return "n" + (++n) + "_" + Date.now().toString(36); }; })();

  var state = {
    pages: [], active: 0, sel: null, tab: "field", drag: null, dsMeta: null, shareMode: "none",
    // Choix dynamiques depuis un autre champ (`choicesFrom`) : liste des
    // autres tâches du projet (chargée une fois, paresseusement) + champs
    // select d'une tâche donnée (mis en cache par id de tâche).
    otherTasks: null, otherTaskFieldsCache: {},
    // Visibilité conditionnelle inter-tâches (`crossTaskVisibility` / la
    // condition tâche-entière du toolbar) : cache SÉPARÉ de
    // `otherTaskFieldsCache` (tout type de champ, pas seulement les select —
    // ne doit pas polluer le picker `choicesFrom` pour la même tâche id).
    otherTaskFieldsAllCache: {}, visibilityCondition: null,
    // Pièces jointes attendues pour la tâche (onglet "Pièces jointes",
    // `Task.attachments` — hors de `form`, donc jamais compilé/décompilé par
    // page comme le reste de `state`, cf. renderAttachmentsEditor).
    attachments: []
  };

  var DS_OPS = [
    ["eq", "="], ["ne", "≠"], ["gt", ">"], ["gte", "≥"], ["lt", "<"], ["lte", "≤"],
    ["contains", t("op_contains", "contient")], ["in", t("op_in_list", "dans (a,b,c)")],
    ["isnull", t("op_isnull", "est vide (NULL)")], ["notnull", t("op_notnull", "est renseigné")]
  ];
  var DS_NULL_OPS = { isnull: 1, notnull: 1 };
  function keptFilters(list) {
    return (list || []).filter(function (f) {
      return f && f.column && (DS_NULL_OPS[f.op] || String(f.value == null ? "" : f.value).trim() !== "");
    });
  }
  var SOURCE_KINDS = [
    ["list", t("src_list", "Liste manuelle")],
    ["db", t("src_db", "Base de données (PostgreSQL)")],
    ["excel", t("src_excel", "Fichier Excel")],
    ["admin_levels", t("src_admin", "Niveaux administratifs")]
  ];
  var ADMIN_LEVEL_LABELS = { Region: "Région", Prefecture: "Préfecture", Commune: "Commune", Canton: "Canton", Village: "Village" };

  /* ------------------------------------------------------------------ utils */
  function slugKey(label) {
    var s = (label || "").normalize ? label.normalize("NFD").replace(/[̀-ͯ]/g, "") : (label || "");
    s = s.replace(/[^A-Za-z0-9 ]/g, " ").trim().split(/\s+/);
    if (!s[0]) return "champ";
    return s[0].toLowerCase() + s.slice(1).map(function (w) {
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    }).join("");
  }
  function uniqueKey(base, siblings, selfId) {
    var used = {};
    siblings.forEach(function (n) { if (n.id !== selfId) used[n.key] = 1; });
    var k = base || "champ", i = 2;
    while (used[k]) { k = base + i; i++; }
    return k;
  }
  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "class") e.className = attrs[k];
      else if (k === "text") e.textContent = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]);
      else e.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function opt(v, label, sel) { var o = el("option", { value: v, text: label }); if (sel != null && String(sel) === String(v)) o.selected = true; return o; }

  function newSource() {
    return { kind: "list", table: "", value: "", label: "", parent: "", filters: [], orderBy: "", limit: 500, level: "", file: "" };
  }
  function newNode(type) {
    return {
      id: uid(), key: "", type: type || "text", label: "", help: "", required: false,
      def: "", choices: [], min: "", max: "", minLength: "", maxLength: "", pattern: "",
      message: { required: "", range: "", regex: "", type: "" }, mode: type === "date",
      minItems: "", maxItems: "", disableOrder: false,
      accuracyThreshold: type === "geopoint" ? DEFAULT_GPS_ACCURACY : "",
      source: newSource(), dataset: [], cascadeFrom: "", listThreshold: "", _sheet: null,
      share: false,
      // Options dynamiques depuis un AUTRE champ select (même tâche ou une
      // tâche différente) — distinct de `source`/`dataset`/`cascadeFrom`
      // (sources figées à l'enregistrement) : ici, les options sont
      // recalculées côté mobile à partir de la réponse LIVE du champ source.
      // `sourceTaskId` : null = même tâche ; sinon id d'une autre tâche du
      // projet. `sourcePath` : chemin du champ source ("$<page>.<chemin>" ou
      // nu si même page).
      choicesFrom: { sourceTaskId: null, sourcePath: "" },
      // Visibilité conditionnelle DEPUIS UNE AUTRE TÂCHE (jamais la même —
      // same-task/cross-page reste couvert par l'onglet "Règles" existant) :
      // afficher/masquer CE champ selon la valeur d'un champ d'une autre
      // tâche. Mécanisme séparé de `rules`/`choicesFrom`, résolu côté écran
      // mobile. `sourceTaskId: null` = désactivé pour ce champ.
      crossTaskVisibility: {
        sourceTaskId: null, sourcePath: "", op: "eq", value: "",
        action: "show", defaultWhenUnknown: "hidden"
      },
      // État d'ÉDITION transitoire de l'éditeur convivial "Champ calculé"
      // (cf. renderCalcFieldEditor) — `{op, operands}`, jamais compilé/
      // enregistré (comme `_sheet`) : sert de source de vérité PENDANT
      // L'ÉDITION plutôt que `page.calculate[i].expr`, qui ne peut PAS encoder
      // un état partiel (ex. un seul terme choisi sur 2 -> `buildCalcExpr`
      // renvoie "" tant que <2 termes sont remplis) — sans cet état à part,
      // choisir le 1ᵉʳ terme serait aussitôt reperdu au re-rendu déclenché par
      // ce même choix, avant même d'avoir pu choisir le 2ᵉ.
      _calc: null,
      children: []
    };
  }
  function newPage() { return { id: uid(), nodes: [], rules: [], calculate: [], messages: {} }; }

  // Ordre d'affichage : `options.order` d'abord (l'ordre stocké par
  // PostgreSQL/jsonb ne conserve PAS l'ordre des clés d'objet), puis les clés
  // absentes de `order`, pour n'oublier aucun champ.
  function orderedKeys(props, order) {
    var all = Object.keys(props || {});
    if (!Array.isArray(order)) return all;
    var seen = {}, out = [];
    order.forEach(function (k) { if (props && props[k] && !seen[k]) { seen[k] = 1; out.push(k); } });
    all.forEach(function (k) { if (!seen[k]) out.push(k); });
    return out;
  }

  /* -------------------------------------------------------------- decompile */
  function decompile(form) {
    if (!Array.isArray(form) || !form.length) return [newPage()];
    return form.map(function (pg) {
      var page = newPage();
      var schema = (pg && pg.page) || { properties: {} };
      var opts = (pg && pg.options) || {};
      var fields = opts.fields || {};
      var required = schema.required || [];
      page.nodes = orderedKeys(schema.properties || {}, opts.order).map(function (k) {
        return nodeFromSchema(k, schema.properties[k], fields[k] || {}, required.indexOf(k) !== -1);
      });
      page.rules = (pg.rules || []).map(ruleFromStored);
      page.calculate = (pg.calculate || []).map(function (c) { return { target: c.target || "", expr: c.expr || "" }; });
      applyStoredMessages(page.nodes, pg.messages || {});
      applyShareFields(page.nodes, "", pg.share || []);
      applyChoicesFromFields(page.nodes, "", pg.choicesFrom || []);
      applyCrossTaskVisibilityFields(page.nodes, "", pg.crossTaskVisibility || []);
      return page;
    });
  }
  // `share` (partage villages sièges) : chemins pointés (comme les cibles de
  // `rules`/`calculate`), pas des noms de feuille comme `messages`. LE MODE
  // EST PORTÉ PAR CHAMP (`n.shareMode`, "" = non partagé) — deux champs de la
  // même tâche peuvent avoir des modes différents. Chaque entrée stockée est
  // {"path", "mode"} ; tolère les entrées historiques (chaîne nue = chemin
  // seul, sans mode explicite -> SHARE_MODE_DEFAULT).
  var SHARE_MODE_DEFAULT = "fixed_canton";
  function applyShareFields(nodes, prefix, shareList) {
    var shareMap = {};
    (shareList || []).forEach(function (entry) {
      if (typeof entry === "string") shareMap[entry] = SHARE_MODE_DEFAULT;
      else if (entry && entry.path) shareMap[entry.path] = entry.mode || SHARE_MODE_DEFAULT;
    });
    (function walk(list, pre) {
      (list || []).forEach(function (n) {
        var path = (pre ? pre + "." : "") + n.key;
        if (CONTAINER_TYPES[n.type]) { walk(n.children, path); }
        else { n.shareMode = shareMap[path] || ""; }
      });
    })(nodes, prefix);
  }
  function collectShareFields(n, prefix, out) {
    var path = (prefix ? prefix + "." : "") + n.key;
    if (CONTAINER_TYPES[n.type]) { (n.children || []).forEach(function (c) { collectShareFields(c, path, out); }); }
    else if (n.shareMode) { out.push({ path: path, mode: n.shareMode }); }
  }
  // `choicesFrom` (options dynamiques depuis un autre champ) : même mirroir
  // que `share`/`shareMode` ci-dessus — chemins pointés au niveau PAGE, PAS
  // imbriqués dans le schéma JSON du champ (cf. dashboard.process_manager.
  // tasks.form_design.validate_form_design, bloc `choicesFrom`).
  function applyChoicesFromFields(nodes, prefix, list) {
    var map = {};
    (list || []).forEach(function (entry) {
      if (entry && entry.path) {
        map[entry.path] = { sourceTaskId: entry.sourceTaskId != null ? entry.sourceTaskId : null, sourcePath: entry.sourcePath || "" };
      }
    });
    (function walk(nds, pre) {
      (nds || []).forEach(function (n) {
        var path = (pre ? pre + "." : "") + n.key;
        if (CONTAINER_TYPES[n.type]) { walk(n.children, path); }
        else { n.choicesFrom = map[path] || { sourceTaskId: null, sourcePath: "" }; }
      });
    })(nodes, prefix);
  }
  function collectChoicesFromFields(n, prefix, out) {
    var path = (prefix ? prefix + "." : "") + n.key;
    if (CONTAINER_TYPES[n.type]) {
      (n.children || []).forEach(function (c) { collectChoicesFromFields(c, path, out); });
    } else if (n.choicesFrom && n.choicesFrom.sourcePath) {
      out.push({ path: path, sourceTaskId: n.choicesFrom.sourceTaskId != null ? n.choicesFrom.sourceTaskId : null, sourcePath: n.choicesFrom.sourcePath });
    }
  }
  // `crossTaskVisibility` : même mirroir que `choicesFrom` ci-dessus, mais
  // `sourceTaskId` y est TOUJOURS requis (jamais same-task — ce cas reste
  // couvert par l'onglet "Règles").
  function applyCrossTaskVisibilityFields(nodes, prefix, list) {
    var map = {};
    (list || []).forEach(function (entry) {
      if (entry && entry.path) {
        map[entry.path] = {
          sourceTaskId: entry.sourceTaskId != null ? entry.sourceTaskId : null,
          sourcePath: entry.sourcePath || "", op: entry.op || "eq", value: entry.value != null ? entry.value : "",
          action: entry.action || "show", defaultWhenUnknown: entry.defaultWhenUnknown || "hidden"
        };
      }
    });
    (function walk(nds, pre) {
      (nds || []).forEach(function (n) {
        var path = (pre ? pre + "." : "") + n.key;
        if (CONTAINER_TYPES[n.type]) { walk(n.children, path); }
        else {
          n.crossTaskVisibility = map[path] || {
            sourceTaskId: null, sourcePath: "", op: "eq", value: "", action: "show", defaultWhenUnknown: "hidden"
          };
        }
      });
    })(nodes, prefix);
  }
  function collectCrossTaskVisibilityFields(n, prefix, out) {
    var path = (prefix ? prefix + "." : "") + n.key;
    if (CONTAINER_TYPES[n.type]) {
      (n.children || []).forEach(function (c) { collectCrossTaskVisibilityFields(c, path, out); });
    } else if (n.crossTaskVisibility && n.crossTaskVisibility.sourceTaskId != null && n.crossTaskVisibility.sourcePath) {
      var cv = n.crossTaskVisibility;
      out.push({
        path: path, sourceTaskId: cv.sourceTaskId, sourcePath: cv.sourcePath,
        op: cv.op || "eq",
        value: (cv.op === "empty" || cv.op === "notEmpty") ? "" : castValue(cv.value),
        action: cv.action || "show", defaultWhenUnknown: cv.defaultWhenUnknown || "hidden"
      });
    }
  }
  // Bouton "Appliquer à tous les champs" (toolbar) : force `n.shareMode` sur
  // TOUTES les feuilles de TOUTES LES PAGES de la tâche (récursif,
  // groupes/répétables compris) — "mettre toute la tâche dans un mode qui
  // s'appliquera à tous les champs". `mode` "" = efface le partage partout
  // (choix "Aucun partage" au toolbar).
  function applyShareModeToAllFields(mode) {
    (function walk(list) {
      (list || []).forEach(function (n) {
        if (CONTAINER_TYPES[n.type]) { walk(n.children); }
        else if (n.type !== "note") { n.shareMode = mode || ""; }
      });
    })([].concat.apply([], state.pages.map(function (p) { return p.nodes; })));
  }
  function applyStoredMessages(nodes, msgs) {
    (nodes || []).forEach(function (n) {
      if (msgs[n.key]) {
        n.message = {
          required: msgs[n.key].required || "", range: msgs[n.key].range || "",
          regex: msgs[n.key].regex || "", type: msgs[n.key].type || ""
        };
      }
      if (n.children) applyStoredMessages(n.children, msgs);
    });
  }
  function nodeFromSchema(key, prop, opts, isReq) {
    var n = newNode("text");
    n.key = key; n.label = opts.label || key; n.help = opts.help || ""; n.required = !!isReq;
    prop = prop || {};
    if (prop.type === "object") {
      n.type = "group";
      n.children = childrenFromObject(prop, opts);
    } else if (prop.type === "array" && prop.items && prop.items.type === "object") {
      n.type = "repeat";
      n.minItems = prop.minItems != null ? prop.minItems : "";
      n.maxItems = prop.maxItems != null ? prop.maxItems : "";
      n.disableOrder = !!opts.disableOrder;
      // options par ligne : `opts.item.fields` (tcomb), avec repli `opts.fields`.
      n.children = childrenFromObject(prop.items, (opts.item && opts.item.fields) ? opts.item : opts);
    } else if (prop.type === "array" && prop.items && prop.items.enum) {
      n.type = opts.mode === "checklist" ? "select_multiple_check" : "select_multiple";
      n.choices = Array.isArray(prop.items.enum) ? prop.items.enum.slice() : Object.keys(prop.items.enum);
      n.listThreshold = opts.listThreshold != null ? opts.listThreshold : "";
      applyDatasetFromOpts(n, opts);
    } else if (prop.enum) {
      n.type = "select_one";
      n.choices = Array.isArray(prop.enum) ? prop.enum.slice() : Object.keys(prop.enum);
      n.listThreshold = opts.listThreshold != null ? opts.listThreshold : "";
      applyDatasetFromOpts(n, opts);
    } else if (prop.type === "geopoint" || opts.mode === "geopoint") {
      n.type = "geopoint";
      n.accuracyThreshold = opts.accuracyThreshold != null && opts.accuracyThreshold !== ""
        ? opts.accuracyThreshold : DEFAULT_GPS_ACCURACY;
    } else if (prop.type === "integer") { n.type = "integer"; copyRange(n, prop); }
    else if (prop.type === "number") { n.type = "decimal"; copyRange(n, prop); }
    else if (prop.format === "date") { n.type = "date"; n.mode = true; }
    else if (prop.format === "datetime") { n.type = "datetime"; }
    else if (prop.format === "time") { n.type = "time"; }
    else if (prop._note) { n.type = "note"; }
    else { n.type = "text"; if (prop.minLength != null) n.minLength = prop.minLength; if (prop.maxLength != null) n.maxLength = prop.maxLength; if (prop.pattern) n.pattern = prop.pattern; }
    return n;
  }
  function childrenFromObject(objSchema, opts) {
    var props = objSchema.properties || {};
    var req = objSchema.required || [];
    var subFields = opts.fields || {};
    return orderedKeys(props, opts.order).map(function (k) {
      return nodeFromSchema(k, props[k], subFields[k] || {}, req.indexOf(k) !== -1);
    });
  }
  function copyRange(n, prop) { if (prop.minimum != null) n.min = prop.minimum; if (prop.maximum != null) n.max = prop.maximum; }
  function ruleFromStored(r) {
    var out = { id: uid(), target: "", conj: "all", conds: [], action: "show" };
    var then = (r.then || [])[0] || {};
    out.action = then.action || "show"; out.target = then.target || "";
    var w = r.when || {};
    if (w.all || w.any) { out.conj = w.all ? "all" : "any"; (w.all || w.any).forEach(function (c) { out.conds.push(condFromStored(c)); }); }
    else { out.conds.push(condFromStored(w)); }
    if (!out.conds.length) out.conds.push({ field: "", op: "eq", value: "" });
    return out;
  }
  function condFromStored(c) { c = c || {}; return { field: c.field || "", op: c.op || "eq", value: c.value != null ? c.value : "" }; }

  /* ---------------------------------------------------------------- compile */
  function compile() {
    return state.pages.map(function (page) {
      var properties = {}, fields = {}, required = [], order = [];
      page.nodes.forEach(function (n) {
        var r = compileNode(n);
        properties[n.key] = r.schema; fields[n.key] = r.options; order.push(n.key);
        if (needsRequired(n)) required.push(n.key);
      });
      // `order` explicite : PostgreSQL/jsonb ne conserve pas l'ordre des clés.
      var out = { options: { fields: fields, order: order }, page: { type: "object", properties: properties, required: required } };
      var rules = page.rules.map(compileRule).filter(Boolean);
      if (rules.length) out.rules = rules;
      var calc = page.calculate.filter(function (c) { return c.target && c.expr; })
        .map(function (c) { return { target: c.target, expr: c.expr }; });
      if (calc.length) out.calculate = calc;
      var msgs = {};
      page.nodes.forEach(function (n) { collectMessages(n, msgs); });
      if (Object.keys(msgs).length) out.messages = msgs;
      var shareList = [];
      page.nodes.forEach(function (n) { collectShareFields(n, "", shareList); });
      if (shareList.length) out.share = shareList;
      var choicesFromList = [];
      page.nodes.forEach(function (n) { collectChoicesFromFields(n, "", choicesFromList); });
      if (choicesFromList.length) out.choicesFrom = choicesFromList;
      var crossTaskVisibilityList = [];
      page.nodes.forEach(function (n) { collectCrossTaskVisibilityFields(n, "", crossTaskVisibilityList); });
      if (crossTaskVisibilityList.length) out.crossTaskVisibility = crossTaskVisibilityList;
      return out;
    });
  }
  function num(v) { if (v === "" || v == null) return null; var n = Number(v); return isNaN(n) ? null : n; }

  // Vrai si `n` (feuille cochée « Obligatoire ») OU un groupe contenant au moins
  // un descendant obligatoire. Un groupe optionnel devient sinon t.maybe côté
  // mobile et « groupe entièrement vide » passe la validation même si ses
  // enfants sont requis.
  function hasRequiredDescendant(n) {
    if (!n) return false;
    if (n.required && !CONTAINER_TYPES[n.type]) return true;
    return (n.children || []).some(hasRequiredDescendant);
  }
  function needsRequired(n) {
    if (n.type === "group") return hasRequiredDescendant(n);
    return !CONTAINER_TYPES[n.type] && !!n.required; // repeat : géré par minItems
  }

  function compileNode(n) {
    var schema = {}, options = { label: n.label || n.key, help: n.help || "", i18n: { optional: "", required: "*" } };
    switch (n.type) {
      case "note": schema = { type: "string", _note: true }; options.editable = false; break;
      case "integer": schema = { type: "integer" }; applyRange(schema, n); break;
      case "decimal": schema = { type: "number" }; applyRange(schema, n); break;
      case "select_one":
      case "select_multiple":
      case "select_multiple_check": schema = compileSelectSchema(n, options); break;
      case "date": schema = { type: "string", format: "date" }; options.mode = "date"; if (!options.help) options.help = "DD/MM/YYYY"; break;
      case "datetime": schema = { type: "string", format: "datetime" }; break;
      case "time": schema = { type: "string", format: "time" }; if (!options.help) options.help = "HH:MM"; break;
      case "geopoint": {
        schema = { type: "geopoint" };
        options.mode = "geopoint";
        var acc = num(n.accuracyThreshold);
        options.accuracyThreshold = acc != null ? acc : DEFAULT_GPS_ACCURACY;
        break;
      }
      case "group": {
        var g = compileContainer(n); schema = { type: "object", properties: g.properties, required: g.required };
        options.fields = g.fields; options.order = g.order; break;
      }
      case "repeat": {
        var rr = compileContainer(n);
        schema = { type: "array", items: { type: "object", properties: rr.properties, required: rr.required } };
        if (num(n.minItems) != null) schema.minItems = num(n.minItems);
        if (num(n.maxItems) != null) schema.maxItems = num(n.maxItems);
        // tcomb-form-native : options par ligne d'une liste -> `options.item`.
        options.item = { fields: rr.fields, order: rr.order };
        options.disableOrder = !!n.disableOrder;
        options.i18n = { add: "+ " + t("add_row", "Ajouter"), remove: "✕", optional: "", required: "*", up: "↑", down: "↓" };
        break;
      }
      default: schema = { type: "string" };
        if (num(n.minLength) != null) schema.minLength = num(n.minLength);
        if (num(n.maxLength) != null) schema.maxLength = num(n.maxLength);
        if (n.pattern) schema.pattern = n.pattern;
    }
    return { schema: schema, options: options };
  }
  function applyRange(schema, n) { if (num(n.min) != null) schema.minimum = num(n.min); if (num(n.max) != null) schema.maximum = num(n.max); }

  function isDynamicSource(n) {
    return !!(n.source && n.source.kind && n.source.kind !== "list" && (n.dataset || []).length);
  }
  // select_one / select_multiple -> schéma + (si source dynamique) dataset figé
  // dans `options` + `cascadeFrom` + `_source` (métadonnée de design).
  function compileSelectSchema(n, options) {
    var isCheck = n.type === "select_multiple_check";
    var isMulti = n.type === "select_multiple" || isCheck;
    // Seuil (nb d'éléments) au-delà duquel le mobile affiche une recherche +
    // liste virtualisée (select_one / select_multiple / cases à cocher).
    if (num(n.listThreshold) != null) options.listThreshold = num(n.listThreshold);
    if (isCheck) {
      // Widget dédié « cases à cocher » (mobile : CheckListInput, injecté via
      // options.factory sur mode==='checklist'). Valeur = tableau de valeurs.
      options.mode = "checklist";
      if (n.required) options.minItemsRequired = 1; // -> schema.minItems (au moins 1 coché)
    } else if (isMulti) {
      // rendu tcomb `t.list` : libellés des boutons + pas de réordonnancement
      // (l'ordre des choix cochés n'a pas de sens). Sans ça -> boutons vides.
      options.i18n = { add: "+ " + t("add_choice_row", "Ajouter"), remove: "✕", optional: "", required: "*", up: "↑", down: "↓" };
      options.disableOrder = true;
    }
    if (isDynamicSource(n)) {
      var enumObj = {}, ds = [];
      (n.dataset || []).forEach(function (r) {
        var v = r && r.v != null ? String(r.v) : "";
        if (v === "" || Object.prototype.hasOwnProperty.call(enumObj, v)) return;
        var l = r.l != null && r.l !== "" ? String(r.l) : v;
        enumObj[v] = l;
        var row = { v: v, l: l };
        if (r.p != null && String(r.p) !== "") row.p = String(r.p);
        ds.push(row);
      });
      options.dataset = ds;
      if (n.cascadeFrom) options.cascadeFrom = n.cascadeFrom;
      options._source = compileSourceMeta(n.source);
      var base = { type: "string", enum: enumObj };
      if (isCheck) options.options = ds.map(function (r) { return { value: r.v, text: r.l }; });
      return isMulti ? _arraySchema(base, options) : base;
    }
    var vals = (n.choices || []).filter(String);
    if (isCheck) options.options = vals.map(function (v) { return { value: v, text: v }; });
    return isMulti
      ? _arraySchema({ type: "string", enum: vals }, options)
      : { type: "string", enum: vals };
  }
  function _arraySchema(itemSchema, options) {
    var s = { type: "array", items: itemSchema };
    if (options && options.minItemsRequired) { s.minItems = options.minItemsRequired; delete options.minItemsRequired; }
    return s;
  }
  function compileSourceMeta(s) {
    s = s || {};
    var m = { kind: s.kind || "list" };
    var kf = keptFilters(s.filters).map(function (f) {
      return { column: f.column, op: f.op || "eq", value: f.value };
    });
    if (s.kind === "db") {
      m.table = s.table || ""; m.value_column = s.value || ""; m.label_column = s.label || "";
      m.parent_column = s.parent || ""; m.order_by = s.orderBy || ""; m.limit = num(s.limit) || 500;
      m.filters = kf;
    } else if (s.kind === "admin_levels") {
      m.level = s.level || ""; m.filters = kf;
    } else if (s.kind === "excel") {
      m.file = s.file || "";
    }
    return m;
  }
  function decompileSourceMeta(m) {
    m = m || {};
    return {
      kind: m.kind || "list", table: m.table || "", value: m.value_column || "",
      label: m.label_column || "", parent: m.parent_column || "",
      filters: (m.filters || []).map(function (f) {
        return { column: f.column || "", op: f.op || "eq", value: f.value != null ? f.value : "" };
      }),
      orderBy: m.order_by || "", limit: m.limit != null ? m.limit : 500,
      level: m.level || "", file: m.file || ""
    };
  }
  function applyDatasetFromOpts(n, opts) {
    if (!opts || !Array.isArray(opts.dataset)) return;
    n.dataset = opts.dataset.map(function (r) {
      return { v: r.v != null ? r.v : "", l: r.l != null ? r.l : "", p: r.p != null ? r.p : "" };
    });
    n.cascadeFrom = opts.cascadeFrom || "";
    n.source = decompileSourceMeta(opts._source);
    if (!n.source.kind || n.source.kind === "list") n.source.kind = "excel";
  }
  function compileContainer(n) {
    var properties = {}, fields = {}, required = [], order = [];
    (n.children || []).forEach(function (c) {
      var r = compileNode(c);
      properties[c.key] = r.schema; fields[c.key] = r.options; order.push(c.key);
      if (needsRequired(c)) required.push(c.key);
    });
    return { properties: properties, fields: fields, required: required, order: order };
  }
  // Messages indexés par NOM DE CHAMP (feuille) : c'est ainsi que le module
  // patché `tcomb-json-schema` (transform.setMessages) les retrouve côté mobile.
  function collectMessages(n, out) {
    var m = n.message || {};
    if ((m.required || m.range || m.regex || m.type) && !CONTAINER_TYPES[n.type]) {
      var o = {};
      if (m.required) o.required = m.required;
      if (m.range) o.range = m.range;
      if (m.regex) o.regex = m.regex;
      if (m.type) o.type = m.type;
      out[n.key] = o;
    }
    (n.children || []).forEach(function (c) { collectMessages(c, out); });
  }
  function compileRule(r) {
    var conds = r.conds.filter(function (c) { return c.field; }).map(function (c) {
      var o = { field: c.field, op: c.op };
      if (c.op !== "empty" && c.op !== "notEmpty") o.value = castValue(c.value);
      return o;
    });
    if (!conds.length || !r.target) return null;
    var when = conds.length === 1 ? conds[0] : (function () { var w = {}; w[r.conj] = conds; return w; })();
    return { when: when, then: [{ action: r.action, target: r.target }] };
  }
  function castValue(v) {
    if (typeof v !== "string") return v;
    if (v.trim() === "") return v;
    if (/^-?\d+(\.\d+)?$/.test(v.trim())) return Number(v);
    if (v === "true") return true;
    if (v === "false") return false;
    return v;
  }

  /* ----------------------------------------------------- path helpers (UI) */
  function fieldPaths(nodes, prefix, acc) {
    (nodes || []).forEach(function (n) {
      var p = (prefix ? prefix + "." : "") + n.key;
      if (!CONTAINER_TYPES[n.type]) acc.push({ path: p, label: n.label || n.key, type: n.type });
      else { acc.push({ path: p, label: (n.label || n.key) + " …", type: n.type }); fieldPaths(n.children, p, acc); }
    });
    return acc;
  }
  var SELECT_TYPES = { select_one: 1, select_multiple: 1, select_multiple_check: 1 };
  function currentPagePaths() { return fieldPaths(state.pages[state.active].nodes, "", []); }
  function crossPagePaths() {
    var acc = [];
    state.pages.forEach(function (pg, i) {
      if (i === state.active) return;
      fieldPaths(pg.nodes, "", []).forEach(function (f) {
        // `type` doit être reporté ici (pas seulement path/label) — sans ça,
        // le filtre `SELECT_TYPES[p.type]` de `renderChoicesFromEditor`
        // (picker "Champ source") élimine TOUTES les entrées cross-page
        // (type undefined -> falsy), ne laissant jamais que les champs de
        // la page courante. Bug réel rapporté par l'utilisateur : "Champ
        // source" ne listait que les champs de la 1ʳᵉ page du formulaire.
        acc.push({ path: "$" + i + "." + f.path, label: "P" + (i + 1) + " · " + f.label, type: f.type });
      });
    });
    return acc;
  }
  // Mirroir de `crossPagePaths()`, SAUF qu'elle inclut aussi la page active :
  // utilisée pour le picker "Champ source (même tâche)" des conditions
  // d'attachment (`renderAttachmentConditionRow`), qui n'est pas rattaché à
  // une page en particulier (contrairement à `rules`/`choicesFrom`), donc
  // n'a aucune raison d'exclure la page courante de la liste.
  function allTaskPathsWithPageIndex() {
    var acc = [];
    state.pages.forEach(function (pg, i) {
      fieldPaths(pg.nodes, "", []).forEach(function (f) {
        acc.push({ path: "$" + i + "." + f.path, label: "P" + (i + 1) + " · " + f.label, type: f.type });
      });
    });
    return acc;
  }

  /* ----------------------------------------------------------------- render */
  var root = document.getElementById("tfb-root");

  // Autocomplete/filtre sur les <select> de l'éditeur (select2, déjà
  // vendorisé et utilisé ailleurs dans le dashboard — cf. modale
  // "Synchroniser" de ce même écran). `#tfb-root` est entièrement recréé en
  // JS vanilla à chaque `render()`/`refreshTree()` -> select2 doit être
  // ré-appliqué à CHAQUE reconstruction plutôt qu'une seule fois au
  // chargement (d'où le bloc `{% block select2 %}{% endblock %}` VIDE dans
  // form_builder.html, qui désactive exprès l'init globale
  // `$("select").select2()` du layout de base — inadaptée ici, elle ne
  // verrait jamais les <select> créés après le premier rendu).
  // BUG RÉEL trouvé en testant en direct (vrai clic utilisateur simulé via
  // CDP dans un vrai navigateur, pas juste en lisant le code) : select2
  // notifie un changement de valeur EXCLUSIVEMENT via
  // `this.$element.trigger('change')` (jQuery), JAMAIS via un vrai
  // `dispatchEvent` DOM natif. Or TOUS les handlers `onchange` de ce fichier
  // sont posés par `el()` via `addEventListener("change", fn)` (natif) —
  // jQuery `.trigger()` sur CET élément (cf. son `special.change`) ne les
  // atteint PAS de façon fiable. Résultat confirmé en direct : choisir une
  // "Tâche source" (ou n'importe quel autre select de ce fichier : type,
  // partage, source des choix, cascade…) via le vrai menu select2 changeait
  // bien la valeur affichée, mais AUCUN `onchange` ne se déclenchait ->
  // aucun re-render, état JS jamais mis à jour. Un test avec
  // `el.dispatchEvent(new Event('change', {bubbles:true}))` (natif) déclenche
  // correctement le handler, confirmant le pont ci-dessous comme le point de
  // correction minimal (un seul endroit, pas besoin de toucher chaque
  // `onchange` du fichier) : quand select2 déclenche son 'change' jQuery, on
  // redispatch un VRAI événement natif sur le même élément.
  function applySelect2(scopeEl) {
    var $ = window.jQuery;
    if (!$ || !$.fn || !$.fn.select2) return;
    $(scopeEl || root).find("select").each(function () {
      var $s = $(this);
      if ($s.data("select2")) $s.select2("destroy");
      $s.select2({ width: "100%", minimumResultsForSearch: 0 });
      $s.off("change.tfbNativeBridge").on("change.tfbNativeBridge", function () {
        // Garde anti-récursion : jQuery attache TOUJOURS un vrai listener
        // natif (`addEventListener`) pour porter son propre `.on()` — le
        // `dispatchEvent` ci-dessous serait donc autrement recapté par CE
        // MÊME handler jQuery (boucle infinie synchrone).
        if (this.__tfbBridging) return;
        this.__tfbBridging = true;
        this.dispatchEvent(new Event("change", { bubbles: true }));
        this.__tfbBridging = false;
      });
    });
  }

  function render() {
    root.innerHTML = "";
    var wrap = el("div", { class: "tfb-wrap" });
    wrap.appendChild(renderLeft());
    wrap.appendChild(renderMain());
    wrap.appendChild(renderRight());
    root.appendChild(wrap);
    applySelect2();
    renderVisibilityConditionToolbar();
  }

  // Rafraîchit UNIQUEMENT les colonnes gauche + centre (liste des pages, arbre
  // des champs) sans reconstruire la colonne de droite : le champ en cours de
  // saisie (Libellé, etc.) garde le focus et la position du curseur.
  function refreshTree() {
    var wrap = root.querySelector(".tfb-wrap");
    if (!wrap) { render(); return; }
    var left = wrap.querySelector(".tfb-col-left");
    var main = wrap.querySelector(".tfb-col-main");
    if (left) wrap.replaceChild(renderLeft(), left);
    if (main) wrap.replaceChild(renderMain(), main);
    applySelect2();
  }

  function renderLeft() {
    var card = el("div", { class: "tfb-card tfb-col-left" }, [el("h6", { text: t("pages", "Pages") })]);
    var body = el("div", { class: "tfb-body" });
    var ul = el("ul", { class: "tfb-pages" });
    state.pages.forEach(function (pg, i) {
      var li = el("li", { class: i === state.active ? "active" : "", onclick: function () { state.active = i; state.sel = null; render(); } }, [
        el("span", { text: t("page", "Page") + " " + (i + 1) + " (" + pg.nodes.length + ")" }),
        el("span", { class: "tfb-page-actions" }, [
          btn("▲", function (e) { e.stopPropagation(); movePage(i, -1); }),
          btn("▼", function (e) { e.stopPropagation(); movePage(i, 1); }),
          btn("✕", function (e) { e.stopPropagation(); removePage(i); }, "btn-danger")
        ])
      ]);
      ul.appendChild(li);
    });
    body.appendChild(ul);
    body.appendChild(btn("+ " + t("add_page", "Ajouter une page"), addPage, "btn-primary btn-block mt-2"));
    card.appendChild(body);
    return card;
  }

  function renderMain() {
    var card = el("div", { class: "tfb-card tfb-col-main" }, [el("h6", { text: t("fields", "Champs") + " — " + t("page", "Page") + " " + (state.active + 1) })]);
    var body = el("div", { class: "tfb-body" });
    body.appendChild(renderErrorBox());
    var page = state.pages[state.active];
    var tree = el("ul", { class: "tfb-tree" });
    page.nodes.forEach(function (n, i) { tree.appendChild(renderNode(n, page.nodes, i, null)); });
    body.appendChild(tree);
    body.appendChild(renderAddField(page.nodes, null));
    card.appendChild(body);
    return card;
  }

  function renderNode(n, siblings, idx, parent) {
    var li = el("li");
    var card = el("div", { class: "tfb-node" + (state.sel === n.id ? " selected" : ""), draggable: "true", title: t("drag_hint", "Glissez pour réordonner ou déposer dans un groupe"), onclick: function (e) { e.stopPropagation(); state.sel = n.id; state.tab = "field"; render(); } });
    card._tfbId = n.id;
    card._tfbType = n.type;
    card._tfbChildren = n.children;
    card.addEventListener("dragstart", function (e) {
      e.stopPropagation();
      state.drag = n.id;
      try { e.dataTransfer.setData("text/plain", n.id); e.dataTransfer.effectAllowed = "move"; } catch (x) {}
      card.classList.add("tfb-dragging");
      document.body.classList.add("tfb-drag-active");
    });
    card.addEventListener("dragend", function (e) {
      e.stopPropagation();
      state.drag = null;
      card.classList.remove("tfb-dragging");
      document.body.classList.remove("tfb-drag-active");
      clearDropMarks();
    });
    makeDropTarget(card, "card");
    var head = el("div", { class: "tfb-node-head" }, [
      el("span", { class: "tfb-badge", text: n.type }),
      n.required && !CONTAINER_TYPES[n.type] ? el("span", { class: "tfb-badge req", text: "*" }) : null,
      el("span", { class: "tfb-label", text: n.label || "(" + t("no_label", "sans libellé") + ")" }),
      el("span", { class: "tfb-key", text: n.key ? "{" + n.key + "}" : "" }),
      el("span", { class: "tfb-node-actions" }, [
        btn("▲", function (e) { e.stopPropagation(); moveNode(siblings, idx, -1); }),
        btn("▼", function (e) { e.stopPropagation(); moveNode(siblings, idx, 1); }),
        hasContainerSibling(siblings, idx) ? btn("⇥", function (e) { e.stopPropagation(); indentNode(siblings, idx); }, "", t("act_indent", "Placer dans un groupe voisin")) : null,
        parent ? btn("⇤", function (e) { e.stopPropagation(); outdentNode(n.id); }, "", t("act_outdent", "Sortir du groupe")) : null,
        btn("⧉", function (e) { e.stopPropagation(); duplicateNode(siblings, idx); }, "", t("act_duplicate", "Dupliquer")),
        btn("✕", function (e) { e.stopPropagation(); siblings.splice(idx, 1); if (state.sel === n.id) state.sel = null; render(); }, "btn-danger")
      ])
    ]);
    card.appendChild(head);
    if (CONTAINER_TYPES[n.type]) {
      var ul = el("ul", { class: "tfb-children" });
      n.children.forEach(function (c, i) { ul.appendChild(renderNode(c, n.children, i, n)); });
      card.appendChild(ul);
      card.appendChild(renderAddField(n.children, n));
    }
    li.appendChild(card);
    return li;
  }

  function renderAddField(list, parent) {
    var sel = el("select", { class: "form-control form-control-sm", style: "max-width:220px;display:inline-block" });
    FIELD_TYPES.forEach(function (ft) {
      if (parent && parent.type === "repeat" && ft[0] === "repeat") return; // pas de repeat dans repeat
      sel.appendChild(opt(ft[0], ft[1]));
    });
    var box = el("div", { class: "mt-2 tfb-dropzone" }, [
      sel, " ",
      btn("+ " + t("add_field", "Ajouter le champ"), function () {
        var n = newNode(sel.value);
        n.key = uniqueKey(slugKey(t("field", "champ")), list, n.id);
        list.push(n); state.sel = n.id; state.tab = "field"; render();
      }, "btn-primary btn-sm"),
      el("span", { class: "tfb-dropzone-hint", text: " " + (parent ? t("drop_into_group", "… ou déposer un champ ici pour l'ajouter au groupe") : t("drop_into_page", "… ou déposer un champ ici")) })
    ]);
    makeDropTarget(box, "zone", list);
    return box;
  }

  /* -------------------------------------------------------------- right col */
  function renderRight() {
    var card = el("div", { class: "tfb-card tfb-col-right" });
    var tabs = el("div", { class: "tfb-tabs" });
    [["field", t("tab_field", "Champ")], ["rules", t("tab_rules", "Règles")],
     ["calc", t("tab_calc", "Calculs")], ["attachments", t("tab_attachments", "Pièces jointes")],
     ["preview", t("tab_preview", "Aperçu")], ["json", "JSON"]].forEach(function (tb) {
      tabs.appendChild(el("button", { class: state.tab === tb[0] ? "active" : "", text: tb[1], onclick: function () { state.tab = tb[0]; render(); } }));
    });
    card.appendChild(tabs);
    var pane = el("div", { class: "tfb-tabpane active" });
    if (state.tab === "field") pane.appendChild(renderFieldEditor());
    else if (state.tab === "rules") pane.appendChild(renderRulesEditor());
    else if (state.tab === "calc") pane.appendChild(renderCalcEditor());
    else if (state.tab === "attachments") pane.appendChild(renderAttachmentsEditor());
    else if (state.tab === "preview") pane.appendChild(renderPreview());
    else pane.appendChild(renderJsonEditor());
    card.appendChild(pane);
    return card;
  }

  function findNode(id, nodes) {
    nodes = nodes || state.pages[state.active].nodes;
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].id === id) return { node: nodes[i], siblings: nodes };
      if (nodes[i].children && nodes[i].children.length) {
        var r = findNode(id, nodes[i].children);
        if (r) return r;
      }
    }
    return null;
  }
  // Chemin pointé compilé (même convention que `collectChoicesFromFields`/
  // `collectCrossTaskVisibilityFields`) d'un nœud identifié par `id`, utilisé
  // par le "Champ calculé" (cf. renderCalcFieldEditor) pour retrouver/poser
  // son entrée dans `page.calculate` — les AUTRES sections champ n'en ont
  // jamais eu besoin car elles stockent leur état sur le nœud lui-même
  // (`n.choicesFrom`, `n.crossTaskVisibility`), pas dans un tableau au niveau
  // page indexé par chemin comme `calculate`/`rules`.
  function nodePath(id) {
    function walk(nodes, prefix) {
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        var path = (prefix ? prefix + "." : "") + n.key;
        if (n.id === id) return path;
        if (CONTAINER_TYPES[n.type] && n.children && n.children.length) {
          var found = walk(n.children, path);
          if (found != null) return found;
        }
      }
      return null;
    }
    return walk(state.pages[state.active].nodes, "");
  }

  /* -------------------------------------- déplacement / copie / glisser-déposer */
  // Localise un nœud sur la page courante avec son contexte (liste fratrie,
  // index, parent conteneur, liste du parent).
  function locateNode(id, nodes, parent, parentSiblings) {
    nodes = nodes || state.pages[state.active].nodes;
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].id === id) {
        return { node: nodes[i], siblings: nodes, idx: i, parent: parent || null, parentSiblings: parentSiblings || null };
      }
      var ch = nodes[i].children;
      if (ch && ch.length) {
        var r = locateNode(id, ch, nodes[i], nodes);
        if (r) return r;
      }
    }
    return null;
  }
  function listWithin(list, node) {
    if (!node || !node.children) return false;
    if (list === node.children) return true;
    return node.children.some(function (c) { return listWithin(list, c); });
  }
  function subtreeContains(root, target) {
    return (root.children || []).some(function (c) { return c === target || subtreeContains(c, target); });
  }
  function ownerOfList(list, nodes) {
    nodes = nodes || state.pages[state.active].nodes;
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].children === list) return nodes[i];
      if (nodes[i].children) { var r = ownerOfList(list, nodes[i].children); if (r) return r; }
    }
    return null;
  }
  function subtreeHasRepeat(n) {
    return n.type === "repeat" || (n.children || []).some(subtreeHasRepeat);
  }
  function reId(n) { n.id = uid(); (n.children || []).forEach(reId); }

  // Duplique `siblings[idx]` (avec tout son sous-arbre) juste après lui ; le
  // champ copié est sélectionné pour édition immédiate de ses détails.
  function duplicateNode(siblings, idx) {
    var copy;
    try { copy = JSON.parse(JSON.stringify(siblings[idx])); } catch (e) { return; }
    copy._sheet = null; // aperçu Excel transitoire : non copié
    reId(copy);
    var base = (siblings[idx].key || slugKey(siblings[idx].label) || "champ") + "Copie";
    copy.key = uniqueKey(base, siblings, copy.id);
    siblings.splice(idx + 1, 0, copy);
    state.sel = copy.id; state.tab = "field";
    render();
  }

  // Déplace le nœud `dragId` dans `destList` à la position `destIndex`
  // (défaut : fin). Couvre hors-groupe -> groupe, groupe -> hors-groupe,
  // groupe -> autre groupe et le simple réordonnancement.
  function moveNodeTo(dragId, destList, destIndex) {
    var loc = locateNode(dragId);
    if (!loc || !destList) return;
    var node = loc.node;
    if (destList === loc.siblings && (destIndex === loc.idx || destIndex === loc.idx + 1)) return;
    if (listWithin(destList, node)) return;                       // pas dans son propre sous-arbre
    var destOwner = ownerOfList(destList);
    if (destOwner && destOwner.type === "repeat" && subtreeHasRepeat(node)) {
      alert(t("no_repeat_in_repeat", "Un groupe répétable ne peut pas en contenir un autre."));
      return;
    }
    var srcIdx = loc.siblings.indexOf(node);
    loc.siblings.splice(srcIdx, 1);
    if (loc.siblings === destList && srcIdx < destIndex) destIndex--;
    if (destIndex == null || destIndex < 0 || destIndex > destList.length) destIndex = destList.length;
    node.key = uniqueKey(node.key || slugKey(node.label) || "champ", destList, node.id);
    destList.splice(destIndex, 0, node);
    state.sel = node.id; state.tab = "field";
    render();
  }

  // Destinations valides pour « Déplacer vers » : racine de la page + tout
  // groupe/répétable, en excluant le champ lui-même, ses descendants et
  // (pour un répétable cible) un champ contenant déjà un répétable.
  function moveDestinations(id) {
    var loc = locateNode(id);
    var self = loc && loc.node;
    var out = [{ list: state.pages[state.active].nodes, label: t("move_root", "— Racine de la page —") }];
    (function walk(nodes, prefix) {
      (nodes || []).forEach(function (n) {
        if (!CONTAINER_TYPES[n.type]) return;
        var forbidden = self && (n === self || subtreeContains(self, n));
        if (forbidden) return;
        if (!(n.type === "repeat" && self && subtreeHasRepeat(self)) &&
            !(loc && loc.siblings === n.children)) {
          out.push({ list: n.children, label: prefix + (n.label || n.key || n.type) });
        }
        walk(n.children, prefix + (n.label || n.key || n.type) + " › ");
      });
    })(state.pages[state.active].nodes, "");
    return out;
  }

  function outdentNode(id) {
    var loc = locateNode(id);
    if (!loc || !loc.parent || !loc.parentSiblings) return;
    moveNodeTo(id, loc.parentSiblings, loc.parentSiblings.indexOf(loc.parent) + 1);
  }
  function indentNode(siblings, idx) {
    var target = null, j;
    for (j = idx - 1; j >= 0; j--) if (CONTAINER_TYPES[siblings[j].type]) { target = siblings[j]; break; }
    if (!target) for (j = idx + 1; j < siblings.length; j++) if (CONTAINER_TYPES[siblings[j].type]) { target = siblings[j]; break; }
    if (!target) { alert(t("no_group_sibling", "Aucun groupe voisin où placer ce champ.")); return; }
    moveNodeTo(siblings[idx].id, target.children, target.children.length);
  }
  function hasContainerSibling(siblings, idx) {
    return siblings.some(function (s, i) { return i !== idx && CONTAINER_TYPES[s.type]; });
  }

  function clearDropMarks() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".tfb-drop-before,.tfb-drop-after,.tfb-drop-into"),
      function (x) { x.classList.remove("tfb-drop-before", "tfb-drop-after", "tfb-drop-into"); }
    );
  }
  // Rend un conteneur (carte de champ ou zone « + Ajouter ») cible de dépôt.
  function makeDropTarget(node, kind, list) {
    node.addEventListener("dragover", function (e) {
      if (!state.drag || state.drag === (kind === "card" ? node._tfbId : null)) return;
      e.preventDefault(); e.stopPropagation();
      try { e.dataTransfer.dropEffect = "move"; } catch (x) {}
      clearDropMarks();
      if (kind === "zone") { node.classList.add("tfb-drop-into"); return; }
      var r = node.getBoundingClientRect();
      var canInto = CONTAINER_TYPES[node._tfbType] && e.clientY > r.top + 14 && e.clientY < r.bottom - 14;
      if (canInto) node.classList.add("tfb-drop-into");
      else node.classList.add(e.clientY < r.top + r.height / 2 ? "tfb-drop-before" : "tfb-drop-after");
    });
    node.addEventListener("dragleave", function (e) {
      if (kind === "zone") node.classList.remove("tfb-drop-into");
      e.stopPropagation();
    });
    node.addEventListener("drop", function (e) {
      if (!state.drag) return;
      e.preventDefault(); e.stopPropagation();
      var dragId = state.drag;
      if (kind === "zone") {
        clearDropMarks(); state.drag = null;
        moveNodeTo(dragId, list, list.length);
        return;
      }
      if (dragId === node._tfbId) { clearDropMarks(); state.drag = null; return; }
      var into = node.classList.contains("tfb-drop-into");
      var before = node.classList.contains("tfb-drop-before");
      clearDropMarks(); state.drag = null;
      if (into && CONTAINER_TYPES[node._tfbType]) {
        moveNodeTo(dragId, node._tfbChildren, node._tfbChildren.length);
        return;
      }
      var loc = locateNode(node._tfbId);
      if (loc) moveNodeTo(dragId, loc.siblings, loc.idx + (before ? 0 : 1));
    });
  }

  function fieldRow(label, control) {
    return el("div", { class: "tfb-field-row" }, [el("label", { text: label }), control]);
  }
  function textInput(val, on) { return el("input", { class: "form-control form-control-sm", value: val == null ? "" : val, oninput: function () { on(this.value); } }); }
  function checkbox(val, on, label) {
    var c = el("input", { type: "checkbox", onchange: function () { on(this.checked); } });
    if (val) c.checked = true;
    return el("label", { class: "tfb-muted", style: "font-weight:600" }, [c, " " + label]);
  }

  function renderFieldEditor() {
    if (!state.sel) return el("div", { class: "tfb-muted", text: t("select_field", "Sélectionnez un champ à gauche.") });
    var f = findNode(state.sel);
    if (!f) { state.sel = null; return el("div", { text: "" }); }
    var n = f.node, box = el("div");
    var nPath = nodePath(n.id);
    var isCalcTarget = (n.type === "integer" || n.type === "decimal")
      && !!findCalcEntry(state.pages[state.active], nPath);

    box.appendChild(fieldRow(t("f_type", "Type"), (function () {
      var s = el("select", { class: "form-control form-control-sm", onchange: function () {
        n.type = this.value;
        if (n.type === "date") n.mode = true;
        if (n.type === "geopoint" && (n.accuracyThreshold === "" || n.accuracyThreshold == null)) n.accuracyThreshold = DEFAULT_GPS_ACCURACY;
        render();
      } });
      FIELD_TYPES.forEach(function (ft) { s.appendChild(opt(ft[0], ft[1], n.type)); });
      return s;
    })()));
    var keyInput = textInput(n.key, function (v) {
      n.key = uniqueKey(v.replace(/[^A-Za-z0-9_]/g, "") || "champ", f.siblings, n.id);
      refreshTree();
    });
    box.appendChild(fieldRow(t("f_key", "Clé (technique)"), keyInput));
    box.appendChild(fieldRow(t("f_label", "Libellé"), textInput(n.label, function (v) {
      n.label = v;
      if (!n.key) { n.key = uniqueKey(slugKey(v), f.siblings, n.id); keyInput.value = n.key; }
      refreshTree();
    })));
    box.appendChild(fieldRow(t("f_help", "Aide / indication"), textInput(n.help, function (v) { n.help = v; })));

    // Placement : déplacer vers un groupe / la racine + dupliquer.
    (function () {
      var row = el("div", { class: "tfb-inline" });
      var dests = moveDestinations(n.id);
      var s = el("select", { class: "form-control form-control-sm", onchange: function () {
        var d = dests[parseInt(this.value, 10)];
        if (d) moveNodeTo(n.id, d.list, d.list.length);
      } });
      s.appendChild(opt("", t("f_move_to_ph", "Déplacer vers…"), ""));
      dests.forEach(function (d, i) { s.appendChild(opt(String(i), d.label)); });
      row.appendChild(fieldRow(t("f_move_to", "Déplacer vers"), s));
      row.appendChild(fieldRow(" ", btn("⧉ " + t("act_duplicate", "Dupliquer"), function () {
        var loc = locateNode(n.id);
        if (loc) duplicateNode(loc.siblings, loc.idx);
      }, "btn-secondary btn-sm")));
      box.appendChild(row);
    })();

    if (!CONTAINER_TYPES[n.type] && n.type !== "note") {
      if (isCalcTarget) {
        // Un champ calculé automatiquement ne peut pas être "Obligatoire" —
        // sa complétude dépend de ses termes sources, pas d'une saisie
        // directe (cf. renderCalcFieldEditor, qui force déjà n.required=false
        // à l'activation) : case remplacée par une note explicative plutôt que
        // laissée cochable, pour ne pas rester silencieusement inefficace.
        box.appendChild(el("div", { class: "tfb-muted", text: t(
          "f_required_disabled_calc", "Champ calculé : ne peut pas être marqué « Obligatoire » (voir plus bas)."
        ) }));
      } else {
        box.appendChild(el("div", { class: "tfb-field-row" }, [checkbox(n.required, function (v) { n.required = v; refreshTree(); }, t("f_required", "Obligatoire"))]));
      }
      // Mode de partage PROPRE À CE CHAMP (villages sièges) : "" = non
      // partagé. Indépendant des autres champs de la même tâche — le bouton
      // "Appliquer à tous les champs" du toolbar (cf. applyShareModeToAllFields)
      // offre un raccourci pour tout mettre au même mode en une fois.
      box.appendChild(fieldRow(t("f_share", "Partage villages sièges"), (function () {
        var s = el("select", { class: "form-control form-control-sm", onchange: function () { n.shareMode = this.value; } });
        s.appendChild(opt("", t("f_share_none", "Non partagé")));
        s.appendChild(opt("fixed_canton", t("share_fixed_canton", "Automatique — villages sièges du canton")));
        s.appendChild(opt("facilitator_then_validator", t("share_facilitator_then_validator", "Facilitateur puis validateur")));
        s.appendChild(opt("validator_only", t("share_validator_only", "Validateur uniquement")));
        s.value = n.shareMode || "";
        return s;
      })()));
      // Visibilité conditionnelle DEPUIS UNE AUTRE TÂCHE — tout type de champ
      // (contrairement à `renderChoicesFromEditor`, réservé aux select),
      // puisqu'on peut cacher/afficher un texte/nombre/date selon la réponse
      // d'un select (ou l'inverse) d'une autre tâche.
      box.appendChild(renderCrossTaskVisibilityEditor(n));
    }
    if (n.type === "date") {
      box.appendChild(el("div", { class: "tfb-field-row" }, [checkbox(n.mode, function (v) { n.mode = v; }, t("f_datepicker", "Sélecteur de date (mode date)"))]));
    }

    if (n.type === "select_one" || n.type === "select_multiple" || n.type === "select_multiple_check") {
      box.appendChild(renderChoiceSource(n, f.siblings));
      box.appendChild(fieldRow(
        t("f_list_threshold", "Seuil liste défilante (nb d'éléments)"),
        textInput(n.listThreshold, function (v) { n.listThreshold = v; })
      ));
      box.appendChild(el("div", { class: "tfb-muted", text: t(
        "f_list_threshold_hint",
        "Une barre de recherche est toujours affichée sur ce champ. Ce nombre fixe le seuil au-delà duquel les cases à cocher passent en liste défilante virtualisée (défaut 25). Mettre 0 désactive la recherche des listes déroulantes."
      ) }));
      box.appendChild(renderChoicesFromEditor(n));
    }

    if (n.type === "geopoint") {
      box.appendChild(fieldRow(
        t("f_gps_accuracy", "Précision requise (mètres)"),
        textInput(n.accuracyThreshold, function (v) { n.accuracyThreshold = v; })
      ));
      box.appendChild(el("div", { class: "tfb-muted", text: t(
        "f_gps_hint",
        "Le mobile retente la capture jusqu'à atteindre cette précision (≈ getBestLocation), puis retourne le meilleur point après 30 s."
      ) }));
    }

    if (n.type === "integer" || n.type === "decimal") {
      box.appendChild(el("div", { class: "tfb-inline" }, [
        fieldRow(t("f_min", "Minimum"), textInput(n.min, function (v) { n.min = v; })),
        fieldRow(t("f_max", "Maximum"), textInput(n.max, function (v) { n.max = v; }))
      ]));
      // Champ calculé : somme/différence/produit/quotient/pourcentage de 2+
      // autres champs numériques de CETTE page, affiché désactivé sur mobile
      // (cf. cdd-form-logic.js `markCalculatedTargetsDisabled`). Façade
      // conviviale au-dessus du mécanisme `calculate` déjà existant (onglet
      // "Calculs") — cf. commentaire d'en-tête de renderCalcFieldEditor.
      box.appendChild(renderCalcFieldEditor(n, nPath));
    }
    if (n.type === "text") {
      box.appendChild(el("div", { class: "tfb-inline" }, [
        fieldRow(t("f_minlen", "Long. min"), textInput(n.minLength, function (v) { n.minLength = v; })),
        fieldRow(t("f_maxlen", "Long. max"), textInput(n.maxLength, function (v) { n.maxLength = v; }))
      ]));
      box.appendChild(fieldRow(t("f_pattern", "Expression régulière (regex)"), textInput(n.pattern, function (v) { n.pattern = v; })));
    }
    if (n.type === "repeat") {
      box.appendChild(el("div", { class: "tfb-inline" }, [
        fieldRow(t("f_minitems", "Nb min de lignes"), textInput(n.minItems, function (v) { n.minItems = v; })),
        fieldRow(t("f_maxitems", "Nb max de lignes"), textInput(n.maxItems, function (v) { n.maxItems = v; }))
      ]));
      box.appendChild(el("div", { class: "tfb-field-row" }, [checkbox(n.disableOrder, function (v) { n.disableOrder = v; }, t("f_disableorder", "Interdire le réordonnancement des lignes"))]));
    }

    if (!CONTAINER_TYPES[n.type] && n.type !== "note") {
      box.appendChild(el("h6", { class: "tfb-muted mt-3", text: t("f_messages", "Messages de validation (optionnels)") }));
      box.appendChild(fieldRow(t("m_required", "Message « obligatoire »"), textInput(n.message.required, function (v) { n.message.required = v; })));
      box.appendChild(fieldRow(t("m_range", "Message « hors bornes »"), textInput(n.message.range, function (v) { n.message.range = v; })));
      box.appendChild(fieldRow(t("m_regex", "Message « format invalide »"), textInput(n.message.regex, function (v) { n.message.regex = v; })));
    }
    return box;
  }


  /* ----------------------------------------------- source des choix (dynamique) */
  function ensureDsMeta() {
    if (state.dsMeta) return;
    state.dsMeta = { tables: [], admin_levels: ["Region", "Prefecture", "Commune", "Canton", "Village"], ops: [] };
    fetch(CFG.urls.datasources, { headers: { "X-CSRFToken": CFG.csrfToken } })
      .then(function (r) { return r.json(); })
      .then(function (j) { state.dsMeta = j && j.tables ? j : state.dsMeta; render(); })
      .catch(function () { render(); });
  }
  function tableColumns(tableName) {
    var meta = state.dsMeta || {};
    var row = (meta.tables || []).filter(function (x) { return x.table === tableName; })[0];
    return (row && row.columns) || [];
  }
  function colSelect(cols, val, on, withEmpty) {
    var pairs = (withEmpty ? [["", "—"]] : []).concat((cols || []).map(function (c) { return [c, c]; }));
    return selectFrom(pairs, val, on);
  }
  function renderDsFilters(n, cols) {
    var s = n.source;
    var box = el("div", { class: "tfb-field-row" }, [el("label", { text: t("f_ds_filters", "Contraintes (filtres)") })]);
    (s.filters || []).forEach(function (fl, i) {
      box.appendChild(el("div", { class: "tfb-cond-row" }, [
        colSelect(cols, fl.column, function (v) { fl.column = v; }, true),
        selectFrom(DS_OPS, fl.op, function (v) { fl.op = v; render(); }),
        DS_NULL_OPS[fl.op] ? el("span") : textInput(fl.value, function (v) { fl.value = v; }),
        btn("✕", function () { s.filters.splice(i, 1); render(); }, "btn-danger btn-sm")
      ]));
    });
    box.appendChild(btn("+ " + t("add_filter", "Ajouter un filtre"), function () {
      (s.filters = s.filters || []).push({ column: "", op: "eq", value: "" }); render();
    }, "btn-secondary btn-sm"));
    return box;
  }
  function datasetStatus(n) {
    var c = (n.dataset || []).length;
    var txt = c
      ? c + " " + t("rows_loaded", "lignes chargées") + (n.cascadeFrom ? " · " + t("cascade_active", "cascade activée") : "")
      : t("no_rows_loaded", "Aucune donnée chargée.");
    return el("div", { class: c ? "tfb-ok" : "tfb-muted", style: "padding:6px 8px", text: txt });
  }
  function cascadeParentRow(n, siblings) {
    var opts = (siblings || []).filter(function (s) {
      return s.id !== n.id && (s.type === "select_one" || s.type === "select_multiple" || s.type === "select_multiple_check");
    }).map(function (s) { return [s.key, (s.label || s.key) + " {" + s.key + "}"]; });
    return fieldRow(
      t("f_cascade_from", "Champ parent (cascade)"),
      selectFrom([["", t("cascade_none", "— aucun (niveau racine) —")]].concat(opts), n.cascadeFrom, function (v) { n.cascadeFrom = v; refreshTree(); })
    );
  }
  function loadDataset(n, spec, okMsg) {
    fetch(CFG.urls.datasource_preview, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": CFG.csrfToken },
      body: JSON.stringify(spec)
    })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j.ok) { flash((j.errors || [t("load_failed", "Échec du chargement.")])[0], false); return; }
        n.dataset = (j.rows || []).map(function (r) { return { v: r.v, l: r.l, p: r.p != null ? r.p : "" }; });
        render();
        flash((okMsg || t("rows_loaded", "lignes chargées")) + " : " + n.dataset.length +
          (j.truncated ? " (" + t("truncated_warn", "tronqué — ajoutez des filtres") + ")" : ""), !j.truncated);
      })
      .catch(function () { flash(t("network_err", "Erreur réseau."), false); });
  }
  function dbSpec(n) {
    var s = n.source;
    return {
      kind: "db", table: s.table, value_column: s.value, label_column: s.label || s.value,
      parent_column: s.parent || "", order_by: s.orderBy || "", limit: num(s.limit) || 500,
      filters: keptFilters(s.filters)
    };
  }

  function renderDbSource(n) {
    ensureDsMeta();
    var s = n.source, box = el("div");
    var tables = ((state.dsMeta || {}).tables || []).map(function (x) { return [x.table, x.table]; });
    box.appendChild(fieldRow(t("f_ds_table", "Table"), selectFrom([["", "—"]].concat(tables), s.table, function (v) {
      s.table = v; s.value = ""; s.label = ""; s.parent = ""; s.orderBy = ""; render();
    })));
    if (s.table) {
      var cols = tableColumns(s.table);
      box.appendChild(fieldRow(t("f_ds_value", "Colonne valeur"), colSelect(cols, s.value, function (v) { s.value = v; render(); }, true)));
      box.appendChild(fieldRow(t("f_ds_label", "Colonne libellé"), colSelect(cols, s.label, function (v) { s.label = v; }, true)));
      box.appendChild(fieldRow(t("f_ds_parent", "Colonne parent (cascade)"), colSelect(cols, s.parent, function (v) { s.parent = v; render(); }, true)));
      if (s.parent && s.value && s.parent === s.value) {
        box.appendChild(el("div", { class: "tfb-errors", style: "padding:6px 8px", text: t(
          "ds_parent_eq_value",
          "La colonne parent doit être différente de la colonne valeur (typiquement « parent_id »), sinon la cascade ne filtre rien."
        ) }));
      }
      box.appendChild(renderDsFilters(n, cols));
      box.appendChild(el("div", { class: "tfb-inline" }, [
        fieldRow(t("f_ds_order", "Trier par"), colSelect(cols, s.orderBy, function (v) { s.orderBy = v; }, true)),
        fieldRow(t("f_ds_limit", "Limite"), textInput(s.limit, function (v) { s.limit = v; }))
      ]));
      box.appendChild(btn("⟳ " + t("ds_load", "Charger / rafraîchir depuis la base"), function () {
        if (!s.value) { flash(t("ds_need_value", "Choisissez la colonne valeur."), false); return; }
        loadDataset(n, dbSpec(n), t("rows_loaded", "lignes chargées"));
      }, "btn-primary btn-sm"));
    }
    return box;
  }

  function renderAdminSource(n) {
    ensureDsMeta();
    var s = n.source, box = el("div");
    var levels = ((state.dsMeta || {}).admin_levels || ["Region", "Prefecture", "Commune", "Canton", "Village"])
      .map(function (l) { return [l, ADMIN_LEVEL_LABELS[l] || l]; });
    box.appendChild(fieldRow(t("f_admin_level", "Niveau"), selectFrom([["", "—"]].concat(levels), s.level, function (v) { s.level = v; render(); })));
    if (s.level) {
      box.appendChild(renderDsFilters(n, ["name", "type", "parent_id", "rural", "frontalier"]));
      box.appendChild(btn("⟳ " + t("ds_load", "Charger / rafraîchir depuis la base"), function () {
        loadDataset(n, { kind: "admin_levels", level: s.level, filters: keptFilters(s.filters) }, t("rows_loaded", "lignes chargées"));
      }, "btn-primary btn-sm"));
    }
    box.appendChild(el("div", { class: "mt-2" }, [
      btn("⛓ " + t("admin_cascade_scaffold", "Générer la cascade Région → Village"), function () {
        var loc = locateNode(n.id);
        if (loc) scaffoldAdminCascade(loc.siblings, loc.idx);
      }, "btn-outline-secondary btn-sm", t("admin_cascade_hint", "Remplace ce champ par 5 champs chaînés (Région, Préfecture, Commune, Canton, Village)."))
    ]));
    return box;
  }

  function renderExcelSource(n) {
    var s = n.source, box = el("div");
    var fileInput = el("input", {
      type: "file", accept: ".xlsx,.xls", style: "display:none",
      onchange: function () {
        var file = this.files[0]; this.value = "";
        if (!file) return;
        s.file = file.name;
        var fd = new FormData(); fd.append("file", file);
        fetch(CFG.urls.dataset_sheet, { method: "POST", headers: { "X-CSRFToken": CFG.csrfToken }, body: fd })
          .then(function (r) { return r.json(); })
          .then(function (j) {
            if (!j.ok) { flash((j.errors || [t("load_failed", "Échec du chargement.")])[0], false); return; }
            n._sheet = { columns: j.columns || [], rows: j.rows || [] };
            render();
          })
          .catch(function () { flash(t("network_err", "Erreur réseau."), false); });
      }
    });
    box.appendChild(el("div", {}, [
      btn("⭳ " + t("excel_pick", "Choisir un fichier Excel"), function () { fileInput.click(); }, "btn-outline-secondary btn-sm"),
      fileInput,
      s.file ? el("span", { class: "tfb-muted", text: "  " + s.file }) : null
    ]));
    if (n._sheet && n._sheet.columns.length) {
      var cols = n._sheet.columns;
      box.appendChild(fieldRow(t("f_ds_value", "Colonne valeur"), colSelect(cols, s.value, function (v) { s.value = v; }, true)));
      box.appendChild(fieldRow(t("f_ds_label", "Colonne libellé"), colSelect(cols, s.label, function (v) { s.label = v; }, true)));
      box.appendChild(fieldRow(t("f_ds_parent", "Colonne parent (cascade)"), colSelect(cols, s.parent, function (v) { s.parent = v; }, true)));
      box.appendChild(btn(t("excel_apply", "Appliquer le mappage"), function () {
        if (!s.value) { flash(t("ds_need_value", "Choisissez la colonne valeur."), false); return; }
        var seen = {};
        n.dataset = [];
        n._sheet.rows.forEach(function (row) {
          var v = (row[s.value] != null ? String(row[s.value]) : "").trim();
          if (!v || seen[v]) return;
          seen[v] = 1;
          n.dataset.push({
            v: v,
            l: (s.label && row[s.label] != null && String(row[s.label]).trim()) || v,
            p: s.parent && row[s.parent] != null ? String(row[s.parent]).trim() : ""
          });
        });
        render();
        flash(t("rows_loaded", "lignes chargées") + " : " + n.dataset.length, true);
      }, "btn-primary btn-sm"));
    }
    return box;
  }

  function scaffoldAdminCascade(siblings, idx) {
    var levels = (state.dsMeta && state.dsMeta.admin_levels) || ["Region", "Prefecture", "Commune", "Canton", "Village"];
    var made = [], prevKey = "";
    (function loadNext(i) {
      if (i >= levels.length) {
        siblings.splice.apply(siblings, [idx, 1].concat(made));
        state.sel = made[0].id; render();
        flash(t("cascade_generated", "Cascade générée : ") + made.length, true);
        return;
      }
      var lvl = levels[i];
      fetch(CFG.urls.datasource_preview, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": CFG.csrfToken },
        body: JSON.stringify({ kind: "admin_levels", level: lvl })
      })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j.ok) { flash((j.errors || [t("load_failed", "Échec du chargement.")])[0], false); return; }
          var nn = newNode("select_one");
          nn.label = ADMIN_LEVEL_LABELS[lvl] || lvl;
          nn.key = uniqueKey(slugKey(nn.label), siblings.concat(made), nn.id);
          nn.source = decompileSourceMeta({ kind: "admin_levels", level: lvl });
          nn.dataset = (j.rows || []).map(function (r) { return { v: r.v, l: r.l, p: r.p != null ? r.p : "" }; });
          nn.cascadeFrom = prevKey;
          made.push(nn); prevKey = nn.key;
          loadNext(i + 1);
        })
        .catch(function () { flash(t("network_err", "Erreur réseau."), false); });
    })(0);
  }

  function renderChoiceSource(n, siblings) {
    var wrap = el("div");
    wrap.appendChild(fieldRow(t("f_source", "Source des choix"), selectFrom(SOURCE_KINDS, (n.source || (n.source = newSource())).kind, function (v) {
      n.source.kind = v;
      if (v !== "list") ensureDsMeta();
      render();
    })));
    if (n.source.kind === "list") { wrap.appendChild(renderChoices(n)); return wrap; }

    if (n.source.kind === "db") wrap.appendChild(renderDbSource(n));
    else if (n.source.kind === "admin_levels") wrap.appendChild(renderAdminSource(n));
    else if (n.source.kind === "excel") wrap.appendChild(renderExcelSource(n));

    wrap.appendChild(cascadeParentRow(n, siblings));
    wrap.appendChild(datasetStatus(n));
    if ((n.dataset || []).length) {
      var prev = (n.dataset || []).slice(0, 6).map(function (r) {
        return r.l + " {" + r.v + "}" + (r.p ? " ← " + r.p : "");
      }).join("  ·  ");
      wrap.appendChild(el("div", { class: "tfb-muted", style: "margin-top:4px", text: prev + ((n.dataset || []).length > 6 ? " …" : "") }));
    }
    return wrap;
  }

  /* ------------------------ choix dynamiques depuis un AUTRE champ select */
  // Distinct de `renderChoiceSource` ci-dessus (sources figées à l'enregis-
  // trement, cf. dataset/cascadeFrom) : ici les options du champ sont
  // recalculées côté mobile à partir de la réponse LIVE d'un autre select —
  // même page/autre page de la même tâche (même convention `$<index>.` que
  // `rules`), ou champ d'une tâche complètement différente du projet.
  function ensureOtherTasks() {
    if (state.otherTasks) return;
    state.otherTasks = [];
    fetch(CFG.urls.other_tasks, { headers: { "X-CSRFToken": CFG.csrfToken } })
      .then(function (r) { return r.json(); })
      .then(function (j) { state.otherTasks = (j && j.tasks) || []; render(); })
      .catch(function () { render(); });
  }
  function ensureOtherTaskFields(taskId) {
    if (state.otherTaskFieldsCache[taskId]) return;
    state.otherTaskFieldsCache[taskId] = [];
    var url = CFG.urls.task_fields_tmpl.replace("other_task_id", String(taskId));
    fetch(url, { headers: { "X-CSRFToken": CFG.csrfToken } })
      .then(function (r) { return r.json(); })
      .then(function (j) { state.otherTaskFieldsCache[taskId] = (j && j.fields) || []; render(); })
      .catch(function () { render(); });
  }
  function renderChoicesFromEditor(n) {
    var cf = n.choicesFrom || (n.choicesFrom = { sourceTaskId: null, sourcePath: "" });
    ensureOtherTasks(); // liste des tâches nécessaire dès l'ouverture du picker "tâche"

    var wrap = el("div", { style: "margin-top:10px; padding-top:10px; border-top:1px dashed #ccc" });
    wrap.appendChild(el("div", { class: "tfb-field-row" }, [
      el("label", { text: t("f_choices_from", "Options dynamiques depuis un autre champ") })
    ]));

    var taskOpts = [["", t("choices_from_same_task", "— même tâche —")]].concat(
      (state.otherTasks || []).map(function (tsk) {
        var label = (tsk.phase_name ? tsk.phase_name + " / " : "") +
          (tsk.activity_name ? tsk.activity_name + " / " : "") + tsk.name;
        return [String(tsk.id), label];
      })
    );
    wrap.appendChild(fieldRow(t("f_choices_from_task", "Tâche source"), selectFrom(
      taskOpts, cf.sourceTaskId ? String(cf.sourceTaskId) : "",
      function (v) {
        cf.sourceTaskId = v ? Number(v) : null;
        cf.sourcePath = ""; // la tâche source change -> le champ choisi précédemment n'est plus valide
        if (cf.sourceTaskId) ensureOtherTaskFields(cf.sourceTaskId);
        // `render()`, PAS `refreshTree()` : `refreshTree()` ne reconstruit QUE
        // les colonnes gauche/centre (cf. sa propre docstring) — la colonne de
        // droite (donc le picker "Champ source" juste en dessous, qui dépend
        // de la tâche choisie ici) resterait sinon affichée avec son ANCIENNE
        // liste de champs, potentiellement indéfiniment si cette tâche était
        // déjà en cache (`ensureOtherTaskFields` ne renderait alors jamais).
        render();
      }
    )));

    var fieldOpts;
    if (cf.sourceTaskId) {
      ensureOtherTaskFields(cf.sourceTaskId);
      fieldOpts = state.otherTaskFieldsCache[cf.sourceTaskId] || [];
    } else {
      fieldOpts = currentPagePaths().concat(crossPagePaths()).filter(function (p) { return SELECT_TYPES[p.type]; });
    }
    wrap.appendChild(fieldRow(
      t("f_choices_from_field", "Champ source"),
      selectPaths(fieldOpts, cf.sourcePath, function (v) { cf.sourcePath = v; })
    ));
    wrap.appendChild(el("div", { class: "tfb-muted", text: t(
      "f_choices_from_hint",
      "Les options de ce champ seront exactement ce que le facilitateur a choisi dans le champ source. Liste vide tant que la source n'a pas encore de réponse."
    ) }));
    return wrap;
  }

  /* ------------------ visibilité conditionnelle DEPUIS UNE AUTRE TÂCHE --- */
  // Distinct de `choicesFrom` (qui construit des OPTIONS) : ici on
  // affiche/masque CE champ selon la valeur d'un champ d'une autre tâche.
  // Toujours inter-tâches (le same-task/cross-page reste couvert par l'onglet
  // "Règles"). `ensureOtherTaskFieldsAll` cible TOUT type de champ (pas
  // seulement les select) -> endpoint `task_fields_tmpl` avec `?all=1`, cache
  // séparé pour ne pas mélanger avec le picker select-only de `choicesFrom`.
  function ensureOtherTaskFieldsAll(taskId) {
    if (state.otherTaskFieldsAllCache[taskId]) return;
    state.otherTaskFieldsAllCache[taskId] = [];
    var url = CFG.urls.task_fields_tmpl.replace("other_task_id", String(taskId)) + "?all=1";
    fetch(url, { headers: { "X-CSRFToken": CFG.csrfToken } })
      .then(function (r) { return r.json(); })
      .then(function (j) { state.otherTaskFieldsAllCache[taskId] = (j && j.fields) || []; render(); })
      .catch(function () { render(); });
  }
  var VISIBILITY_ACTIONS = ACTIONS.filter(function (a) { return a[0] === "show" || a[0] === "hide"; });
  var VISIBILITY_DEFAULTS = [
    ["hidden", t("vis_default_hidden", "Caché tant que la source n'est pas répondue")],
    ["visible", t("vis_default_visible", "Visible tant que la source n'est pas répondue")]
  ];
  function renderCrossTaskVisibilityEditor(n) {
    var cv = n.crossTaskVisibility || (n.crossTaskVisibility = {
      sourceTaskId: null, sourcePath: "", op: "eq", value: "", action: "show", defaultWhenUnknown: "hidden"
    });
    ensureOtherTasks();

    var wrap = el("div", { style: "margin-top:10px; padding-top:10px; border-top:1px dashed #ccc" });
    wrap.appendChild(el("div", { class: "tfb-field-row" }, [
      el("label", { text: t("f_cross_task_visibility", "Visibilité conditionnelle depuis une autre tâche") })
    ]));

    var taskOpts = [["", t("cross_task_visibility_none", "— aucune condition —")]].concat(
      (state.otherTasks || []).map(function (tsk) {
        var label = (tsk.phase_name ? tsk.phase_name + " / " : "") +
          (tsk.activity_name ? tsk.activity_name + " / " : "") + tsk.name;
        return [String(tsk.id), label];
      })
    );
    wrap.appendChild(fieldRow(t("f_choices_from_task", "Tâche source"), selectFrom(
      taskOpts, cv.sourceTaskId ? String(cv.sourceTaskId) : "",
      function (v) {
        cv.sourceTaskId = v ? Number(v) : null;
        cv.sourcePath = ""; // la tâche source change -> le champ choisi précédemment n'est plus valide
        if (cv.sourceTaskId) ensureOtherTaskFieldsAll(cv.sourceTaskId);
        render(); // cf. commentaire équivalent dans renderChoicesFromEditor : refreshTree() ne suffirait pas
      }
    )));

    if (!cv.sourceTaskId) return wrap; // pas de tâche choisie -> rien de plus à configurer

    ensureOtherTaskFieldsAll(cv.sourceTaskId);
    var fieldOpts = state.otherTaskFieldsAllCache[cv.sourceTaskId] || [];
    wrap.appendChild(fieldRow(
      t("f_choices_from_field", "Champ source"),
      selectPaths(fieldOpts, cv.sourcePath, function (v) { cv.sourcePath = v; })
    ));

    wrap.appendChild(el("div", { class: "tfb-inline" }, [
      fieldRow(t("r_action", "Action"), selectFrom(VISIBILITY_ACTIONS, cv.action, function (v) { cv.action = v; })),
      fieldRow(t("op_label", "Condition"), selectFrom(OPS, cv.op, function (v) { cv.op = v; render(); }))
    ]));
    if (cv.op !== "empty" && cv.op !== "notEmpty") {
      wrap.appendChild(fieldRow(t("r_value", "Valeur"), textInput(cv.value, function (v) { cv.value = v; })));
    }
    wrap.appendChild(fieldRow(
      t("f_cross_task_visibility_default", "Si la tâche source n'a pas encore de réponse"),
      selectFrom(VISIBILITY_DEFAULTS, cv.defaultWhenUnknown, function (v) { cv.defaultWhenUnknown = v; })
    ));
    return wrap;
  }

  /* ----------------------------------------- pièces jointes (Task.attachments) */
  // Onglet "Pièces jointes" (colonne de droite, cf. renderRight) : à la
  // différence de "Champ"/"Règles"/"Calculs", CE contenu ne dépend PAS du
  // nœud/page sélectionné — `Task.attachments` est une liste au niveau
  // TÂCHE, mirroir de `Task.visibility_condition` (state.attachments,
  // envoyée par `save()` à côté de `form`/`share_mode`, PAS compilée dans
  // `page.*`). Slots kobocollect-style {name,type,optional,order,conditions?}
  // — le mobile (TaskDetail.tsx) les remplit un par un avec un fichier
  // capturé ; `conditions` (nouveau) piloté par `evaluateAttachmentConditions`
  // côté mobile (`attachmentConditions.ts`) réutilise le même vocabulaire
  // d'opérateur/action que `rules`/`crossTaskVisibility`, appliqué ici à un
  // champ soit de LA MÊME tâche (`sourceTaskId: null`, résolu localement,
  // aucune lecture réseau), soit d'une AUTRE tâche (mêmes pickers que
  // `renderCrossTaskVisibilityEditor`, réutilisés tels quels).
  var ATTACHMENT_TYPES = [
    ["photos", t("attach_type_photos", "Photos")],
    ["procès-verbaux", t("attach_type_pv", "Procès-verbaux")],
    ["autre document", t("attach_type_other", "Autre document")]
  ];
  var ATTACHMENT_CONDITION_ACTIONS = ACTIONS.filter(function (a) {
    return a[0] === "show" || a[0] === "hide" || a[0] === "require" || a[0] === "optional";
  });
  function newAttachmentSlot() {
    return { name: "", type: "photos", optional: false, conditions: [] };
  }
  function newAttachmentCondition() {
    return { sourceTaskId: null, sourcePath: "", op: "eq", value: "", action: "show", defaultWhenUnknown: "hidden" };
  }
  function renderAttachmentConditionRow(cond, onRemove) {
    // PAS `.tfb-cond-row` ici : cette classe est `display:flex` pour une seule
    // ligne de quelques contrôles côte à côte (cf. `renderRulesEditor`) — ce
    // wrap contient plusieurs `fieldRow` EMPILÉS verticalement (même besoin
    // que `renderCrossTaskVisibilityEditor`, qui n'utilise aucune classe flex
    // pour son wrap non plus).
    var wrap = el("div", { style: "margin-top:6px; padding-top:6px; border-top:1px dotted #ccc" });

    var scopeOpts = [["same", t("attach_scope_same", "Champ de cette tâche")], ["cross", t("attach_scope_cross", "Champ d'une autre tâche")]];
    // BUG RÉEL trouvé en testant en direct (CDP, vrais clics simulés) :
    // dériver `scope` UNIQUEMENT de `cond.sourceTaskId` (comme un premier
    // jet l'avait fait) empêche de jamais choisir "Autre tâche" : au moment
    // où l'utilisateur bascule le sélecteur, `sourceTaskId` est encore
    // `null` (aucune tâche choisie pour l'instant) -> au `render()` suivant,
    // `scope` était recalculé à "same" et le sélecteur "revenait" tout seul
    // en arrière, sans jamais laisser apparaître le picker "Tâche source".
    // `cond._scopeUI` (transient, mirroir de `n._calc` pour le champ calculé)
    // mémorise le choix explicite de l'utilisateur indépendamment de
    // `sourceTaskId` — propriété superflue silencieusement éliminée par le
    // nettoyage backend (`_clean_attachment_condition` ne connaît qu'une
    // liste blanche de clés), jamais persistée telle quelle.
    var scope = cond._scopeUI || (cond.sourceTaskId ? "cross" : "same");
    wrap.appendChild(fieldRow(t("attach_scope", "Source"), selectFrom(scopeOpts, scope, function (v) {
      cond._scopeUI = v;
      if (v === "same") cond.sourceTaskId = null;
      cond.sourcePath = ""; // la portée change -> le champ choisi précédemment n'est plus valide
      render(); // pas refreshTree() : le picker "Champ source" juste en dessous doit changer de liste
    })));

    if (scope === "cross") {
      ensureOtherTasks();
      var taskOpts = [["", t("cross_task_visibility_none", "— choisir —")]].concat(
        (state.otherTasks || []).map(function (tsk) {
          var label = (tsk.phase_name ? tsk.phase_name + " / " : "") +
            (tsk.activity_name ? tsk.activity_name + " / " : "") + tsk.name;
          return [String(tsk.id), label];
        })
      );
      wrap.appendChild(fieldRow(t("f_choices_from_task", "Tâche source"), selectFrom(
        taskOpts, cond.sourceTaskId ? String(cond.sourceTaskId) : "",
        function (v) {
          cond.sourceTaskId = v ? Number(v) : null;
          cond.sourcePath = "";
          if (cond.sourceTaskId) ensureOtherTaskFieldsAll(cond.sourceTaskId);
          render();
        }
      )));
      if (cond.sourceTaskId) {
        ensureOtherTaskFieldsAll(cond.sourceTaskId);
        var crossFieldOpts = state.otherTaskFieldsAllCache[cond.sourceTaskId] || [];
        wrap.appendChild(fieldRow(t("f_choices_from_field", "Champ source"), selectPaths(crossFieldOpts, cond.sourcePath, function (v) { cond.sourcePath = v; })));
      }
    } else {
      wrap.appendChild(fieldRow(t("f_choices_from_field", "Champ source"), selectPaths(allTaskPathsWithPageIndex(), cond.sourcePath, function (v) { cond.sourcePath = v; })));
    }

    wrap.appendChild(el("div", { class: "tfb-inline" }, [
      fieldRow(t("r_action", "Action"), selectFrom(ATTACHMENT_CONDITION_ACTIONS, cond.action, function (v) { cond.action = v; })),
      fieldRow(t("op_label", "Condition"), selectFrom(OPS, cond.op, function (v) { cond.op = v; render(); }))
    ]));
    if (cond.op !== "empty" && cond.op !== "notEmpty") {
      wrap.appendChild(fieldRow(t("r_value", "Valeur"), textInput(cond.value, function (v) { cond.value = v; })));
    }
    wrap.appendChild(fieldRow(
      t("f_cross_task_visibility_default", "Si la source n'a pas encore de réponse"),
      selectFrom(VISIBILITY_DEFAULTS, cond.defaultWhenUnknown, function (v) { cond.defaultWhenUnknown = v; })
    ));
    wrap.appendChild(btn("✕ " + t("attach_cond_remove", "Supprimer la condition"), onRemove, "btn-danger btn-sm"));
    return wrap;
  }
  function renderAttachmentsEditor() {
    var box = el("div");
    box.appendChild(el("p", { class: "tfb-muted", text: t(
      "attach_help",
      "Pièces jointes attendues pour cette tâche (photo, procès-verbal, document…), à remplir sur mobile — même logique que kobocollect."
    ) }));

    state.attachments.forEach(function (slot, i) {
      if (!slot.conditions) slot.conditions = [];
      var card = el("div", { class: "tfb-calc" });
      card.appendChild(el("div", { class: "tfb-inline" }, [
        fieldRow(t("f_attachment_name", "Nom"), textInput(slot.name, function (v) { slot.name = v; })),
        fieldRow(t("f_attachment_type", "Type"), selectFrom(ATTACHMENT_TYPES, slot.type, function (v) { slot.type = v; }))
      ]));
      card.appendChild(checkbox(slot.optional, function (v) { slot.optional = v; },
        t("f_attachment_optional_default", "Facultatif par défaut (si aucune condition « rendre obligatoire/facultatif » ci-dessous)")));

      card.appendChild(el("div", { class: "tfb-node-actions", style: "margin-top:6px" }, [
        btn("▲", function () { moveNode(state.attachments, i, -1); }),
        btn("▼", function () { moveNode(state.attachments, i, 1); }),
        btn("✕ " + t("del_attachment", "Supprimer cette pièce jointe"), function () { state.attachments.splice(i, 1); render(); }, "btn-danger btn-sm")
      ]));

      slot.conditions.forEach(function (cond, ci) {
        card.appendChild(renderAttachmentConditionRow(cond, function () { slot.conditions.splice(ci, 1); render(); }));
      });
      card.appendChild(btn("+ " + t("attach_add_condition", "Ajouter une condition"), function () {
        slot.conditions.push(newAttachmentCondition()); render();
      }, "btn-secondary btn-sm"));

      box.appendChild(card);
    });

    box.appendChild(btn("+ " + t("attach_add", "Ajouter une pièce jointe"), function () {
      state.attachments.push(newAttachmentSlot()); render();
    }, "btn-primary btn-sm"));
    return box;
  }

  /* ---------- visibilité conditionnelle de LA TÂCHE ENTIÈRE (toolbar) ---- */
  // Mirroir task-level de renderCrossTaskVisibilityEditor : `state.
  // visibilityCondition` (même forme, sans "path" — la cible est la tâche
  // elle-même) est envoyé au save() à côté de `form`/`share_mode`. Conteneur
  // dédié (#tfb-visibility-condition, HORS de #tfb-root) reconstruit à
  // chaque render() — même raison que renderChoicesFromEditor : la liste
  // "Champ source" dépend de la tâche choisie, chargée en AJAX.
  function renderVisibilityConditionToolbar() {
    var host = document.getElementById("tfb-visibility-condition");
    if (!host) return;
    host.innerHTML = "";
    var vc = state.visibilityCondition;
    ensureOtherTasks();

    host.appendChild(el("span", { class: "tfb-share-mode-label", style: "font-weight:600" }, [
      el("i", { class: "fa fa-eye mr-1" }), t("vc_toolbar_title", "Visibilité de la tâche")
    ]));

    var taskOpts = [["", t("cross_task_visibility_none", "— aucune condition —")]].concat(
      (state.otherTasks || []).map(function (tsk) {
        var label = (tsk.phase_name ? tsk.phase_name + " / " : "") +
          (tsk.activity_name ? tsk.activity_name + " / " : "") + tsk.name;
        return [String(tsk.id), label];
      })
    );
    var taskSel = selectFrom(taskOpts, vc && vc.sourceTaskId ? String(vc.sourceTaskId) : "", function (v) {
      if (!v) { state.visibilityCondition = null; renderVisibilityConditionToolbar(); return; }
      state.visibilityCondition = vc = state.visibilityCondition || {
        sourceTaskId: null, sourcePath: "", op: "eq", value: "", action: "show", defaultWhenUnknown: "hidden"
      };
      vc.sourceTaskId = Number(v);
      vc.sourcePath = "";
      ensureOtherTaskFieldsAll(vc.sourceTaskId);
      renderVisibilityConditionToolbar();
    });
    taskSel.style.width = "auto";
    taskSel.classList.add("d-inline-block");
    host.appendChild(taskSel);

    if (vc && vc.sourceTaskId) {
      ensureOtherTaskFieldsAll(vc.sourceTaskId);
      var fieldOpts = state.otherTaskFieldsAllCache[vc.sourceTaskId] || [];
      var fieldSel = selectPaths(fieldOpts, vc.sourcePath, function (v) { vc.sourcePath = v; });
      fieldSel.style.width = "auto";
      fieldSel.classList.add("d-inline-block");
      host.appendChild(fieldSel);

      var actionSel = selectFrom(VISIBILITY_ACTIONS, vc.action, function (v) { vc.action = v; });
      actionSel.style.width = "auto";
      actionSel.classList.add("d-inline-block");
      host.appendChild(actionSel);

      var opSel = selectFrom(OPS, vc.op, function (v) { vc.op = v; renderVisibilityConditionToolbar(); });
      opSel.style.width = "auto";
      opSel.classList.add("d-inline-block");
      host.appendChild(opSel);

      if (vc.op !== "empty" && vc.op !== "notEmpty") {
        var valInput = textInput(vc.value, function (v) { vc.value = v; });
        valInput.style.width = "auto";
        valInput.classList.add("d-inline-block");
        valInput.placeholder = t("r_value", "Valeur");
        host.appendChild(valInput);
      }

      var defaultSel = selectFrom(VISIBILITY_DEFAULTS, vc.defaultWhenUnknown, function (v) { vc.defaultWhenUnknown = v; });
      defaultSel.style.width = "auto";
      defaultSel.classList.add("d-inline-block");
      host.appendChild(defaultSel);

      host.appendChild(btn(t("vc_clear", "Effacer la condition"), function () {
        state.visibilityCondition = null;
        renderVisibilityConditionToolbar();
      }, "btn-outline-secondary btn-sm"));
    }

    applySelect2(host);
  }

  function renderChoices(n) {
    var box = el("div", { class: "tfb-field-row" }, [el("label", { text: t("f_choices", "Choix (une valeur par ligne)") })]);

    var fileInput = el("input", {
      type: "file", accept: ".xlsx,.xls", style: "display:none",
      onchange: function () { var f = this.files[0]; this.value = ""; if (f) importChoices(n, f); }
    });
    box.appendChild(el("div", { class: "tfb-choice-tools" }, [
      btn("⭳ " + t("choices_import", "Importer (Excel)"), function () { fileInput.click(); }, "btn-outline-secondary btn-sm",
        t("choices_import_hint", "Charger les choix depuis un fichier Excel (colonne « valeur »).")),
      btn("⭱ " + t("choices_export", "Exporter (Excel)"), function () { exportChoices(n); }, "btn-outline-secondary btn-sm",
        t("choices_export_hint", "Télécharger les choix listés (montre aussi le format attendu à l'import).")),
      fileInput
    ]));

    (n.choices || []).forEach(function (c, i) {
      box.appendChild(el("div", { class: "tfb-choice-row" }, [
        textInput(c, function (v) { n.choices[i] = v; }),
        btn("✕", function () { n.choices.splice(i, 1); render(); }, "btn-danger btn-sm")
      ]));
    });
    box.appendChild(btn("+ " + t("add_choice", "Ajouter un choix"), function () { n.choices.push(""); render(); }, "btn-secondary btn-sm"));
    return box;
  }

  function downloadBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = el("a", { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); URL.revokeObjectURL(url); }, 0);
  }
  function exportChoices(n) {
    fetch(CFG.urls.choices_export, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": CFG.csrfToken },
      body: JSON.stringify({ choices: (n.choices || []).filter(String) })
    })
      .then(function (r) { if (!r.ok) throw new Error(); return r.blob(); })
      .then(function (b) { downloadBlob(b, "choix_" + (n.key || "champ") + ".xlsx"); })
      .catch(function () { flash(t("network_err", "Erreur réseau."), false); });
  }
  function importChoices(n, file) {
    var fd = new FormData();
    fd.append("file", file);
    fetch(CFG.urls.choices_import, { method: "POST", headers: { "X-CSRFToken": CFG.csrfToken }, body: fd })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j.ok) { flash((j.errors || [t("import_warn", "Import partiel — voir les erreurs.")])[0], false); return; }
        var incoming = (j.choices || []).filter(String);
        if (!incoming.length) { flash(t("choices_import_empty", "Aucune valeur de choix trouvée dans le fichier."), false); return; }
        var cur = (n.choices || []).filter(String);
        if (cur.length && !confirm(t("choices_replace_confirm", "Remplacer les choix actuels par ceux du fichier ? (Annuler = ajouter à la suite)"))) {
          incoming.forEach(function (v) { if (cur.indexOf(v) === -1) cur.push(v); });
          n.choices = cur;
        } else {
          n.choices = incoming.slice();
        }
        render();
        flash(t("choices_import_done", "Choix importés : ") + n.choices.length, true);
      })
      .catch(function () { flash(t("network_err", "Erreur réseau."), false); });
  }

  /* --------------------------------------------------------------- rules UI */
  function renderRulesEditor() {
    var page = state.pages[state.active];
    var box = el("div");
    box.appendChild(el("p", { class: "tfb-muted", text: t("rules_help", "Conditions entre champs : afficher / masquer / rendre obligatoire un champ selon la valeur d'un autre.") }));
    var paths = currentPagePaths().concat(crossPagePaths());
    page.rules.forEach(function (r, ri) {
      var rb = el("div", { class: "tfb-rule" });
      rb.appendChild(el("div", { class: "tfb-inline" }, [
        fieldRow(t("r_action", "Action"), selectFrom(ACTIONS, r.action, function (v) { r.action = v; })),
        fieldRow(t("r_target", "Champ cible"), selectPaths(currentPagePaths(), r.target, function (v) { r.target = v; }))
      ]));
      rb.appendChild(fieldRow(t("r_when", "Quand"), selectFrom([["all", t("r_all", "toutes les conditions")], ["any", t("r_any", "au moins une condition")]], r.conj, function (v) { r.conj = v; })));
      r.conds.forEach(function (c, ci) {
        rb.appendChild(el("div", { class: "tfb-cond-row" }, [
          selectPaths(paths, c.field, function (v) { c.field = v; }),
          selectFrom(OPS, c.op, function (v) { c.op = v; render(); }),
          (c.op === "empty" || c.op === "notEmpty") ? el("span") : textInput(c.value, function (v) { c.value = v; }),
          btn("✕", function () { r.conds.splice(ci, 1); if (!r.conds.length) r.conds.push({ field: "", op: "eq", value: "" }); render(); }, "btn-danger btn-sm")
        ]));
      });
      rb.appendChild(el("div", {}, [
        btn("+ " + t("add_cond", "Ajouter une condition"), function () { r.conds.push({ field: "", op: "eq", value: "" }); render(); }, "btn-secondary btn-sm"), " ",
        btn("✕ " + t("del_rule", "Supprimer la règle"), function () { page.rules.splice(ri, 1); render(); }, "btn-danger btn-sm")
      ]));
      box.appendChild(rb);
    });
    box.appendChild(btn("+ " + t("add_rule", "Ajouter une règle"), function () {
      page.rules.push({ id: uid(), target: "", conj: "all", conds: [{ field: "", op: "eq", value: "" }], action: "show" });
      render();
    }, "btn-primary btn-sm"));
    return box;
  }
  function selectFrom(pairs, val, on) {
    var s = el("select", { class: "form-control form-control-sm", onchange: function () { on(this.value); } });
    pairs.forEach(function (p) { s.appendChild(opt(p[0], p[1], val)); });
    return s;
  }
  function selectPaths(paths, val, on) {
    var s = el("select", { class: "form-control form-control-sm", onchange: function () { on(this.value); } });
    s.appendChild(opt("", "—", val));
    paths.forEach(function (p) { s.appendChild(opt(p.path, p.label + "  {" + p.path + "}", val)); });
    if (val && !paths.some(function (p) { return p.path === val; })) s.appendChild(opt(val, val, val));
    return s;
  }

  /* -------------------- champ calculé (raccourci convivial par champ) ---- */
  // Interface simple (opération + termes) posée DIRECTEMENT sur le champ
  // cible, plutôt que de forcer l'utilisateur à écrire une expression brute
  // dans l'onglet "Calculs" — mais lit/écrit EXACTEMENT le même tableau
  // `page.calculate` que cet onglet (aucun second état, aucune duplication) :
  // cette section n'est qu'une façade conviviale au-dessus du mécanisme
  // `calculate` déjà existant (target + expr). Une entrée créée ici apparaît
  // donc aussi, en toute transparence, dans l'onglet "Calculs" — et une
  // entrée écrite à la main là-bas peut être reprise ici si son expression
  // correspond à un des motifs reconnus (cf. `parseCalcExpr`).
  var CALC_OPS = [
    ["sum", t("calc_op_sum", "Somme (+)")],
    ["diff", t("calc_op_diff", "Différence (−)")],
    ["product", t("calc_op_product", "Produit (×)")],
    ["quotient", t("calc_op_quotient", "Quotient (÷)")],
    ["percentage", t("calc_op_percentage", "Pourcentage (%)")]
  ];
  var CALC_FIXED_2_OPS = { quotient: 1, percentage: 1 };
  function findCalcEntry(page, path) {
    return (page.calculate || []).filter(function (c) { return c.target === path; })[0] || null;
  }
  function buildCalcExpr(op, operands) {
    var ops = operands.filter(Boolean);
    if (ops.length < 2) return "";
    if (op === "sum") return ops.join(" + ");
    if (op === "diff") return ops.join(" - ");
    if (op === "product") return ops.join(" * ");
    if (op === "quotient") return ops.slice(0, 2).join(" / ");
    if (op === "percentage") return "(" + ops[0] + " / " + ops[1] + ") * 100";
    return "";
  }
  // Reconnaît une expression PRÉCÉDEMMENT générée par `buildCalcExpr` (même
  // format exact) pour préremplir l'éditeur convivial au rechargement d'un
  // formulaire existant. Une expression qui ne correspond à AUCUN motif
  // reconnu (fonctions, parenthésage différent, littéraux numériques…) est
  // traitée comme "personnalisée" — affichée en lecture seule ici, toujours
  // éditable telle quelle dans l'onglet "Calculs".
  function parseCalcExpr(expr) {
    if (!expr) return null;
    var pm = /^\((.+)\s\/\s(.+)\)\s\*\s100$/.exec(expr);
    if (pm) return { op: "percentage", operands: [pm[1].trim(), pm[2].trim()] };
    var isSimplePath = function (s) { return /^[A-Za-z_$][A-Za-z0-9_.$]*$/.test(s.trim()); };
    function trySplit(sep, op) {
      if (expr.indexOf(sep) === -1) return null;
      var parts = expr.split(sep);
      if (parts.length < 2 || !parts.every(isSimplePath)) return null;
      return { op: op, operands: parts.map(function (p) { return p.trim(); }) };
    }
    return trySplit(" + ", "sum") || trySplit(" - ", "diff") || trySplit(" * ", "product") || trySplit(" / ", "quotient");
  }
  function renderCalcFieldEditor(n, path) {
    var page = state.pages[state.active];
    var entry = findCalcEntry(page, path);
    var enabled = !!entry;

    // BUG réel trouvé en testant en direct (clic simulé) : `path` (paramètre
    // reçu à l'appel de CETTE fonction, donc figé au moment du DERNIER
    // render() complet) peut devenir périmé sans qu'aucun render() complet
    // n'intervienne entre-temps — notamment juste après avoir tapé la « Clé »
    // ou le « Libellé » du champ, qui ne déclenchent qu'un `refreshTree()`
    // (par design, pour garder le focus pendant la saisie — cf. sa propre
    // docstring) : refreshTree() NE reconstruit PAS la colonne de droite,
    // donc CETTE section continue de vivre avec l'ancien `path` tant qu'aucun
    // render() complet n'a eu lieu. Cocher la case juste après avoir renommé
    // le champ écrivait alors une entrée `page.calculate` avec l'ANCIEN chemin
    // -> la case semblait "ne pas rester cochée" au rendu suivant (qui, lui,
    // recalcule `path` à jour et ne retrouve plus l'entrée). Fix : toujours
    // recalculer le chemin ACTUEL au moment où un handler s'exécute, jamais se
    // fier au `path` fermé par la closure de rendu.
    function currentPath() { return nodePath(n.id); }

    var wrap = el("div", { style: "margin-top:10px; padding-top:10px; border-top:1px dashed #ccc" });
    wrap.appendChild(el("div", { class: "tfb-field-row" }, [checkbox(enabled, function (v) {
      var p = currentPath();
      if (v) {
        if (!findCalcEntry(page, p)) page.calculate.push({ target: p, expr: "" });
        // Un champ calculé automatiquement n'a pas de sens comme "Obligatoire"
        // (sa complétude dépend de SES TERMES, pas d'une saisie directe) —
        // c'est à ceux-ci d'être marqués obligatoires si besoin.
        n.required = false;
        n._calc = { op: "sum", operands: ["", ""] };
      } else {
        page.calculate = page.calculate.filter(function (c) { return c.target !== p; });
        n._calc = null;
      }
      render();
    }, t("f_calc_enabled", "Ce champ est calculé automatiquement à partir d'autres champs"))]));

    if (!enabled) return wrap;
    wrap.appendChild(el("div", { class: "tfb-muted", text: t(
      "f_calc_disabled_hint",
      "Ce champ sera affiché désactivé (lecture seule) sur mobile — sa valeur est recalculée automatiquement à chaque saisie."
    ) }));

    // Une entrée FRAÎCHEMENT créée (case tout juste cochée, ou dont MOINS de
    // 2 termes ont pour l'instant été choisis) a `expr: ""` — `parseCalcExpr`
    // renvoie `null` pour toute expression non reconnue, ce qui inclut la
    // chaîne vide, mais CE N'EST PAS une expression "personnalisée" : juste
    // "pas encore complète". Ne bascule en lecture seule ("personnalisée")
    // que si une VRAIE expression existe et reste non reconnue.
    var parsed = parseCalcExpr(entry.expr);
    var isCustom = !!entry.expr && !parsed;
    if (isCustom) {
      n._calc = null;
      wrap.appendChild(el("div", { class: "tfb-muted", text: t("f_calc_custom_hint", "Expression personnalisée (modifiable dans l'onglet « Calculs ») : ") + entry.expr }));
      return wrap;
    }

    // `n._calc` (état d'INTERFACE transitoire, jamais compilé/enregistré,
    // comme `_sheet`/`_calcOperandCount` avant lui) est la source de vérité
    // PENDANT L'ÉDITION — PAS `entry.expr` : `buildCalcExpr` renvoie ""
    // tant que MOINS de 2 termes sont renseignés (ex. juste après avoir
    // choisi le 1ᵉʳ terme, avant le 2ᵉ), et re-dériver `operands` depuis
    // `parseCalcExpr("")` (qui renvoie `null`) PERDRAIT alors ce 1ᵉʳ choix au
    // re-rendu suivant — bug réel rencontré en testant en direct. `n._calc`
    // n'est (ré)initialisé depuis `entry.expr` QUE s'il n'existe pas encore
    // (ex. au chargement d'un formulaire existant déjà calculé), jamais
    // écrasé pendant une édition en cours.
    if (!n._calc) {
      n._calc = parsed ? { op: parsed.op, operands: parsed.operands.slice() } : { op: "sum", operands: ["", ""] };
    }
    var op = n._calc.op;
    var operands = n._calc.operands;
    while (operands.length < 2) operands.push("");

    // Re-pose aussi `entry.target` (pas seulement `.expr`) à chaque commit :
    // auto-guérison si `path` a pu devenir périmé entre le rendu de cette
    // section et cette modification (cf. commentaire de `currentPath` plus haut).
    function commit() { entry.target = currentPath(); entry.expr = buildCalcExpr(op, operands); }

    wrap.appendChild(fieldRow(t("f_calc_op", "Opération"), selectFrom(CALC_OPS, op, function (v) {
      op = n._calc.op = v;
      if (CALC_FIXED_2_OPS[op] && operands.length > 2) { operands = n._calc.operands = operands.slice(0, 2); }
      commit(); render();
    })));

    var numericPaths = currentPagePaths().filter(function (p) {
      return (p.type === "integer" || p.type === "decimal") && p.path !== path;
    });

    operands.forEach(function (val, i) {
      var label = (op === "quotient" || op === "percentage")
        ? (i === 0 ? t("f_calc_numerator", "Numérateur") : t("f_calc_denominator", "Dénominateur"))
        : t("f_calc_term", "Terme") + " " + (i + 1);
      // PAS `.tfb-inline` ici : cette classe force `flex:1` sur TOUS ses
      // enfants (voulu pour 2 fieldRow à parts égales ailleurs, ex. Action/
      // Champ cible des Règles) — appliqué à ce bouton ✕ minuscule, ça
      // l'étirait sur la moitié de la ligne (bug réel vu en testant en
      // direct). Ligne flex "à la main" : le fieldRow prend l'espace
      // disponible, le bouton garde sa taille naturelle.
      var row = el("div", { style: "display:flex; gap:6px; align-items:flex-end; max-width:100%;" });
      var fieldWrap = fieldRow(label, selectPaths(numericPaths, val, function (v) { operands[i] = v; commit(); render(); }));
      fieldWrap.style.flex = "1";
      fieldWrap.style.minWidth = "0";
      row.appendChild(fieldWrap);
      if (!CALC_FIXED_2_OPS[op] && operands.length > 2) {
        row.appendChild(btn("✕", function () {
          operands.splice(i, 1);
          commit(); render();
        }, "btn-danger btn-sm"));
      }
      wrap.appendChild(row);
    });

    if (!CALC_FIXED_2_OPS[op]) {
      wrap.appendChild(btn("+ " + t("f_calc_add_term", "Ajouter un terme"), function () {
        operands.push("");
        render();
      }, "btn-secondary btn-sm"));
    }

    return wrap;
  }

  /* ----------------------------------------------------------------- calc UI */
  function renderCalcEditor() {
    var page = state.pages[state.active];
    var box = el("div");
    box.appendChild(el("p", { class: "tfb-muted", text: t("calc_help", "Champs calculés : opérateurs + - * / ( ) et fonctions sum, min, max, round, abs.") }));
    page.calculate.forEach(function (c, i) {
      var cb = el("div", { class: "tfb-calc" }, [
        fieldRow(t("c_target", "Champ résultat"), selectPaths(currentPagePaths(), c.target, function (v) { c.target = v; })),
        fieldRow(t("c_expr", "Expression"), textInput(c.expr, function (v) { c.expr = v; })),
        btn("✕ " + t("del_calc", "Supprimer"), function () { page.calculate.splice(i, 1); render(); }, "btn-danger btn-sm")
      ]);
      box.appendChild(cb);
    });
    box.appendChild(btn("+ " + t("add_calc", "Ajouter un calcul"), function () { page.calculate.push({ target: "", expr: "" }); render(); }, "btn-primary btn-sm"));
    return box;
  }

  /* --------------------------------------------------------------- preview */
  function renderPreview() {
    var form = safeCompile();
    var box = el("div", { class: "tfb-preview" });
    if (!form) { box.appendChild(el("div", { class: "tfb-errors", text: t("preview_err", "Le formulaire n'est pas compilable en l'état.") })); return box; }
    var pg = form[state.active];
    Object.keys(pg.page.properties).forEach(function (k) {
      var p = pg.page.properties[k], o = pg.options.fields[k] || {};
      var req = (pg.page.required || []).indexOf(k) !== -1;
      box.appendChild(el("div", { class: "tfb-p-field", text: (o.label || k) + (req ? " *" : "") + "  —  " + previewType(p, o) }));
    });
    (pg.rules || []).forEach(function (r) {
      box.appendChild(el("div", { class: "tfb-p-rule", text: "⟹ " + r.then[0].action + " " + r.then[0].target + "  " + t("when", "quand") + "  " + JSON.stringify(r.when) }));
    });
    (pg.calculate || []).forEach(function (c) { box.appendChild(el("div", { class: "tfb-p-rule", text: "ƒ " + c.target + " = " + c.expr })); });
    return box;
  }
  function enumLabels(e) {
    return (Array.isArray(e) ? e : Object.keys(e || {}).map(function (k) { return e[k]; })).slice(0, 8).join(", ");
  }
  function previewType(p, o) {
    if (p.type === "geopoint") return "GPS (lat/long/précision" + ((o && o.accuracyThreshold) ? " ≤ " + o.accuracyThreshold + " m" : "") + ")";
    if (p.enum) return "choix: " + enumLabels(p.enum);
    if (p.type === "array" && p.items && p.items.enum) {
      return (o && o.mode === "checklist" ? "cases à cocher: " : "choix multiple: ") + enumLabels(p.items.enum);
    }
    if (p.type === "array") return "répétable";
    if (p.type === "object") return "groupe";
    if (p.format) return p.format;
    return p.type + (p.minimum != null || p.maximum != null ? " [" + (p.minimum != null ? p.minimum : "") + "…" + (p.maximum != null ? p.maximum : "") + "]" : "");
  }

  /* ------------------------------------------------------------- json editor */
  function renderJsonEditor() {
    var box = el("div");
    var ta = el("textarea", { class: "tfb-json form-control" });
    ta.value = JSON.stringify(safeCompile() || [], null, 2);
    box.appendChild(el("p", { class: "tfb-muted", text: t("json_help", "Vous pouvez coller ici un formulaire existant (context/formulaires_dcc) puis « Appliquer ».") }));
    box.appendChild(ta);
    box.appendChild(btn(t("json_apply", "Appliquer le JSON"), function () {
      try {
        var parsed = JSON.parse(ta.value);
        state.pages = decompile(parsed); state.active = 0; state.sel = null; render();
      } catch (e) { alert("JSON invalide : " + e.message); }
    }, "btn-primary btn-sm mt-2"));
    return box;
  }

  /* -------------------------------------------------------------- errors box */
  var lastErrors = [];
  function renderErrorBox() {
    if (!lastErrors.length) return el("span");
    return el("div", { class: "tfb-errors" }, [
      el("strong", { text: t("errors_title", "Le formulaire n'a pas été enregistré :") }),
      el("ul", {}, lastErrors.map(function (e) { return el("li", { text: e }); }))
    ]);
  }

  /* --------------------------------------------------------------- actions */
  function btn(label, on, cls, title) {
    var a = { type: "button", class: "btn btn-xs " + (cls || "btn-outline-secondary"), text: label, onclick: on };
    if (title) a.title = title;
    return el("button", a);
  }
  function addPage() { state.pages.push(newPage()); state.active = state.pages.length - 1; state.sel = null; render(); }
  function removePage(i) {
    if (state.pages.length === 1) { alert(t("min_one_page", "Au moins une page est requise.")); return; }
    state.pages.splice(i, 1); state.active = Math.max(0, state.active - (i <= state.active ? 1 : 0)); state.sel = null; render();
  }
  function movePage(i, d) { var j = i + d; if (j < 0 || j >= state.pages.length) return; var x = state.pages.splice(i, 1)[0]; state.pages.splice(j, 0, x); state.active = j; render(); }
  function moveNode(list, i, d) { var j = i + d; if (j < 0 || j >= list.length) return; var x = list.splice(i, 1)[0]; list.splice(j, 0, x); render(); }

  function safeCompile() { try { return compile(); } catch (e) { return null; } }

  function save() {
    var form = safeCompile();
    if (!form) { lastErrors = [t("compile_err", "Formulaire non compilable (vérifiez les clés des champs).")]; render(); return; }
    lastErrors = [];
    fetch(CFG.urls.save, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": CFG.csrfToken },
      body: JSON.stringify({
        form: form, share_mode: state.shareMode || "none",
        visibility_condition: state.visibilityCondition, attachments: state.attachments
      })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.j.ok) {
          lastErrors = [];
          flash(t("saved", "Formulaire enregistré."), true);
        } else {
          lastErrors = res.j.errors || [t("save_failed", "Échec de l'enregistrement.")];
          flash(t("save_failed", "Échec de l'enregistrement."), false);
        }
        render();
      })
      .catch(function () { lastErrors = [t("network_err", "Erreur réseau.")]; render(); });
  }
  function flash(msg, ok) {
    var d = document.getElementById("tfb-flash");
    d.className = ok ? "tfb-ok" : "tfb-errors";
    d.textContent = msg;
    d.style.display = "block";
    setTimeout(function () { d.style.display = "none"; }, 4000);
  }

  function importXls(file) {
    var fd = new FormData(); fd.append("file", file);
    fetch(CFG.urls.import, { method: "POST", headers: { "X-CSRFToken": CFG.csrfToken }, body: fd })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.form) { state.pages = decompile(j.form); state.active = 0; state.sel = null; }
        lastErrors = j.errors || [];
        render();
        flash(j.ok ? t("imported", "XLSForm importé — relisez puis Enregistrez.") : t("import_warn", "Import partiel — voir les erreurs."), j.ok);
      })
      .catch(function () { flash(t("network_err", "Erreur réseau."), false); });
  }

  /* ------------------------------------------------------------------- init */
  document.getElementById("tfb-save").addEventListener("click", save);
  document.getElementById("tfb-import").addEventListener("change", function () { if (this.files[0]) importXls(this.files[0]); this.value = ""; });
  // `state.shareMode` : simple mémo du dernier mode choisi au toolbar, utilisé
  // UNIQUEMENT comme valeur par défaut du bouton "Appliquer à tous les champs"
  // (raccourci) — le mode réellement effectif est TOUJOURS celui porté par
  // chaque champ (`n.shareMode`, cf. applyShareFields/collectShareFields).
  state.shareMode = CFG.shareMode || "none";
  var shareModeSel = document.getElementById("tfb-share-mode");
  if (shareModeSel) {
    shareModeSel.value = state.shareMode;
    shareModeSel.addEventListener("change", function () { state.shareMode = this.value; });
    // Statique (jamais recréé, contrairement à #tfb-root) -> initialisé une
    // seule fois ici, pas via applySelect2()/render().
    if (window.jQuery && window.jQuery.fn && window.jQuery.fn.select2) {
      window.jQuery(shareModeSel).select2({ width: "100%", minimumResultsForSearch: 0 });
    }
  }
  var shareModeApplyAll = document.getElementById("tfb-share-mode-apply-all");
  if (shareModeApplyAll) {
    shareModeApplyAll.addEventListener("click", function () {
      var mode = state.shareMode === "none" ? "" : state.shareMode;
      applyShareModeToAllFields(mode);
      render();
    });
  }
  // Visibilité conditionnelle de LA TÂCHE ENTIÈRE — embarquée à part
  // (#tfb-vc-json, via json_script) plutôt que dans le blob CFG (qui utilise
  // le mécanisme de substitution "__FORM_JSON__" spécifiquement pour éviter
  // le double-échappement d'un JSON complexe ; inutile ici, une simple valeur).
  (function () {
    var vcEl = document.getElementById("tfb-vc-json");
    if (!vcEl) return;
    try { state.visibilityCondition = JSON.parse(vcEl.textContent) || null; }
    catch (e) { state.visibilityCondition = null; }
  })();
  // Pièces jointes de la tâche — même mécanisme que #tfb-vc-json ci-dessus
  // (embarqué à part via json_script plutôt que dans CFG).
  (function () {
    var attEl = document.getElementById("tfb-attachments-json");
    if (!attEl) return;
    try { state.attachments = JSON.parse(attEl.textContent) || []; }
    catch (e) { state.attachments = []; }
  })();
  state.pages = decompile(CFG.formJson);
  render();
})();
