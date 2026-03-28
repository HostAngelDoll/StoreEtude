<p align="center">
  <img src="img/icon.png" width="128" height="128" alt="Precure Media Manager Icon">
</p>

# 📺 Precure Media Manager (Desktop)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Architecture](https://img.shields.io/badge/Architecture-MVC%20%2B%20Services-orange.svg)](#architecture)

Precure Media Manager is a comprehensive desktop application designed for the management and tracking of multimedia resources (episodes, movies, soundtracks) related to the Precure franchise. It features a robust SQLite-based yearly database architecture, Telegram integration for automated downloads, Firebase synchronization, and an internal REST API.

---

## 🌎 Idiomas / Languages
- [English](#-precure-media-manager-desktop)
- [Español (Spanish)](#-precure-media-manager-desktop-es)

---

## 🚀 Key Features

### 📦 Resource Management
*   **Automated Scanning:** Intelligent detection of `.mp4`, `.mkv`, and audio files, linking them to the database registry.
*   **Dynamic CRUD:** Full table editing support with foreign key validation and custom delegates.
*   **Bulk Migration:** Excel-based data import for resources and viewing history.
*   **Metadata Detection:** Integration with `ffprobe` for duration and stream analysis.

### 🔍 Advanced Visualization
*   **Excel-Style Filtering:** Multi-column filtering and sorting system.
*   **Real-time Analytics:** Automatic calculation of playback durations (lapses) and opening version detection.
*   **Material Reporting:** Specialized tools for generating collection reports.

### 🌐 Connectivity & Integration
*   **Telegram Downloader:** Dedicated bot integration (`Telethon`) for downloading resources directly from chats.
*   **Firebase Sync:** Bidirectional synchronization of "Journals" (Viewing Agendas) via Firebase Admin SDK.
*   **Internal REST API:** Flask-powered server (Waitress) for programmatic resource queries and database access.
*   **Security:** Network-based whitelisting (SSID/BSSID/Gateway) to control API and Firebase access.

### 🛡️ Reliability
*   **Hybrid Offline Mode:** Seamless hot-swapping between external drive (Online) and local SQLite snapshots (Offline).
*   **Drive Monitoring:** Real-time tracking of hardware connectivity and storage space.

---

## 🏗️ Architecture

The project follows a strict **Layered MVC (Model-View-Controller)** pattern combined with a **Service Layer** to ensure high decoupling and maintainability.

### Layer Breakdown:
1.  **Presentation (UI):** Built with `PyQt6`. Encapsulates views and user interaction logic.
2.  **Orchestration (Controllers):** Thin controllers (`MainController`) that coordinate the flow between the UI and Services.
3.  **Business Logic (Services):** Domain-specific logic (Scanning, Migration, Sync) isolated from UI concerns.
4.  **Data/Core:** Low-level database management, configuration handling, and external API managers.

### Directory Structure:

| Directory / File | Responsibility |
|------------------|----------------|
| `main.pyw` | Main entry point for the GUI application. |
| `controllers/` | Orchestrators (`MainController`, `TelegramController`) that coordinate flow between UI and Services. |
| `core/` | Cross-cutting concerns: `ConfigManager`, `APIServer`, `FirebaseManager`, and low-level resource logic. |
| `db/` | Low-level SQLite connection management (`QSqlDatabase`) and session/year context handling. |
| `services/` | Encapsulated business services (e.g., `ScannerService`, `MigrationService`, `SyncService`). |
| `ui/` | Core UI components: `MainWindow`, `ActionsManager`, and modular table widgets in `ui/table/`. |
| `dialogs/` | Modularized forms and custom cell delegates (e.g., `SpinoffDelegate`) used throughout the app. |
| `journals_manager/` | Specialized module for the "Journal Agenda" system with its own logic and GUI components. |
| `sql/` | Master SQL schema definitions used for database initialization and maintenance. |
| `img/` | Application assets, icons, and splash screens. |

---

## 🗄️ Database Schema

### 1. Global Database (`_global.db`)
Stores master metadata used across all years:
*   **T_Seasons:** Franchise installments, master paths, and year mappings.
*   **T_Type_Resources:** Resource categories (Episodes, Movies, OSTs).
*   **T_Opener_Models:** Opening/Ending version definitions.
*   **T_Type_Catalog_Reg:** Registry classification types.

### 2. Yearly Databases (`YYYY.db`)
Isolated databases for each year (2004 - Present):
*   **T_Resources:** File inventory (paths, titles, duration, download timestamps).
*   **T_Registry:** Viewing history, playback lapses, and version tracking.

---

## 🛠️ Setup & Installation

### Prerequisites
*   Python 3.10+
*   `ffmpeg` & `ffprobe` (Must be in system PATH)

### Installation
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/HostAngelDoll/StoreEtude.git
    cd StoreEtude
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # Windows:
    venv\Scripts\activate
    # Linux/Mac:
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Launch the application:**
    ```bash
    python main.pyw
    ```

---

## ⚙️ Configuration

The application centralizes its configuration in a `config.json` file managed by `ConfigManager`.

*   **Telegram:** Requires `api_id` and `api_hash` from [my.telegram.org](https://my.telegram.org).
*   **Firebase:** Requires a service account JSON file and the Realtime Database URL.
*   **API:** Port and toggle available in the "Servidor API" settings tab.

---

## 👨‍💻 Developer Notes

*   **Syntax Verification:** Use `py_compile` to check component integrity before committing.
*   **Extensibility:** New features should be implemented as a **Service** first, then exposed via a **Controller**.
*   **Database Migrations:** Schema changes in `sql/` files should be propagated using the internal `DBService`.

---

# 📺 Precure Media Manager (Desktop) [ES]

Sistema integral de gestión de recursos multimedia para la franquicia Precure. Basado en una arquitectura de escritorio moderna que prioriza la modularidad y el desacoplamiento de capas.

---

## 🚀 Características Principales

### 📦 Gestión de Recursos
*   **Escaneo Inteligente:** Detección automática de archivos multimedia y vinculación con el registro de la base de datos.
*   **CRUD Dinámico:** Soporte completo para edición de tablas con validación de claves foráneas y delegados personalizados.
*   **Migración Masiva:** Importación de datos desde Excel para recursos e historial de visualización.
*   **Detección de Metadatos:** Integración con `ffprobe` para análisis de duración y flujos.

### 🔍 Visualización Avanzada
*   **Filtros estilo Excel:** Sistema de filtrado y ordenamiento multi-columna.
*   **Analítica en Tiempo Real:** Cálculo automático de lapsos de reproducción e identificación de versiones de apertura.
*   **Reportes de Material:** Generación de reportes detallados sobre la colección.

### 🌐 Integración y Conectividad
*   **Descargador Telegram:** Integración con `Telethon` para descarga directa de recursos desde chats.
*   **Sincronización Firebase:** Sincronización bidireccional de "Jornadas" (Agendas de visualización).
*   **API REST Interna:** Servidor Flask (Waitress) para consultas programáticas y acceso a datos.
*   **Seguridad:** Lista blanca de redes (SSID/BSSID) para control de acceso a servicios externos.

---

## 🏗️ Arquitectura

El proyecto implementa un patrón **MVC por Capas** junto con una **Capa de Servicios** para garantizar el desacoplamiento.

### Desglose de Directorios y Archivos:

| Directorio / Archivo | Responsabilidad |
|----------------------|----------------|
| `main.pyw` | Punto de entrada principal para la aplicación GUI. |
| `controllers/` | Orquestadores (`MainController`, `TelegramController`) que coordinan el flujo entre la UI y los Servicios. |
| `core/` | Lógica transversal: `ConfigManager`, `APIServer`, `FirebaseManager` y lógica de recursos de bajo nivel. |
| `db/` | Gestión de conexiones SQLite (`QSqlDatabase`) y manejo de contexto de sesión/año. |
| `services/` | Servicios de negocio encapsulados (ej. `ScannerService`, `MigrationService`, `SyncService`). |
| `ui/` | Componentes de UI principales: `MainWindow`, `ActionsManager` y widgets de tabla modulares en `ui/table/`. |
| `dialogs/` | Formularios modularizados y delegados de celda personalizados usados en toda la app. |
| `journals_manager/` | Módulo especializado para el sistema de "Jornadas" con su propia lógica y componentes GUI. |
| `sql/` | Definiciones maestras de esquemas SQL para inicialización y mantenimiento. |
| `img/` | Assets de la aplicación, iconos y pantallas de carga. |

---

## 🛠️ Instalación y Requisitos

### Requisitos
*   Python 3.10+
*   `ffmpeg` & `ffprobe` en el PATH del sistema.

### Instalación
1.  Clonar: `git clone https://github.com/HostAngelDoll/StoreEtude.git`
2.  Entorno virtual: `python -m venv venv`
3.  Dependencias: `pip install -r requirements.txt`
4.  Ejecución: `python main.pyw`

---

## 🔐 Notas para Desarrolladores

*   **Principio de Responsabilidad Única:** Mantener lógica de negocio fuera de los archivos de la `ui/`.
*   **Modo Offline:** El sistema soporta hot-swap entre la unidad externa 'E:/' y snapshots locales en `offline_dbs/`.
*   **Configuración:** Gestionada a través de `ConfigManager`, persistida en el registro de Windows y archivos JSON.
