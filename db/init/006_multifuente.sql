-- Varias fuentes fusionadas (feature 013). Idempotente: vale en un volumen ya creado.
-- En un volumen existente lo aplican también los servicios al arrancar: productores
-- (ingesta.*), consumidor (live.*, replay.*) y fusión (fusion.*). Ver data-model.md de 013.

-- ── Ingesta: de qué fuente es cada fila ─────────────────────────────
ALTER TABLE ingesta.publicadas  ADD COLUMN IF NOT EXISTS fuente text NOT NULL DEFAULT 'usgs';
ALTER TABLE ingesta.consultas   ADD COLUMN IF NOT EXISTS fuente text NOT NULL DEFAULT 'usgs';
ALTER TABLE ingesta.exclusiones ADD COLUMN IF NOT EXISTS fuente text NOT NULL DEFAULT 'usgs';

-- Los ids de USGS y de EMSC son espacios distintos: la fuente entra en la clave.
DO $$
DECLARE pk text;
BEGIN
    SELECT conname INTO pk FROM pg_constraint
    WHERE conrelid = 'ingesta.publicadas'::regclass AND contype = 'p' AND array_length(conkey, 1) = 2;
    IF pk IS NOT NULL THEN
        EXECUTE format('ALTER TABLE ingesta.publicadas DROP CONSTRAINT %I', pk);
        ALTER TABLE ingesta.publicadas ADD PRIMARY KEY (fuente, event_id, updated_ms);
    END IF;
END $$;

-- ── Analítico: las fuentes de cada evento ───────────────────────────
ALTER TABLE live.versiones_evento   ADD COLUMN IF NOT EXISTS fuentes text[];
ALTER TABLE replay.versiones_evento ADD COLUMN IF NOT EXISTS fuentes text[];
ALTER TABLE live.evento_actual      ADD COLUMN IF NOT EXISTS fuentes text[] NOT NULL DEFAULT '{}';
ALTER TABLE replay.evento_actual    ADD COLUMN IF NOT EXISTS fuentes text[] NOT NULL DEFAULT '{}';
UPDATE live.evento_actual   SET fuentes = ARRAY[source] WHERE fuentes = '{}';
UPDATE replay.evento_actual SET fuentes = ARRAY[source] WHERE fuentes = '{}';

-- ── Estado de la fusión (lo escribe solo el servicio fusion) ────────
CREATE SCHEMA IF NOT EXISTS fusion;

CREATE TABLE IF NOT EXISTS fusion.informe (
    fuente         text              NOT NULL,
    id_origen      text              NOT NULL CHECK (id_origen <> ''),
    updated_ms     bigint            NOT NULL CHECK (updated_ms >= 0),
    tiempo_ms      bigint            NOT NULL,
    latitud        double precision  NOT NULL,
    longitud       double precision  NOT NULL,
    profundidad    double precision,
    magnitud       double precision,
    tipo_magnitud  text,
    lugar          text,
    ingested_at    timestamptz       NOT NULL,
    original       jsonb             NOT NULL,
    canonico       text              NOT NULL,
    PRIMARY KEY (fuente, id_origen)
);
COMMENT ON TABLE fusion.informe IS
    'Último informe de cada fuente sobre un terremoto y el evento fusionado al que pertenece.';
CREATE INDEX IF NOT EXISTS informe_tiempo_idx ON fusion.informe (tiempo_ms);
CREATE INDEX IF NOT EXISTS informe_canonico_idx ON fusion.informe (canonico);

CREATE TABLE IF NOT EXISTS fusion.canonico (
    id                text         PRIMARY KEY,
    updated_ms        bigint       NOT NULL,
    firma             text         NOT NULL,
    fuente_principal  text         NOT NULL,
    actualizado_en    timestamptz  NOT NULL DEFAULT clock_timestamp()
);
COMMENT ON TABLE fusion.canonico IS
    'Lo último emitido de cada evento fusionado: si la firma no cambia, no se vuelve a emitir.';

CREATE TABLE IF NOT EXISTS fusion.descartes (
    id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fuente        text,
    id_origen     text,
    motivo        text         NOT NULL,
    detalle       text,
    topic         text         NOT NULL,
    particion     integer      NOT NULL,
    offset_kafka  bigint       NOT NULL,
    visto_en      timestamptz  NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT descartes_posicion_unica UNIQUE (topic, particion, offset_kafka)
);
COMMENT ON TABLE fusion.descartes IS 'Informes que la fusión no puede tratar, con su motivo.';

INSERT INTO ingesta.version_esquema (version, nombre)
VALUES (6, 'multifuente') ON CONFLICT (version) DO NOTHING;
