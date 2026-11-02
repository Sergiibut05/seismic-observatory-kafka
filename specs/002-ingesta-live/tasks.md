# Tareas 002

- [x] T1 `feed.py` + `tests/unit/test_feed.py`: clasificar, HTTP, copia por hash y retención
- [x] T2 `db/init/002_ingesta_live.sql` y creación al arrancar
- [x] T3 `ciclo.py` + test con dobles: publica, omite, excluye, marca tras el acuse, no marca si el acuse falla
- [x] T4 Config, compose, `.env.example`: URL, periodo, timeout, directorio, retención y PostgreSQL en el productor
- [x] T5 `app.py`: bucle junto a los supervisores de Kafka y PostgreSQL
- [x] T6 README: feed, originales, «no está en la ventana ≠ borrado», hueco > 24 h
- [x] T7 pytest en la imagen (376) y una pasada real: 229 publicados, al minuto siguiente 228 omitidos
