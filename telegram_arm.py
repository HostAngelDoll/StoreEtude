"""
Script para listar diálogos y obtener los últimos 3 mensajes de uno seleccionado.
Requisitos: pip install telethon
Muy Pronto: motor para acceder a canal de telegram y descargar episodios nuevos recientes de forma automatica
"""

import os
from dotenv import load_dotenv
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Cambia el nombre de sesión si quieres otra ruta para el archivo .session
SESSION_NAME = 'session_telegram'

def get_api_credentials():
    # Intenta leer de variables de entorno primero
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    if api_id and api_hash:
        return int(api_id), api_hash
    # Si no están en variables de entorno, pide por consola
    api_id = input("Introduce tu API ID (my.telegram.org): ").strip()
    api_hash = input("Introduce tu API HASH (my.telegram.org): ").strip()
    return int(api_id), api_hash

async def main():
    load_dotenv("env/telegram.env")
    api_id, api_hash = get_api_credentials()
    client = TelegramClient(SESSION_NAME, api_id, api_hash)

    try:
        await client.start()  # Inicia sesión; pedirá número y código si es necesario
    except SessionPasswordNeededError:
        # Si tu cuenta tiene 2FA, Telethon pedirá la contraseña aquí
        pw = input("Tu cuenta tiene 2FA. Introduce la contraseña: ")
        await client.sign_in(password=pw)

    print("\nObteniendo diálogos (esto puede tardar unos segundos)...\n")
    dialogs = await client.get_dialogs()  # devuelve Dialog objects

    # Filtrar y mostrar (grupos y canales suelen interesar; mostramos todo por si acaso)
    editable_list = []
    for i, d in enumerate(dialogs):
        kind = "unknown"
        if d.is_group:
            kind = "group"
        elif d.is_channel:
            kind = "channel"
        elif d.is_user:
            kind = "user"
        title = d.name or getattr(d.entity, 'title', '(sin nombre)')
        print(f"{i:3d}: {title}  [{kind}]")
        editable_list.append(d)

    if not editable_list:
        print("No se encontraron diálogos.")
        await client.disconnect()
        return

    # Selección por índice
    try:
        idx = int(input("\nSelecciona el índice del diálogo a consultar (número): ").strip())
    except ValueError:
        print("Índice inválido. Saliendo.")
        await client.disconnect()
        return

    if idx < 0 or idx >= len(editable_list):
        print("Índice fuera de rango. Saliendo.")
        await client.disconnect()
        return

    selected_dialog = editable_list[idx]
    print(f"\nObteniendo últimos 3 mensajes de: {selected_dialog.name}\n")

    # Obtener últimos 3 mensajes
    messages = await client.get_messages(selected_dialog.entity, limit=3)

    if not messages:
        print("No hay mensajes en este diálogo.")
        await client.disconnect()
        return

    for msg in reversed(messages):

        date = msg.date.isoformat(sep=' ', timespec='seconds') if msg.date else 'fecha-desconocida'

        sender_name = None
        if msg.sender_id:
            try:
                sender = await client.get_entity(msg.sender_id)
                if hasattr(sender, 'first_name') and sender.first_name:
                    last = getattr(sender, 'last_name', '') or ''
                    sender_name = (sender.first_name + ' ' + last).strip()
                else:
                    sender_name = getattr(sender, 'title', None) or str(getattr(sender, 'id', msg.sender_id))
            except Exception:
                sender_name = str(msg.sender_id)
        else:
            sender_name = getattr(selected_dialog.entity, 'title', 'canal/autor-desconocido')

        text = msg.message if getattr(msg, 'message', None) else ''

        # detectar video
        has_video = msg.video is not None

        print("------------------------------------------------------------")
        print(f"Fecha : {date}")
        print(f"Autor : {sender_name}")

        if text:
            print(f"Texto : {text}")
        else:
            print("Texto : <sin texto>")

        if has_video:
            print("Video : SI (el mensaje contiene video)")
        else:
            print("Video : NO")

        print("------------------------------------------------------------")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())