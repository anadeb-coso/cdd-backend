from datetime import datetime, timedelta
from django.utils import timezone
import zlib

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


def is_datetime_in_past_or_now(input_datetime):
    """datetime.strptime(d, '%Y-%m-%dT%H:%M:%SZ')"""
    try:
        date_time_to_check = input_datetime
        now = timezone.now()
        return date_time_to_check <= now
    except:
        date_time_to_check = input_datetime
        now = datetime.now()
        return date_time_to_check <= now


def times_split(hours=24, minutes=60, minutes_between=15):
    times = []
    for h in range(hours):
        for m in range(0, minutes, minutes_between):
            time_str = f"{h:02}:{m:02}"
            times.append(time_str)
    return times


def get_dates_between(start_date, end_date, must_between=None):
    dates = []
    if type(start_date) is str:
        current_date = datetime.fromisoformat(start_date)
    else:
        current_date = start_date

    while current_date <= (datetime.fromisoformat(end_date) if type(end_date) is str else end_date):
        if not must_between:
            dates.append(current_date.date()) # .isoformat()
        elif current_date.date() in must_between:
            dates.append(current_date.date())
        current_date += timedelta(days=1)

    return dates


def get_validation_code(seed):
    return str(zlib.adler32(str(seed).encode('utf-8')))[:6]

def get_code(seed):
        import zlib
        return str(zlib.adler32(str(seed).encode('utf-8')))[:6]