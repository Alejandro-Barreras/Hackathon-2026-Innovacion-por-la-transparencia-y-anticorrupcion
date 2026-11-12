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

import csv
import io
import re
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


csv.field_size_limit(10_000_000)  # algunos campos (textos de contratos) son muy largos


def _unir_montos(fila: list[str]) -> list[str]:
    """Si un monto viene sin comillas, '$11,448.85' llega partido en '$11' y '448.85': los vuelve a unir."""
    unida: list[str] = []
    for campo in fila:
        if unida and unida[-1].strip().startswith("$") and re.fullmatch(r"\d{3}(\.\d*)?", campo.strip()):
            unida[-1] += "," + campo.strip()
        else:
            unida.append(campo)
    return unida


def _leer_csv(ruta: Path) -> tuple[pd.DataFrame, int]:
    """
    Lee el CSV tal como lo publica el portal:
      - montos sin comillas ("$11,448.85") se vuelven a unir;
      - comas sobrantes al final de la fila se recortan;
      - filas con campos de mas QUE SI TIENEN CONTENIDO (comas sin comillas dentro de un texto)
        se omiten, porque no se pueden alinear con seguridad.
    Devuelve (DataFrame de texto, numero de filas omitidas).
    """
    crudo = ruta.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = crudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    primera = texto.split("\n", 1)[0]
    sep = max((",", ";", "\t"), key=primera.count)
    filas = csv.reader(io.StringIO(texto, newline=""), delimiter=sep, skipinitialspace=True)
    encabezado = next(filas, None)
    if not encabezado:
        raise HTTPException(500, f"{ruta.name} esta vacio")

    n = len(encabezado)
    nombres, vistos = [], {}
    for i, c in enumerate(encabezado):
        c = " ".join(str(c).split()) or f"col_{i}"
        vistos[c] = vistos.get(c, 0) + 1
        nombres.append(c if vistos[c] == 1 else f"{c}.{vistos[c] - 1}")  # evita columnas repetidas

    datos, omitidas = [], 0
    for fila in filas:
        if not any(c.strip() for c in fila):
            continue
        fila = _unir_montos(fila)
        if len(fila) > n:
            if any(c.strip() for c in fila[n:]):
                omitidas += 1
                continue
            fila = fila[:n]
        datos.append(fila + [""] * (n - len(fila)))

    if omitidas:
        print(f"[api] {ruta.name}: se omitieron {omitidas} filas mal formadas")

    df = pd.DataFrame(datos, columns=nombres, dtype=str)
    df = df.apply(lambda col: col.str.strip()).replace("", pd.NA)
    return df, omitidas


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


# Sueldos (LGT Art. 70 fr. VIII): las columnas se toman por POSICION porque los encabezados
# oficiales son muy largos y cambian de redaccion entre anios.
POSICIONES_SUELDOS = {
    0: "ejercicio", 1: "fecha_inicio", 2: "fecha_fin", 3: "tipo_integrante", 4: "nivel",
    5: "puesto", 6: "cargo", 7: "area", 8: "nombre", 9: "apellido1", 10: "apellido2",
    11: "sexo", 12: "sueldo_bruto", 14: "sueldo_neto", 29: "dependencia", 30: "fecha_actualizacion",
}


def limpiar_sueldos(df: pd.DataFrame) -> pd.DataFrame:
    salida = pd.DataFrame(index=df.index)
    for pos, nuevo in POSICIONES_SUELDOS.items():
        if pos < df.shape[1]:
            salida[nuevo] = df.iloc[:, pos]

    for c in salida.columns:
        if c.startswith("fecha"):
            salida[c] = _fecha_iso(salida[c])
    for c in ("sueldo_bruto", "sueldo_neto"):
        if c in salida:
            salida[c] = _dinero(salida[c])
    if "dependencia" in salida:  # "10-Tesoreria" -> "Tesoreria"
        salida["dependencia"] = salida["dependencia"].str.replace(r"^\d+\s*-\s*", "", regex=True)

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
    # Renglones sin nombre de programa = el area no reporto apoyos en ese periodo
    if "programa" in salida:
        salida["sin_informacion"] = salida["programa"].isna()
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
    "sueldos": {"agrupar_por": "dependencia", "valor": "sueldo_bruto"},
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
        mask = df.astype("string").apply(
            lambda c: c.str.contains(buscar, case=False, na=False, regex=False)
        ).any(axis=1)
        df = df[mask]
    if filtro_columna or filtro_valor:
        if not (filtro_columna and filtro_valor):
            raise HTTPException(400, "Usa filtro_columna y filtro_valor juntos.")
        _exigir_columna(df, filtro_columna)
        df = df[df[filtro_columna].astype("string").str.contains(
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
    limite: int = Query(50, ge=1, le=200_000),
    pagina: int = Query(1, ge=1),
    buscar: str | None = Query(None, description="Texto a buscar en cualquier columna"),
    filtro_columna: str | None = None,
    filtro_valor: str | None = None,
    ordenar_por: str | None = None,
    desc: bool = True,
    columnas: str | None = Query(None, description="Columnas a devolver, separadas por coma (por defecto todas)"),
):
    """Filas del dataset con paginacion, busqueda, filtro, orden y seleccion de columnas."""
    df = filtrar(cargar(dataset), buscar, filtro_columna, filtro_valor)
    if ordenar_por:
        _exigir_columna(df, ordenar_por)
        df = df.sort_values(ordenar_por, ascending=not desc, na_position="last")
    ini = (pagina - 1) * limite
    pagina_df = df.iloc[ini:ini + limite]
    if columnas:
        cols = [c.strip() for c in columnas.split(",") if c.strip()]
        for c in cols:
            _exigir_columna(df, c)
        pagina_df = pagina_df[cols]
    return {"total": len(df), "pagina": pagina, "limite": limite, "filas": _a_json(pagina_df)}


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