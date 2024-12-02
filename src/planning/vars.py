from cdd.functions import times_split



TIMES = tuple([(t, t) for t in times_split()])
DAYS = tuple([(d, d) for d in range(7)])