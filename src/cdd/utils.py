from administrativelevels.models import AdministrativeLevel
from functools import wraps
from django.http import HttpResponseServerError
import signal



def get_administrative_region_name(administrative_id, use_cvd=True):
    not_found_message = f'[Missing region with administrative_id "{administrative_id}"]'
    if not administrative_id:
        return not_found_message

    region_names = []
    has_parent = True

    while has_parent:
        objects = AdministrativeLevel.objects.using('mis').filter(id=int(administrative_id))

        try:
            _object = objects.first()
            region_names.append(_object.cvd.name if (use_cvd and _object.type == "Village") else _object.name)
            administrative_id = _object.parent_id
            has_parent = administrative_id is not None
        except Exception:
            region_names.append(not_found_message)
            has_parent = False

    return ', '.join(region_names)


def elements_communs(liste1, liste2):
    communs = list(set(liste1) & set(liste2))
    return communs


#sudo service nginx restart

class TimeoutError(Exception):
    pass

def timeout(timeout_sec=600):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError("Request timed out")
            
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(timeout_sec)
            
            try:
                result = view_func(request, *args, **kwargs)
                signal.alarm(0)  # Désactive l'alarme
                return result
            except TimeoutError:
                return HttpResponseServerError("504 Gateway Timeout", status=504)
        return wrapped_view
    return decorator