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

def _p(id_: str, nombre: str, descripcion: str, icono: str) -> dict:
    return {"id": id_, "nombre": nombre, "descripcion": descripcion, "icono": icono}


GRUPOS = [
    {
        "id": "dinero",
        "titulo": "¿En qué se gasta el dinero público?",
        "icono": ":material/payments:",
        "paginas": [
            _p("presupuesto", "Transparencia Presupuestaria Hermosillo",
               "Cuánto dinero aprobó el Ayuntamiento, cuánto ha gastado y en qué áreas.", "mdi-cash-multiple"),
            _p("sueldos", "Sueldos",
               "Remuneraciones del personal del Ayuntamiento por área, puesto y sexo.", "mdi-account-cash"),
            _p("multas_transito", "Ingresos por Multas de Tránsito",
               "Lo que recauda el municipio por infracciones de tránsito.", "mdi-car-emergency"),
            _p("parquimetros", "Ingresos por Parquímetros",
               "Lo que recauda el municipio por el uso de parquímetros.", "mdi-parking"),
            _p("financiamiento_agua", "Financiamiento Temporal Agua de Hermosillo",
               "Deuda y financiamiento temporal del organismo Agua de Hermosillo.", "mdi-bank"),
        ],
    },
    {
        "id": "compras",
        "titulo": "Compras, contratos y obras",
        "icono": ":material/handshake:",
        "paginas": [
            _p("licitaciones", "Licitaciones y Convocatorias",
               "Concursos abiertos y convocatorias para contratar con el Ayuntamiento.", "mdi-bullhorn"),
            _p("adjudicaciones", "Adjudicaciones",
               "Contratos, licitaciones y adjudicaciones directas del Ayuntamiento.", "mdi-file-sign"),
            _p("tu_obra", "Portal Tu Obra",
               "Obras públicas del municipio: dónde, cuánto cuestan y cómo avanzan.", "mdi-hard-hat"),
        ],
    },
    {
        "id": "gobierno",
        "titulo": "Gobierno y decisiones",
        "icono": ":material/account_balance:",
        "paginas": [
            _p("cabildo", "Cabildo",
               "Sesiones y acuerdos del Cabildo de Hermosillo.", "mdi-account-tie-voice"),
            _p("actas_ayuntamiento", "Actas Ayuntamiento",
               "Actas oficiales de las sesiones del Ayuntamiento.", "mdi-file-document-multiple"),
            _p("normativo", "Marco Normativo",
               "Leyes, reglamentos y lineamientos que rigen al Ayuntamiento.", "mdi-scale-balance"),
            _p("directorio", "Directorio",
               "Funcionarios del Ayuntamiento y cómo contactarlos.", "mdi-card-account-phone"),
            _p("transparencia_historico", "Transparencia Histórico",
               "Información de transparencia de años anteriores.", "mdi-history"),
        ],
    },
    {
        "id": "ciudad",
        "titulo": "Servicios y vida en la ciudad",
        "icono": ":material/location_city:",
        "paginas": [
            _p("bachometro", "Bachometro",
               "Reportes y reparación de baches en las calles.", "mdi-road-variant"),
            _p("red_ciclista", "Red Ciclista",
               "Ciclovías y rutas para moverse en bicicleta.", "mdi-bike"),
            _p("recoleccion_basura", "Recolección de Basura",
               "Rutas y horarios del servicio de recolección.", "mdi-delete-empty"),
            _p("wifi", "Puntos de WIFI-Hermosillo Crece Conectado",
               "Ubicación de los puntos de internet gratuito.", "mdi-wifi"),
        ],
    },
    {
        "id": "ambiente",
        "titulo": "Agua y medio ambiente",
        "icono": ":material/eco:",
        "paginas": [
            _p("calidad_agua", "Calidad del Agua",
               "Resultados de los análisis de calidad del agua potable.", "mdi-water-check"),
            _p("monitoreo_aire", "Sistema de Monitoreo de la Calidad del Aire",
               "Mediciones de la calidad del aire en la ciudad.", "mdi-weather-windy"),
            _p("remah", "REMAH: Programa de Gestión para Mejorar la Calidad del Aire",
               "Acciones del municipio para mejorar el aire que respiramos.", "mdi-leaf"),
        ],
    },
    {
        "id": "bienestar",
        "titulo": "Apoyos y bienestar",
        "icono": ":material/volunteer_activism:",
        "paginas": [
            _p("padron_beneficiarios", "Padrón de Beneficiarios",
               "Personas y grupos que reciben apoyos de los programas sociales municipales.", "mdi-account-group"),
            _p("espacios_deportivos", "Espacios y Actividades Deportivas H",
               "Unidades deportivas y actividades para la comunidad.", "mdi-soccer"),
            _p("bienestar_animal", "Instituto Municipal de Protección y Bienestar Animal",
               "Adopciones, esterilizaciones y protección de animales.", "mdi-paw"),
        ],
    },
    {
        "id": "seguridad",
        "titulo": "Seguridad y participación ciudadana",
        "icono": ":material/shield:",
        "paginas": [
            _p("videovigilancia", "Sistema de Videovigilancia Inteligente",
               "Cámaras de vigilancia para la seguridad de la ciudad.", "mdi-cctv"),
            _p("denuncias", "Denuncias, Quejas y Reconocimientos",
               "Presenta una denuncia, queja o reconocimiento a servidores públicos.", "mdi-message-alert"),
            _p("h_digital", "H Digital",
               "Trámites y servicios municipales en línea.", "mdi-cellphone-check"),
        ],
    },
]
NOMBRES = {p["id"]: p["nombre"] for g in GRUPOS for p in g["paginas"]}

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
    for g in GRUPOS:
        with st.expander(g["titulo"], icon=g["icono"], key=f"grupo_{g['id']}"):
            for fila in range(0, len(g["paginas"]), 3):
                for columna, p in zip(st.columns(3, gap="large"), g["paginas"][fila : fila + 3]):
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
