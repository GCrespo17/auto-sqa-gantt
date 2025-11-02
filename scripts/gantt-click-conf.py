import os
import sys
import json
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from dotenv import load_dotenv
import io

load_dotenv()


# --- Funciones auxiliares ---
def load_config(config_file="config.json"):
    """Carga configuración desde archivo JSON o variables de entorno."""
    print(f"[INFO] Cargando configuración desde {config_file}...")

    # Intentar cargar desde archivo JSON
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"[OK] Configuración cargada desde {config_file}")
            return config
        except Exception as e:
            print(f"[ERROR] No se pudo leer {config_file}: {e}")
            sys.exit(1)

    # Fallback: usar variables de entorno (compatibilidad con versión anterior)
    print("[INFO] Archivo config.json no encontrado, usando variables de entorno...")

    config = {
        "confluence": {
            "url": os.getenv("CONFLUENCE_URL"),
            "user": os.getenv("CONFLUENCE_USER"),
            "api_token": os.getenv("CONFLUENCE_API_TOKEN"),
        },
        "clickup": {"api_token": os.getenv("CLICKUP_API_TOKEN")},
        "mappings": [],
    }

    # Buscar múltiples proyectos (numerados desde 1)
    index = 1
    while True:
        # Buscar variables con sufijo numérico
        list_id = (
            os.getenv(f"CLICKUP_LIST_ID_{index}")
            if index > 1
            else os.getenv("CLICKUP_LIST_ID_1") or os.getenv("CLICKUP_LIST_ID")
        )
        folder_id = (
            os.getenv(f"CLICKUP_FOLDER_ID_{index}")
            if index > 1
            else os.getenv("CLICKUP_FOLDER_ID_1") or os.getenv("CLICKUP_FOLDER_ID")
        )
        page_id = (
            os.getenv(f"CONFLUENCE_PAGE_ID_{index}")
            if index > 1
            else os.getenv("CONFLUENCE_PAGE_ID_1") or os.getenv("CONFLUENCE_PAGE_ID")
        )
        name = os.getenv(f"PROJECT_NAME_{index}", f"Proyecto {index}")

        # Si no hay más IDs, terminar búsqueda
        if not list_id and not folder_id:
            break

        # Validar que tenga página asociada
        if not page_id:
            print(
                f"[WARNING] Proyecto {index} no tiene CONFLUENCE_PAGE_ID_{index}, saltando..."
            )
            index += 1
            continue

        # Crear mapping
        mapping = {"name": name, "confluence_page_id": page_id}

        if folder_id:
            mapping["clickup_folder_id"] = folder_id
            print(
                f"[INFO] Proyecto {index}: Usando CLICKUP_FOLDER_ID_{index} (carpeta)"
            )
        elif list_id:
            mapping["clickup_list_id"] = list_id
            print(f"[INFO] Proyecto {index}: Usando CLICKUP_LIST_ID_{index} (lista)")

        config["mappings"].append(mapping)
        index += 1

    # Validar que las credenciales básicas existan
    if not all(
        [
            config["confluence"]["url"],
            config["confluence"]["user"],
            config["confluence"]["api_token"],
            config["clickup"]["api_token"],
        ]
    ):
        print("[ERROR] Faltan credenciales básicas en variables de entorno")
        sys.exit(1)

    # Validar que al menos haya un proyecto
    if not config["mappings"]:
        print("[ERROR] No se encontraron proyectos en variables de entorno")
        print(
            "[INFO] Define CLICKUP_LIST_ID_1 o CLICKUP_FOLDER_ID_1 (y sus respectivos CONFLUENCE_PAGE_ID_1)"
        )
        sys.exit(1)

    print(
        f"[OK] Se encontraron {len(config['mappings'])} proyecto(s) en variables de entorno"
    )

    return config


def get_lists_from_folder(api_token, folder_id):
    """Obtiene todas las listas dentro de una carpeta."""
    print(f"[INFO] Obteniendo listas de la carpeta {folder_id}...")
    url = f"https://api.clickup.com/api/v2/folder/{folder_id}"
    headers = {"Authorization": api_token}

    # Intentar 3 veces con timeout creciente
    max_retries = 3
    for attempt in range(max_retries):
        try:
            timeout = 15 + (attempt * 5)  # 15s, 20s, 25s
            print(f"[DEBUG] Intento {attempt + 1}/{max_retries} (timeout: {timeout}s)")

            response = requests.get(url, headers=headers, timeout=timeout)

            # Verificar el código de respuesta
            if response.status_code == 404:
                print(f"[ERROR] Folder ID '{folder_id}' no existe o no tienes acceso")
                print(f"[AYUDA] Verifica el ID en la URL de ClickUp: /v/o/f/FOLDER_ID")
                return None
            elif response.status_code == 401:
                print(f"[ERROR] Token de API inválido o sin permisos")
                return None
            elif response.status_code == 403:
                print(f"[ERROR] Sin permisos para acceder a esta carpeta")
                return None

            response.raise_for_status()
            folder_data = response.json()
            lists = folder_data.get("lists", [])
            print(f"[OK] Encontradas {len(lists)} listas en la carpeta")
            return lists

        except requests.exceptions.Timeout:
            print(f"[WARNING] Timeout en intento {attempt + 1}")
            if attempt == max_retries - 1:
                print(f"[ERROR] Timeout después de {max_retries} intentos")
                return None
        except requests.exceptions.ConnectionError as e:
            print(f"[WARNING] Error de conexión en intento {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                print(f"[ERROR] No se pudo conectar después de {max_retries} intentos")
                print(f"[AYUDA] Posibles causas:")
                print(f"  1. El Folder ID es incorrecto")
                print(f"  2. Problemas de red/firewall")
                print(f"  3. La API de ClickUp está temporalmente no disponible")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] No se pudo obtener la carpeta: {e}")
            return None

    return None


def get_clickup_tasks(api_token, list_id):
    """Obtiene tareas de una lista específica de ClickUp."""
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    headers = {"Authorization": api_token}

    # Intentar 3 veces
    max_retries = 3
    for attempt in range(max_retries):
        try:
            timeout = 15 + (attempt * 5)
            response = requests.get(
                url,
                headers=headers,
                params={
                    "archived": False,
                    "include_closed": True,
                },
                timeout=timeout,
            )

            # Verificar errores específicos
            if response.status_code == 404:
                print(f"[ERROR] List ID '{list_id}' no existe o no tienes acceso")
                return None
            elif response.status_code == 401:
                print(f"[ERROR] Token de API inválido")
                return None

            response.raise_for_status()
            tasks = response.json().get("tasks", [])
            return tasks

        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                print(f"[ERROR] Timeout al obtener tareas de la lista {list_id}")
                return None
        except requests.exceptions.ConnectionError as e:
            if attempt == max_retries - 1:
                print(f"[ERROR] Error de conexión al obtener tareas: {e}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] {e}")
            return None

    return None


def get_all_tasks_from_source(api_token, source_id, source_type="list"):
    """
    Obtiene todas las tareas de una lista o carpeta.

    Args:
        api_token: Token de API de ClickUp
        source_id: ID de la lista o carpeta
        source_type: 'list' o 'folder'
    """
    all_tasks = []

    if source_type == "folder":
        print(f"[INFO] Obteniendo tareas de la carpeta {source_id}...")
        lists = get_lists_from_folder(api_token, source_id)

        if not lists:
            return None

        for list_item in lists:
            list_id = list_item["id"]
            list_name = list_item["name"]
            print(f"  → Obteniendo tareas de lista: {list_name} (ID: {list_id})")

            tasks = get_clickup_tasks(api_token, list_id)
            if tasks:
                all_tasks.extend(tasks)
                print(f"    Obtenidas {len(tasks)} tareas")

        print(f"[OK] Total de tareas obtenidas: {len(all_tasks)}")

    else:  # source_type == "list"
        print(f"[INFO] Obteniendo tareas de la lista {source_id}...")
        tasks = get_clickup_tasks(api_token, source_id)
        if tasks:
            all_tasks = tasks
            print(f"[OK] Obtenidas {len(all_tasks)} tareas")

    if not all_tasks:
        return None

    # Debug: mostrar status de todas las tareas
    status_counts = {}
    for task in all_tasks:
        status = task.get("status", {}).get("status", "Sin Status")
        status_counts[status] = status_counts.get(status, 0) + 1
    print(f"[DEBUG] Status encontrados: {status_counts}")

    return all_tasks


def clickup_timestamp_to_date(timestamp):
    """Convierte timestamp de ClickUp a datetime."""
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000)
    except:
        return None


def generate_gantt_image(tasks, project_name="ClickUp"):
    """Genera imagen PNG del Gantt usando matplotlib."""
    print("[INFO] Generando imagen del Gantt...")
    print(f"[DEBUG] Total de tareas recibidas: {len(tasks)}")

    # Filtrar tareas con fechas
    valid_tasks = []
    for task in tasks:
        start_date = clickup_timestamp_to_date(task.get("start_date"))
        due_date = clickup_timestamp_to_date(task.get("due_date"))

        task_name = task.get("name", "Sin nombre")
        status = task.get("status", {}).get("status", "Sin Status")
        print(
            f"[DEBUG] Tarea: {task_name[:30]} | Start: {start_date} | Due: {due_date} | Status: {status}"
        )

        if not start_date and not due_date:
            print(f"  -> Descartada (sin fechas)")
            continue

        if not start_date and due_date:
            start_date = due_date - timedelta(days=1)

        if start_date and not due_date:
            due_date = start_date + timedelta(days=1)

        valid_tasks.append(
            {"name": task_name, "start": start_date, "end": due_date, "status": status}
        )

    if not valid_tasks:
        print("[ERROR] No hay tareas con fechas")
        return None

    print(f"[DEBUG] Tareas válidas para graficar: {len(valid_tasks)}")

    # Ordenar por fecha de inicio
    valid_tasks.sort(key=lambda x: x["start"])

    # Calcular rango de fechas con margen
    min_date = min(task["start"] for task in valid_tasks)
    max_date = max(task["end"] for task in valid_tasks)

    # Agregar margen de 7 días antes y después
    date_margin = timedelta(days=7)
    chart_start = min_date - date_margin
    chart_end = max_date + date_margin

    print(
        f"[DEBUG] Rango de fechas: {chart_start.strftime('%Y-%m-%d')} a {chart_end.strftime('%Y-%m-%d')}"
    )

    # Configurar colores estilo ClickUp
    status_colors = {
        "ACHIEVED": "#8dd879",
        "COMPLETE": "#8dd879",
        "COMPLETED": "#8dd879",
        "APPROVED": "#8dd879",
        "FINALIZED": "#8dd879",
        "DONE": "#8dd879",
        "CLOSED": "#8dd879",
        "MONITORING": "#a8c5f0",
        "IMPLEMENTING": "#a8c5f0",
        "PROGRESS": "#a8c5f0",
        "REVIEWING": "#a8c5f0",
        "IN PROGRESS": "#a8c5f0",
        "TODO": "#e0e0e0",
        "TO DO": "#e0e0e0",
        "OPEN": "#e0e0e0",
        "DRAFTING": "#e0e0e0",
        "NOT STARTED": "#e0e0e0",
    }

    # Crear figura más grande
    fig, ax = plt.subplots(figsize=(18, max(6, len(valid_tasks) * 0.5)))
    fig.patch.set_facecolor("white")

    # Dibujar barras (invertir orden para que coincida con ClickUp)
    for idx, task in enumerate(reversed(valid_tasks)):
        start = task["start"]
        end = task["end"]
        duration = (end - start).days + 1

        # Color según status
        color = "#e0e0e0"  # Gris claro por defecto
        for key, col in status_colors.items():
            if key in task["status"].upper():
                color = col
                break

        # Dibujar barra con bordes suaves
        ax.barh(
            idx,
            duration,
            left=mdates.date2num(start),
            height=0.7,
            color=color,
            edgecolor="#333333",
            linewidth=1,
            alpha=0.9,
        )

        # Etiqueta de tarea a la izquierda (fuera de la barra)
        ax.text(
            mdates.date2num(start) - 0.3,
            idx,
            task["name"],
            ha="right",
            va="center",
            fontsize=10,
            fontweight="normal",
        )

    # Establecer límites del eje X con margen
    ax.set_xlim(mdates.date2num(chart_start), mdates.date2num(chart_end))

    # Configurar ejes con más detalle
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=0, ha="center", fontsize=9)

    ax.set_yticks(range(len(valid_tasks)))
    ax.set_yticklabels([])
    ax.set_ylim(-0.5, len(valid_tasks) - 0.5)

    # Cuadrícula estilo ClickUp
    ax.grid(True, axis="x", alpha=0.2, linestyle="-", linewidth=0.5, color="#cccccc")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    plt.title(
        f"Diagrama de Gantt - {project_name}",
        fontsize=14,
        fontweight="bold",
        pad=15,
        loc="center",
    )
    plt.xlabel("")
    plt.tight_layout()

    # Guardar en memoria con mayor resolución
    img_buffer = io.BytesIO()
    plt.savefig(
        img_buffer, format="png", dpi=200, bbox_inches="tight", facecolor="white"
    )
    img_buffer.seek(0)
    plt.close()

    print("[OK] Imagen generada")
    return img_buffer


def upload_attachment_to_confluence(confluence_config, page_id, image_buffer, filename):
    """Sube imagen como attachment a Confluence."""
    print(f"[INFO] Subiendo imagen a Confluence (Page ID: {page_id})...")

    url = f"{confluence_config['url']}/wiki/rest/api/content/{page_id}/child/attachment"
    auth = (confluence_config["user"], confluence_config["api_token"])

    # Verificar si ya existe el attachment
    try:
        response = requests.get(url, auth=auth, timeout=10)
        response.raise_for_status()
        attachments = response.json().get("results", [])

        # Eliminar attachment anterior si existe
        for att in attachments:
            if att["title"] == filename:
                att_id = att["id"]
                delete_url = (
                    f"{confluence_config['url']}/wiki/rest/api/content/{att_id}"
                )
                requests.delete(delete_url, auth=auth, timeout=10)
                print("[INFO] Attachment anterior eliminado")
                break
    except:
        pass

    # Subir nuevo attachment
    files = {"file": (filename, image_buffer, "image/png")}
    headers = {"X-Atlassian-Token": "no-check"}

    try:
        response = requests.post(
            url, auth=auth, headers=headers, files=files, timeout=30
        )
        response.raise_for_status()
        result = response.json()
        print("[OK] Imagen subida")
        return result["results"][0]["id"]
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] {e}")
        return None


def update_confluence_with_image(
    confluence_config, page_id, attachment_id, filename, project_name
):
    """Actualiza página con la imagen."""
    print(f"[INFO] Actualizando página (Page ID: {page_id})...")

    # Obtener info de página
    url = f"{confluence_config['url']}/wiki/rest/api/content/{page_id}?expand=body.storage,version"
    auth = (confluence_config["user"], confluence_config["api_token"])

    try:
        response = requests.get(url, auth=auth, timeout=10)
        response.raise_for_status()
        page_info = response.json()
    except:
        return False

    current_version = page_info["version"]["number"]
    page_title = page_info["title"]
    page_type = page_info["type"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Contenido con imagen
    page_content = f"""
<h2>Diagrama de Gantt - {project_name}</h2>
<p><em>Última actualización: {timestamp}</em></p>
<p> </p>

<ac:image ac:height="600">
  <ri:attachment ri:filename="{filename}" />
</ac:image>

<p> </p>
<p><ac:structured-macro ac:name="info">
  <ac:rich-text-body>
    <p>Sincronizado desde ClickUp API automáticamente (Imagen PNG)</p>
  </ac:rich-text-body>
</ac:structured-macro></p>
"""

    url = f"{confluence_config['url']}/wiki/rest/api/content/{page_id}"
    headers = {"Content-Type": "application/json"}

    payload = {
        "version": {"number": current_version + 1},
        "title": page_title,
        "type": page_type,
        "body": {"storage": {"value": page_content, "representation": "storage"}},
    }

    try:
        response = requests.put(
            url, json=payload, headers=headers, auth=auth, timeout=10
        )
        response.raise_for_status()
        print("[OK] Página actualizada")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] {e}")
        return False


def process_mapping(config, mapping):
    """Procesa un mapping individual (lista/carpeta → página)."""
    project_name = mapping.get("name", "ClickUp")
    page_id = mapping.get("confluence_page_id")

    # Determinar si es lista o carpeta
    source_id = None
    source_type = None

    if mapping.get("clickup_list_id"):
        source_id = mapping["clickup_list_id"]
        source_type = "list"
    elif mapping.get("clickup_folder_id"):
        source_id = mapping["clickup_folder_id"]
        source_type = "folder"
    else:
        print(
            f"[ERROR] No se encontró clickup_list_id ni clickup_folder_id para {project_name}"
        )
        return False

    print("\n" + "=" * 70)
    print(f"PROCESANDO: {project_name}")
    print(f"  ClickUp {source_type.capitalize()}: {source_id}")
    print(f"  Página Confluence: {page_id}")
    print("=" * 70)

    # 1. Obtener tareas
    tasks = get_all_tasks_from_source(
        config["clickup"]["api_token"], source_id, source_type
    )
    if not tasks:
        print(f"[ERROR] No se pudieron obtener tareas para {project_name}")
        return False

    # 2. Generar imagen
    image_buffer = generate_gantt_image(tasks, project_name)
    if not image_buffer:
        print(f"[ERROR] No se pudo generar imagen para {project_name}")
        return False

    # 3. Subir a Confluence
    filename = f"gantt-{project_name.lower().replace(' ', '-')}-{datetime.now().strftime('%Y%m%d')}.png"
    attachment_id = upload_attachment_to_confluence(
        config["confluence"], page_id, image_buffer, filename
    )

    if not attachment_id:
        print(f"[ERROR] No se pudo subir imagen para {project_name}")
        return False

    # 4. Actualizar página
    success = update_confluence_with_image(
        config["confluence"], page_id, attachment_id, filename, project_name
    )

    if success:
        print(f"\n[✓] {project_name} sincronizado correctamente!")
        print(f"    Ver en: {config['confluence']['url']}/wiki/pages/{page_id}")
        return True
    else:
        print(f"[✗] Error al actualizar {project_name}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("ClickUp -> Gantt PNG en Confluence (Multi-Proyecto)")
    print("=" * 70)
    print()

    # Cargar configuración
    config = load_config()

    # Validar configuración
    if not config.get("mappings"):
        print("[ERROR] No se encontraron mappings en la configuración")
        sys.exit(1)

    print(f"[INFO] Se encontraron {len(config['mappings'])} proyectos para sincronizar")
    print()

    # Procesar cada mapping
    results = []
    for mapping in config["mappings"]:
        success = process_mapping(config, mapping)
        results.append({"name": mapping.get("name", "Unknown"), "success": success})

    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN DE SINCRONIZACIÓN")
    print("=" * 70)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"\nTotal proyectos: {len(results)}")
    print(f"✓ Exitosos: {successful}")
    print(f"✗ Fallidos: {failed}")
    print()

    for result in results:
        status = "✓" if result["success"] else "✗"
        print(f"  {status} {result['name']}")

    print("\n" + "=" * 70)

    # Exit code basado en resultados
    sys.exit(0 if failed == 0 else 1)
