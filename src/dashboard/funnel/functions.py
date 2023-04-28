

def get_item_phase(items, id_phase):
    for key, item in items.items():
        if item and item.get('id') == id_phase:
            return key, item
    return None, None

def get_region_id(administrativelevel):
    if not administrativelevel:
        return 0
    if administrativelevel.parent:
        return get_region_id(administrativelevel.parent)
    return administrativelevel.id