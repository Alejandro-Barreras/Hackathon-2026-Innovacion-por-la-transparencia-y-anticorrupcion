from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Gasto público de Hermosillo",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    f"<style>{(Path(__file__).parent / 'styles.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

AZUL = "#0F4C81"
TINTA = "#1C2B39"
TINTA_2 = "#4A5A6A"
LINEA = "#CDD5DD"
FUENTE = '"Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif'

# --- Datos de ejemplo (millones de pesos). Reemplazar con la fuente oficial. ---
FECHA_CORTE = "31 de octubre de 2026"
APROBADO = 7850

por_dependencia = pd.DataFrame(
    {
        "Dependencia": [
            "Seguridad pública",
            "Servicios públicos (alumbrado, basura, parques)",
            "Obra pública",
            "Administración y finanzas",
            "Deuda y pagos financieros",
            "Desarrollo social",
            "Salud municipal",
            "Otras dependencias",
        ],
        "Gastado": [1420, 1265, 980, 712, 540, 455, 298, 242],
    }
)

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
programado_acum = [round(APROBADO * (i + 1) / 12) for i in range(12)]
ejercido_acum = [410, 930, 1475, 2040, 2610, 3190, 3770, 4400, 5150, 5912]

EJERCIDO = ejercido_acum[-1]
PROGRAMADO_A_LA_FECHA = programado_acum[len(ejercido_acum) - 1]


def millones(valor: float) -> str:
    return f"${valor:,.0f} millones"


def pct(parte: float, total: float) -> float:
    return parte / total * 100


def estilo_grafica(fig: go.Figure, alto: int) -> go.Figure:
    fig.update_layout(
        height=alto,
        margin=dict(l=0, r=24, t=8, b=8),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family=FUENTE, size=16, color=TINTA),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=LINEA, font=dict(family=FUENTE, size=15, color=TINTA)),
        dragmode=False,
    )
    return fig


CONFIG_GRAFICA = {"displayModeBar": False, "scrollZoom": False}

# --- Encabezado ---
st.markdown(
    """
<a class="saltar" href="#contenido">Saltar al contenido</a>
<header class="encabezado">
  <p class="institucion"><strong>Gasto público de Hermosillo</strong>H. Ayuntamiento de Hermosillo</p>
  <nav aria-label="Secciones de esta página">
    <ul>
      <li><a href="#por-dependencia">Por dependencia</a></li>
      <li><a href="#mes-a-mes">Mes a mes</a></li>
      <li><a href="#sobre-los-datos">Sobre los datos</a></li>
    </ul>
  </nav>
</header>
<div class="aviso" role="note">
  <p><strong>Datos de ejemplo.</strong> Este sitio está en desarrollo y las cifras todavía no provienen de fuentes oficiales.</p>
</div>
""",
    unsafe_allow_html=True,
)

# --- Resumen ---
p_ejercido = pct(EJERCIDO, APROBADO)
p_meta = pct(PROGRAMADO_A_LA_FECHA, APROBADO)

st.markdown(
    f"""
<section class="resumen" id="contenido" aria-labelledby="titulo">
  <h1 id="titulo">¿En qué se gasta el dinero público de Hermosillo?</h1>
  <p class="entrada">Consulta cuánto dinero aprobó el Ayuntamiento para este año, cuánto ha gastado y en qué.</p>
  <p class="cifra">Al {FECHA_CORTE}, el Ayuntamiento ha gastado <strong>{millones(EJERCIDO)}</strong>
  de los <strong>{millones(APROBADO)}</strong> aprobados para 2026. Es el {p_ejercido:.0f}&nbsp;% del presupuesto anual.</p>
  <div class="barra" role="img"
       aria-label="Gastado: {p_ejercido:.0f} % del presupuesto. Lo previsto a esta fecha era {p_meta:.0f} %.">
    <div class="ejercido" style="width:{p_ejercido:.1f}%"></div>
    <div class="meta" style="left:{p_meta:.1f}%"></div>
  </div>
  <ul class="barra-leyenda">
    <li><span class="muestra ejercido" aria-hidden="true"></span>Gastado: {millones(EJERCIDO)} ({p_ejercido:.0f}&nbsp;%)</li>
    <li><span class="muestra meta" aria-hidden="true"></span>Previsto a esta fecha: {millones(PROGRAMADO_A_LA_FECHA)} ({p_meta:.0f}&nbsp;%)</li>
    <li><span class="muestra pendiente" aria-hidden="true"></span>Por gastar: {millones(APROBADO - EJERCIDO)}</li>
  </ul>
</section>
""",
    unsafe_allow_html=True,
)

# --- Por dependencia ---
st.markdown(
    """
<section class="seccion" id="por-dependencia" aria-labelledby="titulo-dependencia">
  <h2 id="titulo-dependencia">¿Qué áreas del Ayuntamiento gastan más?</h2>
  <p>Dinero gastado por cada área en lo que va del año, de mayor a menor.</p>
</section>
""",
    unsafe_allow_html=True,
)

orden = por_dependencia.sort_values("Gastado")
fig_dep = go.Figure(
    go.Bar(
        x=orden["Gastado"],
        y=orden["Dependencia"],
        orientation="h",
        marker=dict(color=AZUL),
        text=[f"  {millones(v)}" for v in orden["Gastado"]],
        textposition="outside",
        textfont=dict(color=TINTA, size=15),
        cliponaxis=False,
        customdata=[pct(v, EJERCIDO) for v in orden["Gastado"]],
        hovertemplate="<b>%{y}</b><br>$%{x:,.0f} millones<br>%{customdata:.1f} % del total gastado<extra></extra>",
    )
)
# Nombre de cada área sobre su barra: así cabe en pantallas angostas.
for nombre in orden["Dependencia"]:
    fig_dep.add_annotation(
        x=0, y=nombre, text=nombre, showarrow=False, xanchor="left", yanchor="bottom",
        yshift=15, font=dict(size=16, color=TINTA),
    )
fig_dep.update_layout(bargap=0.55, barcornerradius=4, margin=dict(l=0, r=0, t=32, b=8))
fig_dep.update_xaxes(visible=False, range=[0, orden["Gastado"].max() * 1.5])
fig_dep.update_yaxes(visible=False)
st.plotly_chart(estilo_grafica(fig_dep, 640), config=CONFIG_GRAFICA, width="stretch")

with st.expander("Ver los datos en tabla"):
    tabla_dep = por_dependencia.assign(
        **{
            "Gastado": por_dependencia["Gastado"].map(millones),
            "Parte del total": por_dependencia["Gastado"].map(lambda v: f"{pct(v, EJERCIDO):.1f} %"),
        }
    ).set_index("Dependencia")
    st.table(tabla_dep)

# --- Mes a mes ---
st.markdown(
    """
<section class="seccion" id="mes-a-mes" aria-labelledby="titulo-mes">
  <h2 id="titulo-mes">¿El gasto va de acuerdo con lo previsto?</h2>
  <p>Dinero gastado acumulado cada mes, comparado con lo que se tenía previsto gastar.
  Si la línea azul queda por debajo de la gris, se ha gastado menos de lo previsto.</p>
</section>
""",
    unsafe_allow_html=True,
)

fig_mes = go.Figure()
fig_mes.add_trace(
    go.Scatter(
        x=MESES,
        y=programado_acum,
        name="Previsto",
        mode="lines",
        line=dict(color=TINTA_2, width=2, dash="dash"),
        hovertemplate="Previsto: $%{y:,.0f} millones<extra></extra>",
    )
)
fig_mes.add_trace(
    go.Scatter(
        x=MESES[: len(ejercido_acum)],
        y=ejercido_acum,
        name="Gastado",
        mode="lines+markers",
        line=dict(color=AZUL, width=2),
        marker=dict(size=8, color=AZUL, line=dict(color="#FFFFFF", width=2)),
        hovertemplate="Gastado: $%{y:,.0f} millones<extra></extra>",
    )
)
fig_mes.add_annotation(
    x=MESES[len(ejercido_acum) - 1], y=EJERCIDO, text=f"Gastado<br>{millones(EJERCIDO)}",
    showarrow=False, xanchor="left", xshift=12, yshift=-18, align="left", font=dict(color=TINTA, size=15),
)
fig_mes.add_annotation(
    x=MESES[-1], y=programado_acum[-1], text=f"Previsto<br>{millones(APROBADO)}",
    showarrow=False, xanchor="right", yanchor="bottom", yshift=8, align="right", font=dict(color=TINTA_2, size=15),
)
fig_mes.update_layout(
    hovermode="x unified",
    legend=dict(orientation="h", x=0, y=1.08, xanchor="left", font=dict(size=15)),
    margin=dict(l=0, r=24, t=48, b=8),
)
fig_mes.update_xaxes(showgrid=False, linecolor=LINEA, ticks="", tickangle=0, tickfont=dict(size=14, color=TINTA_2))
fig_mes.update_yaxes(
    gridcolor="#E6EAEE", zeroline=False, tickprefix="$", ticksuffix=" M", tickformat=",.0f",
    tickfont=dict(size=14, color=TINTA_2), rangemode="tozero",
)
st.plotly_chart(estilo_grafica(fig_mes, 480), config=CONFIG_GRAFICA, width="stretch")

with st.expander("Ver los datos en tabla"):
    tabla_mes = pd.DataFrame(
        {
            "Mes": MESES,
            "Previsto (acumulado)": [millones(v) for v in programado_acum],
            "Gastado (acumulado)": [millones(v) for v in ejercido_acum] + ["Sin datos"] * (12 - len(ejercido_acum)),
        }
    ).set_index("Mes")
    st.table(tabla_mes)

# --- Pie de página ---
st.markdown(
    f"""
<footer class="pie" id="sobre-los-datos">
  <div>
    <h2>Sobre los datos</h2>
    <p>Cifras en millones de pesos, actualizadas al {FECHA_CORTE}. Por ahora son datos de ejemplo.</p>
  </div>
  <div>
    <h2>¿Dudas o quieres reportar un error?</h2>
    <p>Comunícate con la Unidad de Transparencia del H. Ayuntamiento de Hermosillo.</p>
  </div>
</footer>
""",
    unsafe_allow_html=True,
)
