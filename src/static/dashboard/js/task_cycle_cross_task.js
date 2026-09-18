/**
 * Portage web (quasi verbatim) de src/utils/choicesFrom.ts +
 * src/utils/crossTaskVisibility.ts (cdd-frontend) : options d'un select
 * construites depuis la réponse d'un AUTRE champ (même tâche ou tâche
 * différente), et visibilité d'un champ/d'une tâche pilotée par la réponse
 * d'une AUTRE tâche. Résolu entièrement ici (jamais d'accès CouchDB direct
 * depuis le navigateur — la page hôte fournit un callback `fetchExternalTask`
 * qui passe par l'endpoint Django `TaskFormFetchView`, déjà utilisé pour
 * charger la tâche courante).
 *
 * `relaxChoicesFromSchema` (mobile) n'est PAS porté : c'est un correctif
 * spécifique à la validation JSON-schema statique de tcomb-form-native, que
 * ce moteur web n'utilise pas (task_cycle_fill_form.js lit directement les
 * options résolues, jamais un `enum` figé).
 */
(function (window) {
  'use strict';

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

  function isEmpty(v) {
    return v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0);
  }

  function toNumber(v) {
    if (typeof v === 'number') return v;
    var n = parseFloat(v);
    return isNaN(n) ? NaN : n;
  }

  /* ============================================================ choicesFrom */

  function parseSourcePathChoices(sourcePath) {
    if (sourcePath && sourcePath.charAt(0) === '$') {
      var dot = sourcePath.indexOf('.');
      var idx = parseInt(sourcePath.slice(1, dot === -1 ? undefined : dot), 10);
      var rest = dot === -1 ? '' : sourcePath.slice(dot + 1);
      return { pageIndex: isNaN(idx) ? null : idx, rest: rest };
    }
    return { pageIndex: null, rest: sourcePath };
  }

  function descendOptionsFields(fieldsOptions, path) {
    var parts = String(path).split('.');
    var cur = fieldsOptions;
    for (var i = 0; i < parts.length; i++) {
      if (!cur || typeof cur !== 'object') return null;
      var node = cur[parts[i]];
      if (!node) return null;
      if (i === parts.length - 1) return node;
      cur = node.fields || (node.item && node.item.fields);
    }
    return null;
  }

  function labelsForField(designDoc, pageIndex, fieldPath) {
    var page = designDoc && designDoc.form && designDoc.form[pageIndex];
    var node = descendOptionsFields(page && page.options && page.options.fields, fieldPath);
    var list = node && node.options;
    if (!Array.isArray(list)) return null;
    var map = {};
    list.forEach(function (o) {
      if (o && o.value != null) map[String(o.value)] = o.text != null ? String(o.text) : String(o.value);
    });
    return map;
  }

  function resolveChoicesFrom(entry, ctx) {
    var parsed = parseSourcePathChoices(entry.sourcePath);
    var pageIndex = parsed.pageIndex, rest = parsed.rest;

    var designDoc, effectivePageIndex, rawValue;

    if (entry.sourceTaskId) {
      designDoc = ctx.externalDocs[entry.sourceTaskId];
      if (!designDoc || pageIndex == null) return [];
      effectivePageIndex = pageIndex;
      rawValue = resolvePath((designDoc.form_response || [])[pageIndex], rest);
    } else if (pageIndex != null) {
      designDoc = ctx.task;
      effectivePageIndex = pageIndex;
      rawValue = resolvePath((ctx.task.form_response || [])[pageIndex], rest);
    } else {
      designDoc = ctx.task;
      effectivePageIndex = ctx.currentPageIndex;
      rawValue = resolvePath(ctx.currentPageValue, entry.sourcePath);
    }

    var rawValues = Array.isArray(rawValue) ? rawValue : (rawValue != null && rawValue !== '' ? [rawValue] : []);
    var values = rawValues.filter(function (v) { return v != null && v !== ''; });
    if (!values.length) return [];

    var sourceFieldPath = pageIndex != null ? rest : entry.sourcePath;
    var labelMap = designDoc ? labelsForField(designDoc, effectivePageIndex, sourceFieldPath) : null;

    return values.map(function (v) {
      var key = String(v);
      return { value: key, text: (labelMap && labelMap[key] != null) ? labelMap[key] : key };
    });
  }

  function applyChoicesFromToOptions(choicesFrom, fieldsOptions, ctx) {
    if (!Array.isArray(choicesFrom) || !choicesFrom.length || !fieldsOptions) return;
    choicesFrom.forEach(function (entry) {
      if (!entry || !entry.path) return;
      var target = descendOptionsFields(fieldsOptions, entry.path);
      if (!target) return;
      var resolved = resolveChoicesFrom(entry, ctx);
      target.options = resolved;
      target.item = (target.item && typeof target.item === 'object') ? target.item : {};
      target.item.options = resolved;
    });
  }

  function externalTaskIdsFor(choicesFrom) {
    if (!Array.isArray(choicesFrom)) return [];
    var ids = [];
    choicesFrom.forEach(function (entry) {
      if (entry && entry.sourceTaskId && ids.indexOf(entry.sourceTaskId) === -1) ids.push(entry.sourceTaskId);
    });
    return ids;
  }

  /* ===================================================== crossTaskVisibility */

  function parseSourcePathVisibility(sourcePath) {
    if (!sourcePath || sourcePath.charAt(0) !== '$') return { pageIndex: null, rest: '' };
    var dot = sourcePath.indexOf('.');
    var idx = parseInt(sourcePath.slice(1, dot === -1 ? undefined : dot), 10);
    var rest = dot === -1 ? '' : sourcePath.slice(dot + 1);
    return { pageIndex: isNaN(idx) ? null : idx, rest: rest };
  }

  function evaluateOp(op, actual, expected) {
    switch (op) {
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

  function evaluateCrossTaskCondition(entry, sourceDoc) {
    if (!entry) return true;
    var parsed = parseSourcePathVisibility(entry.sourcePath);
    var pageIndex = parsed.pageIndex, rest = parsed.rest;
    var resolved = (sourceDoc && pageIndex != null)
      ? resolvePath((sourceDoc.form_response || [])[pageIndex], rest)
      : undefined;

    if (!sourceDoc || pageIndex == null || isEmpty(resolved)) {
      return entry.defaultWhenUnknown === 'visible';
    }

    var met = evaluateOp(entry.op, resolved, entry.value);
    return entry.action === 'show' ? met : !met;
  }

  function applyCrossTaskVisibilityToOptions(entries, fieldsOptions, sourceDocsByTaskId) {
    if (!Array.isArray(entries) || !entries.length || !fieldsOptions) return;
    entries.forEach(function (entry) {
      if (!entry || !entry.path) return;
      var target = descendOptionsFields(fieldsOptions, entry.path);
      if (!target) return;
      target.hidden = !evaluateCrossTaskCondition(entry, sourceDocsByTaskId[entry.sourceTaskId]);
    });
  }

  function resolveWholeTaskVisibility(visibilityCondition, sourceDoc) {
    return evaluateCrossTaskCondition(visibilityCondition, sourceDoc);
  }

  function externalTaskIdsForCrossTaskVisibility(entries) {
    if (!Array.isArray(entries)) return [];
    var ids = [];
    entries.forEach(function (entry) {
      if (entry && entry.sourceTaskId && ids.indexOf(entry.sourceTaskId) === -1) ids.push(entry.sourceTaskId);
    });
    return ids;
  }

  window.TCCrossTask = {
    resolveChoicesFrom: resolveChoicesFrom,
    applyChoicesFromToOptions: applyChoicesFromToOptions,
    externalTaskIdsFor: externalTaskIdsFor,
    evaluateCrossTaskCondition: evaluateCrossTaskCondition,
    applyCrossTaskVisibilityToOptions: applyCrossTaskVisibilityToOptions,
    resolveWholeTaskVisibility: resolveWholeTaskVisibility,
    externalTaskIdsForCrossTaskVisibility: externalTaskIdsForCrossTaskVisibility
  };
})(typeof window !== 'undefined' ? window : this);
