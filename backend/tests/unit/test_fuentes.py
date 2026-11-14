"""Adaptadores de fuente (USGS y EMSC): URLs, recuentos, tipo y versión."""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from observatorio.common.config import ConfigError, ajustes_productor
from observatorio.producer.fuentes import FuenteEmsc, FuenteUsgs, fuente_por_nombre, tipo_emsc, version_emsc

DESDE = datetime(2025, 3, 1, tzinfo=timezone.utc)
HASTA = datetime(2025, 4, 1, tzinfo=timezone.utc)


def params(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_usgs_consulta_y_recuento_fdsn():
    f = FuenteUsgs()
    q = params(f.url_consulta(DESDE, HASTA, 2.5))
    assert q == {
        "format": "geojson",
        "starttime": "2025-03-01T00:00:00",
        "endtime": "2025-04-01T00:00:00",
        "minmagnitude": "2.5",
        "eventtype": "earthquake",
        "orderby": "time-asc",
    }
    assert f.url_recuento(DESDE, HASTA, 2.5).startswith("https://earthquake.usgs.gov/fdsnws/event/1/count?")
    assert f.leer_recuento(b"18305\n") == 18305
    assert f.url_directo(DESDE).endswith("all_day.geojson")
    assert f.tope_consulta < 20_000  # USGS rechaza más de 20.000


def test_emsc_consulta_recuento_y_directo():
    f = FuenteEmsc()
    q = params(f.url_consulta(DESDE, HASTA, 2.5))
    assert q["format"] == "json" and q["minmag"] == "2.5" and q["orderby"] == "time-asc"
    assert (q["start"], q["end"]) == ("2025-03-01T00:00:00", "2025-04-01T00:00:00")
    assert f.leer_recuento(b'<?xml version="1.0"?>\n<Counts>\n<Events>\n109952\n</Events>\n</Counts>') == 109952
    with pytest.raises(ValueError):
        f.leer_recuento(b"<html>error</html>")
    directo = params(f.url_directo(datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)))
    assert directo["start"] == "2026-11-13T10:00:00"  # 26 h antes
    assert f.tope_consulta < 10_000  # EMSC corta en ~10.000 sin avisar


def test_tipo_y_version_de_emsc():
    assert tipo_emsc({"evtype": "ke"}) == (True, "ke")
    assert tipo_emsc({"evtype": "se"}) == (False, "se")
    assert tipo_emsc({}) == (False, None)
    assert version_emsc({"lastupdate": "2026-11-14T10:00:00Z"}) == 1_794_650_400_000
    assert version_emsc({"lastupdate": "mañana"}) is None


def test_version_de_un_evento():
    assert FuenteUsgs().version_de({"properties": {"updated": 5}}) == 5
    assert FuenteEmsc().version_de({"properties": {"lastupdate": "1970-01-01T00:00:01Z"}}) == 1000
    assert FuenteEmsc().version_de({}) is None


def test_fuente_por_nombre():
    assert isinstance(fuente_por_nombre("usgs"), FuenteUsgs)
    assert isinstance(fuente_por_nombre("emsc", emsc_base="http://x"), FuenteEmsc)
    with pytest.raises(ValueError):
        fuente_por_nombre("isc")


def test_ajustes_por_fuente():
    usgs = ajustes_productor({"POSTGRES_PASSWORD": "x"})
    assert (usgs.fuente, usgs.topic_fuente, usgs.feed_dir) == ("usgs", "eventos.usgs", "/data/usgs")
    emsc = ajustes_productor({"POSTGRES_PASSWORD": "x", "FUENTE": "emsc"})
    assert (emsc.fuente, emsc.topic_fuente, emsc.feed_dir) == ("emsc", "eventos.emsc", "/data/emsc")
    assert emsc.topic_live == "eventos.live"  # lo sigue creando (lo escribe la fusión)
    with pytest.raises(ConfigError, match="FUENTE"):
        ajustes_productor({"POSTGRES_PASSWORD": "x", "FUENTE": "isc"})
