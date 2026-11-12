import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from collector import consultar, INTERVALO

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


async def ciclo_recolector():
    """Consulta OpenSky cada INTERVALO segundos y reparte el resultado."""
    global ultimo_lote
    while True:
        try:
            ultimo_lote = await asyncio.to_thread(consultar)
            await difundir(empaquetar(ultimo_lote))
            print(f"{len(ultimo_lote)} aviones -> {len(clientes)} clientes")
        except Exception as error:
            print(f"Error en el recolector: {error}")
        await asyncio.sleep(INTERVALO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarea = asyncio.create_task(ciclo_recolector())
    yield
    tarea.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
def inicio():
    return FileResponse("static/index.html")


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