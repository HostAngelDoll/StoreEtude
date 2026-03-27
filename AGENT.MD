# `agent.md` - Directrices de Arquitectura y Mentoría

## 🎯 Objetivo
Transformar cada entrega de código en un sistema modular, desacoplado y pedagógico. Jules no solo escribe código que funciona; escribe código que enseña y permite el crecimiento sin fricción.

## 🛠️ Principios de Desarrollo

### 1. Separación Radical de Responsabilidades (SoC)
* **Prohibición de Monolitos:** Ningún archivo debe contener lógica de negocio, acceso a datos e interfaz de usuario simultáneamente.
* **Capas Definidas:** Todo proyecto debe seguir una estructura de carpetas clara (ej. `core/`, `data/`, `ui/`, `utils/`).
* **Inyección de Dependencias:** Las clases no deben instanciar sus dependencias internamente. Deben recibirlas para facilitar el testeo y la modularidad.

### 2. Código "Self-Documenting" y Pedagógico
* **Nombramiento Semántico:** Usa nombres de variables y funciones que describan el *qué* y el *por qué*, no el *cómo*.
* **Tipado Estricto:** Usa *Type Hints* (en Python) o interfaces claras para definir qué entra y qué sale de cada componente.
* **Comentarios de Arquitectura:** Incluye breves comentarios que expliquen la decisión de diseño (ej. "Usamos el patrón Observer aquí para que la lógica de datos no dependa de la UI").

### 3. Facilidad de Mejora (Extensibilidad)
* **Principio Abierto/Cerrado:** El código debe estar abierto a la extensión pero cerrado a la modificación. Los estudiantes deben poder agregar funciones creando nuevas clases, no editando las existentes.
* **Pequeñas Piezas:** Las funciones no deben superar las 20-30 líneas. Si es más larga, se debe subdividir.

---

## 📋 Protocolo de Respuesta

Antes de entregar cualquier código, Jules debe validar internamente:
1.  **¿Es modular?** ¿Puedo cambiar la base de datos sin tocar la interfaz?
2.  **¿Es legible para un novato?** ¿Un estudiante de primer año entendería el flujo?
3.  **¿Está organizado?** ¿He sugerido la estructura de carpetas necesaria?

---

## 📂 Estructura de Proyecto Estándar (Ejemplo)
Cuando el usuario pida un script, Jules siempre propondrá (o asumirá) esta jerarquía:
* `/src/domain/`: Reglas de negocio y modelos.
* `/src/infrastructure/`: Persistencia, APIs, manejo de archivos.
* `/src/presentation/`: Vistas y controladores de UI.
* `main.py`: Orquestador de la aplicación.

---

## Debes estar altamente preocupado por mantener el codigo ordenado, responsabilidades separadas y obsecionado con restrucutrar codigo Monolitos 
