"""Página de adjudicaciones: contratos del Ayuntamiento, con datos de la API."""

import pandas as pd
import streamlit as st

import datos_api as api
import graficas_presupuestos as g

MONTO = "Monto del contrato"  # el nombre se ve en las gráficas
COLUMNAS = [
    "ejercicio", "fecha_contrato", "tipo_procedimiento", "materia", "proveedor",
    "area_contratante", "objeto", "monto_total", "url_contrato",
]


def _preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"monto_total": MONTO})
    df[MONTO] = pd.to_numeric(df[MONTO], errors="coerce")
    return df


def _tabla(df: pd.DataFrame) -> None:
    vista = pd.DataFrame(
        {
            "Fecha": api.fecha(df["fecha_contrato"]),
            "Proveedor": df["proveedor"],
            "Qué se contrató": df["objeto"],
            "Área": df["area_contratante"],
            "Monto": df[MONTO].map(lambda v: g.pesos(v) if pd.notna(v) else "Sin dato"),
            "Contrato": df["url_contrato"],
        }
    )
    st.dataframe(
        vista,
        hide_index=True,
        width="stretch",
        column_config={"Contrato": st.column_config.LinkColumn("Contrato", display_text="Ver contrato")},
    )


def mostrar() -> None:
    cabecera = st.container()
    try:
        df = api.dataframe("adjudicaciones", COLUMNAS)
    except api.ApiError as e:
        with cabecera:
            api.aviso_error(e)
        return
    if df.empty:
        with cabecera:
            api.aviso("<strong>Sin información.</strong> No hay contratos registrados.")
        return
    df = _preparar(df)

    ejercicios = sorted(df["ejercicio"].dropna().unique(), reverse=True)
    ejercicio = st.selectbox("Año", ["Todos"] + ejercicios, index=1 if ejercicios else 0, key="adj_ejercicio")
    if ejercicio != "Todos":
        df = df[df["ejercicio"] == ejercicio]

    cuando = "En total" if ejercicio == "Todos" else f"En {ejercicio}"
    with cabecera:
        api.encabezado(
            "¿A quién contrata el Ayuntamiento y por cuánto dinero?",
            "Contratos de obras y servicios que el Ayuntamiento adjudicó, con su monto y proveedor.",
            f"{cuando} se registraron <strong>{len(df):,}</strong> contratos por un total de "
            f"<strong>{g.pesos(df[MONTO].sum())}</strong>.",
        )

    if df.empty:
        api.aviso("No hay contratos para este año.")
        return

    api.seccion("areas", "¿Qué áreas contratan más?", "Monto de los contratos de cada área, de mayor a menor.")
    g.mostrar(g.grafica_barras(df, "area_contratante", MONTO, top_n=8), key="adj_areas")

    api.seccion(
        "procedimientos",
        "¿Cómo se eligió a quién contratar?",
        "Monto de los contratos según el tipo de procedimiento: adjudicación directa, licitación o invitación.",
    )
    g.mostrar(g.grafica_barras(df, "tipo_procedimiento", MONTO, top_n=6), key="adj_procedimientos")

    api.seccion("mayores", "Los 10 contratos más grandes")
    _tabla(df.nlargest(10, MONTO))

    api.seccion("buscar", "Buscar un contrato", "Escribe una obra, una calle o el nombre de una empresa.")
    consulta = st.text_input(
        "Buscar", placeholder="Ej. pavimentación, Río Conchos, desarrollos", key="adj_buscar",
        label_visibility="collapsed",
    )
    if consulta.strip():
        # La búsqueda la hace la API: encuentra el texto en cualquier columna.
        res = api.get(
            "/api/adjudicaciones/datos",
            buscar=consulta.strip(),
            filtro_columna="ejercicio" if ejercicio != "Todos" else None,
            filtro_valor=ejercicio if ejercicio != "Todos" else None,
            ordenar_por="monto_total",
            limite=25,
            columnas=",".join(COLUMNAS),
        )
        encontrados = pd.DataFrame(res["filas"], columns=COLUMNAS)
        if encontrados.empty:
            api.aviso("No se encontraron contratos con ese texto.")
        else:
            mostrando = f" (se muestran los {len(encontrados)} de mayor monto)" if res["total"] > len(encontrados) else ""
            st.caption(f"Se encontraron {res['total']:,} contratos{mostrando}.")
            _tabla(_preparar(encontrados))