/**
 * Modal UNIQUE de détail de tâche (#taskModalLong) + validation/invalidation +
 * complétion/remise en cours + commentaires — remplace les 3 implémentations
 * JS jusque-là dupliquées (administrative_levels/profile/profile.html,
 * facilitators/profile/profile.html, facilitators/old_profile/task_list.html)
 * et les modals-par-ligne des listes de tâches.
 *
 * Contrat : la page hôte définit, AVANT de charger ce fichier :
 *   window.TFB_FACILITATOR_DB_NAME = "{{ facilitator_db_name }}";
 *   window.TFB_URLS = {
 *     validateInvalidate:  "{% url 'dashboard:process_manager:validate_invalidate_task' %}",
 *     completeUncomplete:  "{% url 'dashboard:process_manager:complete_uncomplete_task' %}",
 *     taskCommentsTmpl:    "{% url 'dashboard:facilitators:task_comments' 'no_sql_db_name' 'task__id' %}",
 *     taskDetailModalTmpl: "{% url 'dashboard:facilitators:task_detail_modal' 'no_sql_db_name' %}"
 *   };
 * et, optionnellement :
 *   window.TFB_RELOAD_PLANNING_CYCLE = function () { ... };  // si la page a un cycle de planification à rafraîchir
 *   window.TFB_I18N = { ... };                                // surcharge des libellés (défaut : FR en dur)
 *
 * Déclencheurs pris en charge :
 *   - `data-toggle="modal" data-target="#taskModalLong"` + logique propre à la
 *     page pour peupler #modal-content (ex. administrative_levels/profile/profile.html,
 *     inchangé — clé par village) ;
 *   - `.js-open-task-modal[data-no-sql-db-name][data-task-id]` (NOUVEAU, pour
 *     les listes de tâches facilitateur — une ligne = un déclencheur, plus de
 *     modal-par-ligne).
 */
(function () {
  "use strict";

  var I18N = {
    needComment: "Merci d'ajouter un commentaire.",
    sending: "Envoi…",
    send: "Envoyer",
    taskValidated: "Tâche validée",
    taskNotValidated: "Tâche non validée",
    markValidated: "Marquer comme validée",
    completed: "Achevée",
    pending: "En attente",
    markCompleted: "Marquer comme achevée",
    markUncompleted: "Marquer comme non achevée",
    serverError: "Erreur serveur",
  };
  if (window.TFB_I18N) {
    for (var k in window.TFB_I18N) { if (window.TFB_I18N[k]) I18N[k] = window.TFB_I18N[k]; }
  }

  function urls() { return window.TFB_URLS || {}; }
  function facilitatorDbName() { return window.TFB_FACILITATOR_DB_NAME || ""; }
  function serverErrorPrefix() { return window.error_server_message || I18N.serverError; }

  function reloadPlanningCycleIfAny() {
    if (typeof window.TFB_RELOAD_PLANNING_CYCLE === "function") {
      try { window.TFB_RELOAD_PLANNING_CYCLE(); } catch (e) { /* no-op */ }
    }
  }

  function loadTaskComments(no_sql_db_name, task__id) {
    var tmpl = urls().taskCommentsTmpl;
    if (!tmpl || !task__id) return;
    var $spin = $('#load-comments-spin-' + task__id);
    $spin.show();
    try {
      $('#task_comments_' + task__id).load(
        tmpl.replace('no_sql_db_name', no_sql_db_name).replace('task__id', task__id),
        function (response, textStatus) {
          if (textStatus === "error") {
            alert(serverErrorPrefix());
          }
          $spin.hide();
        }
      );
    } catch (e) { $spin.hide(); }
  }
  // Exposé : les boutons "rafraîchir" du modal l'appellent en onclick inline.
  window.loadTaskComments = loadTaskComments;

  // --- Visionneuse plein écran ("Voir en grand") d'une pièce jointe --------
  // Overlay unique (#tdmLightbox, cf. facilitators/components/task_modals.html),
  // appelé en onclick inline par facilitators/_task_attachment.html.
  function tdmOpenLightbox(url, type) {
    var $content = $('#tdmLightboxContent');
    if (!$content.length) return;
    if (type === 'pdf') {
      $content.html($('<iframe>').attr('src', url));
    } else if (type === 'office') {
      var viewerUrl = 'https://view.officeapps.live.com/op/embed.aspx?src=' + encodeURIComponent(url);
      $content.html($('<iframe>').attr({ src: viewerUrl, frameborder: '0' }));
    } else {
      $content.html($('<img>').attr('src', url));
    }
    $('#tdmLightbox').addClass('tdm-lightbox-open');
  }
  function tdmCloseLightbox() {
    $('#tdmLightbox').removeClass('tdm-lightbox-open');
    $('#tdmLightboxContent').empty();
  }
  window.tdmOpenLightbox = tdmOpenLightbox;
  window.tdmCloseLightbox = tdmCloseLightbox;

  // --- Notification non bloquante (remplace les `alert()` de statut mail/SMS,
  // cf. plus bas) : un simple bandeau qui s'auto-détruit, style posé en inline
  // pour ne pas dépendre d'une feuille de style supplémentaire à charger sur
  // les 3 pages hôtes de ce fichier. ------------------------------------------
  function showToast(message, isError) {
    var $t = $('<div>').text(message).css({
      position: 'fixed', right: '20px', bottom: '20px', zIndex: 10500,
      maxWidth: '360px', padding: '12px 16px', borderRadius: '8px',
      background: isError ? '#dc3545' : '#333', color: '#fff',
      fontSize: '13px', lineHeight: 1.4, boxShadow: '0 6px 18px rgba(0,0,0,.25)',
      whiteSpace: 'pre-line', opacity: 0, transform: 'translateY(8px)',
      transition: 'opacity .25s ease, transform .25s ease'
    });
    $('body').append($t);
    setTimeout(function () { $t.css({ opacity: 1, transform: 'translateY(0)' }); }, 10);
    setTimeout(function () {
      $t.css({ opacity: 0, transform: 'translateY(8px)' });
      setTimeout(function () { $t.remove(); }, 300);
    }, 5000);
  }
  window.tdmShowToast = showToast;

  $(function () {
    // Fermer la visionneuse : clic sur le fond, ou touche Échap.
    $(document)
      .off('click.taskDetailModal', '#tdmLightbox')
      .on('click.taskDetailModal', '#tdmLightbox', function (e) {
        if (e.target === this) tdmCloseLightbox();
      })
      .off('keydown.taskDetailModal')
      .on('keydown.taskDetailModal', function (e) {
        if (e.key === 'Escape' || e.keyCode === 27) tdmCloseLightbox();
      });

    // --- Ouverture du modal unique depuis une ligne de liste de tâches -----
    $(document)
      .off('click.taskDetailModal', '.js-open-task-modal')
      .on('click.taskDetailModal', '.js-open-task-modal', function (e) {
        e.preventDefault();
        var $el = $(this);
        var dbName = $el.data('no-sql-db-name') || facilitatorDbName();
        var taskId = $el.data('task-id');
        var tmpl = urls().taskDetailModalTmpl;
        if (!tmpl || !taskId) return;
        $('#modal-content').html('<div class="text-center p-5"><i class="fas fa-2x fa-sync-alt fa-spin"></i></div>');
        $('#taskModalLong').modal('show');
        $.ajax({
          type: "GET",
          url: tmpl.replace('no_sql_db_name', dbName),
          data: { task_id: taskId },
          success: function (response) { $('#modal-content').html(response); },
          error: function (x) {
            $('#modal-content').html(
              '<div class="modal-body text-center text-danger p-4">'
              + serverErrorPrefix() + ' ' + (x ? x.status : '') + '</div>'
            );
          }
        });
      });
    $('#taskModalLong').off('hidden.bs.modal.taskDetailModal')
      .on('hidden.bs.modal.taskDetailModal', function () { $('#modal-content').empty(); });

    // --- Valider / Invalider ------------------------------------------------
    var current_task_id = null;
    var current_action_code = null;

    $(document)
      .off('click.taskDetailModal', '.invalidate_valide')
      .on('click.taskDetailModal', '.invalidate_valide', function () {
        var parts = this.id.split('_');
        current_task_id = parts[parts.length - 1];
        current_action_code = null;
        for (var i = 0; i < this.classList.length; i++) {
          if (this.classList[i].indexOf('action_code_') === 0) {
            current_action_code = this.classList[i].split('_')[2];
          }
        }
        $('#card-item-task-' + current_task_id).modal('hide'); // legacy (modal-par-ligne, si encore présent)
        $('#taskModalLong').modal('hide');
        $('#modal_comment').modal('show');
      });

    $(document)
      .off('click.taskDetailModal', '#btn-send-comment')
      .on('click.taskDetailModal', '#btn-send-comment', function () {
        var $btn = $('#btn-send-comment');
        var comment = $('#id_in_validation_comment').val();

        var isInvalidation = ["0", 0].indexOf(current_action_code) !== -1;
        var commentEmpty = [null, undefined, ""].indexOf(comment) !== -1
          || (comment && comment.replace(/\s/g, '') === "");
        if (isInvalidation && commentEmpty) {
          alert(I18N.needComment);
          return;
        }
        if (current_task_id == null || current_action_code == null) return;

        var data = {
          no_sql_db_name: facilitatorDbName(),
          task_id: current_task_id,
          action_code: current_action_code,
          in_validation_comment: comment
        };
        // Partage villages sièges : le mode est porté PAR CHAMP (un même
        // formulaire peut avoir des champs facilitator_then_validator ET
        // validator_only) -> un <select data-share-mode="..."> par mode
        // présent (cf. _task_detail.html), lus ici en {mode: [ids]},
        // uniquement lors d'une VALIDATION (pas d'une invalidation).
        if (String(current_action_code) === "1") {
          var targetsByMode = {};
          $('[id^="tdm_share_targets_' + current_task_id + '_"]').each(function () {
            var mode = $(this).data('share-mode');
            if (mode) targetsByMode[mode] = $(this).val() || [];
          });
          if (Object.keys(targetsByMode).length) {
            data.share_targets_json = JSON.stringify(targetsByMode);
          }
        }

        $btn.prop("disabled", true).text(I18N.sending);
        $.ajax({
          type: "GET",
          url: urls().validateInvalidate,
          data: data,
          success: function (response) {
            var doneTaskId = current_task_id;
            if (response.status === "ok") {
              if (String(current_action_code) === "1") {
                $('#id_invalidate_valide_validation_action_' + doneTaskId).hide();
                $('.cls_invalidation_validation_inclusion').hide();
                $('.text_' + doneTaskId).html(
                  '<div class="status__circle-icon success"><i class="fas fa-check-double"></i></div>'
                );
                $('.modal_text_' + doneTaskId).html(
                  '<div class="status-badge success-color"><i class="fas fa-check success-color"></i> '
                  + I18N.taskValidated + '</div>'
                );
              } else {
                $('.text_' + doneTaskId).html(
                  '<div class="status__circle-icon error"><i class="fas fa-times"></i></div>'
                );
                $('.modal_text_' + doneTaskId).html(
                  '<div class="status-badge warning-color"><i class="fas fa-times warning-color"></i> '
                  + I18N.taskNotValidated + '</div>'
                );
                if (response.previous_status === true) {
                  $('.cls_invalidation_validation').before(
                    '<div style="width: 30%; margin: auto; float: left;" class="cls_invalidation_validation_inclusion">'
                    + '<button type="button" name="invalidate_valide" class="btn btn-primary action_code_1 invalidate_valide" '
                    + 'required id="id_invalidate_valide_validation_action_inclusion_' + doneTaskId + '">'
                    + I18N.markValidated + '</button></div>'
                  );
                }
              }
              $('#modal_comment').modal('hide');
              current_task_id = null;
              current_action_code = null;
              $('#id_in_validation_comment').val("");
              reloadPlanningCycleIfAny();
              loadTaskComments(facilitatorDbName(), doneTaskId);
            } else {
              alert(response.message);
            }
            $btn.prop("disabled", false).text(I18N.send);
            // BUG réel confirmé en testant en direct (clic simulé de bout en
            // bout, cf. task-form-builder.md) : un `alert()` natif est BLOQUANT
            // — tant qu'il n'est pas fermé par l'utilisateur, le thread JS de
            // l'onglet est gelé, y compris le traitement de la réponse déjà en
            // vol de `reloadPlanningCycleIfAny()` juste au-dessus (déclenchée
            // AVANT cet `alert`, mais dont le callback de succès — qui remplace
            // le bloc "Cycle de planification" par sa version à jour — ne
            // s'exécute qu'APRÈS que l'utilisateur ait fermé la popup). Résultat
            // perçu : la tâche semble rester "validée" à l'écran tant que cette
            // notification (mail/SMS, une info secondaire, sans rapport avec le
            // succès de l'invalidation elle-même) n'a pas été fermée — ce que
            // l'utilisateur signalait comme "il faut rafraîchir la page".
            // Remplacé par une notification NON bloquante (cf. `showToast`
            // ci-dessous) : la mise à jour visuelle de la tâche n'attend plus.
            var noticeParts = [response.mail_message, response.sms_message].filter(Boolean);
            if (noticeParts.length) showToast(noticeParts.join("\n"));
          },
          error: function (xhr) {
            alert(serverErrorPrefix() + " " + xhr.status);
            $btn.prop("disabled", false).text(I18N.send);
          }
        });
      });

    // --- Compléter / Remettre en cours --------------------------------------
    $(document)
      .off('click.taskDetailModal', '.uncomplete_complete')
      .on('click.taskDetailModal', '.uncomplete_complete', function () {
        var parts = this.id.split('_');
        var id = parts[parts.length - 1];
        var actionCodeCompleted = $('#action_code_completed_' + id).val();
        var $taskNumber = $('#task_number_' + id);

        $.ajax({
          type: "GET",
          url: urls().completeUncomplete,
          data: { no_sql_db_name: facilitatorDbName(), task_id: id, action_code: actionCodeCompleted },
          success: function (response) {
            if (response.status === "ok") {
              if (String(actionCodeCompleted) === "1") {
                $('#action_code_completed_' + id).val(0);
                $('#id_uncomplete_complete_' + id).text(I18N.markUncompleted)
                  .removeClass('btn-primary').addClass('btn-warning');
                $('.text_' + id).html('<div class="status__circle-icon success"><i class="fas fa-check"></i></div>');
                $('.modal_text_completed_' + id).html(
                  '<div class="status-badge badge-completed">' + I18N.completed + '</div>'
                );
                $taskNumber.removeClass('badge-pending').addClass('badge-completed');
              } else {
                $('#action_code_completed_' + id).val(1);
                $('#id_uncomplete_complete_' + id).text(I18N.markCompleted)
                  .removeClass('btn-warning').addClass('btn-primary');
                $('.text_' + id).html('<div class="header__progress-icon"></div>');
                $('.modal_text_completed_' + id).html(
                  '<div class="status-badge badge-pending">' + I18N.pending + '</div>'
                );
                $taskNumber.removeClass('badge-completed').addClass('badge-pending');
              }
            } else {
              alert(response.message);
            }
            loadTaskComments(facilitatorDbName(), id);
            reloadPlanningCycleIfAny();
          },
          error: function (xhr) {
            alert(serverErrorPrefix() + " " + xhr.status);
          }
        });
      });
  });
})();
