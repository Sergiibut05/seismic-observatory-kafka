"""Mide cómo difieren USGS y EMSC para el mismo terremoto (enero 2025, M>=4).

Para cada evento USGS busca el EMSC más cercano en una ventana amplia (120 s, 300 km) y
resume las diferencias. También cuenta parejas USGS-USGS muy próximas (réplicas), que son el
riesgo de fusionar de más.
"""
import bisect
import json
import math
import sys
import urllib.request
from datetime import datetime

DESDE, HASTA, MMIN = sys.argv[1], sys.argv[2], float(sys.argv[3])


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "seismic-observatory/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def iso_ms(texto):
    return int(datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp() * 1000)


u = get(f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={DESDE}&endtime={HASTA}"
        f"&minmagnitude={MMIN}&eventtype=earthquake&orderby=time-asc")["features"]
e = get(f"https://www.seismicportal.eu/fdsnws/event/1/query?format=json&start={DESDE}&end={HASTA}"
        f"&minmag={MMIN - 0.5}&limit=10000")["features"]
U = sorted((f["properties"]["time"], f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0], f["properties"]["mag"] or 0) for f in u)
E = sorted((iso_ms(f["properties"]["time"]), f["properties"]["lat"], f["properties"]["lon"], f["properties"]["mag"] or 0)
           for f in e if f["properties"].get("evtype") == "ke")
print(f"USGS {len(U)}  EMSC {len(E)} (EMSC con M>={MMIN - 0.5} para no perder pares por magnitud)")


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[2], b[1], b[2]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


tiempos = [x[0] for x in E]
pares = []
for a in U:
    i, j = bisect.bisect_left(tiempos, a[0] - 120_000), bisect.bisect_right(tiempos, a[0] + 120_000)
    mejor = None
    for b in E[i:j]:
        dt, d = abs(b[0] - a[0]) / 1000, km(a, b)
        if d <= 300:
            s = dt / 30 + d / 100
            if mejor is None or s < mejor[0]:
                mejor = (s, dt, d, abs(a[3] - b[3]))
    if mejor:
        pares.append(mejor)


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


dts, ds, dms = [p[1] for p in pares], [p[2] for p in pares], [p[3] for p in pares]
print(f"USGS con pareja EMSC (120 s, 300 km): {len(pares)}/{len(U)} = {len(pares) / len(U):.1%}")
for nombre, v in (("dt s", dts), ("dist km", ds), ("dmag", dms)):
    print(f"  {nombre:8s} p50={pct(v, .5):.1f}  p90={pct(v, .9):.1f}  p95={pct(v, .95):.1f}  p99={pct(v, .99):.1f}  max={max(v):.1f}")
for t, d in ((10, 50), (20, 50), (30, 100), (30, 150), (60, 150)):
    n = sum(1 for p in pares if p[1] <= t and p[2] <= d)
    print(f"  emparejados con <= {t:>2} s y <= {d:>3} km: {n}/{len(U)} = {n / len(U):.1%}")

# Riesgo: dos eventos distintos de la MISMA fuente tan cerca que la regla los confundiría.
tu = [x[0] for x in U]
for t, d in ((30, 100), (60, 150)):
    n = 0
    for k, a in enumerate(U):
        for b in U[k + 1: bisect.bisect_right(tu, a[0] + t * 1000)]:
            if km(a, b) <= d:
                n += 1
    print(f"  parejas USGS-USGS a <= {t} s y <= {d} km (réplicas que no deben fusionarse entre sí): {n}")
