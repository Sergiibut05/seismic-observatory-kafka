"""La selección de replay conserva el tiempo original y añade los dos casos controlados."""

from observatorio.replay import preparar


def evento(event_id, tiempo, updated=None):
    return {"id": event_id, "properties": {"time": tiempo, "updated": updated if updated is not None else tiempo, "type": "earthquake"}}


def test_ordena_por_ocurrencia_y_anade_duplicado_y_revision():
    plan = preparar([evento("b", 200), evento("a", 100), evento("c", 300)], limite=2)
    casos = [caso for caso, _ in plan]
    assert casos == ["normal", "normal", "duplicado", "revision"]
    normales = [e for caso, e in plan if caso == "normal"]
    assert [e["id"] for e in normales] == ["a", "b"]
    assert [e["properties"]["time"] for e in normales] == [100, 200]
    duplicado = plan[2][1]
    revision = plan[3][1]
    assert duplicado == normales[0]
    assert revision["id"] == "a"
    assert revision["properties"]["time"] == 100
    assert revision["properties"]["updated"] == 100 + 60_000
