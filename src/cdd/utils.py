from administrativelevels.models import AdministrativeLevel





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