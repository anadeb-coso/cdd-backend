/**
 * Moteur de remplissage web d'une page de Task.form (parité avec l'écran
 * mobile TaskDetail.tsx / tcomb-form-native) : E1 (parsing du schéma stocké
 * -> descripteurs de champs), E2 (compilateur HTML Bootstrap 4), E6
 * (pagination multi-pages). S'appuie sur task_cycle_form_logic.js
 * (window.TCFormLogic, E3 : règles/calculs, portage quasi verbatim du fichier
 * mobile) pour tout ce qui est déclaratif.
 *
 * Vocabulaire/format exact : dashboard/process_manager/tasks/form_design.py
 * (docstring de module) + static/dashboard/js/task_form_builder.js
 * (nodeFromSchema/childrenFromObject/orderedKeys, la décompilation de
 * référence — ce fichier en reprend la même logique, adaptée au remplissage
 * plutôt qu'à l'édition du design).
 *
 * Ne gère PAS encore (prochaines sous-étapes du plan) : choicesFrom inter-
 * tâches, crossTaskVisibility, share, pièces jointes conditionnelles,
 * sauvegarde serveur — seul le rendu + la saisie en mémoire sont couverts ici.
 */
(function (window, $) {
  'use strict';

  var L = window.TCFormLogic;

  /* ------------------------------------------------------------ E1 : parsing */

  function orderedKeys(props, order) {
    var all = Object.keys(props || {});
    if (!Array.isArray(order)) return all;
    var seen = {}, out = [];
    order.forEach(function (k) { if (props && props[k] && !seen[k]) { seen[k] = 1; out.push(k); } });
    all.forEach(function (k) { if (!seen[k]) out.push(k); });
    return out;
  }

  function fieldFromSchema(key, prop, opts, isRequired) {
    prop = prop || {}; opts = opts || {};
    var f = {
      key: key, label: opts.label || key, help: opts.help || '',
      required: !!isRequired, mode: opts.mode || '', i18n: opts.i18n || {}
    };
    if (prop.type === 'object') {
      f.type = 'group';
      f.children = childrenFromObject(prop, opts);
    } else if (prop.type === 'array' && prop.items && prop.items.type === 'object') {
      f.type = 'repeat';
      f.minItems = prop.minItems != null ? prop.minItems : null;
      f.maxItems = prop.maxItems != null ? prop.maxItems : null;
      f.children = childrenFromObject(prop.items, (opts.item && opts.item.fields) ? opts.item : opts);
    } else if (prop.type === 'array' && prop.items && prop.items.enum) {
      f.type = (opts.mode === 'checklist') ? 'select_multiple_check' : 'select_multiple';
      f.choices = Array.isArray(prop.items.enum) ? prop.items.enum.slice() : Object.keys(prop.items.enum);
      f.listThreshold = opts.listThreshold != null ? opts.listThreshold : null;
      // minItems (form_design.py/task_form_builder.js : posé à 1 quand le champ est
      // obligatoire, "au moins une case cochée") — tcomb-json-schema le traduit en
      // fcomb.minLength, validé à CHAQUE getValue() côté mobile (pas seulement une
      // fois hasDeclarativeLogic) ; cf. checkFieldConstraint plus bas.
      f.minItems = prop.minItems != null ? prop.minItems : null;
    } else if (prop.enum) {
      f.type = 'select_one';
      f.choices = Array.isArray(prop.enum) ? prop.enum.slice() : Object.keys(prop.enum);
      f.listThreshold = opts.listThreshold != null ? opts.listThreshold : null;
    } else if (prop.type === 'geopoint' || opts.mode === 'geopoint') {
      f.type = 'geopoint';
      f.accuracyThreshold = (opts.accuracyThreshold != null && opts.accuracyThreshold !== '') ? opts.accuracyThreshold : 20;
    } else if (prop.type === 'integer') {
      f.type = 'integer'; f.min = prop.minimum != null ? prop.minimum : null; f.max = prop.maximum != null ? prop.maximum : null;
    } else if (prop.type === 'number') {
      f.type = 'decimal'; f.min = prop.minimum != null ? prop.minimum : null; f.max = prop.maximum != null ? prop.maximum : null;
    } else if (prop.format === 'date') { f.type = 'date'; }
    else if (prop.format === 'datetime') { f.type = 'datetime'; }
    else if (prop.format === 'time') { f.type = 'time'; }
    else if (prop._note) { f.type = 'note'; }
    else {
      f.type = 'text';
      f.minLength = prop.minLength != null ? prop.minLength : null;
      f.maxLength = prop.maxLength != null ? prop.maxLength : null;
      f.pattern = prop.pattern || '';
    }
    return f;
  }

  function childrenFromObject(objSchema, opts) {
    var props = objSchema.properties || {};
    var req = objSchema.required || [];
    var subFields = (opts && opts.fields) || {};
    return orderedKeys(props, opts && opts.order).map(function (k) {
      return fieldFromSchema(k, props[k], subFields[k] || {}, req.indexOf(k) !== -1);
    });
  }

  /** Page stockée ({options,page,rules,calculate,...}) -> liste de descripteurs
   * de champs racine, prête pour renderField. */
  function parsePageFields(page) {
    var schema = (page && page.page) || { properties: {} };
    var opts = (page && page.options) || {};
    return childrenFromObject(schema, opts);
  }

  /* --------------------------------------------------------- E2 : rendu HTML */

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function domId(path) { return 'tcf-' + path.replace(/[^a-zA-Z0-9_-]/g, '_'); }

  function getValueAt(values, path) { return L.resolvePath(values, path); }

  /* --------------------------------------------- Conversion date/heure ISO -
     Le stockage (CouchDB, PARTAGÉ avec mobile) est toujours une chaîne
     ISO-8601 : mobile manipule un objet JS `Date` natif (DatePicker.
     transformer est une passe-plat, components.js) et le sérialise via
     Date.prototype.toJSON() au moment du save — "DD-MM-YYYY"/"HH:mm" ne sont
     que des formats d'AFFICHAGE côté mobile (moment(date).format(...)),
     jamais ce qui est réellement stocké. Les <input type="date|datetime-local
     |time"> HTML natifs veulent leurs propres formats -> ces fonctions font
     l'aller-retour dans les 2 sens, pour rester lisible par mobile ET par
     l'affichage lecture-seule existant (structureTheFieldsLabels, qui ne
     reformate jamais rien). */
  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  function isoToDateInput(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    return isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 10);
  }
  function dateInputToIso(val) {
    if (!val) return undefined;
    var d = new Date(val + 'T00:00:00.000Z');
    return isNaN(d.getTime()) ? undefined : d.toISOString();
  }
  function isoToDatetimeInput(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate())
      + 'T' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }
  function datetimeInputToIso(val) {
    if (!val) return undefined;
    var d = new Date(val); // pas de fuseau dans la chaîne -> interprété en HEURE LOCALE (spec ECMA)
    return isNaN(d.getTime()) ? undefined : d.toISOString();
  }
  function isoToTimeInput(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    return isNaN(d.getTime()) ? '' : pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }
  function timeInputToIso(val) {
    if (!val) return undefined;
    var now = new Date();
    var d = new Date(now.getFullYear() + '-' + pad2(now.getMonth() + 1) + '-' + pad2(now.getDate()) + 'T' + val + ':00');
    return isNaN(d.getTime()) ? undefined : d.toISOString();
  }

  /* -------------------------------------------------- Calendrier (date/heure) -
     <input type="date"|"datetime-local"> NATIFS affichent le calendrier propre
     au NAVIGATEUR (langue pilotée par l'OS/le navigateur, PAS par la langue de
     la page malgré `<html lang>`, cf. mémoire projet) -- résultat signalé par
     l'utilisateur : "le calendrier ne s'adapte pas toujours" (fiable seulement
     quand la langue du navigateur/OS de la personne coïncide avec celle de
     l'app, ce qui n'est pas garanti). Remplacé par `daterangepicker` (déjà
     chargé sur TOUT le dashboard, layouts/foot.html), un calendrier rendu en
     JS -> sa langue est intégralement sous notre contrôle via `moment.locale()`
     (réglée sur la langue Django active, même fichier foot.html) plutôt que
     dépendante du poste de la personne qui consulte la page.
     `locale.format` reste volontairement un format FIXE, non localisé
     (ex. "YYYY-MM-DD[T]HH:mm") -- ce qui change avec la langue, c'est
     l'AFFICHAGE du calendrier (noms de mois/jours, boutons Appliquer/Annuler),
     jamais le format de la valeur stockée dans l'input : `isoToDateInput`/
     `dateInputToIso` etc. (ci-dessus) n'ont donc besoin d'AUCUN changement,
     ils continuent de lire/écrire exactement le même format qu'avant. */
  function dateRangePickerLocale() {
    var lang = (window.moment && moment.locale && moment.locale()) || 'fr';
    if (lang === 'en') return { applyLabel: 'Apply', cancelLabel: 'Cancel' };
    return { applyLabel: 'Appliquer', cancelLabel: 'Annuler' };
  }

  function initDateRangePicker($input, withTime) {
    if (!$.fn.daterangepicker) return; // repli silencieux si le plugin n'est pas chargé (ex. tests Node/jsdom)
    var loc = dateRangePickerLocale();
    $input.daterangepicker({
      singleDatePicker: true,
      timePicker: !!withTime,
      timePicker24Hour: true,
      timePickerIncrement: 1,
      autoUpdateInput: true,
      showDropdowns: true,
      locale: {
        format: withTime ? 'YYYY-MM-DD[T]HH:mm' : 'YYYY-MM-DD',
        applyLabel: loc.applyLabel,
        cancelLabel: loc.cancelLabel
      }
    });
  }

  /** Noeud d'options dynamiques du champ enfant `key`, sous le noeud parent
   * `dyn` déjà résolu (dyn = { fields: { key: {...} } }) — pas de recalcul de
   * chemin absolu, contrairement à `optionNodeAtPath` de
   * task_cycle_form_logic.js (utilisé côté écriture des règles). */
  function childDyn(dyn, key) {
    return (dyn && dyn.fields && dyn.fields[key]) || {};
  }

  /** Options à afficher pour un select : si le champ a une source dynamique
   * (dataset/cascadeFrom OU choicesFrom — les deux posent `dyn.options` comme
   * un TABLEAU, cf. applyDatasets/applyChoicesFromToOptions), ce tableau fait
   * TOUJOURS foi, MÊME VIDE (ex. cascade dont le parent n'est pas encore
   * choisi -> aucune option, PAS un repli sur `field.choices`, qui porte de
   * toute façon un enum statique souvent vide/périmé pour ce type de champ,
   * cf. form_design.py). Bug réel corrigé ici : `dyn.options.length` était
   * vérifié en plus de `Array.isArray`, faisant retomber un cascade non
   * encore résolu sur `field.choices` au lieu d'afficher "aucune option". */
  function choiceOptions(dyn, choices) {
    if (Array.isArray(dyn.options)) return dyn.options;
    return (choices || []).map(function (c) { return { value: c, text: c }; });
  }

  /* ------------------------------------------- Validation structurelle (E2b) -
     Côté mobile, minLength/maxLength/pattern/min/max/minItems sont de VRAIES
     contraintes tcomb (tcomb-json-schema construit des t.subtype avec des
     prédicats), vérifiées à CHAQUE Form.getValue() — pas seulement quand la
     page a des `rules`/`calculate` déclaratifs. task_cycle_form_logic.js
     (portage de cdd-form-logic.js) ne couvre QUE l'obligatoire piloté par
     règle + le JSON-schema `required`, et seulement si hasDeclarativeLogic —
     cohérent côté mobile (tcomb fait déjà le reste structurellement), mais
     ça laisse un trou côté web (rien d'équivalent à tcomb ici). Ces fonctions
     comblent ce trou : jamais gated par hasDeclarativeLogic, elles tournent à
     CHAQUE goNext(). Pas un portage (aucun équivalent direct côté mobile à
     dupliquer) — logique neuve, mais mêmes règles que tcomb-json-schema. */

  function messageFor(page, leafKey, kind) {
    var m = page && page.messages && page.messages[leafKey];
    return (m && m[kind]) ? m[kind] : null;
  }

  /** `dyn` dont les enfants vivent sous `.item.fields` (répétable) ->
   * ré-emballé pour être parcouru par `childDyn` comme un groupe simple. */
  function itemDynAsGroup(dyn) {
    return { fields: (dyn && dyn.item && dyn.item.fields) || {} };
  }

  function collectConstraintErrors(fields, dyn, values, prefix, page, out, insideRepeat) {
    (fields || []).forEach(function (f) {
      var path = prefix ? prefix + '.' + f.key : f.key;
      var fieldDyn = childDyn(dyn, f.key);
      if (fieldDyn.hidden) return;
      var val = getValueAt(values, path);

      // `walkSchemaRequired` (task_cycle_form_logic.js) couvre le JSON-schema
      // `required` au niveau page, mais saute explicitement les répétables
      // ("hors périmètre v1" -- validation ligne par ligne jamais faite).
      // Résultat avant ce correctif : une ligne de répétable avec un champ
      // "requis" laissé vide n'empêchait PAS de passer à la page suivante
      // (reproduit avec les vraies données de la tâche 16 : ajouter une ligne
      // "Directeur" vide passait outre malgré `"required":["Nom"]`). Comme
      // cette fonction descend déjà dans chaque ligne pour les autres
      // contraintes, elle couvre aussi le "requis" MAIS SEULEMENT à
      // l'intérieur d'un répétable (le niveau page reste couvert par
      // `validateSchemaRequired`, pas dupliqué ici).
      if (insideRepeat && f.required && (f.type === 'text' || f.type === 'integer' || f.type === 'decimal' ||
          f.type === 'select_one' || f.type === 'date' || f.type === 'datetime' || f.type === 'time' || f.type === 'geopoint') &&
          L.isEmpty(val)) {
        out.push({ path: path, message: messageFor(page, f.key, 'required') || 'Ce champ est obligatoire.' });
      }

      if (f.type === 'group') {
        collectConstraintErrors(f.children, fieldDyn, values, path, page, out, insideRepeat);
        return;
      }
      if (f.type === 'repeat') {
        var arr = Array.isArray(val) ? val : [];
        if (f.minItems != null && arr.length < f.minItems) {
          out.push({ path: path, message: messageFor(page, f.key, 'range') });
        }
        arr.forEach(function (rowVal, i) {
          collectConstraintErrors(f.children, itemDynAsGroup(fieldDyn), values, path + '.' + i, page, out, true);
        });
        return;
      }
      if (f.type === 'text' && val != null && val !== '') {
        var str = String(val);
        if (f.minLength != null && str.length < f.minLength) {
          out.push({ path: path, message: messageFor(page, f.key, 'regex') || messageFor(page, f.key, 'range') });
        }
        if (f.pattern) {
          var re = null;
          try { re = new RegExp(f.pattern); } catch (e) { re = null; }
          if (re && !re.test(str)) {
            out.push({ path: path, message: messageFor(page, f.key, 'regex') });
          }
        }
      } else if ((f.type === 'integer' || f.type === 'decimal') && val != null && val !== '') {
        var num = Number(val);
        if (!isNaN(num)) {
          if ((f.min != null && num < f.min) || (f.max != null && num > f.max)) {
            out.push({ path: path, message: messageFor(page, f.key, 'range') });
          }
        }
      } else if (f.type === 'select_multiple' || f.type === 'select_multiple_check') {
        if (f.minItems != null) {
          var selArr = Array.isArray(val) ? val : [];
          if (selArr.length < f.minItems) {
            out.push({ path: path, message: messageFor(page, f.key, 'range') });
          }
        }
      }
    });
  }

  /** Marque en rouge, DIRECTEMENT dans le DOM déjà rendu, chaque champ en
   * erreur (`{path, message}`) — via `data-field-path`/`data-path`, PAS par
   * mutation de l'arbre `dynOptions` (qui n'a pas de notion d'index de ligne
   * pour un répétable : "monRepetable.0.champ" n'a pas de correspondance 1:1
   * dans dynOptions.fields, seulement dynOptions.fields.monRepetable.item.
   * fields.champ, PARTAGÉ par toutes les lignes) — fonctionne donc de façon
   * uniforme pour les champs simples ET les champs dans un répétable. */
  function applyDomErrors($area, errors, fallbackMsg) {
    errors.forEach(function (e) {
      var sel = '[data-field-path="' + String(e.path).replace(/"/g, '\\"') + '"]';
      var $el = $area.find(sel).first();
      if (!$el.length) return;
      $el.addClass('is-invalid');
      var $wrap = $el.closest('.tcf-field');
      if (!$wrap.length) $wrap = $el.parent();
      $wrap.find('.tcf-error-msg').remove();
      $wrap.append('<div class="invalid-feedback d-block tcf-error-msg">' + esc(e.message || fallbackMsg) + '</div>');
    });
  }

  /** Rend UN champ (feuille ou conteneur) en jQuery, wrapping .form-group. */
  function renderField(field, path, value, dyn, ctx) {
    dyn = dyn || {};
    if (dyn.hidden) return $();

    if (field.type === 'group') {
      return renderGroup(field, path, value || {}, dyn, ctx);
    }
    if (field.type === 'repeat') {
      return renderRepeat(field, path, value || [], dyn, ctx);
    }
    if (field.type === 'note') {
      return $('<div class="form-group"><p class="text-muted">' + esc(field.label) + '</p></div>');
    }

    var required = dyn.__ruleRequired != null ? (dyn.__ruleRequired || field.required) : field.required;
    var disabled = !!dyn.disabled;
    var $wrap = $('<div class="form-group tcf-field" data-path="' + esc(path) + '"></div>');
    var $label = $('<label></label>').attr('for', domId(path)).text(field.label + (required ? ' *' : ''));
    $wrap.append($label);
    if (field.help) $wrap.append('<small class="form-text text-muted mb-1">' + esc(field.help) + '</small>');

    var $input;
    switch (field.type) {
      case 'select_one': {
        $input = $('<select class="form-control"></select>');
        $input.append('<option value="">—</option>');
        choiceOptions(dyn, field.choices).forEach(function (o) {
          var $o = $('<option></option>').attr('value', o.value).text(o.text);
          if (String(value) === String(o.value)) $o.attr('selected', 'selected');
          $input.append($o);
        });
        break;
      }
      case 'select_multiple':
        // Parité mobile : tcomb-form-native rend un select_multiple (sans
        // mode "checklist") comme une LISTE ajout/suppression, une ligne =
        // un menu déroulant simple (t.list de t.enums, components.js) — PAS
        // un <select multiple> natif (ctrl/cmd-clic), interaction différente
        // que l'utilisateur mobile ne reconnaîtrait pas. cf. renderMultiSelect.
        return renderMultiSelect(field, path, value, dyn, ctx, $wrap);
      case 'select_multiple_check': {
        $input = $('<div class="tcf-checklist"></div>');
        var checkedVals = Array.isArray(value) ? value.map(String) : [];
        choiceOptions(dyn, field.choices).forEach(function (o, i) {
          var cid = domId(path) + '_' + i;
          var $c = $(
            '<div class="form-check">' +
              '<input class="form-check-input" type="checkbox" value="' + esc(o.value) + '" id="' + cid + '">' +
              '<label class="form-check-label" for="' + cid + '">' + esc(o.text) + '</label>' +
            '</div>'
          );
          if (checkedVals.indexOf(String(o.value)) !== -1) $c.find('input').prop('checked', true);
          $input.append($c);
        });
        break;
      }
      case 'integer':
      case 'decimal': {
        $input = $('<input class="form-control" type="number">');
        if (field.type === 'decimal') $input.attr('step', 'any'); else $input.attr('step', '1');
        if (field.min != null) $input.attr('min', field.min);
        if (field.max != null) $input.attr('max', field.max);
        if (value != null) $input.val(value);
        break;
      }
      case 'date':
        // input texte + daterangepicker (pas <input type="date"> natif) :
        // calendrier rendu en JS, langue pilotée par `moment.locale()` (donc
        // par la langue Django active) plutôt que par le navigateur/OS de la
        // personne -- cf. dateRangePickerLocale/initDateRangePicker ci-dessus.
        $input = $('<input class="form-control" type="text" readonly autocomplete="off">');
        if (value) $input.val(isoToDateInput(value));
        initDateRangePicker($input, false);
        break;
      case 'datetime':
        $input = $('<input class="form-control" type="text" readonly autocomplete="off">');
        if (value) $input.val(isoToDatetimeInput(value));
        initDateRangePicker($input, true);
        break;
      case 'time':
        $input = $('<input class="form-control" type="time">');
        if (value) $input.val(isoToTimeInput(value));
        break;
      case 'geopoint':
        return renderGeopoint(field, path, value, dyn, ctx, $wrap);
      default: {
        $input = (field.maxLength && field.maxLength > 160)
          ? $('<textarea class="form-control" rows="3"></textarea>')
          : $('<input class="form-control" type="text">');
        if (field.maxLength) $input.attr('maxlength', field.maxLength);
        if (field.pattern) $input.attr('pattern', field.pattern);
        if (value != null) $input.val(value);
      }
    }
    $input.attr('id', domId(path)).attr('name', path).attr('data-field-path', path);
    if (disabled) $input.prop('disabled', true);
    $wrap.append($input);
    $input.on('change input', function () {
      ctx.onFieldChange(path, readInputValue(field, $input));
    });
    return $wrap;
  }

  /** select_multiple (sans mode "checklist") : liste ajout/suppression, une
   * ligne = un menu déroulant simple — même interaction que tcomb-form-native
   * (t.list de t.enums), pas un <select multiple> natif. */
  function renderMultiSelect(field, path, value, dyn, ctx, $wrap) {
    $wrap.attr('data-field-path', path);
    var $rows = $('<div class="tcf-multi-rows"></div>');
    $wrap.append($rows);

    function notify() {
      var vals = [];
      $rows.find('select').each(function () {
        var v = $(this).val();
        if (v !== '' && v != null) vals.push(v);
      });
      ctx.onFieldChange(path, vals);
    }

    function addRow(val) {
      var $row = $('<div class="d-flex align-items-center mb-1" style="gap:.4rem;"></div>');
      var $sel = $('<select class="form-control"></select>');
      $sel.append('<option value="">—</option>');
      choiceOptions(dyn, field.choices).forEach(function (o) {
        var $o = $('<option></option>').attr('value', o.value).text(o.text);
        if (val != null && String(val) === String(o.value)) $o.attr('selected', 'selected');
        $sel.append($o);
      });
      $sel.on('change', notify);
      var $rm = $('<button type="button" class="btn btn-sm btn-outline-danger"><i class="fas fa-times"></i></button>');
      $rm.on('click', function () { $row.remove(); notify(); });
      $row.append($sel).append($rm);
      $rows.append($row);
    }

    (Array.isArray(value) ? value : []).forEach(function (v) { addRow(v); });

    var $add = $('<button type="button" class="btn btn-sm btn-outline-primary"><i class="fas fa-plus"></i> ' + esc(ctx.i18n.addChoice) + '</button>');
    $add.on('click', function () { addRow(null); });
    $wrap.append($add);
    return $wrap;
  }

  function readInputValue(field, $input) {
    switch (field.type) {
      case 'select_multiple_check':
        return $input.find('input:checked').map(function () { return $(this).val(); }).get();
      case 'integer':
        return $input.val() === '' ? undefined : parseInt($input.val(), 10);
      case 'decimal':
        return $input.val() === '' ? undefined : parseFloat($input.val());
      case 'date':
        return dateInputToIso($input.val());
      case 'datetime':
        return datetimeInputToIso($input.val());
      case 'time':
        return timeInputToIso($input.val());
      default:
        return $input.val() === '' ? undefined : $input.val();
    }
  }

  function renderGroup(field, path, value, dyn, ctx) {
    var $fs = $('<fieldset class="tcf-group border rounded p-3 mb-3" data-path="' + esc(path) + '"></fieldset>');
    $fs.append('<legend class="tcf-group-title" style="font-size:1rem;font-weight:700;">' + esc(field.label) + '</legend>');
    (field.children || []).forEach(function (child) {
      var childPath = path + '.' + child.key;
      var $f = renderField(child, childPath, value ? value[child.key] : undefined, childDyn(dyn, child.key), ctx);
      $fs.append($f);
    });
    return $fs;
  }

  /** Options dynamiques (dataset/rules/choicesFrom/crossTaskVisibility) d'un
   * champ enfant DANS un répétable : vivent sous `dyn.item.fields` (mirroir
   * tcomb `t.list`, un seul jeu d'options partagé par toutes les lignes — pas
   * par index de ligne), PAS `dyn.fields` (réservé aux groupes simples). Sans
   * ceci, tout champ à source dynamique/règle/choicesFrom DANS un répétable
   * perdait silencieusement ses options (bug réel trouvé en audit). */
  function itemChildDyn(dyn, key) {
    return (dyn && dyn.item && dyn.item.fields && dyn.item.fields[key]) || {};
  }

  function renderRepeat(field, path, values, dyn, ctx) {
    values = Array.isArray(values) ? values : [];
    var $wrap = $('<div class="tcf-repeat mb-3" data-path="' + esc(path) + '"></div>');
    $wrap.append('<label>' + esc(field.label) + (field.required ? ' *' : '') + '</label>');
    var $rows = $('<div class="tcf-repeat-rows"></div>');
    $wrap.append($rows);

    function renderRow(rowValue, index) {
      var rowPath = path + '.' + index;
      var $row = $('<div class="tcf-repeat-row border rounded p-3 mb-2"></div>');
      var $head = $('<div class="d-flex justify-content-between align-items-center mb-2"></div>');
      $head.append('<b>' + esc(field.label) + ' #' + (index + 1) + '</b>');
      var $rm = $('<button type="button" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></button>');
      $rm.on('click', function () {
        var arr = getValueAt(ctx.state.values[ctx.pageIndex], path) || [];
        arr.splice(index, 1);
        ctx.rerender();
      });
      $head.append($rm);
      $row.append($head);
      (field.children || []).forEach(function (child) {
        var childPath = rowPath + '.' + child.key;
        var $f = renderField(child, childPath, rowValue ? rowValue[child.key] : undefined, itemChildDyn(dyn, child.key), ctx);
        $row.append($f);
      });
      $rows.append($row);
    }

    values.forEach(renderRow);

    var maxReached = field.maxItems != null && values.length >= field.maxItems;
    var addLabel = (field.i18n && field.i18n.add) || ctx.i18n.addRow;
    var $add = $('<button type="button" class="btn btn-sm btn-outline-primary"><i class="fas fa-plus"></i> ' + esc(addLabel) + '</button>');
    if (maxReached) $add.prop('disabled', true);
    $add.on('click', function () {
      var arr = getValueAt(ctx.state.values[ctx.pageIndex], path);
      if (!Array.isArray(arr)) { arr = []; L.setPath(ctx.state.values[ctx.pageIndex], path, arr); }
      arr.push({});
      ctx.rerender();
    });
    $wrap.append($add);
    return $wrap;
  }

  function renderGeopoint(field, path, value, dyn, ctx, $wrap) {
    var $status = $('<div class="tcf-geopoint-status small text-muted"></div>');
    if (value && value.latitude != null) {
      $status.text(value.latitude.toFixed(6) + ', ' + value.longitude.toFixed(6) +
        (value.accuracy != null ? ' (± ' + Math.round(value.accuracy) + ' m)' : ''));
    } else {
      $status.text(ctx.i18n.noLocationYet);
    }
    var $btn = $('<button type="button" class="btn btn-sm btn-outline-primary"><i class="fas fa-map-marker-alt"></i> ' + esc(ctx.i18n.captureLocation) + '</button>');
    $btn.on('click', function () {
      if (!navigator.geolocation) { $status.text(ctx.i18n.geolocationUnavailable); return; }
      $btn.prop('disabled', true).text(ctx.i18n.capturing);

      // Parité mobile (getBestLocation, functions_geolocation.tsx) : mobile
      // RETENTE jusqu'à atteindre accuracyThreshold ou expiration d'un délai,
      // pas une seule lecture — une unique getCurrentPosition() (comme avant
      // ce correctif) accepte une précision bien pire pour le même seuil
      // affiché à l'utilisateur ("Précision requise" dans le form builder).
      // Ici : watchPosition() garde le MEILLEUR relevé vu, s'arrête dès que
      // le seuil est atteint ou après maxDurationMs.
      var threshold = field.accuracyThreshold || 20;
      var maxDurationMs = 20000;
      var best = null;
      var watchId = null;
      var finished = false;
      var timeoutHandle = null;

      function finish() {
        if (finished) return;
        finished = true;
        if (timeoutHandle) clearTimeout(timeoutHandle);
        if (watchId != null && navigator.geolocation.clearWatch) navigator.geolocation.clearWatch(watchId);
        if (best) {
          ctx.onFieldChange(path, best);
          $status.text(best.latitude.toFixed(6) + ', ' + best.longitude.toFixed(6) +
            (best.accuracy != null ? ' (± ' + Math.round(best.accuracy) + ' m)' : ''));
        } else {
          $status.text(ctx.i18n.geolocationFailed);
        }
        $btn.prop('disabled', false).text(ctx.i18n.captureLocation);
      }

      function onPosition(pos) {
        var c = pos.coords;
        var captured = {
          latitude: c.latitude, longitude: c.longitude, accuracy: c.accuracy,
          altitude: c.altitude, altitudeAccuracy: c.altitudeAccuracy,
          heading: c.heading, speed: c.speed,
          timestamp: pos.timestamp, captured_at: new Date().toISOString()
        };
        if (!best || (captured.accuracy != null && (best.accuracy == null || captured.accuracy < best.accuracy))) {
          best = captured;
        }
        if (captured.accuracy != null && captured.accuracy <= threshold) {
          finish();
        }
      }

      timeoutHandle = setTimeout(finish, maxDurationMs);
      if (navigator.geolocation.watchPosition) {
        watchId = navigator.geolocation.watchPosition(onPosition, function () { /* erreur ponctuelle ignorée, on retente jusqu'au timeout */ },
          { enableHighAccuracy: true, maximumAge: 0, timeout: maxDurationMs });
      } else {
        // Pas de watchPosition -> un seul relevé possible, rien à attendre de
        // plus : termine tout de suite avec ce relevé (même imprécis) au lieu
        // d'attendre inutilement maxDurationMs.
        navigator.geolocation.getCurrentPosition(function (pos) { onPosition(pos); finish(); }, finish,
          { enableHighAccuracy: true, maximumAge: 0, timeout: maxDurationMs });
      }
    });
    $wrap.append($status).append($btn);
    return $wrap;
  }

  /* ---------------------------------------------------------- E6 : contrôleur */

  var DEFAULT_I18N = {
    addRow: 'Ajouter une ligne',
    addChoice: 'Ajouter un choix',
    noLocationYet: 'Aucune position capturée',
    captureLocation: 'Capturer la position',
    capturing: 'Capture en cours…',
    geolocationUnavailable: 'Géolocalisation indisponible sur ce navigateur',
    geolocationFailed: 'Échec de la capture de position',
    requiredFieldsMissing: 'Merci de renseigner les champs obligatoires en rouge.',
    invalidValue: 'Valeur non valide.',
    next: 'Suivant',
    previous: 'Précédent',
    // "Enregistrer", pas "Terminer" : ce bouton SAUVEGARDE le formulaire (dernière
    // page), une action distincte de "Marquer comme terminée" (bascule
    // task.completed, cf. le bouton dédié ajouté dans l'en-tête du modal,
    // cvd_list.html) — les 2 portaient le même libellé "Terminer" avant,
    // ambiguïté signalée par l'utilisateur (2 actions différentes, mobile les
    // distingue aussi : Form.getValue()/Next vs le bouton jaune "Marquer...").
    submit: 'Enregistrer',
    attachmentsTitle: 'Pièces jointes',
    viewFile: 'Voir le fichier',
    noFileYet: 'Aucun fichier',
    uploading: 'Envoi en cours…',
    uploadError: "Échec de l'envoi du fichier."
  };

  /**
   * Contrôleur d'un formulaire multi-pages.
   * opts = {
   *   form: [...pages stockées...],
   *   initialResponses: [...valeurs par page déjà saisies...] | [],
   *   i18n: {...} (surcharge partielle de DEFAULT_I18N),
   *   onSubmit: function(allResponses, attachments) {...} (dernière page validée),
   *   fetchExternalTask: function(sourceTaskId, cb) {...} (E4 : résout cb(doc|null)
   *     -- {form, form_response} d'une AUTRE tâche, requis par les pages ayant
   *     `choicesFrom`/`crossTaskVisibility` avec sourceTaskId ; optionnel, ignoré
   *     si aucune page n'en a besoin),
   *   attachments: [...slots Task.attachments...] (E5, optionnel),
   *   existingAttachments: [...doc.attachments déjà saisi...] (E5, optionnel),
   *   uploadFile: function(file, cb) {...} (E5 : cb(url|null, name) après upload S3)
   * }
   */
  function FillFormController($container, opts) {
    this.$container = $container;
    this.form = opts.form || [];
    this.i18n = $.extend({}, DEFAULT_I18N, opts.i18n || {});
    this.onSubmit = opts.onSubmit || function () {};
    this.fetchExternalTask = opts.fetchExternalTask || null;
    this.externalDocs = {}; // sourceTaskId -> {form, form_response} | null (cache, jamais re-fetché)
    this.attachmentSlots = opts.attachments || [];
    this.uploadFile = opts.uploadFile || null;
    this.state = {
      values: (opts.initialResponses || []).map(function (v) { return v || {}; }),
      attachments: (opts.existingAttachments || []).map(function (a) { return a || {}; })
    };
    while (this.state.values.length < this.form.length) this.state.values.push({});
    while (this.state.attachments.length < this.attachmentSlots.length) this.state.attachments.push({});
    this.pageIndex = 0;
    var self = this;
    this.ctx = {
      i18n: this.i18n,
      state: this.state,
      get pageIndex() { return self.pageIndex; },
      onFieldChange: function (path, val) { self.handleFieldChange(path, val); },
      rerender: function () { self.render(); }
    };
    this.$pageArea = $('<div class="tcf-page-area"></div>');
    this.$attachmentsArea = $('<div class="tcf-attachments-area"></div>');
    this.$container.empty().append(this.$pageArea).append(this.$attachmentsArea);
    this.render();
  }

  FillFormController.prototype.currentPage = function () { return this.form[this.pageIndex] || { options: {}, page: { properties: {} } }; };

  /** IDs de tâches externes requis par `page` et pas encore en cache ->
   * les récupère via `this.fetchExternalTask`, puis appelle `done()` (jamais
   * de fetch réseau si tout est déjà en cache -> `done()` synchrone). */
  FillFormController.prototype.ensureExternalDocs = function (page, done) {
    var self = this;
    var CT = window.TCCrossTask;
    var ids = (CT ? CT.externalTaskIdsFor(page.choicesFrom) : [])
      .concat(CT ? CT.externalTaskIdsForCrossTaskVisibility(page.crossTaskVisibility) : []);
    ids = ids.filter(function (id, i) { return ids.indexOf(id) === i; });
    var missing = ids.filter(function (id) { return !(id in self.externalDocs); });
    if (!missing.length || !this.fetchExternalTask) { done(); return; }
    var remaining = missing.length;
    missing.forEach(function (id) {
      self.fetchExternalTask(id, function (doc) {
        self.externalDocs[id] = doc || null;
        remaining -= 1;
        if (remaining === 0) done();
      });
    });
  };

  /** `TCFormLogic.buildDynamicOptions` (règles/calculs/datasets) PUIS
   * `choicesFrom`/`crossTaskVisibility` (E4) appliqués par-dessus — même
   * ordre que mobile (TaskDetail.tsx `toggleFields`). */
  FillFormController.prototype.buildFullDynOptions = function (page, values) {
    var dynOptions = L.buildDynamicOptions(page, values, this.state.values, {});
    var CT = window.TCCrossTask;
    if (CT) {
      CT.applyChoicesFromToOptions(page.choicesFrom, dynOptions.fields, {
        currentPageIndex: this.pageIndex, currentPageValue: values,
        task: { form: this.form, form_response: this.state.values },
        externalDocs: this.externalDocs
      });
      CT.applyCrossTaskVisibilityToOptions(page.crossTaskVisibility, dynOptions.fields, this.externalDocs);
    }
    return dynOptions;
  };

  FillFormController.prototype.handleFieldChange = function (path, val) {
    var page = this.currentPage();
    var values = this.state.values[this.pageIndex];
    L.setPath(values, path, val);
    values = L.applyCalculations(page, values);
    // Vide la valeur d'un select "enfant de cascade" (dataset+cascadeFrom) dont
    // le parent vient de changer et dont l'option choisie n'existe plus dans la
    // nouvelle liste filtrée — sans ça, le <select> affiche une valeur qui ne
    // correspond plus à aucune <option> tout en gardant l'ancienne valeur en
    // mémoire (soumise telle quelle si l'utilisateur ne re-touche pas le champ).
    // Même mécanisme que mobile (Form.render(), components.js).
    //
    // Bouclé jusqu'à stabilité (testé en direct sur une VRAIE cascade à 5
    // niveaux, région -> préfecture -> commune -> canton -> village, tâche 102) :
    // un seul passage ne purge QUE le niveau immédiatement sous le champ
    // modifié — les options d'un PETIT-ENFANT sont calculées à partir de la
    // valeur ENCORE PRÉSENTE (pas encore purgée) de son parent direct au
    // moment de ce même passage, donc un enfant "de 2e génération" peut
    // survivre à tort. Rebâtir dynOptions puis re-purger à partir des valeurs
    // déjà purgées propage la purge de proche en proche. Borné (profondeur de
    // cascade raisonnable) pour ne jamais boucler indéfiniment.
    for (var i = 0; i < 6; i++) {
      var dynOptions = this.buildFullDynOptions(page, values);
      var pruned = L.pruneStaleCascadeValues(dynOptions, values);
      if (pruned === values) break;
      values = pruned;
    }
    this.state.values[this.pageIndex] = values;
    this.render();
  };

  FillFormController.prototype.render = function () {
    var self = this;
    var page = this.currentPage();
    this.ensureExternalDocs(page, function () { self._renderNow(); });
  };

  FillFormController.prototype._renderNow = function () {
    var page = this.currentPage();
    var values = this.state.values[this.pageIndex] || {};
    var dynOptions = this.buildFullDynOptions(page, values);
    var fields = parsePageFields(page);

    var $form = $('<div class="tcf-page"></div>');
    var self = this;
    fields.forEach(function (f) {
      var $el = renderField(f, f.key, values[f.key], childDyn(dynOptions, f.key), self.ctx);
      $form.append($el);
    });

    this.$pageArea.empty().append($form);
    this.renderNav();
    this.renderAttachments();
  };

  FillFormController.prototype.renderNav = function () {
    var $nav = $('<div class="tcf-nav d-flex justify-content-between mt-3"></div>');
    var self = this;
    if (this.pageIndex > 0) {
      var $prev = $('<button type="button" class="btn btn-outline-secondary">' + esc(this.i18n.previous) + '</button>');
      $prev.on('click', function () { self.pageIndex -= 1; self.render(); });
      $nav.append($prev);
    } else {
      $nav.append('<span></span>');
    }
    var isLast = this.pageIndex >= this.form.length - 1;
    var $next = $('<button type="button" class="btn btn-primary">' + esc(isLast ? this.i18n.submit : this.i18n.next) + '</button>');
    $next.on('click', function () { self.goNext(); });
    $nav.append($next);
    this.$pageArea.append($nav);
  };

  /** Obligatoire (schéma + règles) TOUJOURS vérifié — contrairement à
   * `L.checkPageRequired` (gaté par `hasDeclarativeLogic`, correct côté
   * mobile où tcomb fait déjà ce travail structurellement en son absence,
   * mais rien d'équivalent n'existe ici) — on appelle directement les 2
   * fonctions ungated qu'il enveloppe. Combiné aux contraintes
   * minLength/maxLength/pattern/min/max/minItems (`collectConstraintErrors`,
   * jamais couvertes par le portage `cdd-form-logic.js`, qui ne gère QUE
   * l'obligatoire). */
  FillFormController.prototype.validatePage = function (page, values, dynOptions) {
    var missing = L.validateSchemaRequired(page, values, dynOptions)
      .concat(L.validateRuleRequired(dynOptions, values));
    missing = missing.filter(function (p, i) { return missing.indexOf(p) === i; });

    var constraintErrors = [];
    collectConstraintErrors(parsePageFields(page), dynOptions, values, '', page, constraintErrors);

    return { missing: missing, constraintErrors: constraintErrors };
  };

  /** Supprime, dans `values`, la valeur de tout champ ACTUELLEMENT masqué par
   * une règle `hide` (`dyn.hidden`) — mirroir de `Struct.validate`/
   * `List.validate` côté mobile (`components.js`, tcomb-form-native) : quand
   * un ref est marqué `hidden`, mobile ne recopie tout simplement PAS sa
   * valeur dans l'objet assemblé par `getValue()`, appelé à CHAQUE
   * Suivant/Précédent (`TaskDetail.tsx`) — donc une réponse déjà saisie sur
   * un champ qui redevient masqué (l'utilisateur change son avis sur le
   * champ parent) est PERDUE côté mobile dès le prochain Suivant. Sans ce
   * correctif, le web GARDAIT cette valeur périmée en mémoire et la
   * soumettait quand même (bug réel trouvé en audit, jamais rencontré avant
   * faute de tâche réelle avec une règle show/hide ET des données
   * pré-existantes sur le champ masqué). */
  function pruneHiddenValues(fields, dyn, values) {
    (fields || []).forEach(function (f) {
      if (!values || !Object.prototype.hasOwnProperty.call(values, f.key)) return;
      var fieldDyn = childDyn(dyn, f.key);
      if (fieldDyn.hidden) {
        delete values[f.key];
        return;
      }
      if (f.type === 'group' && values[f.key]) {
        pruneHiddenValues(f.children, fieldDyn, values[f.key]);
      } else if (f.type === 'repeat' && Array.isArray(values[f.key])) {
        values[f.key].forEach(function (row) {
          pruneHiddenValues(f.children, itemDynAsGroup(fieldDyn), row);
        });
      }
    });
  }

  FillFormController.prototype.goNext = function () {
    var page = this.currentPage();
    var values = this.state.values[this.pageIndex] || {};
    var dynOptions = this.buildFullDynOptions(page, values);
    var result = this.validatePage(page, values, dynOptions);
    if (result.missing.length || result.constraintErrors.length) {
      this._renderNow();
      var missingErrors = result.missing.map(function (p) { return { path: p, message: null }; });
      applyDomErrors(this.$pageArea, missingErrors, this.i18n.requiredFieldsMissing);
      applyDomErrors(this.$pageArea, result.constraintErrors, this.i18n.invalidValue);
      return;
    }
    pruneHiddenValues(parsePageFields(page), dynOptions, values);
    this.state.values[this.pageIndex] = values;
    if (this.pageIndex < this.form.length - 1) {
      this.pageIndex += 1;
      this.render();
    } else {
      this.onSubmit(this.state.values, this.state.attachments);
    }
  };

  /* --------------------------------------------------------------- E5 : pièces jointes */

  FillFormController.prototype.renderAttachments = function () {
    if (!this.attachmentSlots.length) { this.$attachmentsArea.empty(); return; }
    var self = this;
    var AC = window.TCAttachmentConditions;
    var $wrap = $('<div class="tcf-attachments mt-3 pt-3 border-top"></div>');
    $wrap.append('<h6>' + esc(this.i18n.attachmentsTitle) + '</h6>');

    this.attachmentSlots.forEach(function (slot, i) {
      var evalRes = AC
        ? AC.evaluateAttachmentConditions(slot, self.state.values, self.externalDocs)
        : { hidden: false, required: !slot.optional };
      if (evalRes.hidden) return;

      var current = self.state.attachments[i] || {};
      var $row = $('<div class="tcf-attachment-row form-group" data-slot-index="' + i + '"></div>');
      $row.append('<label>' + esc(slot.name) + (evalRes.required ? ' *' : '') + '</label>');

      var $status = $('<div class="small mb-1"></div>');
      if (current.attachment && current.attachment.uri) {
        $status.html('<a href="' + esc(current.attachment.uri) + '" target="_blank" rel="noopener">'
          + '<i class="fas fa-paperclip"></i> ' + esc(current.attachment.name || self.i18n.viewFile) + '</a>');
      } else {
        $status.addClass('text-muted').text(self.i18n.noFileYet);
      }
      $row.append($status);

      var $input = $('<input type="file" class="form-control-file">');
      var accept = slot.type === 'photos' ? 'image/*' : (slot.type === 'video' ? 'video/*' : (slot.type === 'audio' ? 'audio/*' : ''));
      if (accept) $input.attr('accept', accept);
      var $spin = $('<span class="ml-2" style="display:none;"><i class="fas fa-sync-alt fa-spin"></i> ' + esc(self.i18n.uploading) + '</span>');

      $input.on('change', function () {
        var file = this.files && this.files[0];
        if (!file) return;
        if (!self.uploadFile) return;
        $spin.show();
        self.uploadFile(file, function (url, name) {
          $spin.hide();
          if (!url) { alert(self.i18n.uploadError); return; }
          self.state.attachments[i] = { name: slot.name, attachment: { uri: url, name: name || file.name } };
          self.renderAttachments();
        });
      });
      $row.append($input).append($spin);
      $wrap.append($row);
    });

    this.$attachmentsArea.empty().append($wrap);
  };

  window.TCFillForm = {
    parsePageFields: parsePageFields,
    FillFormController: FillFormController
  };
})(typeof window !== 'undefined' ? window : this, typeof jQuery !== 'undefined' ? jQuery : null);
