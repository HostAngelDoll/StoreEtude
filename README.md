# 📺 Precure Media Manager (Desktop)

Sistema integral de gestión de recursos multimedia para la franquicia Precure. Aplicación de escritorio basada en PyQt6 que gestiona episodios, películas, soundtracks y su historial de visualización, con integración de Telegram, sincronización a Firebase y una API REST interna.

## 🛠️ Tecnologías

* **Lenguaje:** Python 3.10+
* **Interfaz Gráfica:** PyQt6
* **Base de Datos:** SQLite (Arquitectura de bases de datos anuales y global)
* **API/Servidor:** Flask + Waitress
* **Integración Mensajería:** Telethon (Telegram Bot)
* **Procesamiento de Excel:** openpyxl
* **Cloud:** Firebase Admin SDK
* **Multimedia:** ffmpeg/ffprobe (para detección de metadatos y duración)

## 🏗️ Arquitectura del Proyecto

```
StoreEtude/
├── main.pyw                    # Punto de entrada (Windows GUI)
├── requirements.txt            # Dependencias
│
├── 📦 controllers/             # Controladores principales
│   ├── main_controller.py      # Coordinador central de lógica
│   └── telegram_controller.py  # Manejo de bot Telegram
│
├── 📦 core/                    # Lógica de negocio
│   ├── api_server.py          # Servidor Flask REST
│   ├── app_state.py           # Estado global de la aplicación
│   ├── config_manager.py      # Gestión de configuración
│   ├── data_migration.py      # Migraciones y conversiones de datos
│   ├── db_manager_utils.py    # Inicialización y gestión de BD
│   ├── db_operations.py       # Operaciones CRUD en BD
│   ├── drive_monitor.py       # Monitoreo de unidades de almacenamiento
│   ├── firebase_manager.py    # Integración con Firebase
│   ├── resource_management.py # Gestión de recursos (escaneo, vinculación)
│   ├── sync_manager.py        # Sincronización de datos
│   ├── telegram_manager.py    # Gestor del bot Telegram
│   └── whitelist_manager.py   # Gestión de lista blanca de usuarios
│
├── 📦 db/                      # Capa de acceso a datos
│   ├── connection.py          # Manejo de conexiones SQLite
│   └── session_manager.py     # Gestor de sesiones de BD
│
├── 📦 ui/                      # Interfaz de usuario
│   ├── main_window.py         # Ventana principal
│   ├── actions.py             # Acciones de menú y botones
│   ├── filter_widget.py       # Widget de filtrado estilo Excel
│   ├── warning_bar.py         # Barra de advertencias
│   └── 📂 table/              # Módulo de tablas (en desarrollo)
│
├── 📦 dialogs/                 # Diálogos y formularios
│   ├── common_delegates.py    # Delegados personalizados para celdas
│   ├── settings_dialog.py     # Diálogo de configuración
│   ├── database_form.py       # Formulario de gestión de BD
│   ├── column_management.py   # Gestión de columnas en tablas
│   ├── telegram_download.py   # Diálogo de descarga desde Telegram
│   ├── whitelist_dialog.py    # Gestión de whitelist
│   ├── chat_selection.py      # Selección de chat Telegram
│   ├── year_range.py          # Selección de rango de años
│   ├── duplicate_action.py    # Gestión de duplicados
│   ├── report_materials.py    # Generación de reportes
│   └── __init__.py
│
├── 📦 services/                # Servicios de negocio
│   ├── db_service.py          # Servicio de base de datos
│   ├── migration_service.py   # Servicio de migraciones
│   ├── scanner_service.py     # Servicio de escaneo de archivos
│   ├── sync_service.py        # Servicio de sincronización
│   ├── 📂 telegram/           # Submódulo de servicios Telegram
│   └── __init__.py
│
├── 📂 journals_manager/        # Gestor de diarios/registros
│   ├── journal_gui.py         # Interfaz de diarios
│   └── journal_logic.py       # Lógica de diarios
│
├── 📂 sql/                     # Scripts SQL
│   ├── global.sql             # Esquema BD global
│   └── yearly.sql             # Esquema BD anuales
│
├── 📂 db/                      # Directorio de bases de datos (runtime)
│   └── *.db                   # Archivos SQLite generados
│
└── 📂 img/                     # Assets de imagen
```

## 📋 Estructura de la Base de Datos

### Base de Datos Global (`_global.db`)

Contiene metadatos maestros:
* **T_Seasons:** Temporadas (años, nombres, rutas maestras)
* **T_Type_Resources:** Catálogo de tipos (Episodio, Película, Soundtrack, etc.)
* **T_Opener_Models:** Modelos de apertura/versiones
* **T_Type_Catalog_Reg:** Clasificación de tipos de registro

### Bases de Datos Anuales (`AAAA.db`)

Cada año desde 2004 al presente:
* **T_Resources:** Inventario de archivos (rutas, títulos, duración, fecha descarga)
* **T_Registry:** Historial de visualización (rangos, lapsos, modelos detectados)

## ✨ Características Principales

### Gestión de Recursos
- [x] **CRUD Dinámico:** Edición completa de tablas con soporte para claves foráneas
- [x] **Escaneo Automático:** Detección de `.mp4`, `.mkv` y audios vinculándolos automáticamente
- [x] **Importación desde Excel:** Migración masiva de datos existentes
- [x] **Propagación de Esquemas:** Cambios de columnas se replican en todas las BD anuales

### Visualización y Análisis
- [x] **Filtros Avanzados:** Sistema estilo Excel con múltiples criterios
- [x] **Cálculos Automáticos:** Duración de reproducciones (lapsos) en tiempo real
- [x] **Detección de Modelos:** Identificación automática de versiones de apertura
- [x] **Reportes:** Generación de reportes de materiales

### Integración Externa
- [x] **Bot Telegram:** Descarga de recursos directamente desde Telegram
- [x] **Firebase Sync:** Sincronización de datos a Firebase
- [x] **API REST:** Servidor interno Flask para consultas programáticas
- [x] **Whitelist:** Control de acceso por usuario/chat en Telegram

### Mantenimiento
- [x] **Consola SQL Integrada:** Ejecución de scripts SQL directos
- [x] **Logs en Tiempo Real:** Visualización de operaciones del sistema
- [x] **Monitoreo de Unidades:** Seguimiento de espacios de almacenamiento
- [x] **Gestión de Configuración:** Interfaz centralizada de configuración

## 🚀 Instalación y Ejecución

### Requisitos Previos
- Python 3.10 o superior
- `ffmpeg` instalado y accesible desde PATH

### Pasos de Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/HostAngelDoll/StoreEtude.git
cd StoreEtude

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno (Windows)
venv\Scripts\activate
# O en Linux/Mac:
source venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Ejecutar aplicación
python main.pyw
```

## 📝 Flujo de Trabajo Principal

1. **Inicialización:** Al arrancar, se inicializan BD global y anuales
2. **Interfaz:** Se carga la ventana principal con pestañas de recursos y registros
3. **Operaciones:** CRUD de recursos, filtrado, búsqueda
4. **Sincronización:** Datos se sincronizan con Firebase según configuración
5. **Telegram:** Bot espera comandos para descargas y consultas
6. **Reporte:** Generación de reportes sobre colección

## 🔐 Módulos Clave

| Módulo | Responsabilidad |
|--------|-----------------|
| `main_controller.py` | Orquestación central, hilos, coordinación |
| `main_window.py` | Interfaz gráfica PyQt6 |
| `api_server.py` | Servidor Flask para API REST |
| `telegram_manager.py` | Gestor del bot Telegram con Telethon |
| `resource_management.py` | Escaneo y vinculación automática |
| `config_manager.py` | Gestión de configuraciones persistentes |
| `db_operations.py` | Operaciones SQL ejecutadas |

## 📌 Notas de Desarrollo

- La aplicación sigue patrón MVC (Modelo-Vista-Controlador)
- Los servicios encapsulan lógica reutilizable
- Los diálogos modularizados facilitan mantenimiento
- Base de datos con arquitectura híbrida (global + anuales) optimiza rendimiento
