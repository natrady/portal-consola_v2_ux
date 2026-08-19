import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json

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
        # 1. Calendario con memoria (Session State)
        if 'fecha_dist' not in st.session_state:
            st.session_state.fecha_dist = datetime.datetime.now().date() + datetime.timedelta(days=1)
            
        fecha_sel = st.date_input("📅 ¿Para qué fecha es esta distribución?", value=st.session_state.fecha_dist)
        st.session_state.fecha_dist = fecha_sel

        # 2. Recálculo dinámico de disponibilidad basado en la fecha elegida
        def recalcular_disp(fila):
            if pd.notna(fila.get('Inicio incidencia')) and pd.notna(fila.get('Fin Incidencia')):
                # Si la fecha elegida cae dentro de sus vacaciones/incapacidad, no está disponible
                if fila['Inicio incidencia'] <= fecha_sel <= fila['Fin Incidencia']:
                    return "No"
            return "Si"
            
        df_global['Disponibles_Hoy'] = df_global.apply(recalcular_disp, axis=1)

        # Extraemos las regiones operativas y calculamos su personal disponible
        df_operativos = df_global[(df_global['Rol'] == 'Verificador') & (df_global['Disponibles_Hoy'] == 'Si') & (~df_global['Región'].isin(['AD', 'Apoyo']))]
        conteo_regiones = df_operativos['Región'].value_counts()
        limite_minimo = int(conteo_regiones.min()) if not conteo_regiones.empty else 0

        region_sel = st.selectbox("📍 Selecciona tu Región para trabajar:", opciones_regiones_limpias)
        st.divider()
        
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
            
            # Memoria: Intentamos leer si ya hay una estrategia guardada para pre-llenar los números
            try:
                hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                est_hoy = json.loads(hoja_est.acell('B1').value).get(str(st.session_state.fecha_dist), {})
            except:
                est_hoy = {}
                
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
                            try:
                                historico_json = json.loads(hoja_est.acell('B1').value)
                            except:
                                historico_json = {}
                            
                            historico_json[str(st.session_state.fecha_dist)] = estrategia
                            
                            hoja_est.update_acell('A1', 'Estrategias_JSON')
                            hoja_est.update_acell('B1', json.dumps(historico_json))
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
                            try:
                                historico_json = json.loads(hoja_est.acell('B1').value)
                            except:
                                historico_json = {}
                            
                            historico_json[str(st.session_state.fecha_dist)] = estrategia
                            
                            hoja_est.update_acell('A1', 'Estrategias_JSON')
                            hoja_est.update_acell('B1', json.dumps(historico_json))
                            st.success("✅ ¡Estrategia y mensaje guardados en la nube correctamente!")
                        except Exception as e:
                            st.error(f"🚨 Error: Asegúrate de renombrar la pestaña a 'Distribución' en Sheets. Detalle: {e}")
                        
                st.markdown('</div>', unsafe_allow_html=True)

        # ==========================================
        # MODOS 1 Y 2: COORDIS OPERATIVOS
        # ==========================================
        else:
            # 1. Leemos el mensaje desde Google Sheets (Pestaña "Distribución")
            try:
                hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                todas_estrategias = json.loads(hoja_est.acell('B1').value)
                est_guardada = todas_estrategias.get(str(st.session_state.fecha_dist), {})
                
                if est_guardada.get("fecha") == str(st.session_state.fecha_dist):
                    st.info(f"📜 **Instrucción Administrativa para el {st.session_state.fecha_dist.strftime('%d/%m/%Y')}:**\n\n{est_guardada.get('mensaje')}")
            except:
                pass # Si no hay archivo en la nube, no mostramos nada

            # 2. Filtramos el equipo usando Disponibles_Hoy
            df_region = df_global[(df_global['Región'] == region_sel) & (df_global['Rol'] == 'Verificador') & (df_global['Disponibles_Hoy'] == 'Si')].copy()
            
            if df_region.empty:
                st.info(f"No hay verificadores disponibles en la región {region_sel} para esta fecha.")
            else:
                st.subheader(f"👥 Equipo {region_sel} ({len(df_region)} personas)")
                
                tab_dados, tab_lotes, tab_manual = st.tabs(["🎲 Dados Estratégicos", "📦 Por Lotes", "✍️ Uno a Uno"])
                
                estados_disponibles = ["Barrido"] + estados_por_region.get(region_sel, [])
                modulos_operativos = ["RE", "BB", "CT", "TCH", "Actividad Especial", "Irregularidades 4CH", "Apoyo"]
                municipios_dummy = ["Capital", "Zona Norte", "Zona Sur", "Focalizado A", "Focalizado B"]
                
                with tab_dados:
                    st.caption("Tira los dados para aplicar la estrategia administrativa del día de forma aleatoria.")
                    st.markdown('<div class="mobile-card border-tinto">', unsafe_allow_html=True)
                    if st.button("🎲 Tirar los Dados", type="primary", use_container_width=True):
                        try:
                            # Leer dados desde la nube también
                            hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                            todas_estrategias = json.loads(hoja_est.acell('B1').value)
                            estrategia = todas_estrategias.get(str(st.session_state.fecha_dist), {})
                                
                            if estrategia.get("fecha") != str(st.session_state.fecha_dist):
                                st.warning(f"⚠️ No hay estrategia guardada para el {st.session_state.fecha_dist}.")
                            else:
                                import random
                                personas = df_region['Nombre'].tolist()
                                random.shuffle(personas)
                                
                                cubeta = []
                                for mod, qty in [("RE", estrategia.get("re", 0)), ("BB", estrategia.get("bb", 0)), 
                                                 ("CT", estrategia.get("ct", 0)), ("TCH", estrategia.get("tch", 0)), 
                                                 ("Irregularidades 4CH", estrategia.get("4ch", 0))]:
                                    cubeta.extend([mod] * qty)
                                
                                if len(cubeta) < len(personas):
                                    cubeta.extend([estrategia.get("resto", "RE")] * (len(personas) - len(cubeta)))
                                
                                cubeta = cubeta[:len(personas)]
                                random.shuffle(cubeta)
                                
                                # Guardar en memoria de sesión
                                asignaciones = {persona: cubeta[i] for i, persona in enumerate(personas)}
                                st.session_state[f'dados_{region_sel}'] = asignaciones
                                st.success("🎲 ¡Dados tirados exitosamente!")
                        except Exception as e:
                            st.error(f"🚨 No se encontró una estrategia administrativa guardada en la nube. ({e})")
                    
                    # Si ya tiraron los dados, mostramos la radiografía y el mensaje
                    if f'dados_{region_sel}' in st.session_state:
                        st.markdown("### 📋 Vista Previa de Asignación")
                        asignaciones_actuales = st.session_state[f'dados_{region_sel}']
                        
                        # Generamos una tabla HTML con UI pulida
                        html_tabla = "<table style='width:100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); font-family: sans-serif; font-size: 14px; margin-bottom: 20px;'><tr style='background-color: #9b2247; color: white; text-align: left;'><th style='padding: 12px 15px;'>Verificador</th><th style='padding: 12px 15px;'>Módulo Asignado</th></tr>"
                        for i, (persona, mod) in enumerate(asignaciones_actuales.items()):
                            bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
                            html_tabla += f"<tr style='background-color: {bg_color}; border-bottom: 1px solid #e9ecef;'><td style='padding: 10px 15px; color: #343a40;'>👤 {persona}</td><td style='padding: 10px 15px; color: #1e5b4f; font-weight: 600;'>{mod}</td></tr>"
                        html_tabla += "</table>"
                        st.markdown(html_tabla, unsafe_allow_html=True)
                        
                        # Lógica del borrador dinámico de WhatsApp
                        modulos_unicos = list(set(asignaciones_actuales.values()))
                        mods_str = ", ".join(modulos_unicos[:-1]) + f" y {modulos_unicos[-1]}" if len(modulos_unicos) > 1 else modulos_unicos[0]
                        
                        # Leer plantillas desde B2 en Sheets (manejo defensivo)
                        try:
                            hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                            try:
                                plantillas_json = json.loads(hoja_est.acell('B2').value)
                            except:
                                plantillas_json = {}
                        except:
                            plantillas_json = {}
                            
                        plantilla_default = f"Buenos días a tod@s 🍀\n\nEl día de hoy estaremos trabajando en los módulos de [MODULOS] en la Región {region_sel}.\n\nQue tengan una excelente jornada 😉"
                        plantilla_region = plantillas_json.get(region_sel, plantilla_default)
                        
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
                                plantillas_json[region_sel] = nueva_plantilla
                                try:
                                    hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                                    hoja_est.update_acell('A2', 'Plantillas_Mensajes')
                                    hoja_est.update_acell('B2', json.dumps(plantillas_json))
                                    st.success("✅ ¡Plantilla actualizada! Se usará para tus próximas distribuciones.")
                                    st.rerun() # Recargamos para que el cambio se vea inmediato
                                except Exception as e:
                                    st.error(f"Error al guardar en Sheets: {e}")

                    st.markdown('</div>', unsafe_allow_html=True)

                with tab_lotes:
                    st.caption("Asigna a múltiples verificadores al mismo tiempo.")
                    st.markdown('<div class="mobile-card border-verde">AQUÍ PONDREMOS LOS SELECTORES MÚLTIPLES</div>', unsafe_allow_html=True)

                with tab_manual:
                    st.caption("Ajusta detalles individuales. Los cambios de Lotes y Dados se reflejarán aquí antes de guardar.")
                    
                    dict_dados = st.session_state.get(f'dados_{region_sel}', {})
                    
                    # Validación matemática contra la estrategia global
                    if dict_dados:
                        try:
                            hoja_est = gc.open_by_key(SHEET_PERSONAL_ID).worksheet("Distribución")
                            estrategia = json.loads(hoja_est.acell('B1').value).get(str(st.session_state.fecha_dist), {})
                            
                            if estrategia:
                                fijos = sum([estrategia.get('re',0), estrategia.get('bb',0), estrategia.get('ct',0), estrategia.get('tch',0), estrategia.get('4ch',0)])
                                libres = max(0, len(df_region) - fijos)
                                ideal = {"RE": estrategia.get('re',0), "BB": estrategia.get('bb',0), "CT": estrategia.get('ct',0), "TCH": estrategia.get('tch',0), "Irregularidades 4CH": estrategia.get('4ch',0), "Actividad Especial": 0, "Apoyo": 0}
                                resto_mod = estrategia.get('resto', 'RE')
                                if resto_mod in ideal: ideal[resto_mod] += libres
                                    
                                from collections import Counter
                                real = Counter(dict_dados.values())
                                
                                if any(ideal[mod] != real.get(mod, 0) for mod in ideal.keys()):
                                    st.warning("⚠️ **Advertencia:** La distribución actual descuadra con la estrategia administrativa. Sugerimos equilibrar.")
                        except:
                            pass
                    
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
                                    
                                    # Si viene de dados, forzamos a "Barrido", si no, leemos la BD (por hacer)
                                    estado_actual = "Barrido" if nombre in dict_dados else "Barrido" 
                                    idx_est = estados_disponibles.index(estado_actual) if estado_actual in estados_disponibles else 0
                                    st.selectbox("Estado:", estados_disponibles, index=idx_est, key=f"est_{index}")
                                with c2:
                                    st.multiselect("Municipios:", municipios_dummy, key=f"mun_{index}")
                                    st.text_input("Prioridad / Notas:", key=f"notas_{index}", placeholder="Ej. Prioridad 1, contactar a...")
                        
                        if st.form_submit_button("☁️ Guardar Distribución Definitiva", type="primary", use_container_width=True):
                            # Recolectar lo que se movió a mano y guardarlo en memoria
                            nueva_dist = {}
                            for index, row in df_region.iterrows():
                                nombre = row.get('Nombre', 'Sin Nombre')
                                nueva_dist[nombre] = st.session_state[f"mod_{index}"]
                            
                            st.session_state[f'dados_{region_sel}'] = nueva_dist
                            st.rerun() # Reiniciamos para que la tabla y el mensaje lean los nuevos cambios

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
