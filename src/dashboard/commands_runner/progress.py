"""Avancement des commandes lancées depuis le menu « Commandes / sync ».

Les commandes (et les fonctions qu'elles appellent) signalent leur avancement par `report(...)`. Hors de la page
(commande lancée en SSH, tâche Celery), aucun suivi n'est installé : `report` ne fait rien et n'affiche rien."""

_callback = None


def install(callback):
    """Installé par `run_tracked_command` : callback(phase=, done=, total=, current=)."""
    global _callback
    _callback = callback


def report(phase=None, done=None, total=None, current=None):
    """phase : libellé de l'étape (une nouvelle phase remet done/total à zéro si non donnés) ;
    done / total : avancement de la phase ; current : élément en cours (base, facilitateur, village…)."""
    if _callback is not None:
        try:
            _callback(phase=phase, done=done, total=total, current=current)
        except Exception:  # noqa: BLE001 - le suivi ne doit jamais faire échouer la commande
            pass
