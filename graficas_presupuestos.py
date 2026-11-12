"""Gráficas configurables para los datos de gasto público (formato CONAC / "excel-completo-entidad").

Uso en app.py:

    import graficas_presupuestos as g

    df = g.cargar_datos("datos/excel-completo-entidad-1-2026-TRIMESTRE I.csv")
    g.mostrar(g.grafica_barras(df, dimension="CLADM_DEPENDENCIA_DESC", monto="devengado_"))
    g.mostrar(g.grafica_momentos(df, dimension="CLOBJ_capitulo_DESC"))
    g.mostrar(g.grafica_avance(df, dimension="CLADM_DEPENDENCIA_DESC"))
    g.mostrar(g.grafica_jerarquia(df))
    g.explorador(df)  # controles para que la persona elija qué ver

Todas las funciones reciben nombres de columna, así que funcionan con cualquier
archivo que tenga columnas de texto (dimensiones) y columnas numéricas (montos).
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --- Estilo (mismo que app.py) ---
AZUL = "#0F4C81"
TINTA = "#1C2B39"
TINTA_2 = "#4A5A6A"
LINEA = "#CDD5DD"
REJILLA = "#E6EAEE"
FUENTE = '"Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif'
CONFIG_GRAFICA = {"displayModeBar": False, "scrollZoom": False}

# --- Esquema del archivo de ejemplo. Ajustar aquí si cambian los nombres de columna. ---
MONTOS = {
    "aprobado_": "Aprobado",
    "modificado_": "Modificado",
    "comprometido_": "Comprometido",
    "devengado_": "Devengado",
    "pagado_": "Pagado",
}

DIMENSIONES = {
    "CLADM_DEPENDENCIA_DESC": "Dependencia",
    "CLADM_UNIDAD_ADMINISTRATIVA_DESC": "Unidad administrativa",
    "CLOBJ_capitulo_DESC": "Capítulo de gasto",
    "CLOBJ_concepto_DESC": "Concepto de gasto",
    "CLOBJ_partida_generica_DESC": "Partida genérica",
    "CLFUN_gpo_funcional_DESC": "Grupo funcional",
    "CLFUN_funcion_DESC": "Función",
    "CLTIG_tipo_de_gasto_DESC": "Tipo de gasto",
}

# Los momentos del gasto son etapas en orden, así que usan un solo tono de claro a oscuro.
COLORES_MOMENTO = {
    "aprobado_": "#C3D7EC",
    "modificado_": "#8DB4DC",
    "comprometido_": "#5B93CC",
    "devengado_": "#2E6DAA",
    "pagado_": AZUL,
}


# --- Datos ---
def cargar_datos(fuente: str | Path | io.IOBase, montos: Sequence[str] | None = None) -> pd.DataFrame:
    """Lee un CSV (ruta o archivo subido con st.file_uploader).

    Prueba UTF-8 y luego Windows-1252 (el archivo de ejemplo viene en ese formato),
    descarta filas vacías, quita espacios sobrantes y convierte los montos a número.
    Las claves (p. ej. "09") se conservan como texto.
    """
    crudo = fuente.read() if hasattr(fuente, "read") else Path(fuente).read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            df = pd.read_csv(io.BytesIO(crudo), dtype=str, encoding=codificacion)
            break
        except UnicodeDecodeError:
            continue

    df = df.dropna(how="all")
    df = df.apply(lambda col: col.str.strip())
    for col in montos or [c for c in MONTOS if c in df.columns]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df.reset_index(drop=True)


def etiqueta(columna: str) -> str:
    """Nombre legible de una columna."""
    return MONTOS.get(columna) or DIMENSIONES.get(columna) or columna


def pesos(valor: float) -> str:
    """$1,234 · $12.3 mil · $4.5 M. Se ajusta solo a la magnitud del valor."""
    absoluto = abs(valor)
    if absoluto >= 1e9:
        return f"${valor / 1e9:,.1f} mil M"
    if absoluto >= 1e6:
        return f"${valor / 1e6:,.1f} M"
    if absoluto >= 1e4:
        return f"${valor / 1e3:,.1f} mil"
    return f"${valor:,.0f}"


def resumir(
    df: pd.DataFrame,
    dimension: str,
    montos: Sequence[str],
    top_n: int | None = None,
    ordenar_por: str | None = None,
    nombre_resto: str = "Otros",
) -> pd.DataFrame:
    """Suma los montos por dimensión, de mayor a menor. Lo que pase de top_n se junta en "Otros"."""
    ordenar_por = ordenar_por or montos[0]
    tabla = (
        df.groupby(dimension, dropna=False)[list(montos)]
        .sum()
        .sort_values(ordenar_por, ascending=False)
        .reset_index()
    )
    tabla[dimension] = tabla[dimension].fillna("Sin clasificar")
    if top_n and len(tabla) > top_n:
        resto = tabla.iloc[top_n - 1 :][list(montos)].sum()
        tabla = pd.concat(
            [tabla.iloc[: top_n - 1], pd.DataFrame([{dimension: nombre_resto, **resto}])],
            ignore_index=True,
        )
    return tabla


def tabla(df: pd.DataFrame, dimension: str, montos: Sequence[str] | None = None) -> pd.DataFrame:
    """Tabla con montos ya formateados, lista para st.table dentro de un expander."""
    montos = list(montos or [c for c in MONTOS if c in df.columns])
    resumen = resumir(df, dimension, montos)
    resumen[montos] = resumen[montos].map(pesos)
    return resumen.rename(columns=etiqueta).set_index(etiqueta(dimension))


# --- Estilo común ---
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


def mostrar(fig: go.Figure, key: str | None = None) -> None:
    """Muestra la gráfica. Pasa `key` si la misma gráfica aparece más de una vez en la página."""
    st.plotly_chart(fig, config=CONFIG_GRAFICA, width="stretch", key=key)


def _nombres_sobre_barras(fig: go.Figure, nombres: Sequence[str]) -> None:
    # El nombre va arriba de la barra, no al costado: así cabe en pantallas angostas.
    for nombre in nombres:
        fig.add_annotation(
            x=0, y=nombre, text=nombre, showarrow=False, xanchor="left", yanchor="bottom",
            yshift=15, font=dict(size=16, color=TINTA),
        )


# --- Gráficas ---
def grafica_barras(
    df: pd.DataFrame,
    dimension: str,
    monto: str = "devengado_",
    top_n: int | None = 10,
    color: str = AZUL,
) -> go.Figure:
    """Barras horizontales: cuánto suma `monto` en cada categoría de `dimension`."""
    datos = resumir(df, dimension, [monto], top_n).iloc[::-1]
    total = datos[monto].sum() or 1

    fig = go.Figure(
        go.Bar(
            x=datos[monto],
            y=datos[dimension],
            orientation="h",
            marker=dict(color=color),
            text=[f"  {pesos(v)}" for v in datos[monto]],
            textposition="outside",
            textfont=dict(color=TINTA, size=15),
            cliponaxis=False,
            customdata=datos[monto] / total * 100,
            hovertemplate=f"<b>%{{y}}</b><br>{etiqueta(monto)}: $%{{x:,.2f}}"
            "<br>%{customdata:.1f} % del total<extra></extra>",
        )
    )
    _nombres_sobre_barras(fig, datos[dimension])
    fig.update_layout(bargap=0.55, barcornerradius=4, margin=dict(l=0, r=0, t=32, b=8))
    fig.update_xaxes(visible=False, range=[0, max(datos[monto].max(), 1) * 1.5])
    fig.update_yaxes(visible=False)
    return estilo_grafica(fig, 70 * len(datos) + 60)


def grafica_momentos(
    df: pd.DataFrame,
    dimension: str | None = None,
    momentos: Sequence[str] = ("aprobado_", "modificado_", "devengado_", "pagado_"),
    top_n: int | None = 8,
) -> go.Figure:
    """Compara los momentos del gasto (aprobado → pagado).

    Sin `dimension`: una barra por momento con el total.
    Con `dimension`: barras agrupadas por categoría.
    """
    momentos = list(momentos)

    if dimension is None:
        totales = df[momentos].sum()
        fig = go.Figure(
            go.Bar(
                x=[etiqueta(m) for m in momentos],
                y=totales.values,
                marker=dict(color=[COLORES_MOMENTO.get(m, AZUL) for m in momentos]),
                text=[pesos(v) for v in totales.values],
                textposition="outside",
                textfont=dict(color=TINTA, size=15),
                cliponaxis=False,
                hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(bargap=0.45, barcornerradius=4, margin=dict(l=0, r=0, t=32, b=8))
        fig.update_xaxes(showgrid=False, linecolor=LINEA, tickfont=dict(size=15, color=TINTA))
        fig.update_yaxes(visible=False, range=[0, max(totales.max(), 1) * 1.2])
        return estilo_grafica(fig, 420)

    datos = resumir(df, dimension, momentos, top_n).iloc[::-1]
    fig = go.Figure()
    for m in momentos:
        fig.add_trace(
            go.Bar(
                x=datos[m],
                y=datos[dimension],
                name=etiqueta(m),
                orientation="h",
                marker=dict(color=COLORES_MOMENTO.get(m, AZUL), line=dict(color="#FFFFFF", width=1)),
                hovertemplate=f"<b>%{{y}}</b><br>{etiqueta(m)}: $%{{x:,.2f}}<extra></extra>",
            )
        )
    _nombres_sobre_barras(fig, datos[dimension])
    fig.update_layout(
        barmode="group",
        bargap=0.45,
        bargroupgap=0.1,
        barcornerradius=3,
        # La leyenda sigue el orden de los momentos (de arriba hacia abajo en cada grupo).
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", traceorder="reversed", font=dict(size=15)),
        margin=dict(l=0, r=0, t=48, b=8),
    )
    fig.update_xaxes(
        gridcolor=REJILLA, zeroline=False, tickprefix="$", tickformat="~s",
        tickfont=dict(size=14, color=TINTA_2),
    )
    fig.update_yaxes(visible=False)
    return estilo_grafica(fig, (40 + 18 * len(momentos)) * len(datos) + 100)


def grafica_avance(
    df: pd.DataFrame,
    dimension: str,
    numerador: str = "devengado_",
    denominador: str = "modificado_",
    top_n: int | None = 10,
) -> go.Figure:
    """Porcentaje de avance por categoría (p. ej. devengado ÷ modificado), con línea de referencia al 100 %."""
    datos = resumir(df, dimension, [denominador, numerador], top_n)
    datos = datos[datos[denominador] > 0].copy()
    datos["avance"] = datos[numerador] / datos[denominador] * 100
    datos = datos.sort_values("avance")

    fig = go.Figure(
        go.Bar(
            x=datos["avance"],
            y=datos[dimension],
            orientation="h",
            marker=dict(color=AZUL),
            text=[f"  {v:.0f} %" for v in datos["avance"]],
            textposition="outside",
            textfont=dict(color=TINTA, size=15),
            cliponaxis=False,
            customdata=datos[[numerador, denominador]].map(pesos).values,
            hovertemplate=f"<b>%{{y}}</b><br>%{{x:.1f}} %<br>{etiqueta(numerador)}: %{{customdata[0]}}"
            f"<br>{etiqueta(denominador)}: %{{customdata[1]}}<extra></extra>",
        )
    )
    _nombres_sobre_barras(fig, datos[dimension])
    fig.add_vline(x=100, line=dict(color=TINTA_2, width=1, dash="dash"))
    fig.update_layout(bargap=0.55, barcornerradius=4, margin=dict(l=0, r=0, t=32, b=8))
    fig.update_xaxes(visible=False, range=[0, max(datos["avance"].max(), 100) * 1.25])
    fig.update_yaxes(visible=False)
    return estilo_grafica(fig, 70 * len(datos) + 60)


def grafica_jerarquia(
    df: pd.DataFrame,
    niveles: Sequence[str] = ("CLOBJ_capitulo_DESC", "CLOBJ_concepto_DESC", "CLOBJ_partida_generica_DESC"),
    monto: str = "devengado_",
) -> go.Figure:
    """Treemap: cómo se reparte `monto` a través de varios niveles (capítulo → concepto → partida, etc.)."""
    datos = df[df[monto] > 0].copy()
    datos[list(niveles)] = datos[list(niveles)].fillna("Sin clasificar")

    fig = px.treemap(
        datos,
        path=[px.Constant("Total"), *niveles],
        values=monto,
        color=monto,
        color_continuous_scale=["#C3D7EC", AZUL],
    )
    fig.update_traces(
        marker=dict(line=dict(color="#FFFFFF", width=2), cornerradius=4),
        texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}",
        hovertemplate=f"<b>%{{label}}</b><br>{etiqueta(monto)}: $%{{value:,.2f}}"
        "<br>%{percentRoot:.1%} del total<extra></extra>",
        root_color="#FFFFFF",
    )
    fig.update_layout(coloraxis_showscale=False, margin=dict(l=0, r=0, t=8, b=8))
    return estilo_grafica(fig, 560)


def grafica_periodos(
    df: pd.DataFrame,
    montos: Sequence[str] = ("modificado_", "devengado_"),
    columna_periodo: str = "periodo",
    columna_ejercicio: str | None = "ejercicio",
) -> go.Figure:
    """Línea por periodo. Útil cuando se juntan varios archivos trimestrales en un solo DataFrame.

    Los periodos aparecen en el orden en que vienen en los datos (dentro de cada ejercicio).
    """
    claves = [c for c in (columna_ejercicio, columna_periodo) if c and c in df.columns]
    datos = df.groupby(claves, sort=False)[list(montos)].sum().reset_index()
    if columna_ejercicio in datos.columns:
        datos = datos.sort_values(columna_ejercicio, kind="stable")
        eje_x = datos[columna_periodo].str.title() + " " + datos[columna_ejercicio].astype(str)
    else:
        eje_x = datos[columna_periodo]

    fig = go.Figure()
    for m in montos:
        fig.add_trace(
            go.Scatter(
                x=eje_x,
                y=datos[m],
                name=etiqueta(m),
                mode="lines+markers",
                line=dict(color=COLORES_MOMENTO.get(m, AZUL), width=2),
                marker=dict(size=8, color=COLORES_MOMENTO.get(m, AZUL), line=dict(color="#FFFFFF", width=2)),
                hovertemplate=f"{etiqueta(m)}: $%{{y:,.2f}}<extra></extra>",
            )
        )
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.08, xanchor="left", font=dict(size=15)),
        margin=dict(l=0, r=24, t=48, b=8),
    )
    fig.update_xaxes(showgrid=False, linecolor=LINEA, ticks="", tickfont=dict(size=14, color=TINTA_2))
    fig.update_yaxes(
        gridcolor=REJILLA, zeroline=False, tickprefix="$", tickformat="~s",
        tickfont=dict(size=14, color=TINTA_2), rangemode="tozero",
    )
    return estilo_grafica(fig, 440)


# --- Explorador con controles ---
def explorador(df: pd.DataFrame, key: str = "explorador") -> None:
    """Controles en una fila + gráfica + tabla. La persona elige qué ver."""
    dimensiones = [c for c in DIMENSIONES if c in df.columns]
    montos = [c for c in MONTOS if c in df.columns]
    tipos = {
        "Montos por categoría": "barras",
        "Comparar momentos del gasto": "momentos",
        "Avance (%)": "avance",
        "Desglose jerárquico": "jerarquia",
    }

    c1, c2, c3, c4 = st.columns(4)
    tipo = tipos[c1.selectbox("Tipo de gráfica", list(tipos), key=f"{key}_tipo")]
    dimension = c2.selectbox("Agrupar por", dimensiones, format_func=etiqueta, key=f"{key}_dim")
    monto = c3.selectbox(
        "Monto", montos, index=montos.index("devengado_") if "devengado_" in montos else 0,
        format_func=etiqueta, key=f"{key}_monto", disabled=tipo in ("momentos", "avance"),
    )
    top_n = c4.number_input("Máximo de categorías", 3, 30, 10, key=f"{key}_top", disabled=tipo == "jerarquia")

    if tipo == "barras":
        mostrar(grafica_barras(df, dimension, monto, top_n), key=f"{key}_grafica")
    elif tipo == "momentos":
        elegidos = st.multiselect(
            "Momentos", montos, default=[m for m in ("aprobado_", "modificado_", "devengado_", "pagado_") if m in montos],
            format_func=etiqueta, key=f"{key}_momentos",
        )
        if elegidos:
            mostrar(grafica_momentos(df, dimension, sorted(elegidos, key=montos.index), top_n), key=f"{key}_grafica")
    elif tipo == "avance":
        mostrar(grafica_avance(df, dimension, top_n=top_n), key=f"{key}_grafica")
    else:
        mostrar(grafica_jerarquia(df, [dimension], monto), key=f"{key}_grafica")

    with st.expander("Ver los datos en tabla"):
        st.table(tabla(df, dimension))
