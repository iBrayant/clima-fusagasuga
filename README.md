# Clima & Cultivos — Fusagasugá

Dashboard climatológico y agro-predictivo para Fusagasugá (Cundinamarca).
Predice temperatura y precipitación para los próximos días y recomienda
qué cultivos sembrar según esa predicción.

Proyecto académico — Universidad de Cundinamarca, Seccional Fusagasugá,
Ingeniería de Sistemas y Computación, curso de Inteligencia Artificial (604566).

## Arquitectura

El proyecto está dividido en dos partes independientes:

- **Motor de datos** (`motor/generar_predicciones.py`, Python): obtiene el
  histórico climático real de Fusagasugá desde la API de [Open-Meteo](https://open-meteo.com/)
  (con respaldo simulado si la API no responde), aplica las 7 fases de
  limpieza de datos, entrena dos modelos Random Forest (temperatura y
  precipitación), genera la predicción de los próximos 7 días junto con
  la recomendación de cultivos, y exporta todo a `motor/predicciones.json`.
- **Dashboard estático** (`index.html`, `style.css`, `app.js`): lee ese
  JSON y lo muestra en una interfaz visual. No depende de un servidor:
  es HTML/CSS/JS puro, desplegable directamente en Vercel como sitio estático.

Esta separación evita depender de un servidor Python corriendo de forma
permanente (como requeriría Dash) para algo que solo necesita mostrar
un resultado ya calculado.

## Estructura

```
clima-fusagasuga/
├── README.md
├── motor/
│   ├── generar_predicciones.py   -> script Python: datos + limpieza + modelo + prediccion
│   └── predicciones.json         -> resultado que consume el dashboard
├── index.html                    -> pagina principal del dashboard
├── style.css                     -> estilos
└── app.js                        -> lee predicciones.json y dibuja el grafico
```

## Cómo regenerar las predicciones

```bash
cd motor
python3 -m venv .venv && source .venv/bin/activate
pip install pandas numpy requests scikit-learn
python generar_predicciones.py
```

Esto sobrescribe `motor/predicciones.json` con datos y predicciones nuevas.

## Cómo ver el dashboard localmente

```bash
python3 -m http.server 8000
```

Y abrir `http://localhost:8000` en el navegador.

## Despliegue en Vercel

1. Subir el repositorio a GitHub.
2. En [vercel.com](https://vercel.com), **Add New Project** y elegir el repositorio.
3. Vercel detecta automáticamente que es un sitio estático — no requiere
   configurar build command ni output directory. Clic en **Deploy**.

## Actualizar el dashboard con datos más recientes

1. Correr de nuevo `generar_predicciones.py`.
2. Esto sobrescribe `motor/predicciones.json`.
3. `git add`, `git commit`, `git push`.
4. Vercel vuelve a desplegar automáticamente al detectar el cambio.
