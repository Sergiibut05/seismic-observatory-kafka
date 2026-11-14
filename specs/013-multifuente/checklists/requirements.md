# Checklist de requisitos 013

- [x] Cada FR traza a un apartado del enunciado (§2 servicios, §4 fuentes, §5 calidad, §6 modelo) o a una decisión del usuario.
- [x] Ningún requisito depende de una cifra no medida: los umbrales de fusión salen de evidencias/umbrales-*.txt y los volúmenes del relleno de recuentos reales.
- [x] Los criterios de éxito son comprobables con SQL, la API o los logs.
- [x] Lo que queda fuera está escrito (ISC, INGV, WebSocket, petición automática de histórico).
- [x] La constitución se enmienda antes del código (3.0.0).

## Decisiones del usuario (2026-11-14)

1. Enmendar la constitución sin dejar un modo «solo USGS» (la copia previa está en `respaldo/main-antes-multifuente`).
2. EMSC por sondeo, como mejor se vea.
3. Relleno de todo 2025 y lo que va de 2026.
4. Trabajo en una rama local, sin empujar ni fusionar en `main` hasta que lo pida.
5. Un solo subagente: verificador.
