-- Estado de la ingesta live (feature 002). Idempotente: vale en un volumen ya creado.

CREATE TABLE IF NOT EXISTS ingesta.publicadas (
    event_id      text         NOT NULL CHECK (event_id <> ''),
    updated_ms    bigint       NOT NULL CHECK (updated_ms >= 0),
    publicada_en  timestamptz  NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (event_id, updated_ms)
);
COMMENT ON TABLE ingesta.publicadas IS
    'Versiones cuyo acuse de Kafka ya se recibió. No se borra si el evento sale del feed.';

CREATE TABLE IF NOT EXISTS ingesta.consultas (
    id           bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url          text         NOT NULL,
    acabada_en   timestamptz  NOT NULL DEFAULT clock_timestamp(),
    http_status  integer,
    bytes        integer,
    sha256       text,
    features     integer,
    publicados   integer,
    omitidos     integer,
    excluidos    integer,
    copia_nueva  boolean,
    error        text
);
COMMENT ON TABLE ingesta.consultas IS 'Una fila por intento de descarga del feed USGS.';

CREATE TABLE IF NOT EXISTS ingesta.exclusiones (
    id           bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    consulta_id  bigint,
    event_id     text,
    tipo         text,
    motivo       text         NOT NULL,
    visto_en     timestamptz  NOT NULL DEFAULT clock_timestamp()
);
COMMENT ON TABLE ingesta.exclusiones IS 'Eventos del feed que no se publican, con el motivo.';

INSERT INTO ingesta.version_esquema (version, nombre)
VALUES (2, 'ingesta_live') ON CONFLICT (version) DO NOTHING;
