-- Estado actual (una fila por evento) y dimensión de país. Idempotente.

CREATE TABLE IF NOT EXISTS ingesta.pais (
    codigo      text PRIMARY KEY CHECK (codigo <> ''),
    nombre      text NOT NULL,
    continente  text,
    subregion   text
);

CREATE TABLE IF NOT EXISTS live.evento_actual (
    event_id      text             NOT NULL CHECK (event_id <> ''),
    updated       timestamptz      NOT NULL,
    ocurrencia    timestamptz      NOT NULL,
    magnitud      double precision,
    profundidad   double precision,
    longitud      double precision NOT NULL,
    latitud       double precision NOT NULL,
    pais_codigo   text,
    pais_nombre   text             NOT NULL,
    source        text             NOT NULL,
    mode          text             NOT NULL DEFAULT 'live' CHECK (mode = 'live'),
    sintetico     boolean          NOT NULL,
    ingested_at   timestamptz      NOT NULL,
    processed_at  timestamptz      NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT evento_actual_pk PRIMARY KEY (event_id),
    CONSTRAINT evento_actual_sintetico_coherente CHECK (
        sintetico = (source LIKE 'synthetic-%')
        AND sintetico = (event_id LIKE 'synthetic-%')),
    CONSTRAINT evento_actual_pais_fk FOREIGN KEY (pais_codigo) REFERENCES ingesta.pais (codigo)
);
CREATE INDEX IF NOT EXISTS evento_actual_pais_ocurrencia_idx
    ON live.evento_actual (pais_nombre, ocurrencia);

CREATE TABLE IF NOT EXISTS replay.evento_actual (
    event_id      text             NOT NULL CHECK (event_id <> ''),
    updated       timestamptz      NOT NULL,
    ocurrencia    timestamptz      NOT NULL,
    magnitud      double precision,
    profundidad   double precision,
    longitud      double precision NOT NULL,
    latitud       double precision NOT NULL,
    pais_codigo   text,
    pais_nombre   text             NOT NULL,
    source        text             NOT NULL,
    mode          text             NOT NULL DEFAULT 'replay' CHECK (mode = 'replay'),
    sintetico     boolean          NOT NULL,
    ingested_at   timestamptz      NOT NULL,
    processed_at  timestamptz      NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT evento_replay_pk PRIMARY KEY (event_id),
    CONSTRAINT evento_replay_sintetico_coherente CHECK (
        sintetico = (source LIKE 'synthetic-%')
        AND sintetico = (event_id LIKE 'synthetic-%')),
    CONSTRAINT evento_replay_pais_fk FOREIGN KEY (pais_codigo) REFERENCES ingesta.pais (codigo)
);
CREATE INDEX IF NOT EXISTS evento_replay_pais_ocurrencia_idx
    ON replay.evento_actual (pais_nombre, ocurrencia);

INSERT INTO ingesta.version_esquema (version, nombre)
VALUES (4, 'estado_actual') ON CONFLICT (version) DO NOTHING;
