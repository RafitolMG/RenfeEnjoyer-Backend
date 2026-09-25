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

Una sola vez en cada equipo:

```bash
git clone -b ubuntu-dev https://github.com/RafitolMG/RenfeEnjoyer-Backend.git
cd RenfeEnjoyer-Backend
./scripts/install.sh
```

El `-b ubuntu-dev` importa: la rama por defecto del repositorio, `main`, sigue siendo la versión
antigua de Tkinter. Si ya clonaste sin él, cambia de rama con `git switch ubuntu-dev`.

`install.sh` instala las dependencias de Python y del frontend y crea el comando `renfe` en
`~/.local/bin`. No instala nada a nivel de sistema: si falta Python, Node, Chromium o Tailscale, lo
dice. Se puede relanzar sin problema.

Los perfiles y las sesiones de Renfe son de cada equipo y no viajan con el repositorio. En uno nuevo
hay que crear los perfiles otra vez (o copiar `backend/renfe_enjoyer.db`), y la primera búsqueda de
cada perfil pasará por el login y el captcha.

A partir de ahí, desde cualquier directorio:

```bash
renfe
```

Recompila el frontend si has cambiado algo, arranca el servidor, espera a que responda y abre la
app en el navegador. Si ya estaba en marcha, solo abre el navegador. `Ctrl+C` lo para todo.

La app queda en `http://<equipo>.<tailnet>.ts.net:8000`, la dirección MagicDNS completa del equipo,
que el comando muestra al arrancar. Usa esa y no la IP, que cambia si el nodo se vuelve a registrar
en Tailscale. El nombre corto (`http://<equipo>:8000`) no sirve desde el propio equipo: ahí resuelve
a sus direcciones IPv6, y el servidor solo escucha en la IPv4 de Tailscale.

### Desarrollo

Con recarga en caliente, en dos terminales. Solo es accesible desde el propio equipo:

```bash
cd backend && ../.venv/bin/uvicorn app.main:app --reload    # terminal 1
cd frontend && npm run dev                                  # terminal 2
```

La interfaz queda en <http://localhost:5173>. El servidor de Vite hace de proxy de `/api` hacia
el backend, así que no hace falta configurar nada más.

### Importar perfiles de la versión antigua

La app de Tkinter guardaba el correo y la contraseña en columnas intercambiadas. Este script los
reordena al esquema nuevo:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python scripts/migrate_legacy_db.py
```

## Acceso desde el tailnet

`renfe` sirve la API y el frontend en un único puerto, atado a la IP de Tailscale del equipo, así
que la app se puede usar desde el móvil o el portátil sin exponer nada a internet.

Se ata a la IP de Tailscale en concreto, no a `0.0.0.0`, así que **no** queda expuesto en la red
local. Sobrescribe el destino con `RENFE_HOST` y `RENFE_PORT` si lo necesitas.

El bot abre el navegador en el escritorio del equipo, así que **tiene que haber una sesión de
escritorio iniciada** aunque tú lo uses desde otro dispositivo. Si el servidor se arrancó desde una
terminal sin pantalla, el bot localiza la sesión Wayland abierta y abre la ventana ahí.

Advertencias:

- **La API no tiene autenticación.** Cualquiera con acceso a tu tailnet puede leer los perfiles y
  lanzar búsquedas. Vale mientras el tailnet sean solo equipos tuyos.
- **No uses `tailscale funnel`** con esto: publicaría la app en internet.
- Desde el móvil puedes lanzar, seguir y detener una búsqueda, pero **el captcha hay que
  resolverlo en la máquina** donde corre el bot, porque es ahí donde se abre el navegador.

## Sesión persistente

El bot guarda el perfil del navegador, así que **normalmente no inicia sesión**: reutiliza la
sesión anterior y se salta el login, el captcha y la verificación. Solo cuando la sesión caduca
vuelve a pedirte esos pasos.

Hay **un perfil por cuenta de Renfe**, bajo `backend/browser-profile/<hash del correo>/`. Compartir
uno solo haría que el bot buscase con la cuenta que hubiera iniciado sesión la última vez, no con
la del perfil elegido.

La interfaz indica si el perfil seleccionado tiene sesión guardada y permite cerrarla:

```bash
curl -X DELETE http://<host>:8000/api/users/<id>/session
```

Ese directorio contiene tu sesión de Renfe iniciada. Está en `.gitignore`, pero trátalo como una
credencial más.

## Captcha en el inicio de sesión

Renfe protege el login con reCAPTCHA y una sesión automatizada suele recibir un reto de imágenes.
El bot **no intenta resolverlo**: pasa al estado `awaiting_human`, te cede la ventana del navegador
y sigue solo en cuanto lo completes.

Esto implica que el inicio de sesión no es totalmente desatendido, y que si usas la app desde el
móvil puede que necesites acercarte al equipo para ese paso.

## Verificación en dos pasos

Si Renfe pide un código por SMS o correo, el bot **no falla**: se queda esperando en el estado
`awaiting_code` y la interfaz muestra un campo para introducirlo. Funciona igual desde el móvil,
así que puedes contestar la verificación sin estar delante del equipo.

Desde consola, si prefieres:

```bash
curl -X POST http://<host>:8000/api/jobs/current/code \
     -H 'Content-Type: application/json' -d '{"code":"483920"}'
```

El campo del formulario de Renfe se detecta por heurística (`autocomplete="one-time-code"`, y
nombres que contengan `otp`, `codigo`, `sms` o `verificacion`). **Esa parte no está verificada
contra el formulario real**, porque para verlo hace falta provocar un login con verificación
activa. Si no lo reconoce, el registro vuelca los campos visibles de la página al fallar; con eso
puedes fijar el selector exacto:

```bash
RENFE_OTP_SELECTOR="input#el-id-real" ./scripts/serve-tailscale.sh
```

## Cómo funciona una búsqueda

1. Eliges un perfil, el trayecto (ida o vuelta) y la fecha. El abono ya determina origen y destino.
2. El backend lanza el bot en un hilo aparte: entra en Renfe, abre el abono y te muestra los trenes
   de ese día.
3. Marcas uno y confirmas. El bot recarga la página de resultados hasta que ese tren tenga plaza.
4. El progreso llega a la interfaz por WebSocket, con el contador de recargas y el registro en vivo.
5. Al reservar, el bot deja el navegador abierto para que termines a mano. Cuando acabes, pulsa
   **He terminado, cerrar navegador**.

Si ya sabes a qué hora sale tu tren, la API acepta `departure_time` al lanzar la búsqueda y se salta
el listado:

```bash
curl -X POST http://<host>:8000/api/jobs/current -H 'Content-Type: application/json' \
     -d '{"user_id": 1, "journey_type": "ida", "date": "01/10/2026", "departure_time": "07:30"}'
```

Las columnas del listado salen tal cual de la tabla de Renfe. Solo la de salida está comprobada; el
resto no se ha podido ver aún contra la web real.

Puedes detener la búsqueda en cualquier momento; el bucle de recarga es infinito por diseño.

## Desarrollo

```bash
cd backend  && .venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/mypy
cd frontend && npm run build
```

## Aviso

Los perfiles guardan las credenciales de Renfe **en claro** en el SQLite local. El fichero está
en `.gitignore`; aun así, no lo compartas.
