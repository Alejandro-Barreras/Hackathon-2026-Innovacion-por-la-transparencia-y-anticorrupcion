from pathlib import Path

import streamlit as st

import pagina_presupuesto

import pagina_adjudicaciones
import pagina_normativo
import pagina_padron
import pagina_presupuesto
import pagina_sueldos

st.set_page_config(
    page_title="Portal de Transparencia - Hermosillo",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    f"<style>{(Path(__file__).parent / 'styles.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

PAGINAS = [
    {
        "id": "presupuesto",
        "nombre": "Presupuesto",
        "descripcion": "Cuánto dinero aprobó el Ayuntamiento, cuánto ha gastado y en qué áreas.",
        "icono": "mdi-cash-multiple",
    },
    {
        "id": "sueldos",
        "nombre": "Sueldos",
        "descripcion": "Remuneraciones del personal del Ayuntamiento por área, puesto y sexo.",
        "icono": "mdi-account-cash",
    },
    {
        "id": "adjudicaciones",
        "nombre": "Adjudicaciones",
        "descripcion": "Contratos, licitaciones y adjudicaciones directas del Ayuntamiento.",
        "icono": "mdi-file-sign",
    },
    {
        "id": "padron_beneficiarios",
        "nombre": "Padrón de beneficiarios",
        "descripcion": "Personas y grupos que reciben apoyos de los programas sociales municipales.",
        "icono": "mdi-account-group",
    },
    {
        "id": "normativo",
        "nombre": "Normativo",
        "descripcion": "Leyes, reglamentos y lineamientos que rigen al Ayuntamiento.",
        "icono": "mdi-scale-balance",
    },
]
NOMBRES = {p["id"]: p["nombre"] for p in PAGINAS}

# --- Navegación: página actual + historial para "Regresar" ---
st.session_state.setdefault("pagina", "inicio")
st.session_state.setdefault("historial", [])


def ir(pagina: str) -> None:
    st.session_state.historial.append(st.session_state.pagina)
    st.session_state.pagina = pagina


def regresar() -> None:
    st.session_state.pagina = st.session_state.historial.pop()


def inicio() -> None:
    st.session_state.pagina = "inicio"
    st.session_state.historial = []


pagina = st.session_state.pagina

# --- Encabezado ---
miga = "<li>Inicio</li>" if pagina == "inicio" else f"<li>Inicio</li><li>{NOMBRES[pagina]}</li>"
st.markdown(
    f"""
<header class="encabezado-portal">
  <p class="institucion"><strong>Portal de Transparencia</strong>H. Ayuntamiento de Hermosillo</p>
</header>
<nav class="migas" aria-label="Ruta de navegación"><ol>{miga}</ol></nav>
""",
    unsafe_allow_html=True,
)


def tarjeta(p: dict) -> None:
    with st.container(border=True, key=f"tarjeta_{p['id']}"):
        st.markdown(
            f"""
<div class="tarjeta-banda"><div class="tarjeta-icono"><i class="mdi {p['icono']}" aria-hidden="true"></i></div></div>
<h3 class="tarjeta-titulo">{p['nombre']}</h3>
<p class="tarjeta-descripcion">{p['descripcion']}</p>
""",
            unsafe_allow_html=True,
        )
        st.button("Ver información →", key=f"ver_{p['id']}", on_click=ir, args=(p["id"],))


def pagina_inicio() -> None:
    st.markdown('<h2 class="titulo-portal">Transparencia Proactiva</h2>', unsafe_allow_html=True)
    for fila in range(0, len(PAGINAS), 3):
        for columna, p in zip(st.columns(3, gap="large"), PAGINAS[fila : fila + 3]):
            with columna:
                tarjeta(p)


def pagina_pendiente(nombre: str) -> None:
    st.markdown(
        f"""
<h2 class="titulo-portal">{nombre}</h2>
<div class="aviso" role="note"><p><strong>Sección en construcción.</strong> Pronto encontrarás aquí esta información.</p></div>
""",
        unsafe_allow_html=True,
    )


PAGINAS_ACTIVAS = {
    "presupuesto": pagina_presupuesto.mostrar,
    "sueldos": pagina_sueldos.mostrar,
    "adjudicaciones": pagina_adjudicaciones.mostrar,
    "padron_beneficiarios": pagina_padron.mostrar,
    "normativo": pagina_normativo.mostrar,
}

if pagina == "inicio":
    pagina_inicio()
elif pagina in PAGINAS_ACTIVAS:
    PAGINAS_ACTIVAS[pagina]()
else:
    pagina_pendiente(NOMBRES[pagina])

# --- Pie de página del portal ---
st.markdown(
    """
<footer class="pie-portal">
  <p><strong>H. Ayuntamiento de Hermosillo</strong></p>
  <p>Unidad de Transparencia Municipal</p>
</footer>
""",
    unsafe_allow_html=True,
)

# --- Barra fija inferior ---
with st.container(key="barra_nav", horizontal=True):
    st.button(
        "← Regresar", key="btn_regresar", on_click=regresar,
        disabled=not st.session_state.historial,
    )
    st.button("Inicio", key="btn_inicio", type="primary", on_click=inicio, icon=":material/home:")
