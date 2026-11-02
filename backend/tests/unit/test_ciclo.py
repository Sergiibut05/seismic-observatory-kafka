"""Una pasada del ciclo con dobles: no hay Kafka, PostgreSQL ni USGS reales."""

import asyncio
from datetime import datetime, timezone

from observatorio.common.config import ajustes_productor
from observatorio.producer.ciclo import una_pasada
from observatorio.producer.feed import ErrorTransitorio

AHORA = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
FEED = b'{"type":"FeatureCollection","features":[{"type":"Feature","id":"us1","properties":{"type":"earthquake","updated":1000}},{"type":"Feature","id":"us2","properties":{"type":"quarry blast","updated":1000}}]}'


class ProductorFalso:
    def __init__(self, falla=False):
        self.enviados = []
        self.falla = falla

    async def send_and_wait(self, topic, value, key):
        if self.falla:
            raise RuntimeError("sin acuse")
        self.enviados.append((topic, key))


class ConexionFalsa:
    def __init__(self, db):
        self.db = db

    async def execute(self, sql, params=None):
        self.db.sentencias.append((sql, params))
        if "RETURNING" in sql:
            return self

    async def fetchone(self):
        return (1,)


class BaseFalsa:
    def __init__(self, publicadas=()):
        self.publicadas = list(publicadas)
        self.sentencias = []

    async def consultar(self, sql, params=None, timeout=3):
        return list(self.publicadas)

    def transaccion(self, timeout=10):
        conexion = ConexionFalsa(self)
        base = self

        class _Transaccion:
            async def __aenter__(self):
                return conexion

            async def __aexit__(self, *args):
                if any("INSERT INTO ingesta.publicadas" in (sql or "") for sql, _ in base.sentencias[-1:]):
                    params = base.sentencias[-1][1]
                    base.publicadas.append(params)
                return False

        return _Transaccion()


def ajustes(tmp_path):
    return ajustes_productor(
        {
            "POSTGRES_PASSWORD": "x",
            "FEED_DIR": str(tmp_path),
            "POLL_INTERVAL_SECONDS": "60",
        }
    )


def test_publica_el_terremoto_marca_tras_el_acuse_y_excluye_el_resto(tmp_path):
    base = BaseFalsa()
    productor = ProductorFalso()

    def descargar(url, timeout):
        return 200, FEED

    resultado = asyncio.run(una_pasada(ajustes(tmp_path), productor, base, descargar, AHORA))
    assert [e["id"] for e in resultado.publicar] == ["us1"]
    assert productor.enviados[0][1] == b"us1"
    assert ("us1", 1000) in base.publicadas
    assert resultado.exclusiones[0].motivo == "tipo_no_terremoto"
    assert any(tmp_path.glob("*.geojson"))


def test_lo_ya_publicado_no_se_reenvia(tmp_path):
    base = BaseFalsa(publicadas=[("us1", 1000)])
    productor = ProductorFalso()
    resultado = asyncio.run(una_pasada(ajustes(tmp_path), productor, base, lambda url, timeout: (200, FEED), AHORA))
    assert productor.enviados == []
    assert resultado.omitidos == 1


def test_sin_acuse_no_marca_la_version(tmp_path):
    base = BaseFalsa()
    productor = ProductorFalso(falla=True)
    try:
        asyncio.run(una_pasada(ajustes(tmp_path), productor, base, lambda url, timeout: (200, FEED), AHORA))
    except RuntimeError:
        pass
    else:
        raise AssertionError("tenía que fallar el acuse")
    assert base.publicadas == []


def test_json_roto_no_borra_lo_publicado(tmp_path):
    base = BaseFalsa(publicadas=[("us1", 1000)])
    asyncio.run(una_pasada(ajustes(tmp_path), ProductorFalso(), base, lambda url, timeout: (200, b"{"), AHORA))
    assert base.publicadas == [("us1", 1000)]


def test_http_429_es_transitorio_y_conserva_el_estado(tmp_path):
    base = BaseFalsa(publicadas=[("us1", 1000)])
    try:
        asyncio.run(una_pasada(ajustes(tmp_path), ProductorFalso(), base, lambda url, timeout: (429, b""), AHORA))
    except ErrorTransitorio as exc:
        assert exc.motivo == "http_429"
    else:
        raise AssertionError("429 tenía que reintentarse")
    assert base.publicadas == [("us1", 1000)]
