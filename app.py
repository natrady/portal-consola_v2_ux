import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json
import requests #<-- Librería
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
st.set_page_config(page_title="Portal Consola", page_icon="💻", layout="wide")

st.markdown("""
    <style>
    /* Ocultar barra superior (GitHub) y botón de Manage App */
    [data-testid="stHeader"] {display: none;}
    .viewerBadge_container {display: none;}
    
    .stApp { background-color: #f1f2f2; }
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
opciones_modulos = ["RE", "BB", "CT", "TCH", "Actividad Especial", "Irregularidades 4CH", "Apoyo", "Vacaciones", "Incapacidad"]

# Catálogo geográfico duro para los desplegables
estados_por_region = {
    "CO": ["Ciudad de México", "México", "Morelos", "Puebla", "Tlaxcala"],
    "NC": ["Coahuila de Zaragoza", "Hidalgo", "Nuevo León", "Querétaro", "San Luis Potosí", "Tamaulipas", "Veracruz"],
    "No": ["Aguascalientes", "Baja California", "Baja California Sur", "Chihuahua", "Durango", "Sinaloa", "Sonora", "Zacatecas"],
    "PO": ["Colima", "Guanajuato", "Guerrero", "Jalisco", "Michoacán de Ocampo", "Nayarit"],
    "SS": ["Campeche", "Chiapas", "Oaxaca", "Quintana Roo", "Tabasco", "Yucatán"]
}

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
        
        # Blindaje 3: Limpiar Región (Ss -> SS)
        if 'Región' in df.columns:
            df['Región'] = df['Región'].astype(str).str.strip()
            df['Región'] = df['Región'].replace({'Ss': 'SS', 'Sur Sureste': 'SS'})
        
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

@st.cache_data(ttl=120, show_spinner="Cargando Histórico...")
def cargar_distribuciones():
    if not gc: return pd.DataFrame()
    try:
        hoja = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribuir_Modulos")
        datos = hoja.get_all_values()
        if len(datos) < 2: return pd.DataFrame(columns=["Fecha", "Región", "Nombre", "Módulo", "Estado", "Municipios", "Instrucciones"])
        df = pd.DataFrame(datos[1:], columns=datos[0])
        return df
    except Exception as e:
        st.error(f"🚨 Error leyendo Distribuir_Modulos: {e}")
        return pd.DataFrame(columns=["Fecha", "Región", "Nombre", "Módulo", "Estado", "Municipios", "Instrucciones"])

@st.cache_data(ttl=60, show_spinner=False)
def leer_estrategias_nube():
    if not gc: return {}, {}
    try:
        hoja = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
        try: est = json.loads(hoja.acell('B1').value)
        except: est = {}
        try: plant = json.loads(hoja.acell('B2').value)
        except: plant = {}
        return est, plant
    except:
        return {}, {}

# ==========================================
# 2.5. CADENERO (LOGIN CON GOOGLE)
# ==========================================
if 'usuario_correo' not in st.session_state:
    # 1. Si regresamos de Google, checamos si traemos un código en la URL
    if 'code' in st.query_params:
        try:
            code = st.query_params['code']
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": st.secrets["google_oauth"]["client_id"],
                "client_secret": st.secrets["google_oauth"]["client_secret"],
                "redirect_uri": st.secrets["google_oauth"]["redirect_uri"],
                "grant_type": "authorization_code",
            }
            res = requests.post(token_url, data=data)
            
            if res.status_code == 200:
                access_token = res.json().get("access_token")
                user_res = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
                if user_res.status_code == 200:
                    st.session_state.usuario_correo = user_res.json().get("email")
                    st.session_state.usuario_nombre = user_res.json().get("name", "Usuario")
            
            # CRÍTICO: Esto debe estar a la misma altura exacta que el 'if' de arriba.
            st.query_params.clear()
            st.rerun()
            
        except Exception as e:
            st.error(f"🚨 Error de conexión con Google: {e}")
            st.query_params.clear()
            st.rerun()

    # 2. Si no hay sesión ni código, cerramos la puerta y mostramos el botón
    correo_puerta = st.session_state.get('usuario_correo', '')
    if not correo_puerta or str(correo_puerta).strip() == '':
        st.title("🔒 Portal Consola 2.0")
        st.info("Acceso restringido. Por favor, identifícate con tu cuenta autorizada.")
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={st.secrets['google_oauth']['client_id']}&redirect_uri={st.secrets['google_oauth']['redirect_uri']}&response_type=code&scope=openid%20email%20profile&prompt=select_account"
        
        # CRÍTICO: Usamos target="_blank". Streamlit bloquea target="_top" por la seguridad de su iframe.
        html_boton = f'<div style="text-align: center; margin-top: 30px;"><a href="{auth_url}" target="_blank" style="display: inline-block; background-color: #1e5b4f; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-size: 16px; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">🔑 Entrar con Google</a></div>'
        st.markdown(html_boton, unsafe_allow_html=True)
        st.stop() # DETENEMOS LA EJECUCIÓN AQUÍ. 

@st.cache_data(ttl=300, show_spinner=False)
def obtener_permisos(correo):
    if not gc: return None, None
    try:
        hoja = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Usuarios_App")
        datos = hoja.get_all_values() # Blindaje: get_all_values no crashea con columnas vacías
        if len(datos) > 1:
            cabeceras = [str(c).strip() for c in datos[0]]
            idx_correo = cabeceras.index("Correo") if "Correo" in cabeceras else -1
            idx_estatus = cabeceras.index("Estatus") if "Estatus" in cabeceras else -1
            idx_nivel = cabeceras.index("Nivel") if "Nivel" in cabeceras else -1
            idx_modulos = cabeceras.index("Módulos") if "Módulos" in cabeceras else -1
            
            if idx_correo == -1 or idx_estatus == -1: return None, None
            
            for fila in datos[1:]:
                # Evitar IndexError si la fila está incompleta
                if len(fila) > idx_correo and str(fila[idx_correo]).strip().lower() == correo.lower():
                    if len(fila) > idx_estatus and str(fila[idx_estatus]).strip() == "Activo":
                        nivel = str(fila[idx_nivel]).strip() if idx_nivel != -1 and len(fila) > idx_nivel else ""
                        modulos = str(fila[idx_modulos]).strip() if idx_modulos != -1 and len(fila) > idx_modulos else ""
                        return nivel, modulos
        return None, None
    except Exception as e:
        st.sidebar.error(f"🚨 Error leyendo permisos: {e}")
        return None, None
# ==========================================
# 3. BARRA LATERAL (NAVEGACIÓN)
# ==========================================
with st.sidebar:
    st.title("🎭 Consola 2.0")
    # CRÍTICO: Programación defensiva con .get() para evitar AttributeError si se borra la caché
    nombre_mostrar = st.session_state.get("usuario_nombre", "Usuario")
    st.caption(f"👤 Hola, {nombre_mostrar}")

    # Validar permisos en base de datos
    correo_actual = st.session_state.get("usuario_correo", "")
    nivel_user, modulos_user = obtener_permisos(correo_actual)

    # 👑 PUERTA TRASERA (Fail-Safe Anti-Bloqueos para Nax)
    if correo_actual.lower() == "natrady.mr@gmail.com":
        nivel_user = "Completo"
        modulos_user = "Todos"

    if not nivel_user:
        st.error(f"🚫 Acceso denegado para el correo: '{correo_actual}'. No estás registrado o estás inactivo.")
        if st.button("Cerrar Sesión"):
            st.query_params.clear() # 1. Matamos el código zombi de la URL
            try:
                cookie_manager.delete("portal_usuario") # 2. Matamos galletas residuales
            except:
                pass
            st.session_state.clear() # 3. Pulverizamos la memoria
            st.rerun()
        st.stop()
        
    st.caption(f"🛡️ Nivel: {nivel_user}")
    st.divider()
    
    # Construcción dinámica del menú según permisos (Programación defensiva)
    opciones_menu = []
    if nivel_user in ["Completo", "Admin"] or "Todos" in modulos_user or "Distribución" in modulos_user:
        opciones_menu.append("🗺️ Distribución")
        opciones_menu.append("📍 Mi Región")
        
    # NUEVO MÓDULO: Mi Equipo (Visible para Coordis, Admins y Completo)
    if nivel_user in ["Completo", "Admin", "Coordinador"] or "Todos" in modulos_user or "Equipo" in modulos_user:
        opciones_menu.append("👥 Mi Equipo")
        
    if nivel_user in ["Completo", "Admin"] or "Todos" in modulos_user or "Monitoreo" in modulos_user:
        opciones_menu.append("📊 Monitoreo de Equipo")
    if nivel_user in ["Completo", "Admin"] or "Todos" in modulos_user or "Tablero" in modulos_user:
        opciones_menu.append("📈 Tablero Gerencial")
    if nivel_user == "Completo":
        opciones_menu.append("💍 Anillo de Poder")
        
    if not opciones_menu:
        st.warning("⚠️ Tu usuario no tiene módulos asignados.")
        st.stop()
        
    menu = st.radio("Módulos:", opciones_menu)
    
    st.divider()
    if st.button("🚪 Salir", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==========================================
# 4. LÓGICA PRINCIPAL POR MÓDULO
# ==========================================
if menu == "🗺️ Distribución":
    st.title("🗺️ Distribución Operativa")
    
    if df_global.empty:
        st.warning("⚠️ No se cargó la base de personal. Revisa la conexión a Google Sheets.")
    else:
        # 1. UX: Controles fijos inyectados en la barra lateral
        with st.sidebar:
            st.divider()
            st.markdown("### 📌 Controles de Distribución")
            if 'fecha_dist' not in st.session_state:
                st.session_state.fecha_dist = datetime.datetime.now().date() + datetime.timedelta(days=1)
                
            fecha_sel = st.date_input("📅 Fecha a asignar:", value=st.session_state.fecha_dist)
            st.session_state.fecha_dist = fecha_sel
            region_sel = st.selectbox("📍 Región a trabajar:", opciones_regiones_limpias)

        st.markdown(f"**📍 Trabajando en:** {region_sel} | **📅 Fecha:** {fecha_sel.strftime('%d/%m/%Y')}")
        st.divider()

        # 2. Recálculo dinámico de disponibilidad basado en la fecha elegida
        def recalcular_disp(fila):
            if pd.notna(fila.get('Inicio incidencia')) and pd.notna(fila.get('Fin Incidencia')):
                if fila['Inicio incidencia'] <= fecha_sel <= fila['Fin Incidencia']: return "No"
            return "Si"
            
        df_global['Disponibles_Hoy'] = df_global.apply(recalcular_disp, axis=1)

        df_operativos = df_global[(df_global['Rol'] == 'Verificador') & (df_global['Disponibles_Hoy'] == 'Si') & (~df_global['Región'].isin(['AD', 'Apoyo']))]
        conteo_regiones = df_operativos['Región'].value_counts()
        limite_minimo = int(conteo_regiones.min()) if not conteo_regiones.empty else 0
        
        # ==========================================
        # MODO 3: ESTRATEGIA GLOBAL (SOLO PARA AD)
        # ==========================================
        if region_sel == "AD":
            st.subheader("Distribución Administrativa")
            
            # Mostramos el personal disponible por región con métricas limpias
            cols_disp = st.columns(len(conteo_regiones))
            for i, (reg, qty) in enumerate(conteo_regiones.items()):
                cols_disp[i].metric(reg, qty)
            st.caption(f"💡 Tu tope máximo para posiciones fijas es **{limite_minimo}** (la región más pequeña).")
            
            # Memoria: Leemos desde la caché para no bombardear a Google
            estrategias_bd, _ = leer_estrategias_nube()
            est_hoy = estrategias_bd.get(str(st.session_state.fecha_dist), {})
                
            tipo_estrategia = st.radio("Tipo de Estrategia:", ["Asignar a TODOS a un solo módulo", "Repartir posiciones fijas"], horizontal=True)
            
            with st.container():
                st.markdown('<div class="mobile-card border-dorado">', unsafe_allow_html=True)
                if tipo_estrategia == "Asignar a TODOS a un solo módulo":
                    mod_todos = st.selectbox("🎯 Módulo para toda la plantilla:", ["RE", "BB", "CT", "TCH", "Actividad Especial", "Irregularidades 4CH"])
                    st.success(f"Configuración lista: El 100% de los verificadores disponibles irán a {mod_todos}.")
                    
                    if st.button("💾 Guardar Estrategia Global", type="primary", use_container_width=True):
                        estrategia = {
                            "fecha": str(st.session_state.fecha_dist),
                            "mensaje": f"Buenas tardes. La distribución para mañana es la siguiente: toda la plantilla a {mod_todos}.",
                            "re": 0, "bb": 0, "ct": 0, "tch": 0, "4ch": 0, "resto": mod_todos
                        }
                        try:
                            hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                            estrategias_bd, _ = leer_estrategias_nube()
                            estrategias_bd[str(st.session_state.fecha_dist)] = estrategia
                            
                            hoja_est.update_acell('A1', 'Estrategias_JSON')
                            hoja_est.update_acell('B1', json.dumps(estrategias_bd))
                            leer_estrategias_nube.clear() # Limpiamos caché
                            st.success("✅ ¡Estrategia guardada en la nube!")
                            st.info(f"**Mensaje Oficial:**\n{estrategia['mensaje']}")
                        except Exception as e:
                            st.error(f"🚨 Error: Asegúrate de renombrar la pestaña a 'Distribución' en Sheets. Detalle: {e}")
                    
                else:
                    st.markdown("**Posiciones Fijas:**")
                    # Forzamos 5 columnas para que quepan todos los módulos
                    c1, c2, c3, c4, c5 = st.columns(5)
                    # Usamos est_hoy para recordar el número, si no hay, pone 0
                    q_re = c1.number_input("RE", min_value=0, max_value=limite_minimo, value=int(est_hoy.get('re', 0)), step=1)
                    q_bb = c2.number_input("BB", min_value=0, max_value=limite_minimo, value=int(est_hoy.get('bb', 0)), step=1)
                    q_ct = c3.number_input("CT", min_value=0, max_value=limite_minimo, value=int(est_hoy.get('ct', 0)), step=1)
                    q_tch = c4.number_input("TCH", min_value=0, max_value=limite_minimo, value=int(est_hoy.get('tch', 0)), step=1)
                    q_4ch = c5.number_input("4CH", min_value=0, max_value=limite_minimo, value=int(est_hoy.get('4ch', 0)), step=1)
                    
                    total_asignados = q_re + q_bb + q_ct + q_tch + q_4ch
                    lugares_libres = limite_minimo - total_asignados
                    
                    # Lógica excluyente para "El resto"
                    opciones_resto = ["RE", "BB", "CT", "TCH", "Actividad Especial", "Irregularidades 4CH"]
                    if q_re > 0 and "RE" in opciones_resto: opciones_resto.remove("RE")
                    if q_bb > 0 and "BB" in opciones_resto: opciones_resto.remove("BB")
                    if q_ct > 0 and "CT" in opciones_resto: opciones_resto.remove("CT")
                    if q_tch > 0 and "TCH" in opciones_resto: opciones_resto.remove("TCH")
                    if q_4ch > 0 and "Irregularidades 4CH" in opciones_resto: opciones_resto.remove("Irregularidades 4CH")
                    
                    st.markdown(f"**El resto ({lugares_libres} asignaciones dinámicas):**")
                    resto_a = st.selectbox("🎯 Los demás se irán a:", opciones_resto)
                    
                    if total_asignados > limite_minimo:
                        st.error(f"🚨 ¡Alto ahí! Asignaste {total_asignados} posiciones fijas, pero tu límite es {limite_minimo}. Reduce los números.")
                    elif total_asignados == 0:
                        st.warning(f"⚠️ Asignaste 0 fijos. Básicamente estás mandando a todos a {resto_a}.")
                    else:
                        st.success(f"Configuración válida. Los {lugares_libres} verificadores restantes se asignarán a {resto_a}.")
                        
                        partes = []
                        if q_tch > 0: partes.append(f"* Tercer Check: {q_tch} persona(s)")
                        if q_re > 0: partes.append(f"* Revisión de Expedientes: {q_re} persona(s)")
                        if q_bb > 0: partes.append(f"* BaBien: {q_bb} persona(s)")
                        if q_ct > 0: partes.append(f"* Centros de Trabajo: {q_ct} persona(s)")
                        if q_4ch > 0: partes.append(f"* Irregularidades 4CH: {q_4ch} persona(s)")
                        
                        texto_balas = "\n".join(partes)
                        resto_texto = "RE" if resto_a == "RE" else resto_a
                        mensaje_default = f"Buenas tardes. La distribución para mañana por región es la siguiente:\n{texto_balas}\n* Y el resto en {resto_texto}."
                        
                        st.markdown("**Mensaje Oficial (puedes editarlo antes de guardar):**")
                        mensaje_editable = st.text_area("Texto del mensaje", value=mensaje_default, height=180, label_visibility="collapsed")
                
                    if st.button("💾 Guardar Estrategia Oficial", type="primary", use_container_width=True, disabled=(total_asignados > limite_minimo)):
                        estrategia = {
                            "fecha": str(st.session_state.fecha_dist),
                            "mensaje": mensaje_editable,
                            "re": q_re, "bb": q_bb, "ct": q_ct, "tch": q_tch, "4ch": q_4ch, "resto": resto_a
                        }
                        try:
                            hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                            estrategias_bd, _ = leer_estrategias_nube()
                            estrategias_bd[str(st.session_state.fecha_dist)] = estrategia
                            
                            hoja_est.update_acell('A1', 'Estrategias_JSON')
                            hoja_est.update_acell('B1', json.dumps(estrategias_bd))
                            leer_estrategias_nube.clear() # Limpiamos caché
                            st.success("✅ ¡Estrategia y mensaje guardados en la nube correctamente!")
                        except Exception as e:
                            st.error(f"🚨 Error: Asegúrate de renombrar la pestaña a 'Distribución' en Sheets. Detalle: {e}")
                        
                st.markdown('</div>', unsafe_allow_html=True)

        # ==========================================
        # MODOS 1 Y 2: COORDIS OPERATIVOS
        # ==========================================
        else:
            # 1. Leemos caché (0 llamadas a la API si ya se leyó hace poco)
            estrategias_bd, plantillas_bd = leer_estrategias_nube()
            est_guardada = estrategias_bd.get(str(st.session_state.fecha_dist), {})
            
            if est_guardada.get("fecha") == str(st.session_state.fecha_dist):
                with st.expander(f"📜 Instrucción Administrativa para el {st.session_state.fecha_dist.strftime('%d/%m/%Y')}", expanded=False):
                    st.info(est_guardada.get('mensaje'))

            # 2. Filtramos el equipo usando Disponibles_Hoy
            df_region = df_global[(df_global['Región'] == region_sel) & (df_global['Rol'] == 'Verificador') & (df_global['Disponibles_Hoy'] == 'Si')].copy()
            
            if df_region.empty:
                st.info(f"No hay verificadores disponibles en la región {region_sel} para esta fecha.")
            else:
                st.subheader(f"👥 Equipo {region_sel} ({len(df_region)} personas)")
                
                # Leemos la tabla transaccional
                df_todas_dist = cargar_distribuciones()
                fecha_str = str(st.session_state.fecha_dist)
                fecha_ayer_str = str(st.session_state.fecha_dist - datetime.timedelta(days=1))
                
                df_dist_hoy = df_todas_dist[(df_todas_dist.get('Fecha') == fecha_str) & (df_todas_dist.get('Región') == region_sel)]
                
                # UX: Si hoy está vacío, damos la opción de clonar ayer
                if df_dist_hoy.empty and not df_todas_dist.empty:
                    df_dist_ayer = df_todas_dist[(df_todas_dist.get('Fecha') == fecha_ayer_str) & (df_todas_dist.get('Región') == region_sel)]
                    if not df_dist_ayer.empty:
                        if st.button("📋 Copiar distribución de ayer", use_container_width=True):
                            for _, f_ayer in df_dist_ayer.iterrows():
                                idx_persona = df_region.index[df_region['Nombre'] == f_ayer.get('Nombre')].tolist()
                                if idx_persona:
                                    idx_p = idx_persona[0]
                                    st.session_state[f"mod_{idx_p}"] = f_ayer.get('Módulo', 'RE')
                                    st.session_state[f"est_{idx_p}"] = str(f_ayer.get('Estado', 'Barrido')).split(', ')
                                    st.session_state[f"mun_{idx_p}"] = [m.strip() for m in str(f_ayer.get('Municipios', '')).split(', ') if m.strip()]
                                    st.session_state[f"notas_{idx_p}"] = f_ayer.get('Instrucciones', '')
                            # Simulamos una tirada de dados manual para forzar la actualización
                            st.session_state[f'dados_{region_sel}'] = dict(zip(df_dist_ayer['Nombre'], df_dist_ayer['Módulo']))
                            st.rerun()

                dict_dados = st.session_state.get(f'dados_{region_sel}', {})
                
                # Validación matemática contra la estrategia global (Visible para todas las pestañas)
                if dict_dados:
                    try:
                        estrategia = estrategias_bd.get(str(st.session_state.fecha_dist), {})
                        
                        if estrategia:
                            fijos = sum([estrategia.get('re',0), estrategia.get('bb',0), estrategia.get('ct',0), estrategia.get('tch',0), estrategia.get('4ch',0)])
                            libres = max(0, len(df_region) - fijos)
                            ideal = {"RE": estrategia.get('re',0), "BB": estrategia.get('bb',0), "CT": estrategia.get('ct',0), "TCH": estrategia.get('tch',0), "Irregularidades 4CH": estrategia.get('4ch',0), "Actividad Especial": 0, "Apoyo": 0}
                            resto_mod = estrategia.get('resto', 'RE')
                            if resto_mod in ideal: ideal[resto_mod] += libres
                                
                            from collections import Counter
                            real = Counter(dict_dados.values())
                            
                            if any(ideal[mod] != real.get(mod, 0) for mod in ideal.keys()):
                                with st.expander("⚠️ La distribución actual descuadra con la estrategia administrativa (Clic para ver detalles)", expanded=True):
                                    html_balance = "<table style='width:100%; font-size:14px; text-align:center; border-collapse: collapse; margin-bottom:15px;'><tr style='border-bottom: 2px solid #e9ecef; color:#161a1d;'><th>Módulo</th><th>Indicados</th><th>Asignados</th><th>Estatus</th></tr>"
                                    for mod, meta in ideal.items():
                                        if meta > 0 or real.get(mod, 0) > 0: 
                                            asignados = real.get(mod, 0)
                                            icono = "✅" if asignados == meta else "❌"
                                            color = "#1e5b4f" if asignados == meta else "#9b2247"
                                            html_balance += f"<tr style='color: {color}; border-bottom: 1px solid #f8f9fa;'><td><b>{mod}</b></td><td>{meta}</td><td>{asignados}</td><td>{icono}</td></tr>"
                                    html_balance += "</table>"
                                    st.markdown(html_balance, unsafe_allow_html=True)
                    except:
                        pass
                        
                tab_dados, tab_lotes, tab_manual, tab_modalidad = st.tabs(["🎲 Dados Estratégicos", "📦 Por Lotes", "✍️ Uno a Uno", "🏢 Modalidad"])
                
                # --- LECTURA DE REGLAS DE REGIÓN ---
                reglas_region_dict = {} 
                try:
                    hoja_reglas = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Reglas_Region")
                    datos_reglas = hoja_reglas.get_all_values()
                    if len(datos_reglas) > 1:
                        for fila in datos_reglas[1:]:
                            if len(fila) >= 5 and str(fila[0]).strip() == region_sel:
                                # Clave: Estado, Valor: Info
                                reglas_region_dict[str(fila[1]).strip()] = {"Municipios": fila[2], "Etiqueta": fila[3], "Anotaciones": fila[4]}
                except Exception: pass
                
                # Reordenamos: Focalizados van primero
                estados_base = estados_por_region.get(region_sel, [])
                estados_focalizados = [e for e in estados_base if reglas_region_dict.get(e, {}).get("Etiqueta") == "Focalizado"]
                estados_resto = [e for e in estados_base if e not in estados_focalizados]
                
                estados_disponibles = ["Barrido"] + estados_focalizados + estados_resto
                modulos_operativos = ["RE", "BB", "CT", "TCH", "Actividad Especial", "Irregularidades 4CH", "Apoyo"]
                municipios_dummy = ["Capital", "Zona Norte", "Zona Sur", "Focalizado A", "Focalizado B"]
                
                with tab_modalidad:
                    st.markdown("### 🏢 Planeación de Modalidad (Oficina vs Home Office)")
                    st.caption("Por defecto, todo el personal está en Home Office (🏠). Asigna quiénes asistirán a la oficina (🏢).")
                    
                    col_m1, col_m2 = st.columns([1, 2])
                    with col_m1:
                        lugares_ofi = st.number_input("Lugares en oficina:", min_value=0, value=5, help="Capacidad máxima de tu región en sede.")
                    with col_m2:
                        rango_fechas = st.date_input("Selecciona fecha o rango a planear:", value=(st.session_state.fecha_dist, st.session_state.fecha_dist))
                        
                    if len(rango_fechas) == 2:
                        fecha_ini, fecha_fin = rango_fechas
                        dias_rango = [fecha_ini + datetime.timedelta(days=x) for x in range((fecha_fin-fecha_ini).days + 1)]
                        
                        nombres_region = df_region['Nombre'].tolist()
                        
                        # Mostramos el estado actual cruzando las fechas seleccionadas
                        resumen_modalidad = []
                        for nombre in nombres_region:
                            dias_ofi = []
                            for d in dias_rango:
                                str_d = str(d)
                                est_dia = estrategias_bd.get(str_d, {})
                                if nombre in est_dia.get('modalidad', []):
                                    dias_ofi.append(d.strftime('%d/%m'))
                            
                            if len(dias_ofi) == 0:
                                estado = "🏠 Home Office"
                                fechas_str = "-"
                            elif len(dias_ofi) == len(dias_rango):
                                estado = "🏢 Oficina"
                                fechas_str = "Todos los días seleccionados"
                            else:
                                estado = "🏢🏠 Mixto"
                                fechas_str = ", ".join(dias_ofi)
                                
                            resumen_modalidad.append({"Verificador": nombre, "Modalidad": estado, "Días en Oficina": fechas_str})
                        
                        st.dataframe(pd.DataFrame(resumen_modalidad), hide_index=True, use_container_width=True)
                        
                        st.divider()
                        st.markdown(f"**Asignar para el rango seleccionado ({len(dias_rango)} días):**")
                        van_a_oficina = st.multiselect("Selecciona quiénes ASISTIRÁN a la oficina:", nombres_region)
                        
                        if len(van_a_oficina) > lugares_ofi:
                            st.error(f"🚨 ¡Límite excedido! Seleccionaste a {len(van_a_oficina)} personas, pero solo tienes {lugares_ofi} lugares configurados.")
                        else:
                            if st.button("💾 Guardar Modalidad en la Nube", type="primary", use_container_width=True):
                                try:
                                    hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                                    for d in dias_rango:
                                        str_d = str(d)
                                        if str_d not in estrategias_bd:
                                            estrategias_bd[str_d] = {}
                                        estrategias_bd[str_d]['modalidad'] = van_a_oficina
                                        
                                    hoja_est.update_acell('A1', 'Estrategias_JSON')
                                    hoja_est.update_acell('B1', json.dumps(estrategias_bd))
                                    leer_estrategias_nube.clear() 
                                    st.success(f"✅ ¡Modalidad guardada correctamente para los {len(dias_rango)} días seleccionados!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"🚨 Error al guardar modalidad en Sheets: {e}")
                    elif len(rango_fechas) == 1:
                        st.info("Selecciona la fecha de fin (haz clic de nuevo en el calendario) para confirmar el rango.")

                with tab_dados:
                    st.caption("Tira los dados para aplicar la estrategia administrativa del día de forma Inteligente (considera estrellas y debilidades).")
                    st.markdown('<div class="mobile-card border-tinto">', unsafe_allow_html=True)
                    if st.button("🎲 Tirar los Dados Inteligentes", type="primary", use_container_width=True):
                        try:
                            estrategia = estrategias_bd.get(str(st.session_state.fecha_dist), {})
                                
                            if estrategia.get("fecha") != str(st.session_state.fecha_dist):
                                st.warning(f"⚠️ No hay estrategia guardada para el {st.session_state.fecha_dist}.")
                            else:
                                import random
                                personas = df_region['Nombre'].tolist()
                                random.shuffle(personas)
                                
                                # 1. Armamos la bolsa de módulos disponibles según la estrategia
                                cubeta = []
                                for mod, qty in [("RE", estrategia.get("re", 0)), ("BB", estrategia.get("bb", 0)), 
                                                 ("CT", estrategia.get("ct", 0)), ("TCH", estrategia.get("tch", 0)), 
                                                 ("Irregularidades 4CH", estrategia.get("4ch", 0))]:
                                    cubeta.extend([mod] * qty)
                                
                                if len(cubeta) < len(personas):
                                    cubeta.extend([estrategia.get("resto", "RE")] * (len(personas) - len(cubeta)))
                                cubeta = cubeta[:len(personas)]
                                
                                # 2. Extraemos el talento y los miedos (Blindaje si están vacíos)
                                if 'Módulo Estrella' not in df_region.columns: df_region['Módulo Estrella'] = ""
                                if 'Módulo a Evitar' not in df_region.columns: df_region['Módulo a Evitar'] = ""
                                
                                estrellas = dict(zip(df_region['Nombre'], df_region['Módulo Estrella'].fillna('')))
                                debilidades = dict(zip(df_region['Nombre'], df_region['Módulo a Evitar'].fillna('')))
                                
                                asignaciones = {}
                                
                                # 3. Primera vuelta: Asignar a los Expertos ⭐
                                personas_sin_asignar = []
                                for p in personas:
                                    mod_estrellas_p = [m.strip() for m in str(estrellas.get(p, '')).split(',') if m.strip()]
                                    asignado = False
                                    random.shuffle(cubeta) # Mezclamos siempre
                                    
                                    for idx, mod_disponible in enumerate(cubeta):
                                        if mod_disponible in mod_estrellas_p:
                                            asignaciones[p] = cubeta.pop(idx)
                                            asignado = True
                                            break
                                    if not asignado:
                                        personas_sin_asignar.append(p)
                                
                                # 4. Segunda vuelta: Asignar evitando Debilidades ⚠️
                                for p in personas_sin_asignar:
                                    mod_evitar_p = [m.strip() for m in str(debilidades.get(p, '')).split(',') if m.strip()]
                                    asignado = False
                                    random.shuffle(cubeta)
                                    
                                    for idx, mod_disponible in enumerate(cubeta):
                                        if mod_disponible not in mod_evitar_p:
                                            asignaciones[p] = cubeta.pop(idx)
                                            asignado = True
                                            break
                                            
                                    # 5. Tercera vuelta: El trabajo llama (Si solo queda lo que odian, ni modo)
                                    if not asignado and cubeta:
                                        asignaciones[p] = cubeta.pop()
                                
                                st.session_state[f'dados_{region_sel}'] = asignaciones
                                
                                # CRÍTICO: Sobrescribir las llaves de los selectores manuales
                                for idx, row_p in df_region.iterrows():
                                    nombre_p = row_p.get('Nombre')
                                    if f"mod_{idx}" in st.session_state:
                                        st.session_state[f"mod_{idx}"] = asignaciones.get(nombre_p, "RE")
                                
                                st.success("🎲 ¡Dados Tirados! La estrategia fue optimizada con el talento del equipo.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"🚨 Error tirando los dados. ({e})")
                    
                    # Si ya tiraron los dados, mostramos la radiografía y el mensaje
                    if f'dados_{region_sel}' in st.session_state:
                        st.markdown("### 📋 Vista Previa de Asignación")
                        asignaciones_actuales = st.session_state[f'dados_{region_sel}']
                        
                        # ORDENAMIENTO: Primero por Módulo [1] y luego por Nombre de verificador [0] alfabéticamente
                        asignaciones_ordenadas = sorted(asignaciones_actuales.items(), key=lambda item: (item[1], item[0]))
                        
                        # Generamos una tabla HTML con UI pulida
                        html_tabla = "<table style='width:100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); font-family: sans-serif; font-size: 14px; margin-bottom: 20px;'><tr style='background-color: #9b2247; color: white; text-align: left;'><th style='padding: 12px 15px;'>Verificador</th><th style='padding: 12px 15px;'>Módulo Asignado</th><th style='padding: 12px 15px;'>Estado(s)</th><th style='padding: 12px 15px;'>Instrucciones</th></tr>"
                        
                        # Diccionario rápido para encontrar el índice (necesario para leer la sesión manual)
                        dict_indices = {row['Nombre']: idx for idx, row in df_region.iterrows()}
                        
                        for i, (persona, mod) in enumerate(asignaciones_ordenadas):
                            bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
                            idx_persona = dict_indices.get(persona, -1)
                            
                            # Leer valores actuales de la pestaña manual, si no hay, pone defaults limpios
                            estados_act = st.session_state.get(f"est_{idx_persona}", ["Barrido"])
                            estados_str = ", ".join(estados_act) if isinstance(estados_act, list) else estados_act
                            notas_act = st.session_state.get(f"notas_{idx_persona}", "")
                            
                            html_tabla += f"<tr style='background-color: {bg_color}; border-bottom: 1px solid #e9ecef;'><td style='padding: 10px 15px; color: #343a40;'>👤 {persona}</td><td style='padding: 10px 15px; color: #1e5b4f; font-weight: 600;'>{mod}</td><td style='padding: 10px 15px; color: #343a40;'>{estados_str}</td><td style='padding: 10px 15px; color: #6c757d; font-style: italic;'>{notas_act}</td></tr>"
                        html_tabla += "</table>"
                        st.markdown(html_tabla, unsafe_allow_html=True)
                        
                        # Lógica del borrador dinámico de WhatsApp usando CACHÉ
                        modulos_unicos = list(set(asignaciones_actuales.values()))
                        mods_str = ", ".join(modulos_unicos[:-1]) + f" y {modulos_unicos[-1]}" if len(modulos_unicos) > 1 else modulos_unicos[0]
                        
                        plantilla_default = f"Buenos días a tod@s 🍀\n\nEl día de hoy estaremos trabajando en los módulos de [MODULOS] en la Región {region_sel}.\n\nQue tengan una excelente jornada 😉"
                        plantilla_region = plantillas_bd.get(region_sel, plantilla_default)
                        
                        # Reemplazamos el comodín por los módulos reales de la tirada
                        borrador_final = plantilla_region.replace("[MODULOS]", mods_str)
                        
                        st.markdown("#### 📝 Borrador para WhatsApp")
                        # Eliminamos el 'key' de Streamlit para obligar al cuadro de texto a refrescarse con tu nueva plantilla
                        st.text_area("Copia el mensaje generado con la distribución de hoy:", value=borrador_final, height=180, label_visibility="collapsed")
                        
                        # Editor de Plantilla
                        with st.expander("⚙️ Editar mi machote base"):
                            st.caption("Usa la etiqueta exacta **[MODULOS]** donde quieras que se inserten automáticamente los módulos asignados ese día.")
                            nueva_plantilla = st.text_area("Edita el formato para tu región:", value=plantilla_region, height=180, key=f"template_{region_sel}")
                            
                            if st.button("💾 Guardar como mi machote default", use_container_width=True):
                                plantillas_bd[region_sel] = nueva_plantilla
                                try:
                                    hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                                    hoja_est.update_acell('A2', 'Plantillas_Mensajes')
                                    hoja_est.update_acell('B2', json.dumps(plantillas_bd))
                                    leer_estrategias_nube.clear() # Limpiamos caché
                                    st.success("✅ ¡Plantilla actualizada! Se usará para tus próximas distribuciones.")
                                    st.rerun() # Recargamos para que el cambio se vea inmediato
                                except Exception as e:
                                    st.error(f"Error al guardar en Sheets: {e}")

                    st.markdown('</div>', unsafe_allow_html=True)

                with tab_lotes:
                    st.caption("Asigna a múltiples verificadores al mismo tiempo.")
                    st.markdown('<div class="mobile-card border-verde">', unsafe_allow_html=True)
                    
                    mod_lote = st.selectbox("1️⃣ Selecciona el Módulo destino:", modulos_operativos, key="lote_mod")
                    
                    # Filtramos a la gente que NO tiene este módulo asignado para limpiar el multiselect
                    nombres_region = df_region['Nombre'].tolist()
                    gente_disponible = [n for n in nombres_region if dict_dados.get(n, "") != mod_lote]
                    
                    seleccionados = st.multiselect("2️⃣ Elige a los verificadores:", gente_disponible, key="lote_gente")
                    
                    if st.button("🚀 Aplicar a seleccionados", type="primary", use_container_width=True):
                        if seleccionados:
                            for persona in seleccionados:
                                dict_dados[persona] = mod_lote
                            st.session_state[f'dados_{region_sel}'] = dict_dados
                            
                            # CRÍTICO: Sobrescribir las llaves de los selectores manuales
                            for idx, row_p in df_region.iterrows():
                                nombre_p = row_p.get('Nombre')
                                if nombre_p in seleccionados and f"mod_{idx}" in st.session_state:
                                    st.session_state[f"mod_{idx}"] = mod_lote
                                    
                            st.rerun() # Reiniciamos para refrescar la validación y el formulario
                        else:
                            st.error("Debes seleccionar al menos a un verificador.")
                            
                    st.markdown('</div>', unsafe_allow_html=True)

                with tab_manual:
                    st.caption("Ajusta detalles individuales. Los cambios de Lotes y Dados se reflejarán aquí antes de guardar.")
                    
                    # dict_dados ya lo leemos arriba, pero el form lo usa directo desde session_state
                    with st.form("form_distribucion"):
                        for index, row in df_region.iterrows():
                            nombre = row.get('Nombre', 'Sin Nombre')
                            
                            # Prioridad 1: Resultado de los Dados o Ajuste Manual. Prioridad 2: Base de datos.
                            modulo_actual = dict_dados.get(nombre, row.get('Módulo', 'RE'))
                            
                            with st.expander(f"👤 {nombre} | 🏷️ {modulo_actual}"):
                                c1, c2 = st.columns(2)
                                with c1:
                                    idx_mod = modulos_operativos.index(modulo_actual) if modulo_actual in modulos_operativos else 0
                                    st.selectbox("Módulo:", modulos_operativos, index=idx_mod, key=f"mod_{index}")
                                    
                                    estados_seleccionados = st.multiselect("Estado(s):", estados_disponibles, default=["Barrido"], key=f"est_{index}")
                                    
                                    # Pintamos las alertas en tiempo real
                                    for est_sel in estados_seleccionados:
                                        if est_sel in reglas_region_dict:
                                            etq = reglas_region_dict[est_sel]['Etiqueta']
                                            nota = reglas_region_dict[est_sel]['Anotaciones']
                                            if etq == "No tocar":
                                                st.error(f"🚨 {est_sel} es 'No tocar'. ¿Seguro que quieres asignarlo? Razón: {nota}")
                                            elif etq == "Sospecha de gestoría":
                                                st.warning(f"⚠️ {est_sel}: Sospecha de gestoría. Precaución.")
                                            elif etq == "Focalizado":
                                                st.success(f"🎯 {est_sel} es Focalizado. Nota: {nota}")
                                                
                                with c2:
                                    # Extraer los municipios reales de los estados seleccionados cruzando con tu base de datos
                                    municipios_reales = []
                                    for est in estados_seleccionados:
                                        if est in reglas_region_dict:
                                            muni_str = str(reglas_region_dict[est].get("Municipios", ""))
                                            if muni_str and muni_str.lower() != "todos":
                                                # Separamos por comas por si metiste varios en una celda
                                                municipios_reales.extend([m.strip() for m in muni_str.split(",")])
                                                
                                    if not municipios_reales:
                                        municipios_reales = ["Selecciona un Estado específico"]
                                        
                                    # Usamos set() para quitar duplicados
                                    st.multiselect("Municipios:", sorted(list(set(municipios_reales))), key=f"mun_{index}")
                                    st.text_input("Prioridad / Instrucción extra:", key=f"notas_{index}", placeholder="Ej. Atender folios rezagados...")
                        
                        if st.form_submit_button("☁️ Guardar Distribución Definitiva", type="primary", use_container_width=True):
                            # 1. Recolectar lo que se movió a mano y guardarlo en memoria
                            nueva_dist = {}
                            for index, row in df_region.iterrows():
                                nombre = row.get('Nombre', 'Sin Nombre')
                                nueva_dist[nombre] = st.session_state[f"mod_{index}"]
                            
                            st.session_state[f'dados_{region_sel}'] = nueva_dist
                            
                            # 2. Empujar cambios a la pestaña 'Personal' (Batch Update Anti-DDoS)
                            # 2. Empujar cambios a la pestaña 'Distribuir_Modulos' (Guardado Transaccional)
                            try:
                                hoja_dist = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribuir_Modulos")
                                df_historico = cargar_distribuciones()
                                fecha_str = str(st.session_state.fecha_dist)
                                
                                # Limpiamos los datos previos de ESTA fecha y ESTA región para evitar duplicados
                                if not df_historico.empty:
                                    df_filtrado = df_historico[~((df_historico['Fecha'] == fecha_str) & (df_historico['Región'] == region_sel))]
                                else:
                                    df_filtrado = pd.DataFrame(columns=["Fecha", "Región", "Nombre", "Módulo", "Estado", "Municipios", "Instrucciones"])
                                    
                                # Armamos el dataframe con lo de hoy
                                nuevas_filas = []
                                for nom, info in datos_completos.items():
                                    nuevas_filas.append({
                                        "Fecha": fecha_str, "Región": region_sel, "Nombre": nom, 
                                        "Módulo": info["mod"], "Estado": info["est"], "Municipios": info["mun"], "Instrucciones": info["ins"]
                                    })
                                    
                                # Unimos la historia vieja con la info nueva y empujamos
                                df_final = pd.concat([df_filtrado, pd.DataFrame(nuevas_filas)], ignore_index=True)
                                df_final = df_final.fillna("") # Blindaje anti-nulos de Pandas
                                
                                matriz_guardar = [df_final.columns.tolist()] + df_final.astype(str).values.tolist()
                                hoja_dist.clear()
                                hoja_dist.update(values=matriz_guardar, range_name="A1")
                                
                                cargar_distribuciones.clear() # Limpiamos caché para forzar re-lectura
                                st.success("✅ ¡Distribución guardada oficialmente en el histórico transaccional!")
                            except Exception as e:
                                st.error(f"🚨 Error al guardar en Sheets: {e}")

                            st.rerun()
                            
elif menu == "💍 Anillo de Poder":
    st.title("💍 Anillo de Poder")
    st.markdown("Control maestro de la lista de invitados y sus permisos.")
    
    try:
        hoja_usuarios = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Usuarios_App")
        datos_usuarios = hoja_usuarios.get_all_values()
        
        if len(datos_usuarios) > 0:
            df_usuarios = pd.DataFrame(datos_usuarios[1:], columns=datos_usuarios[0])
            
            # --- UI Parte 1: Formulario de Alta (UX Limpia) ---
            st.markdown("### ➕ Agregar Nuevo Usuario")
            with st.form("form_nuevo_invitado", clear_on_submit=True):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    nuevo_correo = st.text_input("Correo Electrónico (Gmail) *", placeholder="ejemplo@gmail.com")
                    nuevo_nombre = st.text_input("Nombre Completo *", placeholder="Ej. Juan Pérez")
                with col_f2:
                    nuevo_nivel = st.selectbox("Nivel de Acceso *", ["Verificador", "Coordinador", "Administrativo", "Admin", "Completo"])
                    nuevo_modulos = st.text_input("Módulos Permitidos", value="Todos", help="Ej: Todos, o Distribución, Monitoreo")
                
                if st.form_submit_button("✉️ Agregar usuario", type="primary", use_container_width=True):
                    if nuevo_correo.strip() and nuevo_nombre.strip():
                        nueva_fila = [nuevo_correo.lower().strip(), nuevo_nombre.strip(), nuevo_nivel, nuevo_modulos, "Activo"]
                        hoja_usuarios.append_row(nueva_fila)
                        st.success(f"✅ ¡{nuevo_nombre} ha sido agregado al Anillo de Poder!")
                        st.rerun()
                    else:
                        st.error("🚨 Faltan campos obligatorios (Correo y Nombre).")
            
            st.divider()
            
            # --- UI Parte 2: Gestión de la tabla existente ---
            st.markdown("### 🛡️ Gestión de Permisos Actuales")
            st.caption("Cambia el nivel, los módulos o da de baja a los usuarios. El correo es la llave y no se puede editar aquí.")
            
            config_columnas = {
                "Correo": st.column_config.TextColumn("Correo (Llave)", disabled=True), # Blindaje: No cambiar correo
                "Nombre": st.column_config.TextColumn("Nombre completo"),
                "Nivel": st.column_config.SelectboxColumn("Nivel", options=["Completo", "Admin", "Administrativo", "Coordinador", "Verificador"], required=True),
                "Módulos": st.column_config.TextColumn("Módulos"),
                "Estatus": st.column_config.SelectboxColumn("Estatus", options=["Activo", "Baja"], required=True)
            }
            
            # Encerramos la tabla en una tarjeta visual
            st.markdown('<div class="mobile-card border-dorado">', unsafe_allow_html=True)
            df_editado = st.data_editor(df_usuarios, column_config=config_columnas, num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 Guardar Cambios en Accesos", type="secondary", use_container_width=True):
                df_editado = df_editado.fillna("")
                nuevos_valores = [df_editado.columns.tolist()] + df_editado.values.tolist()
                hoja_usuarios.clear()
                hoja_usuarios.update(values=nuevos_valores, range_name="A1")
                st.success("✅ Permisos actualizados en la base de datos.")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        else:
            st.warning("⚠️ La pestaña 'Usuarios_App' está vacía. Agrega los encabezados primero.")
    except Exception as e:
        st.error(f"🚨 Error de conexión o formato en Usuarios_App: {e}")

elif menu == "👥 Mi Equipo":
    st.title("👥 Gestión de Mi Equipo")
    st.markdown("Registra justificaciones y define las fortalezas y debilidades operativas de tus verificadores.")
    
    if df_global.empty:
        st.warning("⚠️ No se cargó la base de personal. Revisa la conexión a Google Sheets.")
    else:
        region_sel = st.selectbox("📍 Selecciona tu Región:", opciones_regiones_limpias)
        df_equipo = df_global[(df_global['Región'] == region_sel) & (df_global['Rol'] == 'Verificador')].copy()
        
        if df_equipo.empty:
            st.info(f"No hay verificadores registrados en la región {region_sel}.")
        else:
            # Blindaje estructural: Crear columnas en el df maestro si no existen
            if 'Observaciones' not in df_global.columns: df_global['Observaciones'] = ""
            if 'Módulo Estrella' not in df_global.columns: df_global['Módulo Estrella'] = ""
            if 'Módulo a Evitar' not in df_global.columns: df_global['Módulo a Evitar'] = ""
            
            # Limpiamos las opciones para quitar Vacaciones y Apoyo
            opciones_habilidades = [""] + [m for m in opciones_modulos if m not in ["Vacaciones", "Apoyo", "Incapacidad"]]
            
            # --- SECCIÓN 1: EDICIÓN INDIVIDUAL MANUAL ---
            st.markdown("### ✍️ Edición Individual")
            st.caption("Ajustes rápidos uno a uno. Usa las listas desplegables para mantener el orden de los datos.")
            
            # Recargamos la vista
            df_equipo_actualizado = df_global[(df_global['Región'] == region_sel) & (df_global['Rol'] == 'Verificador')].copy()
            columnas_vista = ['Nombre', 'Módulo Estrella', 'Módulo a Evitar', 'Observaciones']
            
            st.markdown('<div class="mobile-card border-verde">', unsafe_allow_html=True)
            df_editado = st.data_editor(
                df_equipo_actualizado[columnas_vista],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Nombre": st.column_config.TextColumn("Verificador", disabled=True),
                    "Módulo Estrella": st.column_config.SelectboxColumn("Módulo Estrella ⭐", options=opciones_habilidades),
                    "Módulo a Evitar": st.column_config.SelectboxColumn("Módulo a Evitar ⚠️", options=opciones_habilidades),
                    "Observaciones": st.column_config.TextColumn("Justificaciones / Notas 📝")
                }
            )
            
            if st.button("💾 Guardar Edición Individual", type="secondary", use_container_width=True):
                try:
                    df_global.set_index('Nombre', inplace=True)
                    df_editado.set_index('Nombre', inplace=True)
                    df_global.update(df_editado)
                    df_global.reset_index(inplace=True)
                    
                    hoja_personal = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Personal")
                    df_global_str = df_global.fillna("").astype(str)
                    matriz_cruda = [df_global_str.columns.tolist()] + df_global_str.values.tolist()
                    hoja_personal.clear()
                    hoja_personal.update(values=matriz_cruda, range_name="A1")
                    cargar_personal.clear()
                    st.success("✅ ¡Ediciones manuales guardadas exitosamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"🚨 Error al guardar en Sheets: {e}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.divider()

            # --- SECCIÓN 2: ASIGNACIÓN EN LOTE (OCULTA EN EXPANDER) ---
            with st.expander("⚡ Asignación en Lote (Múltiples verificadores)"):
                st.caption("Aplica observaciones o habilidades a varias personas de un solo golpe.")
                
                with st.form("form_lote_equipo", clear_on_submit=True):
                    nombres_equipo = df_equipo['Nombre'].tolist()
                    seleccionados = st.multiselect("1️⃣ Selecciona a los verificadores:", nombres_equipo)
                    
                    col_l1, col_l2 = st.columns(2)
                    with col_l1:
                        lote_fecha = st.date_input("📅 Fecha de la justificación:")
                        lote_obs = st.text_input("📝 Justificación / Observación General:")
                    with col_l2:
                        lote_estrellas = st.multiselect("⭐ Módulos Estrella (Expertos):", opciones_habilidades[1:])
                        lote_evitar = st.multiselect("⚠️ Módulos a Evitar (Poca exp.):", opciones_habilidades[1:])
                        
                    if st.form_submit_button("🚀 Aplicar a seleccionados", type="primary", use_container_width=True):
                        if seleccionados:
                            df_global.set_index('Nombre', inplace=True)
                            for persona in seleccionados:
                                if lote_obs: 
                                    nota_final = f"{lote_obs} ({lote_fecha.strftime('%d/%m')})"
                                    df_global.at[persona, 'Observaciones'] = nota_final
                                if lote_estrellas: df_global.at[persona, 'Módulo Estrella'] = ", ".join(lote_estrellas)
                                if lote_evitar: df_global.at[persona, 'Módulo a Evitar'] = ", ".join(lote_evitar)
                            df_global.reset_index(inplace=True)
                            
                            try:
                                hoja_personal = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Personal")
                                df_global_str = df_global.fillna("").astype(str)
                                matriz_cruda = [df_global_str.columns.tolist()] + df_global_str.values.tolist()
                                hoja_personal.clear()
                                hoja_personal.update(values=matriz_cruda, range_name="A1")
                                cargar_personal.clear()
                                st.success(f"✅ ¡Datos actualizados para {len(seleccionados)} personas!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"🚨 Error al guardar en Sheets: {e}")
                        else:
                            st.error("Debes seleccionar al menos a un verificador.")

elif menu == "📍 Mi Región":
    st.title("📍 Configuración de Mi Región")
    st.markdown("Define particularidades operativas para estados y municipios (Focalizados, No tocar, etc).")
    
    region_sel = st.selectbox("Selecciona tu Región:", opciones_regiones_limpias)
    estados_posibles = estados_por_region.get(region_sel, [])
    
    st.subheader("➕ Agregar Nueva Regla")
    with st.form("form_regla_region", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            estado_regla = st.selectbox("Estado *", estados_posibles)
            muni_regla = st.multiselect("Municipios", municipios_dummy, help="Déjalo vacío para aplicar a todo el estado.")
        with col2:
            etiqueta_regla = st.selectbox("Etiqueta *", ["Focalizado", "No tocar", "Sospecha de gestoría", "IA"])
            notas_regla = st.text_input("Anotaciones")
            
        if st.form_submit_button("Guardar Regla", type="primary", use_container_width=True):
            try:
                hoja_reglas = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Reglas_Region")
                muni_str = ", ".join(muni_regla) if muni_regla else "Todos"
                hoja_reglas.append_row([region_sel, estado_regla, muni_str, etiqueta_regla, notas_regla])
                st.success("✅ Regla agregada correctamente a la base de datos.")
                st.rerun()
            except gspread.exceptions.WorksheetNotFound:
                st.error("🚨 CRÍTICO: No existe la pestaña 'Reglas_Region' en tu Google Sheet. ¡Créala con los encabezados: Región, Estado, Municipios, Etiqueta, Anotaciones!")
            except Exception as e:
                st.error(f"🚨 Error de conexión: {e}")

    st.divider()
    st.subheader("📋 Reglas Activas")
    try:
        hoja_reglas = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Reglas_Region")
        datos_reglas = hoja_reglas.get_all_values()
        if len(datos_reglas) > 1:
            df_reglas = pd.DataFrame(datos_reglas[1:], columns=datos_reglas[0])
            df_reglas_region = df_reglas[df_reglas['Región'] == region_sel]
            st.dataframe(df_reglas_region, hide_index=True, use_container_width=True)
            st.caption("💡 Para borrar o editar una regla existente, modifícala directamente en tu Google Sheets por ahora.")
        else:
            st.info("No hay reglas registradas aún.")
    except Exception:
        st.info("Crea la pestaña 'Reglas_Region' en tu Google Sheet para ver la tabla aquí.")

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
