"""Statistiques de la page « Résumé » d'un formulaire COSOCollect (graphiques façon kobocollect)."""
from collections import Counter, OrderedDict
from datetime import timedelta

from django.db.models import Count, Max, Min
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from .exports import select_fields_for_reports
from .models import CollectSubmission

RANGES = (7, 31, 90, 365)


def overview(form, submissions):
    by_status = dict(submissions.values_list('status').annotate(n=Count('pk')))
    dates = submissions.aggregate(first=Min('created_at'), last=Max('updated_at'))
    authors = set()
    for user_id, facilitator_id in submissions.values_list('user_id', 'facilitator_id'):
        authors.add(('f', facilitator_id) if facilitator_id else ('u', user_id))
    return {
        'total': sum(by_status.values()),
        'by_status': [
            {'status': key, 'label': str(label), 'count': by_status.get(key, 0)}
            for key, label in CollectSubmission.STATUSES
        ],
        'authors': len(authors),
        'first': dates['first'],
        'last': dates['last'],
    }


def timeline(submissions, days):
    """Saisies envoyées et démarrées par jour sur les `days` derniers jours (+ cumul des envoyées)."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    sent = dict(
        submissions.filter(submitted_at__isnull=False)
        .annotate(day=TruncDate('submitted_at')).filter(day__gte=start)
        .values_list('day').annotate(n=Count('pk'))
    )
    started = dict(
        submissions.annotate(day=TruncDate(Coalesce('started_at', 'created_at'))).filter(day__gte=start)
        .values_list('day').annotate(n=Count('pk'))
    )
    before = submissions.filter(submitted_at__isnull=False, submitted_at__date__lt=start).count()
    labels, sent_series, started_series, cumulative = [], [], [], []
    total = before
    for i in range(days):
        day = start + timedelta(days=i)
        labels.append(day.strftime('%d/%m'))
        sent_series.append(sent.get(day, 0))
        started_series.append(started.get(day, 0))
        total += sent.get(day, 0)
        cumulative.append(total)
    return {'labels': labels, 'sent': sent_series, 'started': started_series, 'cumulative': cumulative}


def by_author(submissions, limit=15):
    counter = Counter()
    for submission in submissions.select_related('user', 'facilitator').only(
            'user__first_name', 'user__last_name', 'user__username',
            'facilitator__name', 'facilitator__username'):
        counter[submission.author_name or '—'] += 1
    top = counter.most_common(limit)
    return {'labels': [name for name, _n in top], 'values': [n for _name, n in top]}


def by_source(submissions):
    rows = dict(submissions.values_list('source').annotate(n=Count('pk')))
    labels = dict(CollectSubmission.SOURCES)
    return {'labels': [labels.get(k, k) for k in rows], 'values': list(rows.values())}


def _values_for(field, data):
    """Toutes les valeurs d'un champ dans une saisie (plusieurs si le champ est dans un répétable)."""
    page = data[field['page']] if isinstance(data, list) and field['page'] < len(data) else {}
    parts = field['local_path'].split('.')

    def walk(cur, remaining):
        if not remaining:
            yield cur
            return
        if isinstance(cur, list):
            for item in cur:
                yield from walk(item, remaining)
            return
        if isinstance(cur, dict):
            yield from walk(cur.get(remaining[0]), remaining[1:])

    return [v for v in walk(page or {}, parts) if v not in (None, '', [])]


def question_reports(form, submissions, limit_choices=30):
    fields = select_fields_for_reports(form)
    reports = OrderedDict((f['path'], {'field': f, 'counter': Counter(), 'numbers': [], 'answered': 0}) for f in fields)
    total = 0
    for data in submissions.values_list('data', flat=True).iterator():
        total += 1
        for path, report in reports.items():
            field = report['field']
            values = _values_for(field, data)
            if values:
                report['answered'] += 1
            for value in values:
                if field['type'] in ('integer', 'decimal'):
                    try:
                        report['numbers'].append(float(value))
                    except (TypeError, ValueError):
                        pass
                else:
                    for v in (value if isinstance(value, list) else [value]):
                        report['counter'][str(v)] += 1

    out = []
    for path, report in reports.items():
        field = report['field']
        item = {
            'path': path, 'label': field['label'], 'type': field['type'],
            'group': ' / '.join(field['group_labels']), 'answered': report['answered'], 'total': total,
        }
        if field['type'] in ('integer', 'decimal'):
            numbers = report['numbers']
            if not numbers:
                continue
            item['stats'] = {
                'count': len(numbers), 'sum': round(sum(numbers), 2), 'mean': round(sum(numbers) / len(numbers), 2),
                'min': min(numbers), 'max': max(numbers),
            }
        else:
            counter = report['counter']
            if not counter:
                continue
            ordered = [(v, counter[v]) for v in field['choices'] if counter.get(v)]
            ordered += [(v, n) for v, n in counter.most_common() if v not in field['choices']]
            ordered = ordered[:limit_choices]
            item['labels'] = [field['choices'].get(v, v) for v, _n in ordered]
            item['values'] = [n for _v, n in ordered]
        out.append(item)
    return out


def pick_range(raw):
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return 31
    return days if days in RANGES else 31
