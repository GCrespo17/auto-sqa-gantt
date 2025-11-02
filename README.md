# auto-sqa-gantt

Automatización de diagramas de Gantt de ClickUp a Confluence. Este proyecto sincroniza automáticamente las tareas de ClickUp y genera diagramas de Gantt que se actualizan en páginas de Confluence.

## 🎯 Características

- **Sincronización automática**: Obtiene tareas de ClickUp (listas o carpetas completas)
- **Generación de diagramas Gantt**: Crea visualizaciones profesionales usando matplotlib
- **Actualización en Confluence**: Sube y actualiza automáticamente las páginas de Confluence
- **Multi-proyecto**: Soporta múltiples proyectos con diferentes mapeos
- **Colores por estado**: Los colores del diagrama reflejan el estado de las tareas en ClickUp

## 📋 Requisitos

- Python 3.10 o superior
- Cuenta de ClickUp con API token
- Cuenta de Confluence con permisos de edición
- Credenciales de API (ver sección de configuración)

## 🚀 Instalación

1. Clona el repositorio:
```bash
git clone <url-del-repositorio>
cd auto-sqa-gantt
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

## ⚙️ Configuración

### Variables de Entorno

Copia el archivo `.env` y completa con tus credenciales:

```bash
cp .env.example .env
# Edita .env con tus credenciales
```

#### Variables Requeridas

**Confluence:**
- `CONFLUENCE_URL`: URL base de tu instancia de Confluence (ej: `https://tu-empresa.atlassian.net`)
- `CONFLUENCE_USER`: Email de tu cuenta de Confluence
- `CONFLUENCE_API_TOKEN`: Token de API de Confluence ([Cómo obtenerlo](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/))

**ClickUp:**
- `CLICKUP_API_TOKEN`: Token de API de ClickUp ([Cómo obtenerlo](https://clickup.com/api))

#### Variables de Proyecto

Para cada proyecto necesitas configurar:

**Proyecto 1 (requerido):**
- `CLICKUP_LIST_ID_1` o `CLICKUP_FOLDER_ID`: ID de la lista o carpeta de ClickUp
- `CONFLUENCE_PAGE_ID_1`: ID de la página de Confluence donde se actualizará el diagrama
- `PROJECT_NAME_1`: Nombre del proyecto (opcional, por defecto "Proyecto 1")

**Proyectos adicionales (opcional):**
- `CLICKUP_LIST_ID_2` o `CLICKUP_FOLDER_ID_2`
- `CONFLUENCE_PAGE_ID_2`
- `PROJECT_NAME_2`
- Y así sucesivamente...

### Obtener IDs

**ClickUp:**
- Lista: En la URL de la lista, encontrarás `/l/` seguido del ID
- Carpeta: En la URL de la carpeta, encontrarás `/f/` seguido del ID

**Confluence:**
- Abre la página en Confluence y mira la URL, el ID aparece después de `/pages/`

## 💻 Uso

### Ejecución Local

```bash
python scripts/gantt-click-conf.py
```

### Ejecución con Docker

```bash
docker build -t auto-sqa-gantt .
docker run --env-file .env auto-sqa-gantt
```

## 🔄 Automatización

### GitHub Actions

El proyecto incluye un workflow de GitHub Actions que se ejecuta automáticamente cada 5 horas. También puede ejecutarse manualmente.

#### Configurar Secrets en GitHub

Ve a `Settings > Secrets and variables > Actions` y agrega:

- `CONFLUENCE_URL`
- `CONFLUENCE_USER`
- `CONFLUENCE_API_TOKEN`
- `CLICKUP_API_TOKEN`
- `CLICKUP_LIST_ID` (o `CLICKUP_LIST_ID_1`)
- `CLICKUP_FOLDER_ID` (o `CLICKUP_FOLDER_ID_1`, si usas carpeta)
- `CONFLUENCE_PAGE_ID` (o `CONFLUENCE_PAGE_ID_1`)
- `PROJECT_NAME` (opcional)
- Para proyectos adicionales: `CLICKUP_LIST_ID_2`, `CONFLUENCE_PAGE_ID_2`, etc.

#### Ejecutar Manualmente

1. Ve a la pestaña "Actions" en GitHub
2. Selecciona el workflow "Sincronizar Gantt"
3. Haz clic en "Run workflow"

#### Programación Automática

El workflow se ejecuta automáticamente cada 5 horas usando cron.

### Cron Job (Linux/macOS)

Para ejecutar en un servidor local con cron:

```bash
# Editar crontab
crontab -e

# Agregar esta línea (ejecuta cada 5 horas)
0 */5 * * * cd /ruta/al/proyecto && /usr/bin/python3 scripts/gantt-click-conf.py >> logs/cron.log 2>&1
```

Asegúrate de que el archivo `.env` esté en el directorio del proyecto.

## 📁 Estructura del Proyecto

```
auto-sqa-gantt/
├── scripts/
│   └── gantt-click-conf.py    # Script principal
├── Dockerfile                  # Configuración Docker
├── requirements.txt            # Dependencias Python
├── .env                        # Variables de entorno (no versionado)
├── .gitignore
└── README.md
```

## 🎨 Colores del Diagrama

El diagrama usa colores según el estado de las tareas en ClickUp:

- **Verde** (`#8dd879`): Completadas (ACHIEVED, COMPLETE, DONE, CLOSED)
- **Azul** (`#a8c5f0`): En progreso (IN PROGRESS, IMPLEMENTING, MONITORING)
- **Gris** (`#e0e0e0`): Por hacer (TODO, TO DO, OPEN)

## 🐛 Solución de Problemas

### Error: "Faltan credenciales básicas en variables de entorno"
- Verifica que todas las variables requeridas estén configuradas en `.env`
- Asegúrate de que no haya espacios en blanco adicionales

### Error: "List ID no existe o no tienes acceso"
- Verifica que el ID de la lista/carpeta sea correcto
- Confirma que tu token de API tenga permisos para acceder a ese espacio

### Error: "No se pudo conectar"
- Verifica tu conexión a internet
- Confirma que las URLs de la API sean correctas
- Revisa si hay restricciones de firewall

### El diagrama no se actualiza en Confluence
- Verifica que el `CONFLUENCE_PAGE_ID` sea correcto
- Confirma que tu usuario tenga permisos de edición en la página
- Revisa que el token de API tenga los permisos necesarios

## 📝 Notas

- Las tareas sin fechas (start_date o due_date) no aparecen en el diagrama
- Si una tarea solo tiene fecha de inicio, se le asigna 1 día de duración
- Si una tarea solo tiene fecha de vencimiento, se le asigna 1 día de duración retroactiva
- Los attachments anteriores se eliminan automáticamente antes de subir uno nuevo

