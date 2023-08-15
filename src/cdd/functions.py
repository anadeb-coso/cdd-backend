

def exists_id(liste, id):
    for o in liste:
        if o.id == id:
            return True
    return False

def exists_id_in_a_dict(liste, id):
    for o in liste:
        if o.get('id') == id:
            return True
    return False

def get_number_under_two_letter(n: str):
    if n.isdigit() and len(n) < 2:
        return "0"+n
    return n
        

def datetime_complet_str(d_str: str):
    if d_str:
        datetime_complet_list = d_str.split(" ")
        y_m_d = datetime_complet_list[0].split("-")
        h_m_s = datetime_complet_list[1].split(":")

        return "{}-{}-{} {}:{}:{}".format(
            y_m_d[0], get_number_under_two_letter(y_m_d[1]), get_number_under_two_letter(y_m_d[2]), 
            get_number_under_two_letter(h_m_s[0]), get_number_under_two_letter(h_m_s[1]), 
            get_number_under_two_letter(h_m_s[2])
        )
    return d_str