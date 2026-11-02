-- Tabla de la reproducción histórica. Idempotente. El consumidor también la crea al arrancar.

CREATE TABLE IF NOT EXISTS replay.versiones_evento (
    event_id        text         NOT NULL CHECK (event_id <> ''),
    updated         timestamptz  NOT NULL,
    schema_version  smallint     NOT NULL,
    source          text         NOT NULL,
    mode            text         NOT NULL DEFAULT 'replay' CHECK (mode = 'replay'),
    sintetico       boolean      NOT NULL,
    ingested_at     timestamptz  NOT NULL,
    processed_at    timestamptz  NOT NULL DEFAULT clock_timestamp(),
    topic           text         NOT NULL,
    particion       integer      NOT NULL,
    offset_kafka    bigint       NOT NULL,
    original        jsonb        NOT NULL,
    CONSTRAINT versiones_replay_pk PRIMARY KEY (event_id, updated),
    CONSTRAINT versiones_replay_sintetico_coherente CHECK (
        sintetico = (source LIKE 'synthetic-%')
        AND sintetico = (event_id LIKE 'synthetic-%'))
);

INSERT INTO ingesta.version_esquema (version, nombre)
VALUES (3, 'replay') ON CONFLICT (version) DO NOTHING;
