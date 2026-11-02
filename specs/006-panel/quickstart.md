# Panel: arranque local y publicación

Node 22.14 (el del equipo) y npm 10. La API ya escucha en `http://127.0.0.1:8000`.

```powershell
cd frontend
npm ci
npm test
npm start
```

`npm start` abre `http://localhost:4200` y lee `public/config.json` (`apiBaseUrl` por defecto `http://127.0.0.1:8000`). El catálogo de fronteras se comprueba solo (`catalogo:verificar`); si la copia se estropea, `npm run catalogo:copiar`.

## Túnel y Netlify

1. En el anfitrión, con la cuenta de ngrok ya configurada **fuera del repo**: `ngrok http 8000`.
2. Copia la URL HTTPS a `frontend/public/config.json` (`apiBaseUrl`, sin barra final) **antes** de compilar. Plantilla: `config.ejemplo.json`. No pongas el authtoken en Angular ni en Git.
3. En `.env`, `CORS_ORIGEN_NETLIFY=https://tu-sitio.netlify.app` y `docker compose up -d api`.
4. `npm run build`. El resultado está en `frontend/dist/panel/browser`.
5. En Netlify, sitio nuevo desde este repo. `netlify.toml` fija el directorio, el comando y la redirección de la SPA. `NODE_VERSION` es 22.14.0.

Comprobar el preflight desde el origen de Netlify:

```powershell
curl.exe -i -X OPTIONS -H "Origin: https://tu-sitio.netlify.app" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: ngrok-skip-browser-warning" http://127.0.0.1:8000/eventos
```

Si el panel dice que la API no responde: el túnel se cayó, la URL de ngrok cambió al reiniciarlo (hay que recompilar) o falta el origen en CORS. La página de aviso de ngrok no debería aparecer: las peticiones llevan `ngrok-skip-browser-warning`.
