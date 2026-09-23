# Renfe Enjoyer

Bot que automatiza la compra de billetes de abono de Renfe. Vigila la página de resultados y,
en cuanto aparece una plaza en el tren que buscas, la reserva y te cede el navegador para que
completes la compra.

Monorepo con dos piezas:

| Directorio  | Contenido                                                         |
| ----------- | ----------------------------------------------------------------- |
| `backend/`  | API FastAPI + el bot de Selenium, con SQLite para los perfiles     |
| `frontend/` | SPA en Vue 3 + TypeScript que lanza y monitoriza las búsquedas     |

## Requisitos

- Python 3.12+
- Node 20+
- Chromium o Chrome, y `chromedriver` (en Arch: `sudo pacman -S chromium chromedriver`)

## Puesta en marcha

```bash
# Backend (terminal 1)
cd backend
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload

# Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

La interfaz queda en <http://localhost:5173>. El servidor de Vite hace de proxy de `/api` hacia
el backend, así que no hace falta configurar nada más.

### Importar perfiles de la versión antigua

La app de Tkinter guardaba el correo y la contraseña en columnas intercambiadas. Este script los
reordena al esquema nuevo:

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/migrate_legacy_db.py
```

## Acceso desde el tailnet

Para usarlo desde otro dispositivo tuyo (el móvil, el portátil) sin exponer nada a internet:

```bash
./scripts/serve-tailscale.sh
```

Compila el frontend si hace falta y lo sirve junto con la API en un único puerto, atado a la IP
de Tailscale de la máquina. Queda accesible en `http://<tu-ip-de-tailscale>:8000`.

Se ata a la IP de Tailscale en concreto, no a `0.0.0.0`, así que **no** queda expuesto en la red
local. Sobrescribe el destino con `RENFE_HOST` y `RENFE_PORT` si lo necesitas.

Dos advertencias:

- **La API no tiene autenticación.** Cualquiera con acceso a tu tailnet puede leer los perfiles y
  lanzar búsquedas. Vale mientras el tailnet sean solo equipos tuyos.
- **No uses `tailscale funnel`** con esto: publicaría la app en internet.
- Desde el móvil puedes lanzar, seguir y detener una búsqueda, pero **la compra hay que rematarla
  en la máquina** donde corre el bot, porque es ahí donde se abre el navegador.

## Cómo funciona una búsqueda

1. Eliges un perfil, la hora de salida, el trayecto y la fecha.
2. El backend lanza el bot en un hilo aparte: entra en Renfe, abre el abono y recarga la página
   de resultados hasta encontrar una plaza a esa hora.
3. El progreso llega a la interfaz por WebSocket, con el contador de recargas y el registro en vivo.
4. Al reservar, el bot deja el navegador abierto para que termines la compra a mano. Cuando acabes,
   pulsa **He terminado, cerrar navegador**.

Puedes detener la búsqueda en cualquier momento; el bucle de recarga es infinito por diseño.

## Desarrollo

```bash
cd backend  && .venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/mypy
cd frontend && npm run build
```

## Aviso

Los perfiles guardan las credenciales de Renfe **en claro** en el SQLite local. El fichero está
en `.gitignore`; aun así, no lo compartas.
