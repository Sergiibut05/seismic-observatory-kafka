# Tareas 004

- [x] T1 `historico.py` + `tests/unit/test_historico.py`: partir, exceso, deduplicar, no truncar
- [x] T2 `replay.py` + `tests/unit/test_replay.py`: orden, duplicado y revisión con el tiempo original
- [x] T3 `db/init/003_replay.sql` y `CREATE TABLE IF NOT EXISTS` al arrancar el consumidor
- [x] T4 Productor crea `eventos.replay`; consumidor se suscribe a los dos topics y elige el esquema por el topic
- [x] T5 Compose, `.env.example` y README: `TOPIC_REPLAY`, montaje de `data/historico`, hueco > 24 h
- [x] T6 pytest en la imagen (381), descarga real de 2025 (18.302 eventos, 12 meses) y una reproducción: 41 filas, 40 ids, duplicado omitido, `eventos_reales` se quedó en 239 y `live` no recibió el topic de replay
