# kommo-ai-widget ("AI Bridge")

El widget personalizado de Kommo que conecta el Salesbot con nuestro agente.
Es la pieza que hace que las conversaciones LLEGUEN al agente y que sus
respuestas VUELVAN al chat del lead. Sin el widget instalado en la cuenta de
Kommo, el agente puede pensar pero no hablar.

## Los dos caminos por los que llega una conversacion

El sistema usa DOS entradas que trabajan en equipo (ambas viven en
`app/channels/kommo.py`):

### Camino A — webhook de cuenta (`/kommo/incoming-message`)

1. Se configura un webhook a nivel cuenta de Kommo: "mensaje entrante" →
   `https://tu-dominio/kommo/incoming-message?secret=<KOMMO_WEBHOOK_SECRET>`.
2. Cada mensaje del lead dispara ese POST (form-encoded, claves tipo
   `message[add][0][text]` — el parseo esta en `kommo_payloads.py`).
3. El servidor: valida secreto → dedup por `message_id` → filtros (direccion,
   tipo, whitelist, IA pausada) → **genera la respuesta del agente** → la
   guarda en `pending_ai_responses[lead_id]` → dispara el Salesbot del lead
   via `run_salesbot()`.
4. El Salesbot arranca y, al llegar al paso del widget (ver Camino B), recoge
   esa respuesta pendiente y la muestra en el chat.

Por que este rodeo: el webhook de cuenta NO puede escribir en el chat
directamente; solo el Salesbot puede. El widget es el puente de regreso.

### Camino B — el paso del widget en el Salesbot (`/kommo/widget-request`)

1. En el disenador de Salesbot, el widget agrega un paso propio ("Enviar a
   agente IA"). Cuando el flujo del bot llega a ese paso, Kommo hace un POST
   (`widget_request`) a la URL configurada, con:
   - `data[message]` = `{{message_text}}` (texto del lead, si el paso lo recibe)
   - `data[lead_id]`, `data[contact_id]` (variables de plantilla de Kommo)
   - `return_url` = URL efimera para continuar ESTE run del Salesbot
2. El servidor responde en dos modos:
   - **Sin `message`** (el caso del Camino A): saca la respuesta ya generada de
     `pending_ai_responses` y la entrega via `continue_salesbot(return_url,
     texto)` → el texto aparece en el chat del lead.
   - **Con `message`**: genera la respuesta del agente en ese momento y la
     entrega igual via `continue_salesbot`.

`continue_salesbot` (en `app/integrations/kommo_client.py`) hace POST al
`return_url` con `{"data": {"status": "success", "message": ...},
"execute_handlers": [{"handler": "show", ...}]}` — el handler `show` es lo que
pinta el texto en la conversacion.

## Estructura del widget

```
kommo-ai-widget/
  manifest.json    definicion del widget (ver abajo)
  script.js        logica minima del disenador de Salesbot
  i18n/es.json     textos visibles ("AI Bridge", "Enviar a agente IA", ...)
  images/          logos que Kommo exige en varios tamanos
```

### manifest.json — lo importante

- `"locations": ["settings", "salesbot_designer"]` — el widget aparece en
  ajustes y agrega su paso al disenador de Salesbot.
- `salesbot_designer.ai_request.settings.url` — el campo de URL que se llena
  al configurar el paso. El `default_value` que trae (un dominio de ngrok) es
  SOLO de desarrollo: **en cada cliente se configura su URL real, y debe
  incluir el secreto**: `https://dominio-del-cliente/kommo/widget-request?secret=<KOMMO_WEBHOOK_SECRET>`.
- `interface_version: 2`, `init_once: true` — requisitos de la plataforma.

### script.js — que hace realmente

Casi nada en el navegador (todos los callbacks regresan `true`). Lo unico con
logica es `onSalesbotDesignerSave`: cuando guardas el paso en el disenador,
serializa la definicion del handler `widget_request` con la URL configurada y
las variables de plantilla (`{{message_text}}`, `{{lead.id}}`,
`{{contact.id}}`). Es decir: el script solo le dice a Kommo "cuando llegues a
este paso, haz POST aqui con estos datos" — todo el trabajo real pasa en
nuestro servidor.

## Empaquetar e instalar

Kommo exige el zip con los archivos EN LA RAIZ (no dentro de una carpeta) —
por eso el artefacto se llama `kommo-ai-widget-flat.zip` (esta gitignoreado;
se regenera):

```bash
cd kommo-ai-widget && zip -r ../kommo-ai-widget-flat.zip . && cd ..
```

Instalacion en Kommo: Ajustes → Integraciones → subir widget privado → cargar
el zip. Despues, en el disenador del Salesbot del pipeline, agregar el paso
"Enviar a agente IA" y configurar la URL del cliente (con `?secret=`).

## Checklist por cliente nuevo (fork)

1. `.env` del fork: `KOMMO_BASE_URL`, `KOMMO_ACCESS_TOKEN`,
   `KOMMO_SALESBOT_ID`, `KOMMO_WEBHOOK_SECRET`, `KOMMO_ALLOWED_LEAD_IDS`
   (whitelist del piloto).
2. Webhook de cuenta apuntando a `/kommo/incoming-message?secret=...`.
3. Widget instalado y su paso configurado con
   `/kommo/widget-request?secret=...`.
4. El Salesbot del pipeline debe existir y su id ir en `KOMMO_SALESBOT_ID`
   (es el que `run_salesbot()` dispara en el Camino A).

## Limitaciones conocidas

- `pending_ai_responses` vive en memoria del proceso: si el servidor se
  reinicia entre el webhook y el widget_request, esa respuesta se pierde (el
  Salesbot continua sin texto). Aceptable en piloto; se externaliza junto con
  la cola/worker (ver plan de trabajo).
- El `default_value` del manifest apunta a ngrok de desarrollo — cambiar por
  cliente al configurar el paso (el manifest no necesita reempaquetarse por
  cliente si la URL se configura manualmente en el disenador).
