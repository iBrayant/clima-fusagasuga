"""
Pipeline compartido de datos y prediccion climatologica - Fusagasuga.

Contiene toda la logica reutilizable (obtencion de datos, limpieza de
7 fases, entrenamiento y prediccion, recomendacion de cultivos). La usan:

- motor/generar_predicciones.py -> script de linea de comandos, escribe
  predicciones.json en disco (util para regenerar/probar localmente).
- api/predicciones.py -> funcion serverless de Vercel, devuelve el mismo
  resultado como respuesta HTTP en cada peticion (con cache de por medio).

Los parametros estan ajustados para responder rapido dentro de una
funcion serverless: histórico de ~1.5 anios (suficiente para capturar
estacionalidad) y 100 arboles por bosque en vez de 200.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------
# Configuracion general
# ---------------------------------------------------------------------------

LATITUD = 4.3417
LONGITUD = -74.3644
ZONA_HORARIA = "America/Bogota"

DIAS_HISTORICO = 550             # ~1.5 anios: suficiente estacionalidad, rapido de traer y entrenar
DIAS_PREDICCION = 7              # dias a predecir hacia adelante
N_ARBOLES = 100                  # arboles por Random Forest (balance velocidad/precision)

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"


def log(mensaje: str) -> None:
    print(f"[pipeline] {mensaje}")


# ---------------------------------------------------------------------------
# Obtencion de datos (API real con respaldo simulado)
# ---------------------------------------------------------------------------

def obtener_datos_historicos() -> pd.DataFrame:
    """Trae el historico diario de Fusagasuga desde la API de Open-Meteo.

    Si la API falla (sin internet, timeout, error del servicio) se genera
    un respaldo simulado para que el pipeline nunca se rompa por completo.
    """
    fin = datetime.now(timezone.utc).date() - timedelta(days=2)
    inicio = fin - timedelta(days=DIAS_HISTORICO)

    parametros = {
        "latitude": LATITUD,
        "longitude": LONGITUD,
        "start_date": inicio.isoformat(),
        "end_date": fin.isoformat(),
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": ZONA_HORARIA,
    }

    try:
        log(f"Solicitando historico real a Open-Meteo ({inicio} -> {fin})...")
        respuesta = requests.get(ARCHIVE_API_URL, params=parametros, timeout=15)
        respuesta.raise_for_status()
        datos = respuesta.json()["daily"]

        df = pd.DataFrame({
            "fecha": datos["time"],
            "temperatura_media": datos["temperature_2m_mean"],
            "precipitacion": datos["precipitation_sum"],
        })
        df["fuente"] = "open-meteo"
        log(f"Historico real obtenido: {len(df)} registros.")
        return df

    except (requests.RequestException, KeyError, ValueError) as error:
        log(f"AVISO: fallo la API de Open-Meteo ({error}). Se usa respaldo simulado.")
        return generar_datos_simulados(inicio, fin)


def generar_datos_simulados(inicio, fin) -> pd.DataFrame:
    """Genera un historico sintetico plausible para Fusagasuga (clima frio-templado)."""
    fechas = pd.date_range(start=inicio, end=fin, freq="D")
    n = len(fechas)

    rng = np.random.default_rng(42)
    dia_ano = fechas.dayofyear.to_numpy()
    # Estacionalidad simple: dos temporadas de lluvia (bimodal andino)
    estacionalidad_lluvia = 10 + 8 * np.abs(np.sin(dia_ano / 365 * 4 * np.pi))
    temperatura = 19 + 2.5 * np.sin(dia_ano / 365 * 2 * np.pi) + rng.normal(0, 1.5, n)
    precipitacion = np.clip(
        rng.exponential(scale=estacionalidad_lluvia), 0, None
    )

    df = pd.DataFrame({
        "fecha": fechas.astype(str),
        "temperatura_media": temperatura,
        "precipitacion": precipitacion,
    })
    df["fuente"] = "simulado"
    log(f"Historico simulado generado: {len(df)} registros.")
    return df


def obtener_pronostico_oficial() -> pd.DataFrame:
    """Trae el pronostico oficial de Open-Meteo para los proximos dias (referencia)."""
    parametros = {
        "latitude": LATITUD,
        "longitude": LONGITUD,
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": ZONA_HORARIA,
        "forecast_days": DIAS_PREDICCION,
    }
    try:
        respuesta = requests.get(FORECAST_API_URL, params=parametros, timeout=15)
        respuesta.raise_for_status()
        datos = respuesta.json()["daily"]
        df = pd.DataFrame({
            "fecha": pd.to_datetime(datos["time"]),
            "temperatura_oficial": datos["temperature_2m_mean"],
            "precipitacion_oficial": datos["precipitation_sum"],
        })
        log("Pronostico oficial de referencia obtenido.")
        return df
    except (requests.RequestException, KeyError, ValueError) as error:
        log(f"AVISO: no se pudo obtener el pronostico oficial de referencia ({error}).")
        return pd.DataFrame(columns=["fecha", "temperatura_oficial", "precipitacion_oficial"])


# ---------------------------------------------------------------------------
# Limpieza de datos - 7 fases (metodologia del curso)
# ---------------------------------------------------------------------------

def fase_1_audit(df: pd.DataFrame) -> pd.DataFrame:
    log("Fase 1/7 - Auditoria inicial: "
        f"{df.shape[0]} filas, {df.shape[1]} columnas.")
    return df


def fase_2_nulos(df: pd.DataFrame) -> pd.DataFrame:
    nulos_antes = df[["temperatura_media", "precipitacion"]].isna().sum().sum()
    df["temperatura_media"] = df["temperatura_media"].fillna(
        df["temperatura_media"].median()
    )
    # Sin registro de lluvia -> se asume razonablemente que no llovio
    df["precipitacion"] = df["precipitacion"].fillna(0)
    log(f"Fase 2/7 - Nulos imputados: {nulos_antes} valores corregidos "
        "(mediana para temperatura, 0 para precipitacion).")
    return df


def fase_3_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    filas_antes = len(df)
    df = df.drop_duplicates(subset=["fecha"], keep="last")
    log(f"Fase 3/7 - Duplicados eliminados: {filas_antes - len(df)} filas removidas.")
    return df


def fase_4_outliers(df: pd.DataFrame) -> pd.DataFrame:
    filas_antes = len(df)
    # Filtros logicos: Fusagasuga rara vez baja de 0 grados o sube de 35
    df = df[(df["temperatura_media"] >= 0) & (df["temperatura_media"] <= 35)]
    df = df[(df["precipitacion"] >= 0) & (df["precipitacion"] <= 200)]
    log(f"Fase 4/7 - Outliers descartados (filtros logicos): "
        f"{filas_antes - len(df)} filas removidas.")
    return df


def fase_5_texto(df: pd.DataFrame) -> pd.DataFrame:
    df["fuente"] = df["fuente"].astype(str).str.strip().str.lower()
    log("Fase 5/7 - Texto normalizado (espacios y minusculas en columna 'fuente').")
    return df


def fase_6_tipos(df: pd.DataFrame) -> pd.DataFrame:
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["temperatura_media"] = df["temperatura_media"].astype(float)
    df["precipitacion"] = df["precipitacion"].astype(float)
    df = df.sort_values("fecha").reset_index(drop=True)
    log("Fase 6/7 - Tipos de dato convertidos (fecha->datetime, numericos->float).")
    return df


def fase_7_validacion_final(df: pd.DataFrame) -> pd.DataFrame:
    assert df[["temperatura_media", "precipitacion"]].isna().sum().sum() == 0, \
        "Quedaron nulos tras la limpieza"
    assert df["fecha"].is_monotonic_increasing, "Las fechas no quedaron ordenadas"
    log(f"Fase 7/7 - Validacion final OK: {df.shape[0]} filas limpias, sin nulos, "
        "orden cronologico correcto.")
    return df


def limpiar_dataset(df_crudo: pd.DataFrame) -> pd.DataFrame:
    df = df_crudo.copy()
    df = fase_1_audit(df)
    df = fase_2_nulos(df)
    df = fase_3_duplicados(df)
    df = fase_4_outliers(df)
    df = fase_5_texto(df)
    df = fase_6_tipos(df)
    df = fase_7_validacion_final(df)
    return df


# ---------------------------------------------------------------------------
# Entrenamiento del modelo (Random Forest)
# ---------------------------------------------------------------------------

def construir_features_estacionales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["mes"] = df["fecha"].dt.month
    df["dia_ano"] = df["fecha"].dt.dayofyear
    return df


def entrenar_modelos(df: pd.DataFrame):
    df_feat = construir_features_estacionales(df)
    X = df_feat[["mes", "dia_ano"]]
    y_temp = df_feat["temperatura_media"]
    y_precip = df_feat["precipitacion"]

    X_train, X_test, y_temp_train, y_temp_test = train_test_split(
        X, y_temp, test_size=0.2, random_state=42
    )
    _, _, y_precip_train, y_precip_test = train_test_split(
        X, y_precip, test_size=0.2, random_state=42
    )

    modelo_temp = RandomForestRegressor(n_estimators=N_ARBOLES, random_state=42, n_jobs=-1)
    modelo_precip = RandomForestRegressor(n_estimators=N_ARBOLES, random_state=42, n_jobs=-1)

    modelo_temp.fit(X_train, y_temp_train)
    modelo_precip.fit(X_train, y_precip_train)

    metricas = {
        "temperatura": {
            "mae": round(mean_absolute_error(y_temp_test, modelo_temp.predict(X_test)), 3),
            "r2": round(r2_score(y_temp_test, modelo_temp.predict(X_test)), 3),
        },
        "precipitacion": {
            "mae": round(mean_absolute_error(y_precip_test, modelo_precip.predict(X_test)), 3),
            "r2": round(r2_score(y_precip_test, modelo_precip.predict(X_test)), 3),
        },
    }
    log(f"Modelos entrenados ({N_ARBOLES} arboles). Metricas de validacion: {metricas}")
    return modelo_temp, modelo_precip, metricas


def predecir_proximos_dias(modelo_temp, modelo_precip, dias: int) -> pd.DataFrame:
    manana = datetime.now(timezone.utc).date() + timedelta(days=1)
    fechas_futuras = pd.date_range(start=manana, periods=dias, freq="D")

    df_futuro = pd.DataFrame({
        "fecha": fechas_futuras,
        "mes": fechas_futuras.month,
        "dia_ano": fechas_futuras.dayofyear,
    })

    df_futuro["temperatura_predicha"] = modelo_temp.predict(
        df_futuro[["mes", "dia_ano"]]
    )
    df_futuro["precipitacion_predicha"] = np.clip(
        modelo_precip.predict(df_futuro[["mes", "dia_ano"]]), 0, None
    )
    return df_futuro


# ---------------------------------------------------------------------------
# Sistema de recomendacion de cultivos (reglas de negocio)
# ---------------------------------------------------------------------------

def recomendar_cultivos(temperatura: float, precipitacion: float) -> list:
    """Sistema experto basado en las condiciones agroecologicas de Fusagasuga."""
    recomendaciones = []

    if 17 <= temperatura <= 23 and precipitacion > 3:
        recomendaciones.append("Cafe (variedad Castillo o Colombia)")

    if temperatura > 20:
        recomendaciones.append("Mandarina, mango o guanabana")

    if 14 <= temperatura <= 19:
        recomendaciones.append("Tomate de arbol, mora u hortalizas (lechuga, zanahoria)")

    if 15 <= temperatura <= 22:
        recomendaciones.append("Plantas ornamentales y flores (orquideas, anturios)")

    if not recomendaciones:
        recomendaciones.append(
            "Condiciones extremas: se sugiere revisar cultivos bajo invernadero "
            "o con sistema de riego controlado."
        )

    return recomendaciones


# ---------------------------------------------------------------------------
# Ensamblado del resultado
# ---------------------------------------------------------------------------

def construir_payload(df_historico: pd.DataFrame, df_prediccion: pd.DataFrame,
                       df_oficial: pd.DataFrame, metricas: dict) -> dict:
    historico_reciente = df_historico.tail(60)

    df_pred = df_prediccion.merge(df_oficial, on="fecha", how="left") \
        if not df_oficial.empty else df_prediccion.assign(
            temperatura_oficial=None, precipitacion_oficial=None
        )

    prediccion_lista = []
    for _, fila in df_pred.iterrows():
        cultivos = recomendar_cultivos(
            fila["temperatura_predicha"], fila["precipitacion_predicha"]
        )
        prediccion_lista.append({
            "fecha": fila["fecha"].strftime("%Y-%m-%d"),
            "temperatura_predicha": round(float(fila["temperatura_predicha"]), 1),
            "precipitacion_predicha": round(float(fila["precipitacion_predicha"]), 1),
            "temperatura_oficial": (
                round(float(fila["temperatura_oficial"]), 1)
                if pd.notna(fila.get("temperatura_oficial")) else None
            ),
            "precipitacion_oficial": (
                round(float(fila["precipitacion_oficial"]), 1)
                if pd.notna(fila.get("precipitacion_oficial")) else None
            ),
            "cultivos_sugeridos": cultivos,
        })

    historico_lista = [
        {
            "fecha": fila["fecha"].strftime("%Y-%m-%d"),
            "temperatura_media": round(float(fila["temperatura_media"]), 1),
            "precipitacion": round(float(fila["precipitacion"]), 1),
        }
        for _, fila in historico_reciente.iterrows()
    ]

    payload = {
        "meta": {
            "ubicacion": "Fusagasuga, Cundinamarca, Colombia",
            "latitud": LATITUD,
            "longitud": LONGITUD,
            "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fuente_datos": df_historico["fuente"].iloc[-1] if "fuente" in df_historico else "desconocida",
            "registros_historicos_usados": len(df_historico),
            "metricas_modelo": metricas,
        },
        "historico": historico_lista,
        "prediccion": prediccion_lista,
    }
    return payload


def generar_prediccion_completa() -> dict:
    """Corre el pipeline completo y devuelve el payload final (sin escribir a disco).

    Punto de entrada unico usado tanto por el script de linea de comandos
    como por la funcion serverless de Vercel.
    """
    df_crudo = obtener_datos_historicos()
    df_limpio = limpiar_dataset(df_crudo)

    modelo_temp, modelo_precip, metricas = entrenar_modelos(df_limpio)
    df_prediccion = predecir_proximos_dias(modelo_temp, modelo_precip, DIAS_PREDICCION)
    df_oficial = obtener_pronostico_oficial()

    return construir_payload(df_limpio, df_prediccion, df_oficial, metricas)
