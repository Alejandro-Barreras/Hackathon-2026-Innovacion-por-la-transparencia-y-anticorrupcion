"""Gráficas para las remuneraciones del personal (LGT Art. 70, fracción VIII, "LGT_ART70_FVIIIa_*.csv").

Uso en app.py:

    import graficas_remuneraciones as r

    df = r.cargar_datos("datos/LGT_ART70_FVIIIa_2018_2020.csv")
    r.mostrar(r.grafica_plantilla(df))                              # personas por dependencia (mujeres / hombres)
    r.mostrar(r.grafica_remuneracion(df, dimension="puesto"))       # sueldo mediano por puesto
    r.mostrar(r.grafica_brecha_genero(df))                          # mujeres vs. hombres
    r.mostrar(r.grafica_distribucion(df))                           # qué tan dispares son los sueldos
    r.mostrar(r.grafica_bruto_neto(df))                             # cuánto se retiene del sueldo bruto
    r.explorador(df)                                                # controles para que la persona elija qué ver

Los nombres de las personas se cargan pero no se grafican: las gráficas muestran resúmenes por grupo.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from graficas_presupuestos import (
    AZUL,
    LINEA,
    REJILLA,
    TINTA,
    TINTA_2,
    _nombres_sobre_barras,
    estilo_grafica,
    mostrar,
    pesos,
)

# --- Esquema del formato LGT Art. 70 fr. VIII. Las columnas se toman por posición
# porque los encabezados oficiales son muy largos y cambian de redacción entre años. ---
COLUMNAS = {
    0: "ejercicio",
    1: "inicio",
    2: "fin",
    3: "tipo_integrante",
    4: "clave",
    5: "puesto",
    6: "cargo",
    7: "area",
    8: "nombre",
    9: "primer_apellido",
    10: "segundo_apellido",
    11: "sexo",
    12: "bruto",
    14: "neto",
    29: "dependencia",
    30: "actualizacion",
}

MONTOS = {"bruto": "Remuneración bruta", "neto": "Remuneración neta"}

DIMENSIONES = {
    "dependencia": "Dependencia",
    "puesto": "Puesto",
    "cargo": "Cargo",
    "area": "Área de adscripción",
    "sexo": "Sexo",
    "tipo_integrante": "Tipo de integrante",
    "periodo": "Periodo",
}

# Validado con el validador de paleta de dataviz (separación para daltonismo y contraste).
COLORES_SEXO = {"Mujer": "#2A78D6", "Hombre": "#EB6834", "Sin dato": "#9AA5B1"}
COLOR_BRUTO = "#8DB4DC"


# --- Datos ---
def _unir_montos(fila: list[str]) -> list[str]:
    """Si los montos vienen sin comillas, "$11,448.85" llega partido en "$11" y "448.85": los vuelve a unir."""
    unida: list[str] = []
    for campo in fila:
        if unida and unida[-1].strip().startswith("$") and re.fullmatch(r"\d{3}(\.\d*)?", campo.strip()):
            unida[-1] += "," + campo.strip()
        else:
            unida.append(campo)
    return unida


def cargar_datos(fuente: str | Path | io.IOBase) -> pd.DataFrame:
    """Lee el CSV (ruta o archivo subido con st.file_uploader).

    Las filas del formato oficial terminan con un número variable de comas sobrantes,
    así que cada fila se recorta al largo del encabezado. Los montos "$11,448.85" se
    convierten a número; un neto de $0.00 se toma como "no reportado".
    """
    crudo = fuente.read() if hasattr(fuente, "read") else Path(fuente).read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            texto = crudo.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue

    filas = list(csv.reader(io.StringIO(texto)))
    largo = len(filas[0])
    filas = [(_unir_montos(f) + [""] * largo)[:largo] for f in filas[1:] if any(c.strip() for c in f)]

    df = pd.DataFrame(filas)[list(COLUMNAS)].rename(columns=COLUMNAS)
    df = df.apply(lambda col: col.str.strip()).replace("", pd.NA)

    for col in MONTOS:
        df[col] = pd.to_numeric(df[col].str.replace(r"[$,\s]", "", regex=True), errors="coerce")
        df.loc[df[col] <= 0, col] = pd.NA

    # Unifica mayúsculas para que "Director" y "DIRECTOR" cuenten como el mismo puesto.
    for col in ("puesto", "cargo", "area"):
        df[col] = df[col].str.upper()
    df["sexo"] = df["sexo"].str.capitalize().fillna("Sin dato")
    df["dependencia"] = df["dependencia"].str.replace(r"^\d+\s*-\s*", "", regex=True)
    df["periodo"] = df["inicio"] + " – " + df["fin"]
    return df.reset_index(drop=True)


def etiqueta(columna: str) -> str:
    """Nombre legible de una columna."""
    return MONTOS.get(columna) or DIMENSIONES.get(columna) or columna


def resumir(
    df: pd.DataFrame,
    dimension: str,
    monto: str = "bruto",
    top_n: int | None = None,
    ordenar_por: str = "mediana",
) -> pd.DataFrame:
    """Personas, mediana, promedio, mínimo y máximo de `monto` por categoría."""
    tabla = (
        df.dropna(subset=[monto])
        .groupby(dimension)[monto]
        .agg(personas="size", mediana="median", promedio="mean", minimo="min", maximo="max")
        .sort_values(ordenar_por, ascending=False)
        .reset_index()
    )
    return tabla.head(top_n) if top_n else tabla


def tabla(df: pd.DataFrame, dimension: str, monto: str = "bruto") -> pd.DataFrame:
    """Tabla con montos ya formateados, lista para st.table dentro de un expander."""
    resumen = resumir(df, dimension, monto)
    cifras = ["mediana", "promedio", "minimo", "maximo"]
    resumen[cifras] = resumen[cifras].map(pesos)
    return resumen.rename(
        columns={"personas": "Personas", "mediana": "Mediana", "promedio": "Promedio", "minimo": "Mínimo", "maximo": "Máximo"}
    ).set_index(dimension).rename_axis(etiqueta(dimension))


def _estilo(fig: go.Figure, alto: int) -> go.Figure:
    # estilo_grafica fija margin=8 en todos lados; se conserva el margen propio de cada gráfica.
    margen = fig.layout.margin.to_plotly_json()
    return estilo_grafica(fig, alto).update_layout(margin=margen)


def _nombres_arriba(fig: go.Figure, nombres, yshift: int) -> None:
    # Como _nombres_sobre_barras, pero más arriba para marcas más altas (cajas, barras agrupadas).
    for nombre in nombres:
        fig.add_annotation(
            x=0, y=nombre, text=nombre, showarrow=False, xanchor="left", yanchor="bottom",
            yshift=yshift, font=dict(size=16, color=TINTA),
        )


def _sin_datos(mensaje: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=mensaje, showarrow=False, font=dict(size=16, color=TINTA_2), x=0.5, y=0.5, xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _estilo(fig, 160)


# --- Gráficas ---
def grafica_plantilla(
    df: pd.DataFrame,
    dimension: str = "dependencia",
    por_sexo: bool = True,
    top_n: int | None = 10,
) -> go.Figure:
    """Barras horizontales: cuántas personas hay en cada categoría, divididas en mujeres y hombres."""
    conteo = df.groupby([dimension, "sexo"]).size().unstack(fill_value=0)
    conteo["total"] = conteo.sum(axis=1)
    conteo = conteo.sort_values("total", ascending=False)
    if top_n:
        conteo = conteo.head(top_n)
    conteo = conteo.iloc[::-1]
    nombres = conteo.index.tolist()

    fig = go.Figure()
    if por_sexo:
        for sexo in [s for s in COLORES_SEXO if s in conteo.columns]:
            fig.add_trace(
                go.Bar(
                    x=conteo[sexo], y=nombres, name=sexo, orientation="h",
                    marker=dict(color=COLORES_SEXO[sexo], line=dict(color="#FFFFFF", width=2)),
                    hovertemplate=f"<b>%{{y}}</b><br>{sexo}: %{{x}} personas<extra></extra>",
                )
            )
    else:
        fig.add_trace(
            go.Bar(
                x=conteo["total"], y=nombres, orientation="h", marker=dict(color=AZUL),
                hovertemplate="<b>%{y}</b><br>%{x} personas<extra></extra>",
            )
        )
    for nombre, total in zip(nombres, conteo["total"]):
        fig.add_annotation(
            x=total, y=nombre, text=f"  {total}", showarrow=False, xanchor="left",
            font=dict(size=15, color=TINTA),
        )
    _nombres_sobre_barras(fig, nombres)
    fig.update_layout(
        barmode="stack", bargap=0.55, barcornerradius=4, showlegend=por_sexo,
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", traceorder="normal", font=dict(size=15)),
        margin=dict(l=0, r=0, t=56 if por_sexo else 32, b=8),
    )
    fig.update_xaxes(visible=False, range=[0, max(conteo["total"].max(), 1) * 1.3])
    fig.update_yaxes(visible=False)
    return _estilo(fig, 70 * len(conteo) + (90 if por_sexo else 60))


def grafica_remuneracion(
    df: pd.DataFrame,
    dimension: str = "dependencia",
    monto: str = "bruto",
    estadistico: str = "mediana",
    top_n: int | None = 10,
) -> go.Figure:
    """Barras horizontales: remuneración mediana (o promedio) por categoría, de mayor a menor."""
    datos = resumir(df, dimension, monto, top_n, ordenar_por=estadistico).iloc[::-1]
    if datos.empty:
        return _sin_datos(f"No hay datos de {etiqueta(monto).lower()}.")

    fig = go.Figure(
        go.Bar(
            x=datos[estadistico],
            y=datos[dimension],
            orientation="h",
            marker=dict(color=AZUL),
            text=[f"  {pesos(v)}" for v in datos[estadistico]],
            textposition="outside",
            textfont=dict(color=TINTA, size=15),
            cliponaxis=False,
            customdata=datos[["personas", "minimo", "maximo"]].values,
            hovertemplate=f"<b>%{{y}}</b><br>{etiqueta(monto)} ({estadistico}): $%{{x:,.2f}}"
            "<br>%{customdata[0]} personas<br>De $%{customdata[1]:,.2f} a $%{customdata[2]:,.2f}<extra></extra>",
        )
    )
    _nombres_sobre_barras(fig, datos[dimension])
    fig.update_layout(bargap=0.55, barcornerradius=4, margin=dict(l=0, r=0, t=32, b=8))
    fig.update_xaxes(visible=False, range=[0, datos[estadistico].max() * 1.5])
    fig.update_yaxes(visible=False)
    return _estilo(fig, 70 * len(datos) + 60)


def grafica_brecha_genero(
    df: pd.DataFrame,
    dimension: str = "dependencia",
    monto: str = "bruto",
    top_n: int | None = 10,
) -> go.Figure:
    """Puntos unidos: remuneración mediana de mujeres vs. hombres en cada categoría.

    Solo aparecen las categorías que tienen tanto mujeres como hombres.
    La brecha es (mujeres − hombres) ÷ hombres: negativa = las mujeres ganan menos.
    """
    medianas = df.dropna(subset=[monto]).groupby([dimension, "sexo"])[monto].median().unstack()
    if not {"Mujer", "Hombre"} <= set(medianas.columns):
        return _sin_datos("No hay categorías con mujeres y hombres para comparar.")
    datos = medianas[["Mujer", "Hombre"]].dropna()
    if datos.empty:
        return _sin_datos("No hay categorías con mujeres y hombres para comparar.")
    datos["brecha"] = (datos["Mujer"] - datos["Hombre"]) / datos["Hombre"] * 100
    datos = datos.reindex(datos["brecha"].abs().sort_values(ascending=False).index)
    if top_n:
        datos = datos.head(top_n)
    datos = datos.iloc[::-1]
    nombres = datos.index.tolist()

    fig = go.Figure()
    # Línea que une a los dos puntos de cada categoría.
    xs, ys = [], []
    for nombre, fila in datos.iterrows():
        xs += [fila["Mujer"], fila["Hombre"], None]
        ys += [nombre, nombre, None]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=LINEA, width=2), hoverinfo="skip", showlegend=False))

    for sexo in ("Mujer", "Hombre"):
        fig.add_trace(
            go.Scatter(
                x=datos[sexo], y=nombres, mode="markers", name=sexo,
                marker=dict(size=14, color=COLORES_SEXO[sexo], line=dict(color="#FFFFFF", width=2)),
                customdata=datos["brecha"],
                hovertemplate=f"<b>%{{y}}</b><br>{sexo} (mediana): $%{{x:,.2f}}"
                "<br>Brecha: %{customdata:+.1f} %<extra></extra>",
            )
        )
    tope = datos[["Mujer", "Hombre"]].max(axis=1)
    for nombre, x, brecha in zip(nombres, tope, datos["brecha"]):
        fig.add_annotation(
            x=x, y=nombre, text=f"   {brecha:+.0f} %", showarrow=False, xanchor="left",
            font=dict(size=15, color=TINTA),
        )
    _nombres_sobre_barras(fig, nombres)
    fig.update_layout(
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", font=dict(size=15)),
        margin=dict(l=0, r=0, t=56, b=40),
    )
    fig.update_xaxes(
        range=[0, tope.max() * 1.3], gridcolor=REJILLA, zeroline=False, tickprefix="$", tickformat="~s",
        tickfont=dict(size=14, color=TINTA_2),
    )
    fig.update_yaxes(visible=False, range=[-0.6, len(datos) - 0.2])
    return _estilo(fig, 70 * len(datos) + 140)


def grafica_distribucion(
    df: pd.DataFrame,
    dimension: str = "dependencia",
    monto: str = "bruto",
    top_n: int | None = 10,
) -> go.Figure:
    """Caja por categoría: rango, mediana y valores atípicos de la remuneración. Cada punto es una persona."""
    orden = resumir(df, dimension, monto, top_n)[dimension].tolist()[::-1]
    datos = df[df[dimension].isin(orden)].dropna(subset=[monto])
    if datos.empty:
        return _sin_datos(f"No hay datos de {etiqueta(monto).lower()}.")

    fig = go.Figure(
        go.Box(
            x=datos[monto],
            y=datos[dimension],
            orientation="h",
            boxpoints="all",
            jitter=0.4,
            pointpos=0,
            width=0.4,
            fillcolor="rgba(15, 76, 129, 0.12)",
            line=dict(color=AZUL, width=2),
            marker=dict(color=AZUL, size=8, opacity=0.7, line=dict(color="#FFFFFF", width=1)),
            hovertemplate=f"<b>%{{y}}</b><br>{etiqueta(monto)}: $%{{x:,.2f}}<extra></extra>",
        )
    )
    _nombres_arriba(fig, orden, yshift=24)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=40), showlegend=False)
    fig.update_xaxes(
        range=[0, datos[monto].max() * 1.1], gridcolor=REJILLA, zeroline=False, tickprefix="$", tickformat="~s",
        tickfont=dict(size=14, color=TINTA_2),
    )
    fig.update_yaxes(visible=False, categoryorder="array", categoryarray=orden)
    return _estilo(fig, 100 * len(orden) + 100)


def grafica_bruto_neto(
    df: pd.DataFrame,
    dimension: str = "dependencia",
    top_n: int | None = 10,
) -> go.Figure:
    """Barras agrupadas: remuneración mediana bruta vs. neta y el % que se retiene (impuestos, cuotas).

    Solo usa a las personas con ambos montos reportados.
    """
    completos = df.dropna(subset=["bruto", "neto"])
    if completos.empty:
        return _sin_datos("No hay registros con remuneración bruta y neta.")
    datos = completos.groupby(dimension)[["bruto", "neto"]].median().sort_values("bruto", ascending=False)
    if top_n:
        datos = datos.head(top_n)
    datos = datos.iloc[::-1]
    datos["retenido"] = (1 - datos["neto"] / datos["bruto"]) * 100
    nombres = datos.index.tolist()

    fig = go.Figure()
    # Neto primero: en barras horizontales agrupadas la primera serie queda abajo, así el bruto va arriba.
    for col, color in (("neto", AZUL), ("bruto", COLOR_BRUTO)):
        texto = (
            [f"  {pesos(v)}" for v in datos[col]]
            if col == "bruto"
            else [f"  {pesos(v)} · {r:.0f} % retenido" for v, r in zip(datos[col], datos["retenido"])]
        )
        fig.add_trace(
            go.Bar(
                x=datos[col], y=nombres, name=etiqueta(col), orientation="h",
                marker=dict(color=color, line=dict(color="#FFFFFF", width=2)),
                text=texto, textposition="outside", textfont=dict(color=TINTA, size=14), cliponaxis=False,
                hovertemplate=f"<b>%{{y}}</b><br>{etiqueta(col)} (mediana): $%{{x:,.2f}}<extra></extra>",
            )
        )
    _nombres_arriba(fig, nombres, yshift=28)
    fig.update_layout(
        barmode="group", bargap=0.45, bargroupgap=0.1, barcornerradius=3,
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", traceorder="reversed", font=dict(size=15)),
        margin=dict(l=0, r=0, t=56, b=8),
    )
    fig.update_xaxes(visible=False, range=[0, datos["bruto"].max() * 1.7])
    fig.update_yaxes(visible=False)
    return _estilo(fig, 110 * len(datos) + 100)


# --- Explorador con controles ---
def explorador(df: pd.DataFrame, key: str = "explorador_rem") -> None:
    """Controles en una fila + gráfica + tabla. La persona elige qué ver."""
    dimensiones = [c for c in DIMENSIONES if c in df.columns and c != "sexo"]
    tipos = {
        "Remuneración por categoría": "remuneracion",
        "Personas por categoría": "plantilla",
        "Mujeres vs. hombres": "brecha",
        "Qué tan dispares son los sueldos": "distribucion",
        "Bruto vs. neto": "bruto_neto",
    }

    c1, c2, c3, c4 = st.columns(4)
    tipo = tipos[c1.selectbox("Tipo de gráfica", list(tipos), key=f"{key}_tipo")]
    dimension = c2.selectbox("Agrupar por", dimensiones, format_func=etiqueta, key=f"{key}_dim")
    monto = c3.selectbox(
        "Monto", list(MONTOS), format_func=etiqueta, key=f"{key}_monto",
        disabled=tipo in ("plantilla", "bruto_neto"),
    )
    top_n = c4.number_input("Máximo de categorías", 3, 30, 10, key=f"{key}_top")

    if tipo == "remuneracion":
        fig = grafica_remuneracion(df, dimension, monto, top_n=top_n)
    elif tipo == "plantilla":
        fig = grafica_plantilla(df, dimension, top_n=top_n)
    elif tipo == "brecha":
        fig = grafica_brecha_genero(df, dimension, monto, top_n=top_n)
    elif tipo == "distribucion":
        fig = grafica_distribucion(df, dimension, monto, top_n=top_n)
    else:
        fig = grafica_bruto_neto(df, dimension, top_n=top_n)
    mostrar(fig, key=f"{key}_grafica")

    with st.expander("Ver los datos en tabla"):
        st.table(tabla(df, dimension, monto))
