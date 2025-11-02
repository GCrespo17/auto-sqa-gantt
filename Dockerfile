# Usa una imagen oficial de Python ligera como base
FROM python:3.10-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de requerimientos primero
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia la carpeta de scripts completa al directorio de trabajo
# ✅ CAMBIO #1: Copia la carpeta, no solo el archivo
COPY ./scripts ./scripts

# Comando que se ejecutará cuando el contenedor inicie
# ✅ CAMBIO #2: Especifica la ruta correcta para ejecutar el script
CMD ["python", "scripts/gantt-click-conf.py"]
