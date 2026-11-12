"""Cliente de la API de transparencia + utilidades de interfaz compartidas por las páginas.

La API debe estar corriendo:  python -m uvicorn api:app --reload
Para apuntar a otro servidor:  set TRANSPARENCIA_API_URL=http://otro-host:8000   (PowerShell: $env:TRANSPARENCIA_API_URL="...")
"""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("TRANSPARENCIA_API_URL", "http://127.0.0.1:8000")
LIMITE = 200_000  # tope de filas por consulta de la API


class ApiError(Exception):
    """La API no respondió o devolvió un error."""


# --- Consultas ---
@st.cache_data(ttl=300, show_spinner="Cargando información…")
def get(ruta: str, **params):
    """GET a la API con caché de 5 minutos. Los parámetros None se omiten."""
    params = {k: v for k, v in params.items() if v is not None}
    try:
        r = requests.get(f"{API_URL}{ruta}", params=params, timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        detalle = e.response.text[:300] if getattr(e, "response", None) is not None else str(e)
        raise ApiError(f"No se pudo consultar {ruta}: {detalle}") from e


def dataframe(dataset: str, columnas: list[str] | None = None, **params) -> pd.DataFrame:
    """Filas del dataset como DataFrame. `columnas` limita lo que se descarga; el resto son filtros de la API."""
    if columnas:
        params["columnas"] = ",".join(columnas)
    filas = get(f"/api/{dataset}/datos", limite=LIMITE, **params)["filas"]
    df = pd.DataFrame(filas)
    return df.reindex(columns=columnas) if columnas else df


# --- Fechas y periodos ---
def fecha(serie: pd.Series) -> pd.Series:
    """'2024-02-21' -> '21/02/2024' (vacío si no hay fecha)."""
    return pd.to_datetime(serie, errors="coerce").dt.strftime("%d/%m/%Y").fillna("")


def con_periodo(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega la columna `periodo` ('01/01/2024 – 31/03/2024') a partir de fecha_inicio y fecha_fin."""
    ini = pd.to_datetime(df["fecha_inicio"], errors="coerce").dt.strftime("%d/%m/%Y")
    fin = pd.to_datetime(df["fecha_fin"], errors="coerce").dt.strftime("%d/%m/%Y")
    df = df.copy()
    df["periodo"] = (ini + " – " + fin).where(ini.notna() & fin.notna())
    return df


def filtrar_periodo(df: pd.DataFrame, key: str) -> tuple[pd.DataFrame, str | None]:
    """Selector de periodo (el más reciente por defecto). Evita contar dos veces al mismo personal."""
    periodos = (
        df.dropna(subset=["periodo"])
        .drop_duplicates("periodo")
        .sort_values("fecha_fin", ascending=False)["periodo"]
        .tolist()
    )
    if not periodos:
        return df, None
    periodo = st.selectbox("Periodo", periodos, key=key)
    return df[df["periodo"] == periodo], periodo


# --- Sueldos: deja los datos de la API en el formato que esperan las gráficas de graficas_remuneraciones ---
@st.cache_data(ttl=300, show_spinner=False)
def sueldos() -> pd.DataFrame:
    """Columnas: ejercicio, periodo, tipo_integrante, puesto, cargo, area, dependencia, sexo, bruto, neto.

    No se descargan nombres de personas: las gráficas son resúmenes por grupo.
    """
    df = dataframe(
        "sueldos",
        ["ejercicio", "fecha_inicio", "fecha_fin", "tipo_integrante", "puesto", "cargo",
         "area", "sexo", "sueldo_bruto", "sueldo_neto", "dependencia"],
    )
    if df.empty:
        raise ApiError("La API no devolvió registros de sueldos.")

    df = df.rename(columns={"sueldo_bruto": "bruto", "sueldo_neto": "neto"})
    for col in ("bruto", "neto"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] <= 0, col] = pd.NA  # $0.00 = "no reportado"
    for col in ("puesto", "cargo", "area"):
        df[col] = df[col].str.upper()  # "Director" y "DIRECTOR" cuentan como lo mismo
    df["sexo"] = df["sexo"].str.capitalize().fillna("Sin dato")
    return con_periodo(df)


# --- Interfaz común ---
def encabezado(titulo: str, entrada: str, cifra: str = "") -> None:
    """Título de la página, una línea de introducción y (opcional) la cifra principal."""
    cifra_html = f'<p class="cifra">{cifra}</p>' if cifra else ""
    st.markdown(
        f"""
<section class="resumen" id="contenido" aria-labelledby="titulo">
  <h1 id="titulo">{titulo}</h1>
  <p class="entrada">{entrada}</p>
  {cifra_html}
</section>
""",
        unsafe_allow_html=True,
    )


def seccion(id_: str, titulo: str, texto: str = "") -> None:
    texto_html = f"<p>{texto}</p>" if texto else ""
    st.markdown(
        f"""
<section class="seccion" id="{id_}" aria-labelledby="titulo-{id_}">
  <h2 id="titulo-{id_}">{titulo}</h2>
  {texto_html}
</section>
""",
        unsafe_allow_html=True,
    )


def aviso(mensaje: str) -> None:
    st.markdown(f'<div class="aviso" role="note"><p>{mensaje}</p></div>', unsafe_allow_html=True)


def aviso_error(error: Exception) -> None:
    aviso("<strong>No se pudo cargar la información.</strong> Intenta de nuevo en unos minutos.")
    with st.expander("Detalle técnico (para el equipo)"):
        st.write(str(error))
        st.caption("Revisa que la API esté corriendo: python -m uvicorn api:app --reload")