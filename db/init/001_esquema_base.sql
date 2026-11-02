-- Esquema base de la feature 001-esqueleto (data-model.md §3).
-- Idempotente: se puede ejecutar sobre un volumen con datos sin perder nada (R-07).

CREATE SCHEMA IF NOT EXISTS live;
CREATE SCHEMA IF NOT EXISTS replay;
CREATE SCHEMA IF NOT EXISTS ingesta;
COMMENT ON SCHEMA live    IS 'Datos del modo live (mode = live)';
COMMENT ON SCHEMA replay  IS 'Reservado para la reproducción histórica (feature 004)';
COMMENT ON SCHEMA ingesta IS 'Ingesta y calidad: cuarentena y versión del esquema';

CREATE TABLE IF NOT EXISTS ingesta.version_esquema (
    version      integer      PRIMARY KEY CHECK (version > 0),
    nombre       text         NOT NULL,
    aplicada_en  timestamptz  NOT NULL DEFAULT clock_timestamp()
);

-- Una fila por versión recibida de un evento; el historial no se sobrescribe.
CREATE TABLE IF NOT EXISTS live.versiones_evento (
    event_id        text         NOT NULL CHECK (event_id <> ''),
    updated         timestamptz  NOT NULL,
    schema_version  smallint     NOT NULL,
    source          text         NOT NULL,
    mode            text         NOT NULL DEFAULT 'live' CHECK (mode = 'live'),
    sintetico       boolean      NOT NULL,
    ingested_at     timestamptz  NOT NULL,
    processed_at    timestamptz  NOT NULL DEFAULT clock_timestamp(),
    topic           text         NOT NULL,
    particion       integer      NOT NULL,
    offset_kafka    bigint       NOT NULL,
    original        jsonb        NOT NULL,
    CONSTRAINT versiones_evento_pk PRIMARY KEY (event_id, updated),
    CONSTRAINT versiones_evento_sintetico_coherente CHECK (
        sintetico = (source   LIKE 'synthetic-%')
        AND sintetico = (event_id LIKE 'synthetic-%'))
);
CREATE INDEX IF NOT EXISTS versiones_evento_processed_at_idx
    ON live.versiones_evento (processed_at DESC);

-- Registros Kafka que incumplen el contrato o no se pueden almacenar.
CREATE TABLE IF NOT EXISTS ingesta.cuarentena (
    id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    motivo        text         NOT NULL,
    detalle       text,
    topic         text         NOT NULL,
    particion     integer      NOT NULL,
    offset_kafka  bigint       NOT NULL,
    clave         bytea,
    original      bytea,
    recibido_en   timestamptz  NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT cuarentena_posicion_uk UNIQUE (topic, particion, offset_kafka)
);

INSERT INTO ingesta.version_esquema (version, nombre)
VALUES (1, 'esquema_base') ON CONFLICT (version) DO NOTHING;
