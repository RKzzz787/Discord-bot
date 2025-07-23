import os
import random
import discord
import asyncio
import requests
from bs4 import BeautifulSoup
from discord.ext import commands, tasks

# CONFIGURACIÓN
TOKEN = "MTM5NzM1ODA2MDMzODY3OTgzOA.G7VFH8.vHfZAVJqaGCFAKBes59eXW4q14252YFIOnVsao"
CHANNEL_ID = 1394477916565278933

# ARCHIVO DE FRASES
FRASES_PATH = os.path.join(os.path.dirname(__file__), "frases.txt")
if not os.path.exists(FRASES_PATH):
    open(FRASES_PATH, "w", encoding="utf-8").close()

# INTENTS Y BOT
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


# FUNCIONES
def guardar_frase(frase):
    """Guarda una frase en el archivo si no existe ya."""
    try:
        frase = frase.strip()
        if frase == "":
            return
        with open(FRASES_PATH, "r", encoding="utf-8") as f:
            existentes = set(line.strip() for line in f)
        if frase not in existentes:
            with open(FRASES_PATH, "a", encoding="utf-8") as f:
                f.write(frase + "\n")
            print("🧠 Aprendí:", frase)
    except Exception as e:
        print(f"❌ Error al guardar frase: {e}")

def _get_all_unique_words():
    """Lee todas las frases del archivo y devuelve una lista de todas las palabras únicas."""
    all_words = []
    try:
        with open(FRASES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line:
                    # Dividir por espacios y añadir palabras a la lista
                    all_words.extend(stripped_line.split())
    except Exception as e:
        print(f"❌ Error al leer palabras para extraer únicas: {e}")
    
    # Devolver solo palabras únicas
    return list(set(all_words))

def elegir_frase():
    """
    Selecciona una frase aleatoria completa del archivo de frases.
    Se usa para los mensajes periódicos.
    """
    try:
        with open(FRASES_PATH, "r", encoding="utf-8") as f:
            frases = [line.strip() for line in f if line.strip()]
        if not frases:
            return None
        return random.choice(frases)
    except Exception as e:
        print(f"❌ Error eligiendo frase completa: {e}")
        return None

def generar_respuesta_con_palabras_aleatorias():
    """
    Selecciona de 1 a 10 palabras aleatorias de todas las palabras aprendidas
    y las une para formar una respuesta. Se usa para respuestas a menciones/respuestas.
    """
    all_unique_words = _get_all_unique_words()

    if not all_unique_words:
        return None

    # Determina cuántas palabras elegir (entre 1 y 10, o el total disponible si son menos de 10)
    num_palabras_a_elegir = random.randint(1, min(10, len(all_unique_words)))

    # Elige palabras aleatorias sin repetición en la misma respuesta
    palabras_elegidas = random.sample(all_unique_words, num_palabras_a_elegir)

    # Une las palabras elegidas en una sola cadena
    return " ".join(palabras_elegidas)


# EVENTOS
@bot.event
async def on_ready():
    """Evento que se ejecuta cuando el bot está listo y conectado."""
    print(f"✅ Bot conectado como {bot.user}")
    mensaje_cada_5_minutos.start()


@bot.listen("on_message")
async def on_message_listener(message):
    """
    Escucha todos los mensajes para aprender de ellos y responder a menciones/respuestas.
    """
    if message.author.bot:
        return

    if not message.content or message.content.strip() == "":
        return

    guardar_frase(message.content)

    # Determinar si el bot debe responder (mención o respuesta a un mensaje suyo)
    debe_responder = False

    if bot.user in message.mentions:
        debe_responder = True
    elif message.reference:
        try:
            ref = await message.channel.fetch_message(message.reference.message_id)
            if ref.author == bot.user:
                debe_responder = True
        except discord.NotFound:
            # El mensaje referenciado no se encontró, ignorar
            pass
        except discord.HTTPException as e:
            print(f"❌ Error HTTP al obtener mensaje referenciado: {e}")
            pass
        except Exception as e:
            print(f"❌ Error inesperado al obtener mensaje referenciado: {e}")
            pass

    if debe_responder:
        # Responder con palabras aleatorias cuando es mencionado o se le responde
        respuesta = generar_respuesta_con_palabras_aleatorias()
        
        if respuesta and respuesta.strip() != "":
            # Limpiar posibles menciones de roles si aparecen en las palabras elegidas
            respuesta = respuesta.replace("<@&", "").replace(">", "")
            await message.channel.send(respuesta)
        else:
            await message.channel.send("Todavía no aprendí nada 😢")
    
    # Permite que los comandos del bot (ej. !aprender_de_url) también sean procesados
    await bot.process_commands(message)

# TAREA CADA 5 MINUTOS
@tasks.loop(minutes=5)
async def mensaje_cada_5_minutos():
    """Tarea en segundo plano que envía una frase aleatoria cada 5 minutos."""
    if CHANNEL_ID is None:
        print("❌ ERROR: CHANNEL_ID no está configurado. La tarea periódica no puede ejecutarse.")
        return

    canal = bot.get_channel(CHANNEL_ID)
    if canal:
        # Enviar una frase completa aleatoria para los mensajes periódicos
        frase = elegir_frase() 
        await canal.send(frase if frase else "No tengo nada que decir todavía 😐")
    else:
        print(f"❌ No se encontró el canal con ID {CHANNEL_ID} o el bot no tiene acceso a él. Verifica el ID y los permisos.")


# COMANDO PARA APRENDER DE UNA URL
@bot.command(name='aprender_de_url')
async def aprender_de_url(ctx, url: str):
    """Comando para que el bot aprenda frases de una URL. Uso: !aprender_de_url <URL>"""
    await ctx.send(f"🔍 Intentando aprender de: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Lanza un error para códigos de estado HTTP 4xx/5xx
        soup = BeautifulSoup(response.text, "html.parser")

        # Eliminar scripts y estilos para obtener solo texto visible
        for tag in soup(["script", "style"]):
            tag.decompose()

        texto = soup.get_text()
        nuevas = 0
        for linea in texto.splitlines():
            linea = linea.strip()
            if len(linea) > 5: # Solo guardar líneas con más de 5 caracteres como frases
                guardar_frase(linea)
                nuevas += 1

        if nuevas > 0:
            await ctx.send(f"✅ ¡Aprendí {nuevas} frases nuevas de {url}!")
        else:
            await ctx.send("😕 No encontré nada útil en ese sitio.")
    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Error al acceder a la URL: {e}. Asegúrate de que la URL sea válida y accesible.")
    except Exception as e:
        await ctx.send(f"❌ Ocurrió un error inesperado al aprender de la URL: {e}")


# EJECUCIÓN DEL BOT
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN no está configurado.")
