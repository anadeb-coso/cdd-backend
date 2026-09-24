"""Utilitaires communs à `export_postgres_db` et `import_postgres_db`.

Le préfixe `_` empêche Django de le prendre pour une commande.

Format du fichier d'export (un seul .zip, aucune dépendance à pg_dump/psql,
donc utilisable tel quel sur une instance Elastic Beanstalk) :

    manifest.json     schéma (tables, colonnes, contraintes, index, séquences)
    data/0001.csv …   une table par fichier, COPY CSV, NULL = \\N

Périmètre : le schéma `public` uniquement (tables ordinaires). Les vues,
extensions, rôles, droits et tables partitionnées ne sont pas exportés.
"""
import re
from collections import defaultdict, deque
from urllib.parse import parse_qsl, unquote, urlparse

import psycopg2
from django.core.management.base import CommandError

FORMAT_NAME = "cdd-pg-snapshot"
FORMAT_VERSION = 1
SCHEMA = "public"
MANIFEST_NAME = "manifest.json"

# NULL = \N : distingue NULL de la chaîne vide, comme le pipeline de fusion.
COPY_OPTS = r"WITH (FORMAT csv, NULL '\N', ENCODING 'UTF8')"

NEXTVAL_RE = re.compile(r"nextval\('([^']+)'::regclass\)")
_URL_SCHEMES = ("postgres", "postgresql", "pgsql", "psql")


def qi(name):
    """Identifiant SQL entre guillemets (les noms de tables ont des majuscules)."""
    return '"' + name.replace('"', '""') + '"'


def qt(table):
    return f"{qi(SCHEMA)}.{qi(table)}"


def seq_name(raw):
    """`public.foo_id_seq` / `"public"."foo_id_seq"` -> `foo_id_seq`."""
    raw = re.sub(r'^(?:"public"|public)\.', "", raw.strip())
    return raw.strip('"')


def parse_pg_url(url):
    """postgres://user:pass@host:5432/base?sslmode=require -> kwargs psycopg2."""
    u = urlparse(url)
    if u.scheme not in _URL_SCHEMES:
        raise CommandError(
            f"URL PostgreSQL invalide (schéma « {u.scheme} ») : attendu "
            "postgres://user:motdepasse@hote:5432/base")
    dbname = unquote(u.path.lstrip("/"))
    if not dbname:
        raise CommandError("URL PostgreSQL invalide : nom de base manquant.")
    kwargs = {
        "dbname": dbname,
        "user": unquote(u.username) if u.username else None,
        "password": unquote(u.password) if u.password else None,
        "host": u.hostname,
        "port": u.port,
    }
    kwargs.update(dict(parse_qsl(u.query)))   # sslmode, connect_timeout…
    return {k: v for k, v in kwargs.items() if v is not None}


def mask_url(url):
    """L'URL sans mot de passe, pour l'affichage."""
    u = urlparse(url)
    user = f"{unquote(u.username)}@" if u.username else ""
    port = f":{u.port}" if u.port else ""
    return f"{u.scheme}://{user}{u.hostname or ''}{port}{u.path}"


def connect(url):
    try:
        conn = psycopg2.connect(application_name="cdd_pg_snapshot",
                                **parse_pg_url(url))
    except psycopg2.OperationalError as exc:
        raise CommandError(
            f"Connexion impossible à {mask_url(url)} : {str(exc).strip()}")
    conn.set_client_encoding("UTF8")
    return conn


# ---------------------------------------------------------------------- #
# Lecture du schéma (partagée par export_postgres_db et export_postgres_db_sql)
# ---------------------------------------------------------------------- #
def describe_database(cur):
    """(tables triées par dépendance de FK, séquences) du schéma public."""
    table_defs = [_describe_table(cur, oid, name)
                  for oid, name in _list_tables(cur)]
    sequences = _describe_sequences(cur, table_defs)
    return _sort_by_dependencies(table_defs), sequences


def _list_tables(cur):
    cur.execute(
        "SELECT c.oid, c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = %s AND c.relkind = 'r' AND NOT c.relispartition "
        "ORDER BY c.relname", (SCHEMA,))
    return cur.fetchall()


def _describe_table(cur, oid, name):
    cur.execute(
        "SELECT a.attnum, a.attname, format_type(a.atttypid, a.atttypmod), "
        "       a.attnotnull, pg_get_expr(d.adbin, d.adrelid), "
        "       a.attidentity, a.attgenerated "
        "FROM pg_attribute a "
        "LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
        "WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped "
        "ORDER BY a.attnum", (oid,))
    attnum_to_name, columns = {}, []
    for attnum, col, typ, notnull, default, identity, generated in cur.fetchall():
        attnum_to_name[attnum] = col
        columns.append({
            "name": col, "type": typ, "notnull": bool(notnull),
            "default": default,
            "identity": identity or "",       # '' | 'a' (ALWAYS) | 'd' (BY DEFAULT)
            "generated": generated or "",     # '' | 's' (STORED)
        })

    # p = clé primaire, u = unique, c = check, x = exclusion, f = clé étrangère
    cur.execute(
        "SELECT conname, contype, pg_get_constraintdef(oid), conkey "
        "FROM pg_constraint WHERE conrelid = %s "
        "AND contype IN ('p','u','c','x','f') ORDER BY conname", (oid,))
    constraints, pk = [], []
    for conname, contype, definition, conkey in cur.fetchall():
        constraints.append({"name": conname, "type": contype,
                            "def": definition})
        if contype == "p":
            pk = [attnum_to_name[k] for k in conkey]

    # Les index adossés à une contrainte p/u/x sont recréés avec elle.
    cur.execute(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = %s AND tablename = %s "
        "AND indexname NOT IN (SELECT conname FROM pg_constraint "
        "                      WHERE conrelid = %s AND contype IN ('p','u','x')) "
        "ORDER BY indexname", (SCHEMA, name, oid))
    indexes = [{"name": n, "def": d} for n, d in cur.fetchall()]

    cur.execute(
        "SELECT DISTINCT cf.relname FROM pg_constraint c "
        "JOIN pg_class cf ON cf.oid = c.confrelid "
        "WHERE c.conrelid = %s AND c.contype = 'f' AND c.confrelid <> c.conrelid",
        (oid,))
    depends_on = sorted(r[0] for r in cur.fetchall())

    return {"name": name, "columns": columns, "pk": pk,
            "constraints": constraints, "indexes": indexes,
            "depends_on": depends_on, "rows": 0, "file": None}


def _describe_sequences(cur, table_defs):
    """Séquences « serial » : rattachées à une colonne (OWNED BY) ou citées
    dans un DEFAULT nextval(...). Les colonnes IDENTITY gèrent la leur."""
    owned = {}
    cur.execute(
        "SELECT s.relname, t.relname, a.attname "
        "FROM pg_class s "
        "JOIN pg_depend d ON d.objid = s.oid "
        "  AND d.classid = 'pg_class'::regclass "
        "  AND d.refclassid = 'pg_class'::regclass AND d.deptype = 'a' "
        "JOIN pg_class t ON t.oid = d.refobjid "
        "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid "
        "JOIN pg_namespace n ON n.oid = t.relnamespace "
        "WHERE s.relkind = 'S' AND n.nspname = %s", (SCHEMA,))
    for seq, table, col in cur.fetchall():
        owned[seq] = [table, col]

    wanted = set(owned)
    for t in table_defs:
        for c in t["columns"]:
            m = NEXTVAL_RE.search(c["default"] or "")
            if m:
                wanted.add(seq_name(m.group(1)))

    sequences = []
    for name in sorted(wanted):
        cur.execute(
            "SELECT format_type(s.seqtypid, NULL), s.seqstart, s.seqincrement, "
            "       s.seqmax, s.seqmin, s.seqcache, s.seqcycle "
            "FROM pg_sequence s JOIN pg_class c ON c.oid = s.seqrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relname = %s", (SCHEMA, name))
        row = cur.fetchone()
        if row is None:
            continue
        typ, start, inc, mx, mn, cache, cycle = row
        sql = (f"CREATE SEQUENCE IF NOT EXISTS {qt(name)} AS {typ} "
               f"INCREMENT BY {inc} MINVALUE {mn} MAXVALUE {mx} "
               f"START WITH {start} CACHE {cache} "
               f"{'CYCLE' if cycle else 'NO CYCLE'}")
        sequences.append({"name": name, "sql": sql,
                          "owned_by": owned.get(name)})
    return sequences


def _sort_by_dependencies(table_defs):
    """Tables référencées d'abord (les cycles sont ajoutés en fin de liste :
    les clés étrangères de Django sont DEFERRABLE INITIALLY DEFERRED)."""
    by_name = {t["name"]: t for t in table_defs}
    indeg = {n: 0 for n in by_name}
    children = defaultdict(list)
    for t in table_defs:
        for dep in t["depends_on"]:
            if dep in by_name:
                indeg[t["name"]] += 1
                children[dep].append(t["name"])
    queue = deque(sorted(n for n, d in indeg.items() if d == 0))
    ordered = []
    while queue:
        n = queue.popleft()
        ordered.append(by_name[n])
        for child in sorted(children[n]):
            indeg[child] -= 1
            if indeg[child] == 0:
                queue.append(child)
    done = {t["name"] for t in ordered}
    ordered += [t for t in table_defs if t["name"] not in done]
    return ordered


# ---------------------------------------------------------------------- #
# Format .sql : une instruction par ligne (pas de saut de ligne dans les
# valeurs : elles sont échappées), donc l'import peut lire le fichier ligne à
# ligne sans analyseur SQL. Le fichier reste du SQL valide (`psql -f`).
# ---------------------------------------------------------------------- #
SQL_MAGIC = "-- cdd-pg-snapshot-sql v1"
TABLE_MARKER = "-- @table "        # suivi de {"name": ..., "rows": N} en JSON


def oneline(sql):
    return sql.replace("\r", " ").replace("\n", " ")


def q_lit(value):
    """Littéral SQL simple pour un nom (jamais de valeur utilisateur)."""
    return "'" + value.replace("'", "''") + "'"


def sql_literal(value):
    """Valeur (texte renvoyé par `col::text`) -> littéral SQL sur une ligne.

    Non typé volontairement : dans un INSERT … VALUES, PostgreSQL convertit
    le littéral vers le type de la colonne (bigint, jsonb, timestamptz…).
    """
    if value is None:
        return "NULL"
    if "\\" in value or "\n" in value or "\r" in value:
        value = (value.replace("\\", "\\\\").replace("'", "''")
                 .replace("\n", "\\n").replace("\r", "\\r"))
        return "E'" + value + "'"
    return "'" + value.replace("'", "''") + "'"


def create_table_sql(t):
    defs = []
    for c in t["columns"]:
        d = f"{qi(c['name'])} {c['type']}"
        default = oneline(c["default"]) if c["default"] is not None else None
        if c["generated"] == "s":
            d += f" GENERATED ALWAYS AS ({default}) STORED"
        elif c["identity"] == "a":
            d += " GENERATED ALWAYS AS IDENTITY"
        elif c["identity"] == "d":
            d += " GENERATED BY DEFAULT AS IDENTITY"
        elif default is not None:
            d += f" DEFAULT {default}"
        if c["notnull"]:
            d += " NOT NULL"
        defs.append(d)
    return f"CREATE TABLE IF NOT EXISTS {qt(t['name'])} ({', '.join(defs)});"


def add_constraint_sql(table, c):
    """ALTER TABLE … ADD CONSTRAINT, sans effet si elle existe déjà (par nom ;
    pour une clé primaire : si la table en a déjà une, quel que soit son nom)."""
    cond = "contype = 'p'" if c["type"] == "p" else f"conname = {q_lit(c['name'])}"
    return (f"DO $snap$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint "
            f"WHERE conrelid = {q_lit(qt(table))}::regclass AND {cond}) THEN "
            f"ALTER TABLE {qt(table)} ADD CONSTRAINT {qi(c['name'])} "
            f"{oneline(c['def'])}; END IF; END $snap$;")


def create_index_sql(definition):
    d = oneline(definition)
    d = d.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
    d = d.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
    return d + ";"


def reset_sequence_sql(table, col):
    """setval(séquence, max(colonne)) sans jamais reculer."""
    seq = f"pg_get_serial_sequence({q_lit(qt(table))}, {q_lit(col)})"
    return (f"SELECT setval(s::regclass, GREATEST(m, 1), m > 0) FROM ("
            f"SELECT {seq} AS s, GREATEST("
            f"(SELECT COALESCE(MAX({qi(col)}), 0) FROM {qt(table)}), "
            f"COALESCE(pg_sequence_last_value({seq}::regclass), 0)) AS m) x "
            f"WHERE s IS NOT NULL;")
