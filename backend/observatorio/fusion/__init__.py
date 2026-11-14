"""Fusión de fuentes (feature 013): normalizar, emparejar y emitir el evento fusionado.

`normalizar` y `emparejar` son Python puro (se prueban sin Spark); `estado` habla con PostgreSQL y
`job` es el trabajo de PySpark Structured Streaming que los orquesta.
"""
