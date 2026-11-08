# T25 · Pruebas 9 y 10 con el túnel real de ngrok (2026-11-08)

Pila completa en Compose (los cinco servicios `running`), ngrok 3.39.1 con el authtoken de la cuenta del alumno
(configurado fuera del repositorio) y el panel en `http://localhost:4200` con `frontend/public/config.json` apuntando
**temporalmente** a la URL del túnel; el fichero se restauró a `http://127.0.0.1:8000` al terminar y no se ha
versionado con la URL. La URL pública se escribe aquí como `https://<dominio>.ngrok-free.dev`: es el dominio fijo
gratuito de la cuenta y no cambia al reiniciar el túnel.

## Túnel abierto (16:41–16:42 UTC)

```text
PS> ngrok http 8000 --config <ngrok.yml de la cuenta>
GET  https://<dominio>.ngrok-free.dev/health   → 200
OPTIONS /eventos (Origin: http://localhost:4200, Access-Control-Request-Headers: ngrok-skip-browser-warning)
     → 200, Access-Control-Allow-Origin: http://localhost:4200, la cabecera ngrok-skip-browser-warning permitida
```

Panel: las 11 peticiones de la primera ronda van al dominio de ngrok (ninguna a `127.0.0.1:8000`); «Último acceso
correcto a la API 17:42:09 (16:42 UTC)», 492 eventos reales. Captura: `t25-tunel-abierto.png`.

## Prueba 9 · cerrar el túnel (16:42:29 UTC)

```text
PS> Stop-Process ngrok
PS> curl.exe -s -o NUL -w "HTTP_CODE:%{http_code} ngrok_error:%header{ngrok-error-code}\n" https://<dominio>.ngrok-free.dev/health
HTTP_CODE:404 ngrok_error:ERR_NGROK_3200
```

Sin tocar el panel, en la siguiente ronda de refresco (24 s después de cerrar) aparece «⛔ La API no responde: se
muestran los últimos datos recibidos.», con los avisos de mapa, tabla y bloques «No se pudo actualizar … (La API no
responde (red, túnel de ngrok caído o bloqueo CORS)). Se muestran datos del 17:42:09 (16:42 UTC), desactualizados.».
El mapa y la tabla conservan los 492 eventos. Captura: `t25-tunel-cerrado.png`. En la captura el aviso termina en
«CORS).).»: el punto doble se corrigió justo después en `frontend/src/app/i18n/traducir.ts` (con su prueba).

## Prueba 10 · volver a abrirlo (16:43:32 UTC)

```text
PS> ngrok http 8000 --config <ngrok.yml de la cuenta>
https://<dominio>.ngrok-free.dev      (la misma URL)
HTTP_CODE:200                         (/health)
```

Sin recargar ni recompilar, la siguiente ronda (16:44:11 UTC, 39 s después de reabrir) devuelve el panel a la
normalidad: desaparecen los avisos y «Último acceso correcto a la API» pasa a 17:44:11 (16:44 UTC). Captura:
`t25-tunel-recuperado.png`. El túnel se cerró al terminar para no dejar la API expuesta.

## Lo que sigue sin probarse

- **Netlify**: el panel no se ha publicado; el origen que se probó en CORS es `http://localhost:4200`.
- **Nota práctica**: ngrok instalado desde Microsoft Store guarda `ngrok.yml` en
  `%LOCALAPPDATA%\Packages\ngrok.ngrok_*\LocalCache\Local\ngrok\`; desde otra terminal hay que pasarlo con `--config`.
