"""Périmètre de la fenêtre « Synchroniser cette tâche » du générateur de formulaire.

`sync_tasks` (dashboard.utils.create_task_all_facilitators) crée la tâche dans la base CouchDB de chaque
facilitateur retenu (projet, ou bases choisies ; `develop_mode` / `training_mode` égaux à ceux demandés), pour
chacun de ses niveaux administratifs du document « facilitator » marqués `is_headquarters_village`, du projet
et du cycle (`project_name`, `cycle_name`), éventuellement limités à `administrativelevel_ids` (TEXTES : la
comparaison est `str(id) in administrativelevel_ids`).

Les villages sièges proposés sont donc lus dans ce même document CouchDB (en parallèle, ~0,5 à 3 s pour 150 bases),
et non dans `AggregatedStatus` (calculé à part, absent pour certains projets, avec des villages non sièges) ni dans
la copie en base `Facilitator.administrative_levels` (en retard pour des comptes de formation, constaté le
13/11/2026) ; cette copie ne sert que pour une base CouchDB illisible (`fallback_dbs`).
Région, préfecture, commune et canton se déduisent des parents de ces villages ; les choix se combinent :
plusieurs valeurs d'un même niveau = OU, niveaux différents, villages sièges et bases choisis = ET.
"""
from concurrent.futures import ThreadPoolExecutor

from administrativelevels.models import AdministrativeLevel
from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from process_manager.models import Cycle, Project

COUCH_WORKERS = 8
COUCH_TIMEOUT = 20

GEO_LEVELS = ('region', 'prefecture', 'commune', 'canton')
GEO_TYPES = {'Region': 'region', 'Prefecture': 'prefecture', 'Commune': 'commune', 'Canton': 'canton'}


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class SyncScope:
    """Facilitateurs du projet, leurs villages sièges du cycle et la géographie de ces villages."""

    def __init__(self, project_id, cycle_id, read_couch=True):
        self.facilitators = []   # [{db, label, develop, training, villages: {id}}]
        self.villages = {}       # {id: {'name', 'chain': {niveau: id}, 'dbs': {db}}}
        self.levels = {}         # {id: (type, parent_id, name)}
        self.fallback_dbs = []   # bases CouchDB illisibles : copie en base utilisée
        project = Project.objects.filter(id=project_id).first() if project_id else None
        cycle = Cycle.objects.filter(id=cycle_id).first() if cycle_id else None
        if not project:
            return
        seen, facilitators = set(), []
        for f in Facilitator.objects.filter(projects__id=project.id).order_by('name', 'username'):
            db = (f.no_sql_db_name or '').strip()
            if db and db not in seen:
                seen.add(db)
                facilitators.append(f)
        couch_levels = self._read_couch([f.no_sql_db_name.strip() for f in facilitators]) if read_couch else {}

        def wanted(adl):
            return isinstance(adl, dict) and adl.get('is_headquarters_village')                 and adl.get('project_name') == project.name and (not cycle or adl.get('cycle_name') == cycle.name)

        for f in facilitators:
            db = f.no_sql_db_name.strip()
            levels = couch_levels.get(db)
            if levels is None:
                levels = f.administrative_levels or []
                if read_couch:
                    self.fallback_dbs.append(db)
            villages = {i for i in (_int(adl.get('id')) for adl in levels if wanted(adl)) if i is not None}
            name = (f.name or f.username or db).strip()
            self.facilitators.append({'db': db, 'label': f'{name} — {db}', 'develop': bool(f.develop_mode),
                                      'training': bool(f.training_mode), 'villages': villages})
            for village_id in villages:
                self.villages.setdefault(village_id, {'dbs': set()})['dbs'].add(db)
        if not self.villages:
            return
        self.levels = {row[0]: (row[1], row[2], row[3]) for row in
                       AdministrativeLevel.objects.using('mis').values_list('id', 'type', 'parent_id', 'name')}
        for village_id, info in self.villages.items():
            info['name'] = self.levels.get(village_id, (None, None, str(village_id)))[2]
            info['chain'] = self._chain(village_id)

    @staticmethod
    def _read_couch(db_names):
        """{base: administrative_levels du document « facilitator »} ; base absente du résultat = illisible."""
        try:
            nsc = NoSQLClient(timeout=COUCH_TIMEOUT)
        except Exception:  # noqa: BLE001 - CouchDB injoignable : copie en base pour tout
            return {}

        def read(db):
            try:
                docs = nsc.find_all(nsc.get_db(db), {'type': 'facilitator'}, fields=['administrative_levels'])
            except Exception:  # noqa: BLE001 - base absente ou injoignable
                return db, None
            return db, (docs[0].get('administrative_levels') or []) if docs else []

        with ThreadPoolExecutor(max_workers=COUCH_WORKERS) as pool:
            return {db: levels for db, levels in pool.map(read, db_names) if levels is not None}

    def as_json(self):
        """Listes de la fenêtre (chargées à son ouverture)."""
        return {'villages': self.village_choices(), 'geo': self.geo_choices(),
                'facilitators': self.facilitator_choices(), 'fallback_dbs': self.fallback_dbs}

    def _chain(self, village_id):
        chain, current, seen = {}, self.levels.get(village_id, (None, None, None))[1], set()
        while current in self.levels and current not in seen:
            seen.add(current)
            adm_type, parent_id, _ = self.levels[current]
            key = GEO_TYPES.get(adm_type)
            if key and key not in chain:
                chain[key] = current
            current = parent_id
        return chain

    # -- affichage -------------------------------------------------------------------------------------------
    def village_choices(self):
        """[{value, label, region, prefecture, commune, canton, dbs}] triés par canton puis village."""
        out = []
        for village_id, info in self.villages.items():
            canton = info['chain'].get('canton')
            out.append(dict(
                value=village_id,
                label=f"{info['name']} ({self.levels[canton][2] if canton else '—'})",
                dbs=' '.join(sorted(info['dbs'])),
                **{key: info['chain'].get(key, '') for key in GEO_LEVELS},
            ))
        out.sort(key=lambda c: c['label'].lower())
        return out

    def geo_choices(self):
        """{niveau: [{value, label, region, prefecture, commune}]} : niveaux qui contiennent au moins un village
        siège, avec leurs parents (filtrage en cascade dans la fenêtre)."""
        out = {key: {} for key in GEO_LEVELS}
        for info in self.villages.values():
            chain = info['chain']
            for n, key in enumerate(GEO_LEVELS):
                level_id = chain.get(key)
                if level_id is not None and level_id not in out[key]:
                    out[key][level_id] = dict({'value': level_id, 'label': self.levels[level_id][2]},
                                              **{above: chain.get(above, '') for above in GEO_LEVELS[:n]})
        return {key: sorted(rows.values(), key=lambda r: (r['label'] or '').lower()) for key, rows in out.items()}

    def facilitator_choices(self):
        return [{'value': f['db'], 'label': f['label'], 'develop': f['develop'], 'training': f['training'],
                 'villages': len(f['villages'])} for f in self.facilitators]

    # -- envoi -----------------------------------------------------------------------------------------------
    def resolve(self, develop_mode, training_mode, no_sql_dbs, village_ids, geo):
        """Villages et facilitateurs visés par les choix de la fenêtre.

        Renvoie (administrativelevel_ids, facilitateurs visés, villages visés) ; `administrativelevel_ids` est
        une liste de TEXTES (vide = tous les villages sièges, aucun choix de village ni de zone)."""
        chosen_geo = {key: {i for i in (_int(v) for v in geo.get(key) or []) if i is not None} for key in GEO_LEVELS}
        chosen_geo = {key: ids for key, ids in chosen_geo.items() if ids}
        chosen_villages = {i for i in (_int(v) for v in village_ids or []) if i is not None}
        targeted = set(self.villages)
        for key, ids in chosen_geo.items():
            targeted = {v for v in targeted if self.villages[v]['chain'].get(key) in ids}
        if chosen_villages:
            # Un village choisi hors des villages sièges connus est gardé (copie en base éventuellement en retard
            # sur CouchDB), sauf s'il est hors de la zone choisie.
            known = chosen_villages & targeted
            unknown = {v for v in chosen_villages - set(self.villages) if not chosen_geo}
            targeted = known | unknown
        restricted = bool(chosen_geo or chosen_villages)
        dbs = set(no_sql_dbs or [])
        facilitators = [f for f in self.facilitators
                        if f['develop'] == bool(develop_mode) and f['training'] == bool(training_mode)
                        and (not dbs or f['db'] in dbs)
                        and (f['villages'] & targeted if restricted else f['villages'])]
        if restricted:
            villages = {v for f in facilitators for v in f['villages'] & targeted} | (targeted - set(self.villages))
        else:
            villages = {v for f in facilitators for v in f['villages']}
        ids = sorted(str(v) for v in targeted) if restricted else []
        return ids, facilitators, villages
