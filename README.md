# Clima & Cultivos — Fusagasugá

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Random%20Forest-F7931E?logo=scikitlearn&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-serverless-000000?logo=vercel&logoColor=white)
![Licencia](https://img.shields.io/badge/licencia-MIT-green)

Dashboard climatológico y agro-predictivo para Fusagasugá (Cundinamarca). Predice la temperatura y la precipitación de los próximos 7 días con Random Forest y recomienda qué cultivos sembrar según esa predicción.

> Proyecto académico — Universidad de Cundinamarca, Seccional Fusagasugá, Ingeniería de Sistemas y Computación, curso de Inteligencia Artificial (604566).

<!-- TODO: captura o GIF del dashboard (guardar en docs/img/) -->
<!-- ![Dashboard](docs/img/demo.png) -->
<!-- TODO: enlace a la demo desplegada en Vercel -->

## Características

- **Datos reales:** histórico climático de Fusagasugá desde la API de [Open-Meteo](https://open-meteo.com/), con respaldo simulado si la API no responde.
- **Limpieza de datos en 7 fases:** auditoría, nulos, duplicados, outliers, texto, tipos y validación final.
- **Dos modelos Random Forest** (temperatura y precipitación) con métricas de validación (MAE y R²).
- **Recomendación de cultivos** mediante un sistema experto basado en las condiciones agroecológicas de la zona.
- **Siempre vigente:** función serverless en Vercel que recalcula con la fecha real, con caché en el borde.
- **Interfaz** con fondo animado y tema claro/oscuro.

## Stack

Python · pandas · NumPy · scikit-learn · Open-Meteo API · Vercel (serverless) · HTML/CSS/JS

## Arquitectura

El proyecto está dividido en dos partes:

- **Pipeline de datos y modelo** (`motor/pipeline.py`, Python): obtiene el
  histórico climático real de Fusagasugá desde la API de [Open-Meteo](https://open-meteo.com/)
  (con respaldo simulado si la API no responde), aplica las 7 fases de
  limpieza de datos, entrena dos modelos Random Forest (temperatura y
  precipitación), y genera la predicción de los próximos 7 días junto con
  la recomendación de cultivos.
- **Dashboard** (`index.html`, `style.css`, `app.js`): interfaz visual que
  consume ese resultado y lo muestra. No hace ningún cálculo por su cuenta.

El pipeline se usa de dos formas:

1. **`api/predicciones.py`** — una función serverless de Vercel. Cada vez
   que el dashboard pide datos (`GET /api/predicciones`), esta función corre
   el pipeline completo con la fecha real de ese momento y devuelve el JSON.
   Vercel cachea esa respuesta en su borde (~30 minutos, con una hora extra
   de gracia), así que con el tráfico bajo de este proyecto casi nunca se
   vuelve a entrenar el modelo en cada visita, pero el sitio nunca se queda
   con datos de hace semanas.
2. **`motor/generar_predicciones.py`** — script de línea de comandos que
   corre el mismo pipeline y lo escribe a `predicciones.json` en disco. Sirve
   para regenerar/depurar localmente sin depender de Vercel.

No hay ningún servidor corriendo de forma permanente (como requeriría Dash):
la función de Vercel se prende, calcula, responde, y se apaga.

## Estructura

```
clima-fusagasuga/
├── README.md
├── vercel.json                     -> config de la funcion serverless (tiempo/memoria)
├── api/
│   ├── predicciones.py             -> funcion serverless: GET /api/predicciones
│   └── requirements.txt            -> dependencias Python de esa funcion
├── motor/
│   ├── pipeline.py                 -> datos + limpieza (7 fases) + modelo + recomendacion
│   └── generar_predicciones.py     -> script CLI para regenerar/depurar localmente
├── index.html                      -> pagina principal del dashboard
├── style.css                       -> estilos
└── app.js                          -> consume /api/predicciones y dibuja el grafico
```

## Cómo probarlo localmente

Instalar dependencias:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt
```

Opción rápida (solo el pipeline, sin servidor):

```bash
cd motor
python generar_predicciones.py
```

Esto genera `motor/predicciones.json` con datos y predicciones frescas
(no lo usa el sitio desplegado, es solo para ver el pipeline correr).

Para probar el dashboard completo con la función serverless real, se
recomienda el CLI de Vercel:

```bash
npm install -g vercel
vercel dev
```

## Despliegue en Vercel

1. Subir el repositorio a GitHub.
2. En [vercel.com](https://vercel.com), **Add New Project** y elegir el repositorio.
3. Vercel detecta automáticamente el sitio estático y la función Python en
   `api/` — no requiere configuración adicional. Clic en **Deploy**.

Cada vez que alguien visita el sitio, `/api/predicciones` corre con la
fecha real de ese momento — no hay que regenerar ni volver a desplegar
manualmente para que la predicción se mantenga vigente.

## Aviso

Proyecto académico. Las predicciones y recomendaciones son orientativas y no reemplazan la asesoría de un agrónomo ni los pronósticos oficiales del IDEAM.

## Autor

**Brayant Vásquez Gómez** · [GitHub](https://github.com/iBrayant) · [LinkedIn](https://linkedin.com/in/brayant-vásquez-gómez)

Licencia [MIT](LICENSE).
