import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from kafka import KafkaConsumer

TEMA = "aviones"
SERVIDOR_KAFKA = "127.0.0.1:9092"

clientes: set[WebSocket] = set()   # navegadores conectados
ultimo_lote: list[dict] = []       # últimas posiciones conocidas


def empaquetar(aviones):
    return json.dumps({"tipo": "aviones", "aviones": aviones})


async def difundir(mensaje: str):
    """Envía el mensaje a todos; quita a los que ya se desconectaron."""
    for ws in list(clientes):
        try:
            await ws.send_text(mensaje)
        except Exception:
            clientes.discard(ws)


def crear_consumidor():
    return KafkaConsumer(
        TEMA,
        bootstrap_servers=SERVIDOR_KAFKA,
        value_deserializer=lambda datos: json.loads(datos.decode("utf-8")),
        auto_offset_reset="latest",  # solo mensajes nuevos, no el historial
    )


async def ciclo_consumidor():
    """Lee lotes del tema de Kafka y los reparte a los navegadores."""
    global ultimo_lote
    consumidor = None
    while consumidor is None:
        try:
            consumidor = await asyncio.to_thread(crear_consumidor)
        except Exception as error:
            print(f"Kafka no disponible ({error}); reintento en 5 s")
            await asyncio.sleep(5)
    print("Conectado a Kafka")
    while True:
        registros = await asyncio.to_thread(consumidor.poll, 1000)
        for mensajes in registros.values():
            for mensaje in mensajes:
                ultimo_lote = mensaje.value["aviones"]
                await difundir(empaquetar(ultimo_lote))
                print(f"{len(ultimo_lote)} aviones -> {len(clientes)} clientes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarea = asyncio.create_task(ciclo_consumidor())
    yield
    tarea.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
def inicio():
    return FileResponse("static/index.html")

@app.get("/3d")
def mapa_3d():
    return FileResponse("static/index3d.html")


@app.websocket("/ws")
async def canal(ws: WebSocket):
    await ws.accept()
    clientes.add(ws)
    await ws.send_text(empaquetar(ultimo_lote))  # no esperar al siguiente ciclo
    try:
        while True:
            await ws.receive_text()  # mantiene viva la conexión
    except WebSocketDisconnect:
        clientes.discard(ws)