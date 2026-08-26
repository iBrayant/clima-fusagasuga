"""
Script de linea de comandos para regenerar predicciones.json localmente.

Toda la logica real (datos, limpieza, entrenamiento, prediccion,
recomendacion) vive en pipeline.py, compartida con la funcion serverless
de Vercel (api/predicciones.py). Este script solo orquesta la corrida y
escribe el resultado a disco -- util para probar el pipeline sin depender
de Vercel, o para regenerar un predicciones.json de respaldo versionado
en el repositorio.
"""

import json
import sys

try:
    from pipeline import generar_prediccion_completa, log
except ImportError:
    # Permite ejecutar tambien como 'python -m motor.generar_predicciones'
    from motor.pipeline import generar_prediccion_completa, log

SALIDA_JSON = "predicciones.json"


def main():
    log("Iniciando generacion de predicciones para Fusagasuga...")

    payload = generar_prediccion_completa()

    with open(SALIDA_JSON, "w", encoding="utf-8") as archivo:
        json.dump(payload, archivo, ensure_ascii=False, indent=2)

    log(f"Listo. Prediccion exportada a '{SALIDA_JSON}'.")
    log(f"Manana: {payload['prediccion'][0]['temperatura_predicha']} C, "
        f"{payload['prediccion'][0]['precipitacion_predicha']} mm de lluvia.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # pragma: no cover
        log(f"ERROR FATAL: {error}")
        sys.exit(1)
