"""
API de datos de transparencia - Hermosillo (prototipo de hackathon).

Estructura esperada del proyecto:
    api.py
    app.py
    datos/
        sueldos.csv
        normativo.csv
        padron_beneficiarios.csv
        adjudicaciones.csv

Cada CSV dentro de datos/ se publica automaticamente. El nombre del archivo
(sin .csv) es el nombre del dataset en la URL:  datos/sueldos.csv -> /api/sueldos/...
Si agregas un CSV nuevo no hay que tocar nada: solo guardarlo en datos/.

Instalacion:
    pip install fastapi uvicorn pandas

Ejecutar (desde la carpeta del proyecto):
    python -m uvicorn api:app --reload

Documentacion interactiva (para probar todo desde el navegador):
    http://127.0.0.1:8000/docs
"""

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DIR = Path(__file__).parent / "datos"

app = FastAPI(title="API Transparencia Hermosillo (prototipo)", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ======================================================================
# Utilidades de lectura y limpieza
# ======================================================================
def _dinero(serie: pd.Series) -> pd.Series:
    """'$20,337.09' -> 20337.09 (NaN si no se puede convertir)."""
    limpia = serie.astype("string").str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(limpia, errors="coerce")


def _col(df: pd.DataFrame, prefijo: str):
    """Busca la columna cuyo nombre empieza con `prefijo` (ignora mayusculas)."""
    p = prefijo.lower()
    return next((c for c in df.columns if c.lower().startswith(p)), None)


def _leer_csv(ruta: Path) -> tuple[pd.DataFrame, int]:
    """Lee el CSV. Las filas con mas campos que el encabezado (comas sin comillas) se omiten."""
    omitidas: list[int] = []

    def _fila_mala(fila):
        omitidas.append(len(fila))
        return None  # None = omitir la fila

    for enc in ("utf-8-sig", "latin-1"):
        try:
            omitidas.clear()
            df = pd.read_csv(ruta, encoding=enc, skipinitialspace=True, dtype=str,
                             engine="python", on_bad_lines=_fila_mala)
            if df.shape[1] == 1:  # separador distinto de coma: que pandas lo detecte
                omitidas.clear()
                df = pd.read_csv(ruta, encoding=enc, sep=None, engine="python",
                                 skipinitialspace=True, dtype=str, on_bad_lines=_fila_mala)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(500, f"No se pudo leer {ruta.name}")

    if omitidas:
        print(f"[api] {ruta.name}: se omitieron {len(omitidas)} filas mal formadas")

    # Limpieza general: espacios en nombres de columna y en los valores
    nombres, vistos = [], {}
    for c in df.columns:
        c = " ".join(str(c).split())
        vistos[c] = vistos.get(c, 0) + 1
        nombres.append(c if vistos[c] == 1 else f"{c}.{vistos[c] - 1}")  # evita columnas repetidas
    df.columns = nombres
    return df.apply(lambda col: col.str.strip()), len(omitidas)


def _fecha_iso(serie: pd.Series) -> pd.Series:
    """'21/02/2024' -> '2024-02-21' (asi se pueden ordenar bien). Si no se puede, deja el texto."""
    parsed = pd.to_datetime(serie, format="%d/%m/%Y", errors="coerce")
    return parsed.dt.strftime("%Y-%m-%d").fillna(serie)


def _seleccionar(df: pd.DataFrame, mapa: dict, dinero: tuple = ()) -> pd.DataFrame:
    """
    Conserva solo las columnas del `mapa` {prefijo del nombre original: nombre corto}.
    Las que empiezan con 'fecha' pasan a ISO y las de `dinero` a numero.
    """
    salida = pd.DataFrame(index=df.index)
    for prefijo, nuevo in mapa.items():
        original = _col(df, prefijo)
        if original is not None:
            salida[nuevo] = df[original]
    for c in salida.columns:
        if c.startswith("fecha"):
            salida[c] = _fecha_iso(salida[c])
    for c in dinero:
        if c in salida:
            salida[c] = _dinero(salida[c])
    return salida


def limpiar_sueldos(df: pd.DataFrame) -> pd.DataFrame:
    salida = _seleccionar(df, {
        "Ejercicio": "ejercicio",
        "Fecha de inicio": "fecha_inicio",
        "Fecha de término": "fecha_fin",
        "Tipo de integrante": "tipo_integrante",
        "Clave o nivel": "nivel",
        "Denominación o descripción del puesto": "puesto",
        "Denominación del cargo": "cargo",
        "Área de adscripción": "area",
        "Nombre": "nombre",
        "Primer apellido": "apellido1",
        "Segundo apellido": "apellido2",
        "Sexo": "sexo",
        "Monto de la remuneración bruta": "sueldo_bruto",
        "Monto de la remuneración neta": "sueldo_neto",
        "Fecha de Actualización": "fecha_actualizacion",
    }, dinero=("sueldo_bruto", "sueldo_neto"))

    partes = [c for c in ("nombre", "apellido1", "apellido2") if c in salida]
    if partes:
        salida["nombre_completo"] = (
            salida[partes].fillna("").agg(" ".join, axis=1).str.split().str.join(" ")
        )
    return salida


def limpiar_adjudicaciones(df: pd.DataFrame) -> pd.DataFrame:
    """Contratos adjudicados. Se omiten los textos largos, domicilios y datos de personas fisicas."""
    return _seleccionar(df, {
        "Ejercicio": "ejercicio",
        "Fecha de inicio del periodo": "fecha_inicio",
        "Fecha de término del periodo": "fecha_fin",
        "Tipo de procedimiento": "tipo_procedimiento",
        "Materia o tipo de contratación": "materia",
        "Carácter del procedimiento": "caracter",
        "Número de expediente": "expediente",
        "Denominación o Razón social": "proveedor",
        "Área(s) solicitante": "area_solicitante",
        "Área(s) contratante": "area_contratante",
        "Número que identifique al contrato": "num_contrato",
        "Fecha del contrato": "fecha_contrato",
        "Fecha de inicio de la vigencia": "fecha_inicio_vigencia",
        "Fecha de término de la vigencia": "fecha_fin_vigencia",
        "Monto del contrato sin impuestos": "monto_sin_impuestos",
        "Monto total del contrato con impuestos": "monto_total",
        "Tipo de moneda": "moneda",
        "Objeto del contrato": "objeto",
        "Lugar donde se realizará la obra": "lugar_obra",
        "Etapa de la obra": "etapa_obra",
        "Hipervínculo al documento del contrato": "url_contrato",
        "Fecha de actualización": "fecha_actualizacion",
    }, dinero=("monto_sin_impuestos", "monto_total"))


def limpiar_padron(df: pd.DataFrame) -> pd.DataFrame:
    salida = _seleccionar(df, {
        "Ejercicio": "ejercicio",
        "Fecha de inicio": "fecha_inicio",
        "Fecha de término": "fecha_fin",
        "Ámbito": "ambito",
        "Tipo de programa": "tipo_programa",
        "Denominación del Programa": "programa",
        "Denominación del subprograma": "subprograma",
        "Padrón de beneficiarios": "padron",
        "Hipervínculo a la información estadística": "url_estadistica",
        "Área(s) responsable(s)": "area",
        "Fecha de actualización": "fecha_actualizacion",
        "Nota": "nota",
    })
    # Muchos renglones solo dicen "no se generó información": se marcan para poder filtrarlos
    if "nota" in salida:
        salida["sin_informacion"] = (
            salida["nota"].fillna("").str.upper().str.contains("NO SE GENER", regex=False)
        )
    return salida


def limpiar_normativo(df: pd.DataFrame) -> pd.DataFrame:
    return _seleccionar(df, {
        "Ejercicio": "ejercicio",
        "Tipo de normatividad": "tipo_normatividad",
        "Denominación de la norma": "denominacion",
        "Fecha de publicación": "fecha_publicacion",
        "Fecha de última modificación": "fecha_modificacion",
        "Hipervínculo al documento de la norma": "url_documento",
        "Área(s) responsable(s)": "area",
        "Fecha de Actualización": "fecha_actualizacion",
    })


# Limpieza especifica por dataset (el nombre es el del archivo CSV sin extension).
LIMPIADORES = {
    "sueldos": limpiar_sueldos,
    "adjudicaciones": limpiar_adjudicaciones,
    "padron_beneficiarios": limpiar_padron,
    "normativo": limpiar_normativo,
}

# Valores por defecto para /resumen y /estadisticas cuando no se indican.
# Sin "valor" el resumen cuenta filas; con "valor" suma esa columna.
DEFAULTS = {
    "sueldos": {"agrupar_por": "area", "valor": "sueldo_bruto"},
    "adjudicaciones": {"agrupar_por": "area_contratante", "valor": "monto_total"},
    "padron_beneficiarios": {"agrupar_por": "area"},
    "normativo": {"agrupar_por": "tipo_normatividad"},
}


# ======================================================================
# Carga con cache (se recarga sola si cambias el CSV)
# ======================================================================
_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_omitidas: dict[str, int] = {}  # filas descartadas por dataset (CSV mal formado)


def disponibles() -> list[str]:
    return sorted(p.stem for p in DIR.glob("*.csv"))


def cargar(nombre: str) -> pd.DataFrame:
    if nombre not in disponibles():
        raise HTTPException(404, f"Dataset '{nombre}' no existe. Disponibles: {disponibles()}")
    ruta = DIR / f"{nombre}.csv"
    mtime = ruta.stat().st_mtime
    if nombre not in _cache or _cache[nombre][0] != mtime:
        df, _omitidas[nombre] = _leer_csv(ruta)
        if nombre in LIMPIADORES:
            df = LIMPIADORES[nombre](df)
        _cache[nombre] = (mtime, df)
    return _cache[nombre][1]


def _exigir_columna(df: pd.DataFrame, columna: str) -> None:
    if columna not in df.columns:
        raise HTTPException(400, f"La columna '{columna}' no existe. Columnas: {list(df.columns)}")


def filtrar(df, buscar, filtro_columna, filtro_valor):
    if buscar:
        mask = df.astype(str).apply(
            lambda c: c.str.contains(buscar, case=False, na=False, regex=False)
        ).any(axis=1)
        df = df[mask]
    if filtro_columna or filtro_valor:
        if not (filtro_columna and filtro_valor):
            raise HTTPException(400, "Usa filtro_columna y filtro_valor juntos.")
        _exigir_columna(df, filtro_columna)
        df = df[df[filtro_columna].astype(str).str.contains(
            filtro_valor, case=False, na=False, regex=False)]
    return df


def _a_json(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


# ======================================================================
# Endpoints
# ======================================================================
@app.get("/")
def inicio():
    """Sirve para comprobar que la API esta viva."""
    return {"estado": "ok", "datasets": disponibles(), "docs": "/docs"}


@app.get("/api/datasets")
def datasets():
    """Lista de datasets con filas y columnas. Si un CSV falla, lo reporta sin tumbar los demas."""
    salida = []
    for n in disponibles():
        try:
            df = cargar(n)
            salida.append({"nombre": n, "filas": len(df), "filas_omitidas": _omitidas.get(n, 0),
                           "columnas": list(df.columns)})
        except Exception as e:  # noqa: BLE001
            salida.append({"nombre": n, "error": str(getattr(e, "detail", e))})
    return salida


@app.get("/api/{dataset}/columnas")
def columnas(dataset: str):
    df = cargar(dataset)
    return {"filas": len(df), "columnas": list(df.columns), "tipos": df.dtypes.astype(str).to_dict()}


@app.get("/api/{dataset}/datos")
def datos(
    dataset: str,
    limite: int = Query(50, ge=1, le=1000),
    pagina: int = Query(1, ge=1),
    buscar: str | None = Query(None, description="Texto a buscar en cualquier columna"),
    filtro_columna: str | None = None,
    filtro_valor: str | None = None,
    ordenar_por: str | None = None,
    desc: bool = True,
):
    """Filas del dataset con paginacion, busqueda, filtro y orden."""
    df = filtrar(cargar(dataset), buscar, filtro_columna, filtro_valor)
    if ordenar_por:
        _exigir_columna(df, ordenar_por)
        df = df.sort_values(ordenar_por, ascending=not desc, na_position="last")
    ini = (pagina - 1) * limite
    return {"total": len(df), "pagina": pagina, "limite": limite,
            "filas": _a_json(df.iloc[ini:ini + limite])}


@app.get("/api/{dataset}/valores/{columna}")
def valores(dataset: str, columna: str):
    """Valores distintos de una columna con su conteo (util para listas desplegables)."""
    df = cargar(dataset)
    _exigir_columna(df, columna)
    conteo = df[columna].fillna("Sin dato").value_counts()
    return [{"valor": k, "cantidad": int(v)} for k, v in conteo.items()]


@app.get("/api/{dataset}/resumen")
def resumen(
    dataset: str,
    agrupar_por: str | None = None,
    valor: str | None = Query(None, description="Columna numerica a sumar. Sin ella, se cuentan filas."),
    top: int = Query(5, ge=1, le=50),
    buscar: str | None = None,
    filtro_columna: str | None = None,
    filtro_valor: str | None = None,
):
    """Top N categorias + 'Otros', con porcentaje. Pensado para graficas."""
    df = filtrar(cargar(dataset), buscar, filtro_columna, filtro_valor)
    if agrupar_por is None:  # sin parametros: usar los valores por defecto del dataset
        defecto = DEFAULTS.get(dataset, {})
        agrupar_por = defecto.get("agrupar_por")
        valor = valor or defecto.get("valor")
    if not agrupar_por:
        raise HTTPException(400, f"Indica agrupar_por. Columnas: {list(df.columns)}")
    _exigir_columna(df, agrupar_por)

    grupos = df[agrupar_por].fillna("Sin dato")
    if valor:
        _exigir_columna(df, valor)
        serie = _dinero(df[valor]).groupby(grupos).sum()
        operacion = "suma"
    else:
        serie = df.groupby(grupos).size()
        operacion = "conteo"

    serie = serie.sort_values(ascending=False)
    items = [{"nombre": str(k), "valor": round(float(v), 2)} for k, v in serie.head(top).items()]
    otros = float(serie.iloc[top:].sum())
    if otros:
        items.append({"nombre": "Otros", "valor": round(otros, 2)})

    total = round(float(serie.sum()), 2)
    for it in items:
        it["porcentaje"] = round(it["valor"] / total * 100, 1) if total else 0.0
    return {"agrupado_por": agrupar_por, "operacion": operacion, "total": total, "items": items}


@app.get("/api/{dataset}/estadisticas")
def estadisticas(
    dataset: str,
    valor: str | None = None,
    buscar: str | None = None,
    filtro_columna: str | None = None,
    filtro_valor: str | None = None,
):
    """Numero de registros y estadisticas basicas de una columna numerica."""
    df = filtrar(cargar(dataset), buscar, filtro_columna, filtro_valor)
    valor = valor or DEFAULTS.get(dataset, {}).get("valor")
    out = {"registros": len(df)}
    if valor:
        _exigir_columna(df, valor)
        s = _dinero(df[valor]).dropna()
        if len(s):
            out["columna"] = valor
            out.update({"suma": round(float(s.sum()), 2), "promedio": round(float(s.mean()), 2),
                        "mediana": round(float(s.median()), 2),
                        "minimo": round(float(s.min()), 2), "maximo": round(float(s.max()), 2)})
    return out