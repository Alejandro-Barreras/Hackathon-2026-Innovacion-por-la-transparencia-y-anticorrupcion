"""Página de sueldos: remuneraciones del personal, con datos de la API (sin nombres de personas)."""

import streamlit as st

import datos_api as api
import graficas_remuneraciones as r
from graficas_presupuestos import pesos


def mostrar() -> None:
    cabecera = st.container()  # se llena al final, cuando ya se eligió el periodo
    try:
        df = api.sueldos()
    except api.ApiError as e:
        with cabecera:
            api.aviso_error(e)
        return

    df, periodo = api.filtrar_periodo(df, key="sueldos_periodo")

    sueldos = df["bruto"].dropna()
    cifra = ""
    if len(sueldos):
        cuando = f"En el periodo {periodo}" if periodo else "En los datos disponibles"
        cifra = (
            f"{cuando} hay <strong>{len(df):,}</strong> personas con sueldo registrado. "
            f"La mitad gana menos de <strong>{pesos(sueldos.median())}</strong> de sueldo bruto."
        )
    with cabecera:
        api.encabezado(
            "¿Cuánto ganan las personas que trabajan en el Ayuntamiento?",
            "Consulta cuántas personas trabajan en cada dependencia y cuánto ganan. "
            "Se muestran resúmenes por grupo, sin nombres.",
            cifra,
        )

    api.seccion(
        "plantilla",
        "¿Cuántas personas trabajan en cada dependencia?",
        "Mujeres y hombres que trabajan en cada dependencia, de mayor a menor.",
    )
    r.mostrar(r.grafica_plantilla(df), key="sueldos_plantilla")

    api.seccion(
        "sueldo-tipico",
        "¿Qué dependencias pagan sueldos más altos?",
        "El sueldo bruto típico de cada dependencia: la mitad de su personal gana más y la otra mitad menos.",
    )
    r.mostrar(r.grafica_remuneracion(df), key="sueldos_remuneracion")

    api.seccion(
        "mujeres-hombres",
        "¿Ganan lo mismo mujeres y hombres?",
        "Sueldo típico de mujeres y hombres en cada dependencia. "
        "Un porcentaje negativo significa que las mujeres ganan menos que los hombres.",
    )
    r.mostrar(r.grafica_brecha_genero(df), key="sueldos_brecha")

    # Sin st.expander alrededor: el explorador ya trae el suyo y Streamlit no permite anidarlos.
    api.seccion("explorar", "Explorar con más opciones", "Elige qué gráfica ver y cómo agrupar los datos.")
    r.explorador(df)