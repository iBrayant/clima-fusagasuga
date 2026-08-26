/* ------------------------------------------------------------------
   Clima Fusagasugá — lee predicciones.json y dibuja el dashboard.
   Sin backend: todo el calculo ya vino resuelto en el JSON.
   ------------------------------------------------------------------ */

const RUTA_JSON = "motor/predicciones.json";

let datos = null;
let variableActual = "temperatura";

const el = (id) => document.getElementById(id);

async function cargarDatos() {
  try {
    const respuesta = await fetch(RUTA_JSON, { cache: "no-store" });
    if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
    datos = await respuesta.json();
    render();
  } catch (error) {
    mostrarError(error);
  }
}

function mostrarError(error) {
  console.error("No se pudo cargar predicciones.json:", error);
  el("subtitulo-actualizacion").textContent =
    "No se pudieron cargar los datos. Verifica que motor/predicciones.json exista.";
  el("lista-cultivos").innerHTML =
    '<li class="cultivo-placeholder">Sin datos disponibles.</li>';
}

function formatearFecha(fechaISO) {
  const fecha = new Date(fechaISO + "T00:00:00");
  return fecha.toLocaleDateString("es-CO", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function render() {
  const { meta, prediccion } = datos;
  const primerDia = prediccion[0];

  el("subtitulo-actualizacion").textContent =
    `Predicción para ${formatearFecha(primerDia.fecha)} · actualizado ${formatearGeneracion(meta.generado_en)}`;

  el("kpi-temperatura").textContent = `${primerDia.temperatura_predicha.toFixed(1)}°`;
  el("kpi-precipitacion").textContent = `${primerDia.precipitacion_predicha.toFixed(1)} mm`;

  el("kpi-temperatura-oficial").textContent =
    primerDia.temperatura_oficial != null
      ? `Pronóstico oficial: ${primerDia.temperatura_oficial.toFixed(1)}°`
      : "";
  el("kpi-precipitacion-oficial").textContent =
    primerDia.precipitacion_oficial != null
      ? `Pronóstico oficial: ${primerDia.precipitacion_oficial.toFixed(1)} mm`
      : "";

  renderCultivos(primerDia.cultivos_sugeridos);
  renderInfoModelo(meta);
  dibujarGrafico();

  window.addEventListener("resize", debounce(dibujarGrafico, 150));
}

function formatearGeneracion(iso) {
  const fecha = new Date(iso);
  return fecha.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function renderCultivos(lista) {
  const contenedor = el("lista-cultivos");
  contenedor.innerHTML = "";

  lista.forEach((texto) => {
    const li = document.createElement("li");
    li.textContent = texto;
    if (texto.toLowerCase().startsWith("condiciones extremas")) {
      li.classList.add("cultivo-alerta");
    }
    contenedor.appendChild(li);
  });
}

function renderInfoModelo(meta) {
  el("dato-fuente").textContent =
    meta.fuente_datos === "open-meteo" ? "Open-Meteo (API real)" : "Simulado (respaldo)";
  el("dato-registros").textContent = meta.registros_historicos_usados.toLocaleString("es-CO");
  el("dato-mae").textContent = `± ${meta.metricas_modelo.temperatura.mae.toFixed(2)} °C`;
}

/* -------------------------- Gráfico en canvas -------------------------- */

function dibujarGrafico() {
  const canvas = el("grafico");
  const envoltura = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;

  const ancho = envoltura.clientWidth;
  const alto = envoltura.clientHeight;

  canvas.width = ancho * dpr;
  canvas.height = alto * dpr;
  canvas.style.width = ancho + "px";
  canvas.style.height = alto + "px";

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, ancho, alto);

  const estiloOscuro = esTemaOscuro();
  const colorTexto = estiloOscuro ? "rgba(255,255,255,0.5)" : "rgba(60,60,67,0.5)";
  const colorGrilla = estiloOscuro ? "rgba(255,255,255,0.08)" : "rgba(60,60,67,0.08)";
  const colorHistorico = "#0a84ff";
  const colorPrediccion = "#ff9f0a";

  const campo = variableActual === "temperatura" ? "temperatura_media" : "precipitacion";
  const campoPred = variableActual === "temperatura" ? "temperatura_predicha" : "precipitacion_predicha";

  const historico = datos.historico;
  const prediccion = datos.prediccion;

  const valoresHist = historico.map((d) => d[campo]);
  const valoresPred = prediccion.map((d) => d[campoPred]);
  const todosValores = valoresHist.concat(valoresPred);

  const minValor = Math.min(...todosValores);
  const maxValor = Math.max(...todosValores);
  const margenValor = (maxValor - minValor) * 0.15 || 1;
  const escalaMin = minValor - margenValor;
  const escalaMax = maxValor + margenValor;

  const margen = { arriba: 14, abajo: 24, izq: 8, der: 8 };
  const anchoUtil = ancho - margen.izq - margen.der;
  const altoUtil = alto - margen.arriba - margen.abajo;

  const totalPuntos = historico.length + prediccion.length;
  const x = (i) => margen.izq + (i / (totalPuntos - 1)) * anchoUtil;
  const y = (valor) =>
    margen.arriba + altoUtil - ((valor - escalaMin) / (escalaMax - escalaMin)) * altoUtil;

  // Lineas guia horizontales
  ctx.strokeStyle = colorGrilla;
  ctx.lineWidth = 1;
  const franjas = 3;
  for (let i = 0; i <= franjas; i++) {
    const yPos = margen.arriba + (altoUtil / franjas) * i;
    ctx.beginPath();
    ctx.moveTo(margen.izq, yPos);
    ctx.lineTo(ancho - margen.der, yPos);
    ctx.stroke();
  }

  // --- Curva de historico (suavizada) ---
  dibujarCurva(
    ctx,
    historico.map((_, i) => x(i)),
    valoresHist.map(y),
    colorHistorico,
    2.5,
    false
  );

  // --- Curva de prediccion (punteada), empieza donde termina el historico ---
  const offset = historico.length - 1;
  const xsPred = [x(offset), ...prediccion.map((_, i) => x(offset + 1 + i))];
  const ysPred = [y(valoresHist[valoresHist.length - 1]), ...valoresPred.map(y)];
  dibujarCurva(ctx, xsPred, ysPred, colorPrediccion, 2.5, true);

  // Punto final destacado (prediccion de manana)
  const xFinal = xsPred[1];
  const yFinal = ysPred[1];
  ctx.beginPath();
  ctx.arc(xFinal, yFinal, 4, 0, Math.PI * 2);
  ctx.fillStyle = colorPrediccion;
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = estiloOscuro ? "#0b0b0d" : "#eef1f6";
  ctx.stroke();

  // Etiquetas de eje X: inicio del historico, hoy (si hay espacio), fin de prediccion
  ctx.fillStyle = colorTexto;
  ctx.font = "11px -apple-system, sans-serif";
  ctx.textBaseline = "top";
  const yEtiquetas = alto - margen.abajo + 8;

  ctx.textAlign = "left";
  ctx.fillText(formatearEtiquetaCorta(historico[0].fecha), margen.izq, yEtiquetas);

  ctx.textAlign = "right";
  const etiquetaFinal = formatearEtiquetaCorta(prediccion[prediccion.length - 1].fecha);
  ctx.fillText(etiquetaFinal, ancho - margen.der, yEtiquetas);

  const anchoHoy = ctx.measureText("hoy").width;
  const anchoFinal = ctx.measureText(etiquetaFinal).width;
  const xHoy = x(offset);
  const cabeEspacioHoy = xHoy + anchoHoy / 2 < ancho - margen.der - anchoFinal - 14;

  if (cabeEspacioHoy) {
    ctx.textAlign = "center";
    ctx.fillText("hoy", xHoy, yEtiquetas);
  }
}

function formatearEtiquetaCorta(fechaISO) {
  const fecha = new Date(fechaISO + "T00:00:00");
  return fecha.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function dibujarCurva(ctx, xs, ys, color, grosor, punteada) {
  if (xs.length < 2) return;

  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = grosor;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  if (punteada) ctx.setLineDash([1, 7]);

  ctx.beginPath();
  ctx.moveTo(xs[0], ys[0]);

  for (let i = 0; i < xs.length - 1; i++) {
    const xMedio = (xs[i] + xs[i + 1]) / 2;
    const yMedio = (ys[i] + ys[i + 1]) / 2;
    ctx.quadraticCurveTo(xs[i], ys[i], xMedio, yMedio);
  }
  ctx.quadraticCurveTo(
    xs[xs.length - 2],
    ys[xs.length - 2],
    xs[xs.length - 1],
    ys[xs.length - 1]
  );

  ctx.stroke();
  ctx.restore();
}

function debounce(fn, ms) {
  let temporizador;
  return (...args) => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => fn(...args), ms);
  };
}

/* -------------------------- Interacciones -------------------------- */

document.querySelectorAll(".segmento").forEach((boton) => {
  boton.addEventListener("click", () => {
    document.querySelectorAll(".segmento").forEach((b) => {
      b.classList.remove("activo");
      b.setAttribute("aria-selected", "false");
    });
    boton.classList.add("activo");
    boton.setAttribute("aria-selected", "true");
    variableActual = boton.dataset.variable;
    dibujarGrafico();
  });
});

/* -------------------------- Tema claro / oscuro -------------------------- */

function esTemaOscuro() {
  const forzado = document.documentElement.getAttribute("data-theme");
  if (forzado === "dark") return true;
  if (forzado === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function aplicarTema(tema) {
  if (tema) {
    document.documentElement.setAttribute("data-theme", tema);
    localStorage.setItem("tema", tema);
  } else {
    document.documentElement.removeAttribute("data-theme");
    localStorage.removeItem("tema");
  }
  if (datos) dibujarGrafico();
}

const botonTema = el("boton-tema");
if (botonTema) {
  botonTema.addEventListener("click", () => {
    aplicarTema(esTemaOscuro() ? "light" : "dark");
  });
}

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!localStorage.getItem("tema") && datos) dibujarGrafico();
});

cargarDatos();
