import json
import time

from kafka import KafkaProducer

from collector import consultar, INTERVALO

TEMA = "aviones"
SERVIDOR_KAFKA = "127.0.0.1:9092"

productor = KafkaProducer(
    bootstrap_servers=SERVIDOR_KAFKA,
    value_serializer=lambda valor: json.dumps(valor).encode("utf-8"),
)

if __name__ == "__main__":
    print(f"Publicando en el tema '{TEMA}' cada {INTERVALO} s")
    while True:
        try:
            aviones = consultar()
            productor.send(TEMA, {"hora": time.time(), "aviones": aviones})
            productor.flush()
            print(f"{time.strftime('%H:%M:%S')} — publicados {len(aviones)} aviones")
        except Exception as error:
            print(f"Error: {error}")
        time.sleep(INTERVALO)