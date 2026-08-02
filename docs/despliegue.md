# Despliegue del bot (Dokploy)

Como se despliega este fork para produccion/piloto y por que cada pieza esta
donde esta. Si vas a redeployar o mover de servidor, lee esto primero: casi
todo lo que nos mordio ya esta anotado.

## Panorama

El bot es una app FastAPI (uvicorn) que vive detras de Dokploy en un VPS.
Dokploy hornea la imagen desde el `Dockerfile` en cada push a `origin/main`,
Traefik le pone HTTPS con Let's Encrypt, y Postgres guarda historial y perfiles.

```
GitHub (origin/main) --push--> Dokploy build (Dockerfile) --> contenedor
                                                                  |
lead en WhatsApp --> Kommo --> Traefik (HTTPS) --> uvicorn :8000 (FastAPI)
                                                                  |
                                            Postgres (+ APIs propias del fork)
```

Dominio de produccion actual: `https://bot.tu-dominio.com`

## Reglas que NO se negocian en el deploy

1. **UN solo worker de uvicorn.** Los locks por sesion, el dedup y
   `pending_ai_responses` viven en memoria del proceso. Dos workers =
   respuestas dobles y estado partido. El `Dockerfile` ya fija `--workers 1`.
2. **Postgres real, nunca `memory`.** Con `MEMORY_KIND=memory` cada reinicio
   borra TODAS las conversaciones. En produccion siempre `postgres`.
3. **Container Port = 8000.** La app escucha en 8000 (`--host 0.0.0.0 --port
   8000`). Si Dokploy apunta a otro puerto (ej. el 3000 de ejemplo), da 502.
4. **El secret de Kommo debe ser identico en los 3 lados** (ver seccion Kommo).

## Archivos del deploy (en el repo)

- **`Dockerfile`** — imagen Python 3.12, usuario no-root, un worker. Al arrancar
  corre las migraciones y luego levanta uvicorn.
- **`.dockerignore`** — deja fuera de la imagen `.env`, `.venv`, `tests/`,
  `docs/`, el widget y demas. Los secretos NUNCA van en la imagen.

## Migraciones (automaticas al arrancar)

El `CMD` del `Dockerfile` corre dos scripts antes de servir, en este orden:

1. `scripts/setup_postgres_memory.py` — crea las tablas del checkpointer de
   LangGraph (`checkpoints`, `checkpoint_writes`, ...). Historial de conversacion.
2. `scripts/setup_app_db.py` — crea las tablas propias (`contact_profiles`,
   `conversation_profiles`, `usage_logs`). Perfiles y metricas.

Ambos son idempotentes: correr de nuevo no rompe nada. En los logs del primer
arranque debes ver:

```
Memoria Postgres configurada correctamente.
Migracion aplicada: 1 ... 5
Base de datos de la app configurada correctamente.
Uvicorn running on http://0.0.0.0:8000
```

## Configuracion en Dokploy

### Build

- **Build Type:** Dockerfile
- **Docker File:** `Dockerfile`
- **Docker Context Path:** vacio (usa `.`, la raiz del repo)
- **Docker Build Stage:** vacio (imagen de una sola etapa)

### Domain

- **Host:** `bot.tu-dominio.com` (el registro A del DNS debe apuntar a la
  IP del VPS ANTES de crear el dominio, o Let's Encrypt no emite el cert)
- **Path:** `/`  · **Internal Path:** `/`  · **Strip Path:** apagado
  (las rutas de Kommo son `/kommo/...`; si borras el path, se rompen)
- **Container Port:** `8000`
- **HTTPS:** on · **Certificate Provider:** Let's Encrypt

## Variables de entorno (Dokploy)

Se cargan en el panel de Dokploy, NUNCA en un `.env` subido a la imagen.

### LLM

| Variable | Ejemplo / nota |
|---|---|
| `LLM_PROVIDER` | `google` |
| `LLM_MODEL` | `gemini-3.1-flash-lite` |
| `GOOGLE_API_KEY` | key del provider elegido (o `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) |

### Memoria / base de datos

| Variable | Nota |
|---|---|
| `MEMORY_KIND` | `postgres` |
| `POSTGRES_URL` | `postgresql://usuario:PASSWORD@host-interno:5432/tu-db` |

`POSTGRES_URL` usa formato libpq/URI (NO el `Host=...;Database=...` de .NET). El
host es el interno de Dokploy (nombre del servicio o IP interna), no `localhost`.
Si el Postgres es compartido con otro sistema, el bot solo AGREGA sus tablas:
no toca las del negocio. Confirmalo antes de apuntar `POSTGRES_URL` a una BD
que ya este en produccion.

### Seguridad de endpoints

| Variable | Nota |
|---|---|
| `CHAT_API_KEY` | Bearer del endpoint `/chat` |
| `KOMMO_WEBHOOK_SECRET` | secret que valida los webhooks de Kommo (ver abajo) |
| `MAX_MESSAGE_LENGTH` | opcional, default `4000` |

### Integraciones del fork

Cada fork agrega aqui las variables de sus propias fuentes de verdad (API de
catalogo, de agenda, de inventario). Se declaran en `core/settings.py` del
fork, no en core.

### Kommo

| Variable | Nota |
|---|---|
| `KOMMO_BASE_URL` | API de la cuenta (ej. `https://tucuenta.kommo.com`) |
| `KOMMO_ACCESS_TOKEN` | token de acceso a la API |
| `KOMMO_SALESBOT_ID` | ID del Salesbot que contiene el paso del widget |
| `KOMMO_ALLOWED_LEAD_IDS` | whitelist del piloto, coma-separada (ej. `111111,222222`) |
| `KOMMO_AI_PAUSED_FIELD_ID` | opcional, campo para pausar la IA por lead |
| `KOMMO_AI_PAUSED_VALUES` | opcional, valores que cuentan como "pausada" |
| `KOMMO_EMOJI_REPLACEMENTS` | opcional, reemplazos de emojis problematicos |

`KOMMO_ALLOWED_LEAD_IDS` es la red de seguridad del piloto: el bot SOLO responde
a esos leads. No lo dejes vacio mientras validan.

## Configuracion en Kommo (las DOS entradas)

El bot necesita DOS entradas de Kommo trabajando juntas. Con una sola no responde.

### 1. Webhook de cuenta (GENERA la respuesta)

Kommo -> Ajustes -> Webhooks -> evento "mensaje entrante" -> URL:

```
https://bot.tu-dominio.com/kommo/incoming-message?secret=<KOMMO_WEBHOOK_SECRET>
```

Recibe el mensaje del lead, llama al LLM, guarda la respuesta en
`pending_ai_responses` y dispara el Salesbot (`KOMMO_SALESBOT_ID`).

### 2. Paso del widget en el Salesbot (SIRVE la respuesta)

Se instala el widget (`kommo-ai-widget-flat.zip`) en Ajustes -> Integraciones,
y en el diseñador del Salesbot se agrega el paso "Enviar a agente IA" con URL:

```
https://bot.tu-dominio.com/kommo/widget-request?secret=<KOMMO_WEBHOOK_SECRET>
```

Recoge la respuesta pendiente y la pinta en el chat via `continue_salesbot`.

### El Salesbot juega dos roles

1. CONTIENE el paso del widget (entrada #2).
2. Su ID debe ir en `KOMMO_SALESBOT_ID`, para que el webhook de cuenta dispare
   ESE Salesbot y no otro.

### Regla del secret: identico en 3 lados

El mismo valor debe estar en:

1. La URL del webhook de cuenta (`?secret=`).
2. La URL del paso del widget (`?secret=`).
3. La env var `KOMMO_WEBHOOK_SECRET` en Dokploy (contra la que el server compara).

Si no coinciden -> `401` y el bot ignora todo.

Nota: el `default_value` del `manifest.json` del widget es solo un prefill (el
campo es `manual`); lo que manda es lo que quedo guardado en el paso del Salesbot.
No commitear el secret real en el manifest; se incrusta solo en el zip que se sube.

## Flujo completo (la cadena sana)

```
lead escribe en WhatsApp
  -> POST /kommo/incoming-message  (valida secret, genera respuesta, la guarda,
                                    dispara run_salesbot con KOMMO_SALESBOT_ID)
  -> el Salesbot corre y llega al paso del widget
  -> POST /kommo/widget-request    (recoge la respuesta pendiente)
  -> continue_salesbot pinta el texto en el chat del lead
```

En logs, la secuencia sana es: `POST /kommo/incoming-message` -> `AI RESPONSE`
-> `KOMMO WIDGET REQUEST` -> `WIDGET PENDING AI RESPONSE`.

## Verificacion

- Salud de la app: `curl https://bot.tu-dominio.com/health` -> `{"status":"ok"}`.
- El endpoint del webhook responde a GET con un aviso:
  `curl https://bot.tu-dominio.com/kommo/incoming-message`
  -> `{"status":"ok","message":"Use POST for Kommo webhooks"}`.
- Prueba real: mandar un mensaje desde un lead de `KOMMO_ALLOWED_LEAD_IDS` y ver
  la secuencia de logs completa arriba.

## Troubleshooting

- **502 Bad Gateway** — Traefik no alcanza la app. Casi siempre el Container Port
  no es 8000, o el contenedor se cayo al arrancar (mira los logs: fail-fast por
  `GOOGLE_API_KEY` faltante o `POSTGRES_URL` malo).
- **`database "..." does not exist`** — el nombre de la base en `POSTGRES_URL`
  esta mal escrito. El servidor SI se alcanza; es solo el dbname.
- **`GET / 404` repetidos en el log** — son health-checks de Traefik a la raiz
  (no hay ruta `/`, solo `/health`). Inofensivo.
- **El widget responde 200 pero el lead no recibe nada** — en el log aparece
  `KOMMO WIDGET REQUEST` pero NO `WIDGET PENDING AI RESPONSE` ni
  `POST /kommo/incoming-message`. Falta configurar el webhook de cuenta (#1):
  sin el, la memoria esta vacia y el widget no tiene que servir.
- **401 en los webhooks** — el secret no coincide en los 3 lados.
- **Un fix "no funciona"** — si cambiaste env vars, prompt, tools o
  integraciones, redeploya. El proceso viejo sigue con codigo viejo.

## Deuda conocida del deploy

- `pending_ai_responses` vive en memoria: si el contenedor reinicia entre el
  webhook y el widget_request, esa respuesta se pierde. Aceptable en piloto.
- El secret en uso vino del manifest viejo y esta en el historial de git.
  Considerar rotarlo despues del piloto (cambiar en los 3 lados a la vez).
