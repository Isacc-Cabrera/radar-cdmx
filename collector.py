import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = ("https://auth.opensky-network.org/auth/realms/"
             "opensky-network/protocol/openid-connect/token")
BBOX = {"lamin": 19.0, "lomin": -99.6, "lamax": 19.9, "lomax": -98.6}
INTERVALO = 15      # segundos entre consultas
MAX_ANTIGUEDAD = 60  # descarta aviones sin contacto reciente

_token = {"valor": None, "expira": 0}


def obtener_token():
    """Pide un token nuevo solo cuando el anterior está por vencer."""
    client_id = os.getenv("OPENSKY_CLIENT_ID")
    client_secret = os.getenv("OPENSKY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None  # modo anónimo
    if time.time() < _token["expira"] - 60:
        return _token["valor"]
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }, timeout=10)
    r.raise_for_status()
    datos = r.json()
    _token["valor"] = datos["access_token"]
    _token["expira"] = time.time() + datos.get("expires_in", 1800)
    return _token["valor"]


def limpiar(estado, ahora):
    """Convierte la lista cruda de OpenSky en un diccionario limpio."""
    if estado[5] is None or estado[6] is None:
        return None  # sin posición no se puede pintar
    if ahora - estado[4] > MAX_ANTIGUEDAD:
        return None  # dato viejo
    return {
        "id": estado[0],
        "vuelo": (estado[1] or "").strip() or None,
        "pais": estado[2],
        "lon": estado[5],
        "lat": estado[6],
        "altitud_m": estado[7],
        "en_tierra": estado[8],
        "velocidad_kmh": round(estado[9] * 3.6) if estado[9] is not None else None,
        "rumbo": estado[10],
        "vel_vertical": estado[11],
        "ultimo_contacto": estado[4],
    }


def consultar():
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.get(API_URL, params=BBOX, headers=headers, timeout=10)
    if r.status_code == 429:
        print("Límite de consultas alcanzado; espero un minuto.")
        time.sleep(60)
        return []
    r.raise_for_status()
    datos = r.json()
    ahora = datos["time"]
    aviones = (limpiar(e, ahora) for e in datos.get("states") or [])
    return [a for a in aviones if a]


if __name__ == "__main__":
    while True:
        try:
            aviones = consultar()
            print(f"\n{time.strftime('%H:%M:%S')} — {len(aviones)} aviones")
            for a in aviones:
                estado = "en tierra" if a["en_tierra"] else f"{a['altitud_m']} m"
                print(f"  {a['vuelo'] or a['id']:<9} {a['lat']:.4f}, {a['lon']:.4f}  {estado}")
        except requests.RequestException as error:
            print(f"Error de red: {error}")
        time.sleep(INTERVALO)