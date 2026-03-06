# Precure Media Manager (Desktop)

Sistema de gestión de recursos multimedia y registros de visualización diseñado específicamente para la franquicia Precure. Esta aplicación de escritorio funciona como el núcleo central (Hub) para administrar el inventario de episodios, películas y soundtracks, preparándolo para una futura sincronización automatizada (vía SMB) con una aplicación cliente en Android.

## 🛠️ Tecnologías
* **Lenguaje:** Python 3.10+
* **Interfaz Gráfica:** PyQt6
* **Base de Datos:** SQLite (proyectado para facilitar la portabilidad local/NAS)

## 🗄️ Estructura de la Base de Datos (Core)
El sistema se basa en tres pilares principales:
1. **T Resources:** Inventario de archivos físicos (Rutas, Títulos, Duración).
2. **T Registry:** Historial de consumo (Tiempos de inicio/fin, Lapsed Calculated, UTC-06).
3. **T Seasons:** Metadatos de la franquicia (Años, Prefijos automáticos, Spinoffs).

## 🚀 Funcionalidades Principales (Roadmap)
- [ ] **Fase 1: Gestión CRUD.** Alta, baja y modificación de registros en `T Resources` y `T Seasons`.
- [ ] **Fase 2: Lógica de Directorios.** Escaneo de rutas locales/discos externos para actualizar `Path of File`.
- [ ] **Fase 3: Visor de Registros.** Tabla de lectura para `T Registry` calculando horas invertidas.
- [ ] **Fase 4: Preparación SMB.** API local o scripts de exportación para que la app de Android lea la cola de reproducción ("Smart Caching").

## 💻 Instalación y Ejecución
1. Clonar el repositorio.
2. Crear un entorno virtual: `python -m venv venv`
3. Activar el entorno e instalar dependencias: `pip install PyQt6`
4. Ejecutar: `python main.py`
