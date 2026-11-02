-- Histórico USGS 2025 (denominador de la comparación de la API) e índice de la lista. Idempotente.
-- Mismo esquema que backend/observatorio/historico_cargar.py (_DDL), que lo crea en volúmenes antiguos.

CREATE SCHEMA IF NOT EXISTS historico;

CREATE TABLE IF NOT EXISTS historico.evento_2025 (
    event_id     text             NOT NULL CHECK (event_id <> ''),
    updated      timestamptz      NOT NULL,
    ocurrencia   timestamptz      NOT NULL,
    magnitud     double precision,
    profundidad  double precision,
    longitud     double precision NOT NULL,
    latitud      double precision NOT NULL,
    pais_codigo  text,
    pais_nombre  text             NOT NULL,
    cargado_en   timestamptz      NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT evento_2025_pk PRIMARY KEY (event_id),
    CONSTRAINT evento_2025_ocurrencia_en_2025 CHECK (
        ocurrencia >= '2025-01-01T00:00:00Z' AND ocurrencia < '2026-01-01T00:00:00Z'),
    CONSTRAINT evento_2025_pais_fk FOREIGN KEY (pais_codigo) REFERENCES ingesta.pais (codigo)
);

COMMENT ON TABLE historico.evento_2025 IS
    'Catálogo USGS de 2025 (solo datos reales), una fila por event_id con el updated más reciente. Denominador de la comparación histórica.';
COMMENT ON COLUMN historico.evento_2025.ocurrencia IS
    'properties.time (ms epoch) en UTC; el CHECK la limita a 2025, así el denominador son siempre 365 días.';
COMMENT ON COLUMN historico.evento_2025.updated IS
    'properties.updated (ms epoch) en UTC; solo una revisión estrictamente posterior sustituye la fila.';
COMMENT ON COLUMN historico.evento_2025.magnitud IS 'Nulo si USGS no la informa; nunca se rellena con 0.';
COMMENT ON COLUMN historico.evento_2025.profundidad IS 'Kilómetros, tercera coordenada del punto; nulo si falta.';
COMMENT ON COLUMN historico.evento_2025.pais_codigo IS
    'ADM0_A3 por punto en polígono (EPSG:4326); nulo = «Sin país asignado».';
COMMENT ON COLUMN historico.evento_2025.cargado_en IS 'Instante de la carga o de la última revisión aplicada.';

-- Lista paginada sin ordenar, rangos por fecha y ventanas horarias de la API.
CREATE INDEX IF NOT EXISTS evento_actual_ocurrencia_idx
    ON live.evento_actual (ocurrencia DESC, event_id);

INSERT INTO ingesta.version_esquema (version, nombre)
VALUES (5, 'historico') ON CONFLICT (version) DO NOTHING;
