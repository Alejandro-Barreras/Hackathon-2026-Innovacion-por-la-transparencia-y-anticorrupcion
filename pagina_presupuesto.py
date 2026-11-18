"""Página de presupuesto: el tablero de gasto público, con los reportes trimestrales oficiales (vía la API)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos_api as api

AZUL = "#0F4C81"
TINTA = "#1C2B39"
TINTA_2 = "#4A5A6A"
LINEA = "#CDD5DD"
FUENTE = '"Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif'
CONFIG_GRAFICA = {"displayModeBar": False, "scrollZoom": False}

DEPENDENCIA = "CLADM_DEPENDENCIA_DESC"
GASTADO = "devengado_"  # "Gastado" = lo devengado (el gasto ya reconocido), no solo lo pagado
TOP_DEPENDENCIAS = 7  # las demás se juntan en "Otras dependencias"

# True: cada reporte trimestral trae el acumulado del año hasta ese trimestre (lo usual en CONAC),
#       así que para el año se toma el último trimestre reportado.
# False: cada reporte trae solo lo de su trimestre, así que se suman los trimestres del año.
ACUMULADO = True

TRIMESTRES = ["Ene–Mar", "Abr–Jun", "Jul–Sep", "Oct–Dic"]
MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]


def millones(valor: float) -> str:
    return f"${valor / 1e6:,.1f} millones"


def pct(parte: float, total: float) -> float:
    return parte / total * 100 if total else 0.0


def fecha_larga(iso: str) -> str:
    """'2026-03-31' -> '31 de marzo de 2026'."""
    f = pd.Timestamp(iso)
    return f"{f.day} de {MESES_LARGO[f.month - 1]} de {f.year}"


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


def gasto_por_dependencia(vigente: pd.DataFrame) -> pd.DataFrame:
    """Gastado por dependencia, de mayor a menor (solo las que han gastado algo)."""
    tabla = vigente.groupby(DEPENDENCIA)[GASTADO].sum().sort_values(ascending=False)
    return tabla[tabla > 0].rename("Gastado").rename_axis("Dependencia").reset_index()


def mostrar() -> None:
    try:
        completo = api.presupuesto()
    except api.ApiError as e:
        api.aviso_error(e)
        return

    ejercicios = sorted(completo["ejercicio"].unique(), reverse=True)
    ejercicio = st.selectbox("Ejercicio", ejercicios, key="presupuesto_ejercicio")

    anio = completo[completo["ejercicio"] == ejercicio]
    ultimo = int(anio["trimestre"].max())  # último trimestre con datos
    fecha_corte = anio.loc[anio["trimestre"] == ultimo, "fecha_fin"].iloc[0]
    corte = fecha_larga(fecha_corte)
    vigente = anio[anio["trimestre"] == ultimo] if ACUMULADO else anio

    # --- Cifras del año ---
    aprobado = vigente["aprobado_"].sum()
    ejercido = vigente[GASTADO].sum()
    if aprobado <= 0:
        api.aviso(f"<strong>Sin presupuesto aprobado.</strong> Los reportes de {ejercicio} no traen monto aprobado.")
        return
    previsto = aprobado * ultimo / 4  # lo que se llevaría gastado si el gasto fuera parejo
    p_ejercido = pct(ejercido, aprobado)
    p_meta = pct(previsto, aprobado)
    ancho_ejercido = min(p_ejercido, 100)

    st.markdown(
        f"""
<section class="resumen" id="contenido" aria-labelledby="titulo">
  <h1 id="titulo">¿En qué se gasta el dinero público de Hermosillo?</h1>
  <p class="entrada">Consulta cuánto dinero aprobó el Ayuntamiento para este año, cuánto ha gastado y en qué.</p>
  <p class="cifra">Al {corte}, el Ayuntamiento ha gastado <strong>{millones(ejercido)}</strong>
  de los <strong>{millones(aprobado)}</strong> aprobados para {ejercicio}. Es el {p_ejercido:.0f}&nbsp;% del presupuesto anual.</p>
  <div class="barra" role="img"
       aria-label="Gastado: {p_ejercido:.0f} % del presupuesto. Lo previsto a esta fecha era {p_meta:.0f} %.">
    <div class="ejercido" style="width:{ancho_ejercido:.1f}%"></div>
    <div class="meta" style="left:{p_meta:.1f}%"></div>
  </div>
  <ul class="barra-leyenda">
    <li><span class="muestra ejercido" aria-hidden="true"></span>Gastado: {millones(ejercido)} ({p_ejercido:.0f}&nbsp;%)</li>
    <li><span class="muestra meta" aria-hidden="true"></span>Previsto a esta fecha: {millones(previsto)} ({p_meta:.0f}&nbsp;%)</li>
    <li><span class="muestra pendiente" aria-hidden="true"></span>Por gastar: {millones(max(aprobado - ejercido, 0))}</li>
  </ul>
</section>
""",
        unsafe_allow_html=True,
    )

    # --- Por dependencia ---
    api.seccion(
        "por-dependencia",
        "¿Qué áreas del Ayuntamiento gastan más?",
        "Dinero gastado por cada área en lo que va del año, de mayor a menor.",
    )

    todas = gasto_por_dependencia(vigente)
    if todas.empty:
        api.aviso("Todavía no hay gasto registrado en este periodo.")
    else:
        grafica = todas.head(TOP_DEPENDENCIAS)
        resto = todas["Gastado"].iloc[TOP_DEPENDENCIAS:].sum()
        if resto > 0:
            grafica = pd.concat(
                [grafica, pd.DataFrame([{"Dependencia": "Otras dependencias", "Gastado": resto}])],
                ignore_index=True,
            )
        orden = grafica.sort_values("Gastado")
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
                customdata=[pct(v, ejercido) for v in orden["Gastado"]],
                hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<br>%{customdata:.1f} % del total gastado<extra></extra>",
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
        st.plotly_chart(
            estilo_grafica(fig_dep, 70 * len(orden) + 60),
            config=CONFIG_GRAFICA, width="stretch", key="presupuesto_dependencias",
        )

        with st.expander("Ver los datos en tabla"):
            tabla_dep = todas.assign(
                **{
                    "Gastado": todas["Gastado"].map(millones),
                    "Parte del total": todas["Gastado"].map(lambda v: f"{pct(v, ejercido):.1f} %"),
                }
            ).set_index("Dependencia")
            st.table(tabla_dep)

    # --- Trimestre a trimestre ---
    api.seccion(
        "trimestre-a-trimestre",
        "¿El gasto va de acuerdo con lo previsto?",
        "Dinero gastado acumulado al cierre de cada trimestre, comparado con lo que se tenía previsto gastar. "
        "Si la línea azul queda por debajo de la gris, se ha gastado menos de lo previsto.",
    )

    por_trimestre = anio.groupby("trimestre")[GASTADO].sum().sort_index()
    gastado_acum = por_trimestre if ACUMULADO else por_trimestre.cumsum()
    previsto_acum = [aprobado * (i + 1) / 4 for i in range(4)]
    reportados = [TRIMESTRES[int(t) - 1] for t in gastado_acum.index]

    fig_trim = go.Figure()
    fig_trim.add_trace(
        go.Scatter(
            x=TRIMESTRES,
            y=previsto_acum,
            name="Previsto",
            mode="lines",
            line=dict(color=TINTA_2, width=2, dash="dash"),
            hovertemplate="Previsto: $%{y:,.2f}<extra></extra>",
        )
    )
    fig_trim.add_trace(
        go.Scatter(
            x=reportados,
            y=gastado_acum.values,
            name="Gastado",
            mode="lines+markers",
            line=dict(color=AZUL, width=2),
            marker=dict(size=8, color=AZUL, line=dict(color="#FFFFFF", width=2)),
            hovertemplate="Gastado: $%{y:,.2f}<extra></extra>",
        )
    )
    fig_trim.add_annotation(
        x=reportados[-1], y=gastado_acum.iloc[-1], text=f"Gastado<br>{millones(gastado_acum.iloc[-1])}",
        showarrow=False, xanchor="left", xshift=12, yshift=-18, align="left", font=dict(color=TINTA, size=15),
    )
    fig_trim.add_annotation(
        x=TRIMESTRES[-1], y=previsto_acum[-1], text=f"Previsto<br>{millones(aprobado)}",
        showarrow=False, xanchor="right", yanchor="bottom", yshift=8, align="right", font=dict(color=TINTA_2, size=15),
    )
    fig_trim.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.08, xanchor="left", font=dict(size=15)),
        margin=dict(l=0, r=24, t=48, b=8),
    )
    fig_trim.update_xaxes(showgrid=False, linecolor=LINEA, ticks="", tickangle=0, tickfont=dict(size=14, color=TINTA_2))
    fig_trim.update_yaxes(
        gridcolor="#E6EAEE", zeroline=False, tickprefix="$", tickformat="~s",
        tickfont=dict(size=14, color=TINTA_2), rangemode="tozero",
    )
    st.plotly_chart(
        estilo_grafica(fig_trim, 480), config=CONFIG_GRAFICA, width="stretch", key="presupuesto_trimestres"
    )

    with st.expander("Ver los datos en tabla"):
        gastado_por_nombre = dict(zip(reportados, gastado_acum.values))
        tabla_trim = pd.DataFrame(
            {
                "Trimestre": TRIMESTRES,
                "Previsto (acumulado)": [millones(v) for v in previsto_acum],
                "Gastado (acumulado)": [
                    millones(gastado_por_nombre[t]) if t in gastado_por_nombre else "Sin datos" for t in TRIMESTRES
                ],
            }
        ).set_index("Trimestre")
        st.table(tabla_trim)

    # --- Pie de página ---
    st.markdown(
        f"""
<footer class="pie" id="sobre-los-datos">
  <div>
    <h2>Sobre los datos</h2>
    <p>Cifras en millones de pesos, al {corte}, tomadas de los reportes trimestrales de presupuesto del
    H. Ayuntamiento de Hermosillo. «Gastado» es el monto devengado.</p>
  </div>
  <div>
    <h2>¿Dudas o quieres reportar un error?</h2>
    <p>Comunícate con la Unidad de Transparencia del H. Ayuntamiento de Hermosillo.</p>
  </div>
</footer>
""",
        unsafe_allow_html=True,
    )