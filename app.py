import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 0. AUTENTICACIÓN GOOGLE CLOUD
# ==========================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    credenciales_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(credenciales_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"🚨 Error de autenticación. Revisa tus st.secrets en Streamlit Cloud. Detalle: {e}")
    gc = None

SHEET_PERSONAL_ID = "1WJ2v0IMmfd55hui5YLmDDJ8Hp8tVrdIP-mtb1kdaJXw"

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

@st.cache_data(ttl=600, show_spinner="Descargando Personal...")
def cargar_personal():
    if not gc: return pd.DataFrame()
    try:
        hoja = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Personal")
        # Extraemos crudo para burlar el error de gspread con columnas vacías
        datos = hoja.get_all_values()
        if len(datos) < 2: return pd.DataFrame()

        df = pd.DataFrame(datos[1:], columns=datos[0])
        
        # Blindaje 1: Forzar texto, limpiar espacios y saltos de línea en cabeceras
        df.columns = df.columns.astype(str).str.replace('\n', ' ').str.strip()
        # Blindaje 2: Eliminar columnas vacías ('') y columnas duplicadas
        df = df.loc[:, df.columns != '']
        df = df.loc[:, ~df.columns.duplicated()]
        
        # Mapeo de niveles a roles legibles
        mapa_niveles = {0: "Coordinador", 2: "Verificador", 3: "Administrativo"}
        df['Rol'] = pd.to_numeric(df.get('Nivel', 2), errors='coerce').map(mapa_niveles).fillna("Desconocido")
        
        # Limpieza de fechas y disponibilidad real
        hoy = datetime.datetime.now().date()
        if 'Inicio incidencia' in df.columns:
            df['Inicio incidencia'] = pd.to_datetime(df['Inicio incidencia'], errors='coerce').dt.date
        if 'Fin Incidencia' in df.columns:
            df['Fin Incidencia'] = pd.to_datetime(df['Fin Incidencia'], errors='coerce').dt.date
            
        def calc_disp(fila):
            if pd.notna(fila.get('Inicio incidencia')) and pd.notna(fila.get('Fin Incidencia')):
                if fila['Inicio incidencia'] <= hoy <= fila['Fin Incidencia']:
                    return "No"
            return "Si"
            
        df['Disponibles'] = df.apply(calc_disp, axis=1)
        return df
    except Exception as e:
        # Extraemos el tipo de error exacto para que no vuelva a salir en blanco
        st.error(f"🚨 Error leyendo Personal_DB: {type(e).__name__} - {str(e)}")
        return pd.DataFrame()

df_global = cargar_personal()
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
    
    if df_global.empty:
        st.warning("⚠️ No se cargó la base de personal. Revisa la conexión a Google Sheets.")
    else:
        # Extraemos las regiones operativas y calculamos su personal disponible
        df_operativos = df_global[(df_global['Rol'] == 'Verificador') & (df_global['Disponibles'] == 'Si') & (~df_global['Región'].isin(['AD', 'Apoyo']))]
        conteo_regiones = df_operativos['Región'].value_counts()
        limite_minimo = int(conteo_regiones.min()) if not conteo_regiones.empty else 0

        region_sel = st.selectbox("📍 Selecciona tu Región para trabajar:", opciones_regiones_limpias)
        st.divider()
        
        # ==========================================
        # MODO 3: ESTRATEGIA GLOBAL (SOLO PARA AD)
        # ==========================================
        if region_sel == "AD":
            st.subheader("👑 Configuración del Anillo de Poder (Dados)")
            st.info(f"💡 **Límite Operativo:** La región más pequeña tiene **{limite_minimo}** verificadores disponibles hoy. Ese es tu tope máximo para asignar plazas fijas.")
            
            tipo_estrategia = st.radio("Tipo de Estrategia:", ["Asignar a TODOS a un solo módulo", "Repartir posiciones fijas"], horizontal=True)
            
            with st.container():
                st.markdown('<div class="mobile-card border-dorado">', unsafe_allow_html=True)
                if tipo_estrategia == "Asignar a TODOS a un solo módulo":
                    mod_todos = st.selectbox("🎯 Módulo para toda la plantilla:", ["RE", "BB", "CT", "TCH", "Actividad Especial"])
                    st.success(f"Configuración lista: El 100% de los verificadores disponibles irán a {mod_todos}.")
                    
                else:
                    st.markdown("**Posiciones Fijas (No exceder el límite operativo):**")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    q_re = col1.number_input("RE", min_value=0, max_value=limite_minimo, value=0, step=1)
                    q_bb = col2.number_input("BB", min_value=0, max_value=limite_minimo, value=0, step=1)
                    q_ct = col3.number_input("CT", min_value=0, max_value=limite_minimo, value=0, step=1)
                    q_tch = col4.number_input("TCH", min_value=0, max_value=limite_minimo, value=0, step=1)
                    
                    total_asignados = q_re + q_bb + q_ct + q_tch
                    
                    st.markdown("**Comodín:**")
                    resto_a = st.selectbox("🔄 Los verificadores sobrantes se irán a:", ["RE", "BB", "CT", "TCH", "Actividad Especial"])
                    
                    if total_asignados > limite_minimo:
                        st.error(f"🚨 ¡Alto ahí! Asignaste {total_asignados} posiciones fijas, pero tu límite es {limite_minimo}. Reduce los números.")
                    elif total_asignados == 0:
                        st.warning(f"⚠️ Asignaste 0 fijos. Básicamente estás mandando a todos a {resto_a}.")
                    else:
                        st.success(f"Configuración válida. Quedan {limite_minimo - total_asignados} lugares libres para el comodín en la región más chica.")
                
                st.button("💾 Guardar Estrategia Global", type="primary", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

        # ==========================================
        # MODOS 1 Y 2: COORDIS OPERATIVOS
        # ==========================================
        else:
            df_region = df_global[(df_global['Región'] == region_sel) & (df_global['Rol'] == 'Verificador')].copy()
            
            if df_region.empty:
                st.info(f"No hay verificadores registrados en la región {region_sel}.")
            else:
                st.subheader(f"👥 Equipo {region_sel} ({len(df_region)} personas)")
                
                tab_manual, tab_lotes, tab_dados = st.tabs(["✍️ Uno a Uno", "📦 Por Lotes", "🎲 Dados Estratégicos"])
                
                with tab_manual:
                    st.caption("Ajusta detalles individuales. Los cambios de Lotes y Dados se reflejarán aquí antes de guardar.")
                    with st.form("form_distribucion"):
                        for index, row in df_region.iterrows():
                            nombre = row.get('Nombre', 'Sin Nombre')
                            modulo_actual = row.get('Módulo', 'RE')
                            
                            with st.expander(f"👤 {nombre} | 🏷️ {modulo_actual}"):
                                c1, c2 = st.columns(2)
                                with c1:
                                    idx_mod = opciones_modulos.index(modulo_actual) if modulo_actual in opciones_modulos else 0
                                    st.selectbox("Módulo:", opciones_modulos, index=idx_mod, key=f"mod_{index}")
                                    st.text_input("Estado:", key=f"est_{index}")
                                with c2:
                                    st.selectbox("Prioridad:", ["Ninguna", "1", "2", "3", "Urgente", "Especial"], key=f"prio_{index}")
                                    st.text_input("Municipio / Notas:", key=f"notas_{index}")
                        
                        st.form_submit_button("☁️ Guardar Distribución Definitiva", type="primary", use_container_width=True)

                with tab_lotes:
                    st.caption("Asigna a múltiples verificadores al mismo tiempo.")
                    st.markdown('<div class="mobile-card border-verde">AQUÍ PONDREMOS LOS SELECTORES MÚLTIPLES</div>', unsafe_allow_html=True)

                with tab_dados:
                    st.caption("Autocompletar usando la estrategia del Anillo de Poder.")
                    st.markdown('<div class="mobile-card border-tinto">AQUÍ LEEREMOS LA ESTRATEGIA AD Y REPARTIREMOS A LA GENTE</div>', unsafe_allow_html=True)

elif menu == "📊 Monitoreo de Equipo":                for index, row in df_region.iterrows():
                    nombre = row.get('Nombre', 'Sin Nombre')
                    modulo_actual = row.get('Módulo', 'RE')
                    
                    with st.expander(f"👤 {nombre} | 🏷️ {modulo_actual}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            idx_mod = opciones_modulos.index(modulo_actual) if modulo_actual in opciones_modulos else 0
                            st.selectbox("Módulo:", opciones_modulos, index=idx_mod, key=f"mod_{index}")
                            st.text_input("Estado:", key=f"est_{index}")
                        with col2:
                            st.selectbox("Prioridad:", ["Ninguna", "1", "2", "3", "Urgente", "Especial"], key=f"prio_{index}")
                            st.text_input("Municipio / Notas:", key=f"notas_{index}")
                
                submit_btn = st.form_submit_button("☁️ Guardar Distribución", type="primary", use_container_width=True)
                if submit_btn:
                    st.success("¡Asignaciones capturadas! (Aquí insertaremos la lógica de guardado a Sheets)")

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
