/**
 * Portage web (quasi verbatim) de src/utils/attachmentConditions.ts
 * (cdd-frontend) : affichage/obligation d'un slot de pièce jointe
 * (`Task.attachments[i]`), piloté par la réponse d'un champ de la même tâche
 * ou d'une autre (même mécanisme de résolution que task_cycle_cross_task.js,
 * dont ce fichier reprend volontairement les petits helpers purs plutôt que
 * de les importer — même raisonnement que le fichier mobile original).
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

  function parseSourcePath(sourcePath) {
    if (!sourcePath || sourcePath.charAt(0) !== '$') return { pageIndex: null, rest: '' };
    var dot = sourcePath.indexOf('.');
    var idx = parseInt(sourcePath.slice(1, dot === -1 ? undefined : dot), 10);
    var rest = dot === -1 ? '' : sourcePath.slice(dot + 1);
    return { pageIndex: isNaN(idx) ? null : idx, rest: rest };
  }

  function isEmpty(v) {
    return v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0);
  }

  function toNumber(v) {
    if (typeof v === 'number') return v;
    var n = parseFloat(v);
    return isNaN(n) ? NaN : n;
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

  function resolveConditionValue(cond, sameTaskResponses, sourceDocsByTaskId) {
    var parsed = parseSourcePath(cond.sourcePath);
    var pageIndex = parsed.pageIndex, rest = parsed.rest;
    if (pageIndex == null) return { known: false, value: undefined };

    if (cond.sourceTaskId == null) {
      var resolved = resolvePath((sameTaskResponses || [])[pageIndex], rest);
      return { known: !isEmpty(resolved), value: resolved };
    }

    var sourceDoc = sourceDocsByTaskId[cond.sourceTaskId];
    var resolved2 = sourceDoc ? resolvePath((sourceDoc.form_response || [])[pageIndex], rest) : undefined;
    return { known: !!sourceDoc && !isEmpty(resolved2), value: resolved2 };
  }

  function isConditionMet(cond, sameTaskResponses, sourceDocsByTaskId) {
    var r = resolveConditionValue(cond, sameTaskResponses, sourceDocsByTaskId);
    if (!r.known) {
      var isRestrictiveAction = cond.action === 'hide' || cond.action === 'require';
      return isRestrictiveAction
        ? cond.defaultWhenUnknown === 'hidden'
        : cond.defaultWhenUnknown === 'visible';
    }
    return evaluateOp(cond.op, r.value, cond.value);
  }

  function evaluateAttachmentConditions(slot, sameTaskResponses, sourceDocsByTaskId) {
    var conditions = Array.isArray(slot.conditions) ? slot.conditions : [];
    var buckets = {};
    conditions.forEach(function (cond) {
      if (!cond || !cond.action) return;
      var met = isConditionMet(cond, sameTaskResponses, sourceDocsByTaskId);
      (buckets[cond.action] || (buckets[cond.action] = [])).push(met);
    });

    var some = function (a) { return Array.isArray(a) && a.some(Boolean); };
    var has = function (k) { return Array.isArray(buckets[k]) && buckets[k].length > 0; };

    var hidden = false;
    if (has('show') || has('hide')) {
      var hiddenByHide = has('hide') && some(buckets.hide);
      var hiddenByShow = has('show') && !some(buckets.show);
      hidden = hiddenByHide || hiddenByShow;
    }

    var required = !slot.optional;
    if (has('require') || has('optional')) {
      required = has('require') && some(buckets.require) && !(has('optional') && some(buckets.optional));
    }

    return { hidden: hidden, required: required };
  }

  function externalTaskIdsForAttachmentConditions(attachments) {
    if (!Array.isArray(attachments)) return [];
    var ids = [];
    attachments.forEach(function (slot) {
      (slot.conditions || []).forEach(function (cond) {
        if (cond && cond.sourceTaskId != null && ids.indexOf(cond.sourceTaskId) === -1) ids.push(cond.sourceTaskId);
      });
    });
    return ids;
  }

  window.TCAttachmentConditions = {
    evaluateAttachmentConditions: evaluateAttachmentConditions,
    externalTaskIdsForAttachmentConditions: externalTaskIdsForAttachmentConditions
  };
})(typeof window !== 'undefined' ? window : this);
