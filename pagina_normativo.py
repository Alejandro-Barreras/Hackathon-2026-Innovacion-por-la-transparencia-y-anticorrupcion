"""Página de marco normativo: leyes, reglamentos y lineamientos, con búsqueda en la API."""

import pandas as pd
import streamlit as st

import datos_api as api

COLUMNAS = [
    "tipo_normatividad", "denominacion", "fecha_publicacion",
    "fecha_modificacion", "url_documento",
]


def mostrar() -> None:
    cabecera = st.container()
    try:
        tipos = [v["valor"] for v in api.get("/api/normativo/valores/tipo_normatividad") if v["valor"] != "Sin dato"]
    except api.ApiError as e:
        with cabecera:
            api.aviso_error(e)
        return

    c1, c2 = st.columns([2, 1], gap="large")
    consulta = c1.text_input(
        "Buscar una ley o reglamento", placeholder="Ej. tránsito, transparencia, presupuesto", key="norm_buscar"
    )
    tipo = c2.selectbox("Tipo de norma", ["Todos"] + tipos, key="norm_tipo")

    try:
        res = api.get(
            "/api/normativo/datos",
            buscar=consulta.strip() or None,
            filtro_columna="tipo_normatividad" if tipo != "Todos" else None,
            filtro_valor=tipo if tipo != "Todos" else None,
            ordenar_por="fecha_modificacion",
            desc=True,
            limite=5000,
            columnas=",".join(COLUMNAS),
        )
    except api.ApiError as e:
        with cabecera:
            api.aviso_error(e)
        return

    # El portal repite cada norma en cada trimestre: se deja una sola vez (la modificada más recientemente).
    df = pd.DataFrame(res["filas"], columns=COLUMNAS).drop_duplicates("denominacion")

    with cabecera:
        api.encabezado(
            "¿Qué leyes y reglamentos rigen al Ayuntamiento?",
            "Busca una norma por su nombre o filtra por tipo, y abre el documento oficial.",
            f"Se encontraron <strong>{len(df):,}</strong> normas.",
        )

    if df.empty:
        api.aviso("No se encontraron normas con esos criterios. Prueba con otra palabra.")
        return

    vista = pd.DataFrame(
        {
            "Norma": df["denominacion"],
            "Tipo": df["tipo_normatividad"],
            "Publicada": api.fecha(df["fecha_publicacion"]),
            "Última modificación": api.fecha(df["fecha_modificacion"]),
            "Documento": df["url_documento"],
        }
    )
    st.dataframe(
        vista,
        hide_index=True,
        width="stretch",
        column_config={"Documento": st.column_config.LinkColumn("Documento", display_text="Abrir documento")},
    )