# Precure Media Manager (Desktop)

Sistema de gestión de recursos multimedia y registros de visualización diseñado específicamente para la franquicia Precure. Esta aplicación de escritorio funciona como el núcleo central (Hub) para administrar el inventario de episodios, películas y soundtracks, facilitando la organización de archivos físicos y el seguimiento detallado del consumo.

## 🛠️ Tecnologías
* **Lenguaje:** Python 3.10+
* **Interfaz Gráfica:** PyQt6
* **Base de Datos:** SQLite (Arquitectura de bases de datos anuales y global)
* **Procesamiento de Excel:** openpyxl
* **Multimedia:** ffmpeg/ffprobe (para detección de metadatos y duración)

## 🗄️ Estructura de la Base de Datos
El sistema utiliza una arquitectura híbrida para mantener el rendimiento y la organización:

### 1. Base de Datos Global (`_global.db`)
Contiene metadatos maestros y catálogos:
* **T_Seasons:** Información de todas las temporadas (años, nombres, rutas maestras).
* **T_Type_Resources:** Catálogo de tipos de recursos (Episodio, Película, Soundtrack, etc.).
* **T_Opener_Models:** Modelos de referencia para la identificación de versiones.
* **T_Type_Catalog_Reg:** Clasificación de tipos de registros.

### 2. Bases de Datos Anuales
Cada año tiene su propia base de datos dedicada para almacenar:
* **T_Resources:** Inventario de archivos físicos (Rutas, Títulos, Duración, Fecha de descarga).
* **T_Registry:** Historial de visualización (Rangos de tiempo, lapsos calculados, modelos detectados).

## 🚀 Funcionalidades Implementadas
- [x] **Gestión CRUD Dinámica:** Edición completa de tablas con soporte para claves foráneas y desplegables relacionales.
- [x] **Escaneo y Vinculación Automática:** Localización de archivos `.mp4`, `.mkv` y audios, vinculándolos automáticamente con los registros de la base de datos basándose en patrones de nombres.
- [x] **Migración desde Excel:** Importación masiva de recursos y registros desde archivos de seguimiento existentes.
- [x] **Propagación de Esquemas:** Al añadir, renombrar o borrar columnas desde la interfaz, los cambios se replican automáticamente en todas las bases de datos anuales (desde 2004 hasta el presente).
- [x] **Consola SQL Integrada:** Herramientas para ejecutar scripts SQL directamente y visualizar logs de operaciones en tiempo real.
- [x] **Filtros Avanzados:** Sistema de filtrado estilo Excel para facilitar la búsqueda en tablas con gran volumen de datos.
- [x] **Cálculos Automáticos:** Cálculo en tiempo real de la duración de reproducciones (lapsos) y detección de modelos de apertura basados en fechas.

## 📂 Estructura del Código (Módulos)
* **`main.pyw`:** Punto de entrada de la aplicación. Instancia la interfaz y el controlador.
* **`ui/main_window.py`:** Contiene la clase `MainWindow`, encargada exclusivamente de la interfaz de usuario, menús y disposición de widgets.
* **`controllers/main_controller.py`:** Clase `MainController` que maneja la lógica de negocio, hilos de ejecución, conexiones a bases de datos y coordinación entre componentes.
* **`data_table.py`:** Contiene la clase `DataTableTab`, el motor principal para la visualización y edición de tablas, y `ColumnHeaderView` para la gestión de filtros y menús contextuales de columnas.
* **`core/db_manager_utils.py`:** Se encarga de la inicialización de las bases de datos, la gestión de conexiones y la ejecución de scripts iniciales de SQL.
* **`forms.py`:** Define los diálogos para la entrada de datos (añadir/editar registros) y selección de rangos de años.
* **`filter_widget.py`:** Implementa el menú desplegable de filtrado y ordenación.
* **`sql/`:** Directorio con los scripts de creación de tablas (`global.sql` y `yearly.sql`).

## 💻 Instalación y Ejecución
1. Clonar el repositorio.
2. Asegurarse de tener `ffmpeg` instalado en el sistema y accesible desde el PATH.
3. Crear un entorno virtual: `python -m venv venv`
4. Activar el entorno e instalar dependencias: `pip install -r requirements.txt`
5. Ejecutar: `python main.pyw`
