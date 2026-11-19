"""Tests des règles (village, projet, cycle) des documents de villages (dashboard/diagnostics/village_docs.py).

Fonctions pures uniquement (aucune base) :
    python manage.py test dashboard.diagnostics.tests_village_docs
"""
from django.test import SimpleTestCase

from dashboard.diagnostics import village_docs as vd

P1, P2 = "projet1", "projet2"
C1, C1B, C2 = "cycle1", "cycle1b", "cycle2"  # C1 et C1B : deux cycles du projet 1


def el(village, project, cycle, hq=True, **extra):
    element = {"id": str(village), "name": f"V{village}", "project_id": project, "cycle_id": cycle}
    if hq:
        element["is_headquarters_village"] = True
    element.update(extra)
    return element


class ElementKeysTest(SimpleTestCase):
    def test_keys_by_project_and_cycle(self):
        full, partial, by_key = vd.element_keys({"administrative_levels": [el(10, P1, C1), el(10, P2, C2), "texte", {"id": None}]})
        self.assertEqual(full, {("10", P1, C1), ("10", P2, C2)})
        self.assertEqual(partial, {("10", P1), ("10", P2)})
        self.assertEqual(set(by_key), full)

    def test_integer_ids_are_texts(self):
        full, _, _ = vd.element_keys({"administrative_levels": [{"id": 10, "project_id": P1, "cycle_id": C1}]})
        self.assertEqual(full, {("10", P1, C1)})


class IsOrphanTest(SimpleTestCase):
    def setUp(self):
        self.full, self.partial, _ = vd.element_keys({"administrative_levels": [el(10, P1, C1), el(20, P2, C2)]})

    def test_same_village_project_cycle_is_not_orphan(self):
        self.assertFalse(vd.is_orphan(("10", P1, C1), self.full, self.partial))

    def test_other_cycle_of_same_project_is_orphan(self):
        self.assertTrue(vd.is_orphan(("10", P1, C1B), self.full, self.partial))

    def test_other_project_is_orphan(self):
        # le village 10 est affecté au FC pour le projet 1 seulement
        self.assertTrue(vd.is_orphan(("10", P2, C2), self.full, self.partial))

    def test_documents_without_cycle(self):
        # sans cycle_id : présents tant que le village est dans le projet (n'importe quel cycle)
        self.assertFalse(vd.is_orphan(("10", P1, ""), self.full, self.partial))
        self.assertTrue(vd.is_orphan(("20", P1, ""), self.full, self.partial))


class LocalitiesMoveKeysTest(SimpleTestCase):
    def test_removed_in_one_project_kept_in_another(self):
        removed, added = vd.localities_move_keys([], [el(10, P1, C1)], kept=[el(10, P2, C2)])
        # le travail du projet 2 reste ; les documents sans cycle du projet 1 partent aussi
        self.assertEqual(removed, [("10", P1, C1), ("10", P1, "")])
        self.assertEqual(added, [])

    def test_removed_one_cycle_kept_other_cycle_of_same_project(self):
        removed, _ = vd.localities_move_keys([], [el(10, P1, C1)], kept=[el(10, P1, C1B)])
        self.assertEqual(removed, [("10", P1, C1)])  # documents sans cycle gardés : le village reste dans le projet

    def test_removed_but_still_kept_same_key(self):
        removed, _ = vd.localities_move_keys([], [el(10, P1, C1)], kept=[el(10, P1, C1)])
        self.assertEqual(removed, [])

    def test_removed_non_headquarters_is_still_checked(self):
        # village non siège : vérifié aussi (ses documents éventuels ne doivent pas rester chez l'ancien FC)
        removed, _ = vd.localities_move_keys([], [el(10, P1, C1, hq=False)], kept=[])
        self.assertEqual(removed, [("10", P1, C1), ("10", P1, "")])

    def test_removed_without_project_or_bad_id_ignored(self):
        removed, _ = vd.localities_move_keys([], [el(10, "", C1), {"id": "abc", "project_id": P1, "cycle_id": C1}, "x"], kept=[])
        self.assertEqual(removed, [])

    def test_added_headquarters_only_with_project_and_cycle(self):
        _, added = vd.localities_move_keys(
            [el(10, P1, C1), el(11, P1, C1, hq=False), el(12, P1, ""), el(10, P1, C1), el(13, P2, C2)], [], kept=[])
        self.assertEqual(added, [("10", P1, C1), ("13", P2, C2)])

    def test_duplicates_removed(self):
        removed, _ = vd.localities_move_keys([], [el(10, P1, C1), el(10, P1, C1)], kept=[])
        self.assertEqual(removed, [("10", P1, C1), ("10", P1, "")])


class SelectorAndGuardTest(SimpleTestCase):
    def test_selector_with_cycle(self):
        selector = vd.docs_selector("10", P1, C1)
        self.assertEqual(selector["project_id"], P1)
        self.assertEqual(selector["cycle_id"], C1)
        self.assertEqual(selector["administrative_level_id"], {"$in": ["10", 10]})
        self.assertNotIn("$or", selector)

    def test_selector_without_cycle(self):
        selector = vd.docs_selector("10", P1, "")
        self.assertNotIn("cycle_id", selector)
        self.assertEqual(selector["$or"], [{"cycle_id": {"$exists": False}}, {"cycle_id": None}, {"cycle_id": ""}])

    def test_guard_accepts_only_same_group(self):
        ok = [{"_id": "a", "type": "task", "administrative_level_id": 10, "project_id": P1, "cycle_id": C1}]
        vd.guard_same_group(ok, "10", P1, C1)
        for other in ({"project_id": P2}, {"cycle_id": C1B}, {"administrative_level_id": "11"}, {"type": "facilitator"}):
            with self.assertRaises(vd.CouchError):
                vd.guard_same_group([dict(ok[0], **other)], "10", P1, C1)

    def test_guard_without_cycle(self):
        vd.guard_same_group([{"_id": "a", "type": "phase", "administrative_level_id": "10", "project_id": P1}], "10", P1, "")
        with self.assertRaises(vd.CouchError):
            vd.guard_same_group([{"_id": "a", "type": "phase", "administrative_level_id": "10", "project_id": P1, "cycle_id": C1}], "10", P1, "")

    def test_row_key_round_trip(self):
        self.assertEqual(vd.parse_row_key(vd.row_key("db", "10", P1, C1)), ("db", "10", P1, C1))
        self.assertEqual(vd.parse_row_key(vd.row_key("db", "10", P1, "")), ("db", "10", P1, ""))
        for bad in ("", "db|x|p|c", "db|10||c", "a|b"):
            with self.assertRaises(ValueError):
                vd.parse_row_key(bad)


class FakeCouch:
    def __init__(self, docs):
        self.docs = docs

    def find(self, db, selector, fields=None):
        return [d for d in self.docs if d["project_id"] == selector["project_id"]
                and d["administrative_level_id"] in selector["administrative_level_id"]["$in"]]


def doc(_id, cycle, source="", completed=False, project=P1, village="10"):
    d = {"_id": _id, "type": "task", "project_id": project, "administrative_level_id": village, "completed": completed}
    if cycle is not None:
        d["cycle_id"] = cycle
    if source:
        d["backup_source"] = {"db": source, "moved_at": "2026-11-17"}
    return d


class BackupGroupTest(SimpleTestCase):
    def test_same_cycle_preferred_over_documents_without_cycle(self):
        couch = FakeCouch([doc("a", C1, "fcA"), doc("b", None, "", completed=True), doc("c", None, "", completed=True)])
        self.assertEqual(vd._backup_group(couch, "10", P1, C1), ("fcA", C1, ["a"]))

    def test_other_cycle_and_other_project_ignored(self):
        couch = FakeCouch([doc("a", C1B, "fcA"), doc("b", C1, "fcB", project=P2)])
        self.assertIsNone(vd._backup_group(couch, "10", P1, C1))

    def test_documents_without_cycle_used_when_alone(self):
        couch = FakeCouch([doc("a", None, "fcA"), doc("b", C1B, "fcB")])
        self.assertEqual(vd._backup_group(couch, "10", P1, C1), ("fcA", "", ["a"]))

    def test_most_completed_source_wins(self):
        couch = FakeCouch([doc("a", C1, "fcA"), doc("b", C1, "fcA"), doc("c", C1, "fcB", completed=True)])
        self.assertEqual(vd._backup_group(couch, "10", P1, C1), ("fcB", C1, ["c"]))
