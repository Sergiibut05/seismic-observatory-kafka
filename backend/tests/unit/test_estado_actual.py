"""La comparación de revisiones está escrita en el SQL del upsert, no en un contador de mensajes."""

from psycopg import sql

from observatorio.consumer.persistencia import COMPARACION_REVISION, _upsert_sql


def test_solo_una_revision_estrictamente_posterior_sustituye_el_estado():
    sentencia = _upsert_sql(sql.Identifier("live"))
    assert "updated < EXCLUDED.updated" in COMPARACION_REVISION
    assert sentencia.as_string(None).count("live") == 2
