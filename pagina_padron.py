"""Página del padrón de beneficiarios: programas de apoyo del Ayuntamiento, con datos de la API."""

import pandas as pd
import streamlit as st

import datos_api as api

COLUMNAS = [
    "fecha_inicio", "fecha_fin", "ambito", "tipo_programa", "programa",
    "subprograma", "area", "url_estadistica", "sin_informacion",
]


def mostrar() -> None:
    cabecera = st.container()
    try:
        df = api.dataframe("padron_beneficiarios", COLUMNAS)
    except api.ApiError as e:
        with cabecera:
            api.aviso_error(e)
        return
    if df.empty:
        with cabecera:
            api.aviso("<strong>Sin información.</strong> No hay registros del padrón.")
        return

    df = api.con_periodo(df)
    df, periodo = api.filtrar_periodo(df, key="padron_periodo")
    df = df.assign(
        area=df["area"].str.replace(r"^\d+\s*-\s*", "", regex=True),
        sin_informacion=df["sin_informacion"].fillna(True).astype(bool),
    )

    con_programas = df[~df["sin_informacion"]].drop_duplicates(["programa", "area"])
    areas = df["area"].dropna().unique()
    areas_con = con_programas["area"].dropna().unique()
    cuando = f"En el periodo {periodo}" if periodo else "En los datos disponibles"

    with cabecera:
        api.encabezado(
            "¿Quién recibe apoyos de los programas del Ayuntamiento?",
            "Programas sociales y de apoyo que reporta cada área del Ayuntamiento.",
            f"{cuando}, <strong>{len(areas_con)}</strong> de las <strong>{len(areas)}</strong> áreas "
            f"reportaron programas de apoyo. Las demás informaron que no generaron información.",
        )

    api.seccion("programas", "Programas de apoyo reportados", "Cada programa con el área que lo maneja.")
    if con_programas.empty:
        api.aviso("En este periodo ninguna área reportó programas de apoyo.")
    else:
        vista = pd.DataFrame(
            {
                "Programa": con_programas["programa"],
                "Tipo": con_programas["tipo_programa"],
                "Ámbito": con_programas["ambito"],
                "Área": con_programas["area"],
                "Estadísticas": con_programas["url_estadistica"],
            }
        )
        st.dataframe(
            vista,
            hide_index=True,
            width="stretch",
            column_config={"Estadísticas": st.column_config.LinkColumn("Estadísticas", display_text="Ver estadísticas")},
        )

    sin_reporte = sorted(set(areas) - set(areas_con))
    if sin_reporte:
        with st.expander("Áreas que no reportaron programas en este periodo"):
            st.table(pd.DataFrame({"Área": sin_reporte}).set_index("Área"))