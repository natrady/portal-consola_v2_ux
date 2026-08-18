import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
# Aquí luego importaremos gspread y oauth cuando conectemos la BD

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS MÓVILES (UX/UI)
# ==========================================
st.set_page_config(page_title="Portal Consola 2.0", page_icon="💻", layout="wide")

st.markdown("""
    <style>
    /* Fondo general */
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #161a1d; }
    
    /* Tarjetas limpias para celular */
    .mobile-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        margin-bottom: 15px;
    }
    
    /* Detalles de color institucional */
    .border-tinto { border-left: 4px solid #9b2247; }
    .border-verde { border-left: 4px solid #1e5b4f; }
    .border-dorado { border-left: 4px solid #a57f2c; }
    
    /* Forzar que las métricas destaquen */
    [data-testid="stMetricValue"] { color: #9b2247; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. DICCIONARIOS Y CATÁLOGOS MAESTROS
# ==========================================
# Actualizado con las nuevas regiones 2026
mapa_regiones = {
    "Centro Oriente": "CO", "CO": "CO",
    "Noreste Centro": "NC", "NC": "NC",
    "Noroeste": "No", "No": "No",
    "Pacífico Occidente": "PO", "PO": "PO",
    "Sur Sureste": "SS", "SS": "SS",
    "AD": "AD", "Apoyo": "Apoyo"
}

opciones_regiones_limpias = ["CO", "NC", "No", "PO", "SS", "AD", "Apoyo"]
opciones_modulos = ["RE", "BB", "CT", "TCH", "Actividad Especial", "Apoyo", "Vacaciones", "Incapacidad"]

# ==========================================
# 3. BARRA LATERAL (NAVEGACIÓN)
# ==========================================
st.sidebar.title("🎭 Consola 2.0")
st.sidebar.caption("Modo Coordinador / Admin")
st.sidebar.divider()

# Simplificamos el menú para ir construyendo uno por uno
menu = st.sidebar.radio("Módulos:", [
    "🗺️ Distribución", 
    "📊 Monitoreo de Equipo", 
    "📈 Tablero Gerencial"
])

st.sidebar.divider()
st.sidebar.info("Usuario prueba: Admin") # Luego lo conectamos al Anillo de Poder

# ==========================================
# 4. MÓDULOS (ESQUELETOS)
# ==========================================
if menu == "🗺️ Distribución":
    st.title("🗺️ Distribución Operativa")
    st.markdown("Asigna el trabajo de tu región de forma rápida.")
    
    with st.container():
        st.markdown('<div class="mobile-card border-tinto">AQUÍ CONSTRUIREMOS EL FORMULARIO DE ASIGNACIÓN MÓVIL</div>', unsafe_allow_html=True)

elif menu == "📊 Monitoreo de Equipo":
    st.title("📊 Monitoreo de Equipo")
    st.markdown("Revisa productividad, pausas y capturas de pantalla de tu equipo.")
    
    with st.container():
        st.markdown('<div class="mobile-card border-verde">AQUÍ CONSTRUIREMOS LOS FILTROS DE FECHA Y RENDIMIENTO INDIVIDUAL</div>', unsafe_allow_html=True)

elif menu == "📈 Tablero Gerencial":
    st.title("📈 Tablero Gerencial")
    st.markdown("Visión global de volumetría.")
    
    with st.container():
        st.markdown('<div class="mobile-card border-dorado">AQUÍ TRAEREMOS EL PASTEL Y LAS BARRAS ADAPTADAS A MÓVIL</div>', unsafe_allow_html=True)
