# Directrices para Agentes de Precure Media Manager

Este archivo contiene instrucciones para agentes de IA que trabajen en este repositorio para asegurar la consistencia y el mantenimiento del proyecto.

## 📋 Responsabilidades del Agente

### 1. Mantenimiento del README.md
Cada vez que se implemente una nueva funcionalidad significativa o se realice un cambio estructural, el agente **debe**:
*   Actualizar la sección "Funcionalidades Implementadas" del `README.md`.
*   Asegurarse de que cualquier nuevo módulo de Python sea añadido a la sección "Estructura del Código".
*   Verificar que las instrucciones de instalación sigan siendo válidas (ej. nuevas dependencias en `requirements.txt`).

### 2. Consistencia de Base de Datos
El sistema utiliza archivos SQL en `sql/` como fuente de verdad para la creación de tablas.
*   Si se modifica el esquema de una tabla mediante código (ej. en `data_table.py`), el agente debe verificar que los archivos `sql/global.sql` o `sql/yearly.sql` sean actualizados en consecuencia para reflejar el estado final deseado.
*   Al añadir una nueva tabla, debe documentarse brevemente en la sección "Estructura de la Base de Datos" del `README.md`.

### 3. Convenciones de Código
*   Mantener el estilo de codificación PEP 8 (evitar puntos y coma, usar nombres descriptivos).
*   Asegurar que las nuevas funcionalidades que interactúen con archivos multimedia utilicen `ffmpeg`/`ffprobe` a través de `subprocess` para mantener la consistencia con el resto del sistema.
*   Todas las interfaces de usuario deben ser compatibles con el "dark mode" (ver lógica de colores en `ColumnHeaderView.paintSection`).

## 🔍 Chequeos Programáticos de Integridad

El agente puede y debe ejecutar los siguientes comandos para verificar el estado del repositorio:

### Verificar dependencias
```bash
pip install -r requirements.txt --dry-run
```

### Verificar existencia de archivos SQL y estructura básica
```bash
ls sql/global.sql sql/yearly.sql
grep -i "CREATE TABLE" sql/*.sql
```

### Verificar consistencia del README con el código actual
```bash
# Buscar si hay archivos .py que no están mencionados en el README
for f in *.py *.pyw; do grep -q "$f" README.md || echo "Advertencia: $f no mencionado en README.md"; done
```

### Validar rutas de base de datos en db_manager.py
```bash
grep "BASE_DIR_PATH =" db_manager.py
```

## ⚠️ Notas Importantes
*   El proyecto utiliza una base de datos global y múltiples anuales. Cualquier cambio en `T_Resources` o `T_Registry` debe considerar la propagación a través de todos los archivos `.db` anuales.
*   El idioma preferido para la documentación y comentarios de usuario es el **español**.
