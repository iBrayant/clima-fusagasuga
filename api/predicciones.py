"""
Funcion serverless de Vercel: /api/predicciones

Corre el pipeline completo (datos + limpieza 7 fases + Random Forest +
recomendacion de cultivos) y devuelve el resultado como JSON. Se cachea
en el borde de Vercel por 30 minutos (con 1 hora extra de gracia) para
que, con el trafico bajo de este proyecto, casi nunca se vuelva a
entrenar el modelo en cada visita -- pero el sitio nunca queda con datos
de hace semanas: la primera visita despues de esa ventana dispara un
recalculo automatico con la fecha del dia.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "motor"))

from pipeline import generar_prediccion_completa  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = generar_prediccion_completa()
            cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header(
                "Cache-Control",
                "public, s-maxage=1800, stale-while-revalidate=3600",
            )
            self.end_headers()
            self.wfile.write(cuerpo)
        except Exception as error:
            cuerpo = json.dumps(
                {"error": "No se pudo generar la prediccion.", "detalle": str(error)},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(cuerpo)
