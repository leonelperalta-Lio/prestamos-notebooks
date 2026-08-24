import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import os

# Intentar importar pytz para la zona horaria de Argentina
try:
    import pytz
    TZ_ARG = pytz.timezone("America/Argentina/Buenos_Aires")
except ImportError:
    TZ_ARG = None

def obtener_fecha_hora_actual():
    if TZ_ARG:
        return datetime.now(TZ_ARG)
    return datetime.now()

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Gestión y Préstamo de Recursos",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def init_db_data():
    # Sincronización inicial del Excel si el inventario está vacío
    res = supabase.table("inventario").select("id_item", count="exact").execute()
    if res.count == 0 and os.path.exists("Registro de Notebooks.xlsx"):
        try:
            df = pd.read_excel("Registro de Notebooks.xlsx", sheet_name="Notebooks")
            items = []
            for _, row in df.iterrows():
                items.append({
                    "id_item": str(row['ID_Notebook']).strip(),
                    "nombre_equipo": str(row['Marca y equipo']).strip(),
                    "categoria": "Notebook",
                    "ubicacion_origen": str(row['Ubicacion']).strip(),
                    "estado_item": "Disponible"
                })
            if items:
                supabase.table("inventario").upsert(items).execute()
        except Exception as e:
            st.error(f"Error cargando Excel inicial: {e}")

init_db_data()

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_inventario():
    res = supabase.table("inventario").select("*").execute()
    return pd.DataFrame(res.data)

def obtener_items_disponibles(categoria):
    res = supabase.table("inventario").select("*").eq("categoria", categoria).eq("estado_item", "Disponible").execute()
    return pd.DataFrame(res.data)

def obtener_prestamos_activos():
    res = supabase.table("prestamos").select("*").eq("estado", "En Uso").order("id", desc=True).execute()
    return pd.DataFrame(res.data)

# --- INTERFAZ PRINCIPAL ---
st.title("💻 Sistema de Préstamos de Equipamiento Escolar")
st.markdown("Gestión digital e informatizada respaldada en la nube (Supabase).")

# 🚨 SISTEMA DE ALERTA VISUAL
df_activos_alerta = obtener_prestamos_activos()
ahora_local = obtener_fecha_hora_actual()
hora_actual = ahora_local.time()
HORA_LIMITE = datetime.strptime("18:00:00", "%H:%M:%S").time()

if not df_activos_alerta.empty:
    cant_pendientes = len(df_activos_alerta)
    if hora_actual >= HORA_LIMITE:
        st.error(
            f"🚨 **¡ATENCIÓN - HORARIO LÍMITE SUPERADO (18:00 HS)!**  \n"
            f"Hay **{cant_pendientes} equipo(s) prestado(s)** que aún NO han sido devueltos."
        )
    else:
        st.warning(
            f"⚠️ **Aviso de Préstamos Activos:** "
            f"Actualmente hay **{cant_pendientes} equipo(s) en uso**."
        )

# --- MENÚ LATERAL ---
st.sidebar.header("⚙️ Menú de Opciones")
menu = st.sidebar.radio(
    "Navegación",
    ["📌 Registrar Préstamo", "🔄 Recursos en Uso / Devolución", "📜 Histórico de Préstamos", "📦 Gestión de Inventario"]
)

# -------------------------------------------------------------------
# PESTAÑA 1: REGISTRAR NUEVO PRÉSTAMO
# -------------------------------------------------------------------
if menu == "📌 Registrar Préstamo":
    st.header("📝 Formulario de Solicitud de Recurso")
    df_inv = obtener_inventario()
    
    if df_inv.empty:
        st.warning("⚠️ No hay elementos cargados en el inventario.")
    else:
        categorias = sorted(df_inv['categoria'].unique().tolist())
        col_cat, _ = st.columns([1, 2])
        with col_cat:
            categoria_sel = st.selectbox("1. Tipo de Artículo a Prestar", categorias)
        
        df_disponibles = obtener_items_disponibles(categoria_sel)
        
        if df_disponibles.empty:
            st.error(f"❌ No hay {categoria_sel}s disponibles en este momento.")
        else:
            options_dict = {}
            for _, row in df_disponibles.iterrows():
                label = f"{row['id_item']} | {row['nombre_equipo']} ({row['ubicacion_origen']})"
                options_dict[label] = row
            
            # Cargar auriculares disponibles en la BD si la categoría seleccionada es Notebook
            df_auriculares = pd.DataFrame()
            if categoria_sel == "Notebook":
                df_auriculares = obtener_items_disponibles("Auriculares")
            
            with st.form("form_prestamo", clear_on_submit=True):
                st.subheader("2. Datos del Préstamo y Alumno")
                col1, col2 = st.columns(2)
                
                with col1:
                    item_label = st.selectbox("Seleccionar Recurso Disponible", list(options_dict.keys()))
                    alumno = st.text_input("Nombre y Apellido del Alumno/a *")
                    curso = st.text_input("Curso / División del Alumno/a *")
                
                with col2:
                    selected_item = options_dict[item_label]
                    origen = st.text_input("De dónde salió la Notebook/Artículo *", value=selected_item['ubicacion_origen'])
                    aula_destino = st.text_input("Aula / Espacio de Destino *")
                    
                    auricular_seleccionado = None
                    if categoria_sel == "Notebook":
                        col_acc1, col_acc2, col_acc3 = st.columns(3)
                        with col_acc1:
                            lleva_cargador = st.checkbox("🔌 ¿Con cargador?", value=False)
                        with col_acc2:
                            lleva_mouse = st.checkbox("🖱️ ¿Con mouse?", value=False)
                        with col_acc3:
                            lleva_auriculares = st.checkbox("🎧 ¿Con auriculares?", value=False)
                        
                        # Si se tildan auriculares, desplegar la lista de opciones disponibles
                        if lleva_auriculares:
                            if df_auriculares.empty:
                                st.warning("⚠️ No hay auriculares cargados o disponibles en el inventario.")
                            else:
                                options_auric = [
                                    f"{row['id_item']} | {row['nombre_equipo']}" 
                                    for _, row in df_auriculares.iterrows()
                                ]
                                auricular_seleccionado = st.selectbox("Seleccionar Código de Auriculares:", options_auric)

                        acc_list = []
                        if lleva_cargador: acc_list.append("Cargador")
                        if lleva_mouse: acc_list.append("Mouse")
                        if lleva_auriculares:
                            if auricular_seleccionado:
                                acc_list.append(f"Auriculares ({auricular_seleccionado})")
                            else:
                                acc_list.append("Auriculares")
                        
                        accesorios_str = " + ".join(acc_list) if acc_list else "Solo Notebook"
                    else:
                        accesorios_str = "N/A"
                
                submitted = st.form_submit_button("✅ Registrar y Prestar Recurso")
                
                if submitted:
                    if not alumno.strip() or not curso.strip() or not origen.strip() or not aula_destino.strip():
                        st.error("⚠️ Por favor completa todos los campos obligatorios (*).")
                    else:
                        fecha_actual = obtener_fecha_hora_actual().strftime("%Y-%m-%d %H:%M:%S")
                        item_id = selected_item['id_item']
                        item_nombre = selected_item['nombre_equipo']
                        
                        # Insertar préstamo en Supabase
                        supabase.table("prestamos").insert({
                            "id_item": item_id,
                            "nombre_item": item_nombre,
                            "categoria": categoria_sel,
                            "alumno": alumno.strip(),
                            "curso": curso.strip(),
                            "origen": origen.strip(),
                            "aula_destino": aula_destino.strip(),
                            "con_cargador": accesorios_str,
                            "fecha_prestamo": fecha_actual,
                            "estado": "En Uso"
                        }).execute()
                        
                        # Actualizar estado de la Notebook a "En Uso"
                        supabase.table("inventario").update({"estado_item": "En Uso"}).eq("id_item", item_id).execute()
                        
                        # Si se seleccionaron auriculares específicos, también los marca como "En Uso"
                        if categoria_sel == "Notebook" and lleva_auriculares and auricular_seleccionado:
                            auric_id = auricular_seleccionado.split(" | ")[0]
                            supabase.table("inventario").update({"estado_item": "En Uso"}).eq("id_item", auric_id).execute()
                        
                        st.success(f"🎉 ¡Préstamo registrado exitosamente! Recurso **{item_nombre}** asignado a **{alumno}**.")
                        st.rerun()

# -------------------------------------------------------------------
# PESTAÑA 2: RECURSOS EN USO / DEVOLUCIÓN
# -------------------------------------------------------------------
elif menu == "🔄 Recursos en Uso / Devolución":
    st.header("🔄 Recursos Actualmente Prestados")
    df_activos = obtener_prestamos_activos()
    
    if df_activos.empty:
        st.info("🎉 Excelente. No hay recursos prestados en este momento.")
    else:
        st.markdown(f"Hay **{len(df_activos)}** recurso(s) actualmente prestado(s).")
        cats = ["Todos"] + sorted(df_activos['categoria'].unique().tolist())
        cat_filtro = st.selectbox("Filtrar por categoría:", cats)
        
        if cat_filtro != "Todos":
            df_activos = df_activos[df_activos['categoria'] == cat_filtro]
            
        for idx, row in df_activos.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 3, 3, 2])
                with col1:
                    st.subheader(f"💻 {row['nombre_item']}")
                    st.caption(f"ID: **{row['id_item']}** | Categoría: {row['categoria']}")
                with col2:
                    st.markdown(f"👤 **Alumno:** {row['alumno']}")
                    st.markdown(f"🏫 **Curso:** {row['curso']}")
                with col3:
                    st.markdown(f"📍 **Origen:** {row['origen']} ➔ **Aula:** {row['aula_destino']}")
                    st.markdown(f"📦 **Accesorios:** {row['con_cargador']}")
                    st.markdown(f"⏱️ **Fecha/Hora:** {row['fecha_prestamo']}")
                with col4:
                    if st.button("↩️ Devolver Recurso", key=f"dev_{row['id']}"):
                        fecha_dev = obtener_fecha_hora_actual().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Actualizar estado del préstamo
                        supabase.table("prestamos").update({"estado": "Devuelto", "fecha_devolucion": fecha_dev}).eq("id", row['id']).execute()
                        
                        # Devolver el ítem principal a "Disponible"
                        supabase.table("inventario").update({"estado_item": "Disponible"}).eq("id_item", row['id_item']).execute()
                        
                        # Si incluía auriculares, extraer ID y devolverlos a "Disponible"
                        acc_text = str(row['con_cargador'])
                        if "Auriculares (" in acc_text:
                            try:
                                auric_id = acc_text.split("Auriculares (")[1].split(" |")[0]
                                supabase.table("inventario").update({"estado_item": "Disponible"}).eq("id_item", auric_id).execute()
                            except Exception:
                                pass
                        
                        st.success(f"✅ El recurso **{row['nombre_item']}** fue devuelto correctamente.")
                        st.rerun()
            st.divider()

# -------------------------------------------------------------------
# PESTAÑA 3: HISTÓRICO DE PRÉSTAMOS
# -------------------------------------------------------------------
elif menu == "📜 Histórico de Préstamos":
    st.header("📜 Histórico y Registro Completo de Préstamos")
    res = supabase.table("prestamos").select("*").order("id", desc=True).execute()
    df_todos = pd.DataFrame(res.data)
    
    if df_todos.empty:
        st.info("No hay registros de préstamos archivados todavía.")
    else:
        df_todos['fecha_dt'] = pd.to_datetime(df_todos['fecha_prestamo'], errors='coerce')
        df_todos['mes_año'] = df_todos['fecha_dt'].dt.strftime('%Y-%m')
        
        meses_disponibles = ["Todos los meses"] + sorted(df_todos['mes_año'].dropna().unique().tolist(), reverse=True)
        
        c_busq, c_est, c_mes = st.columns([2, 1, 1])
        with c_busq: search_query = st.text_input("🔍 Buscar por Alumno, Curso, ID o Nombre:")
        with c_est: estado_filtro = st.selectbox("Estado:", ["Todos", "En Uso", "Devuelto"])
        with c_mes: mes_filtro = st.selectbox("Filtrar por Mes:", meses_disponibles)
            
        df_filtrado = df_todos.copy()
        if estado_filtro != "Todos": df_filtrado = df_filtrado[df_filtrado['estado'] == estado_filtro]
        if mes_filtro != "Todos los meses": df_filtrado = df_filtrado[df_filtrado['mes_año'] == mes_filtro]
            
        if search_query.strip():
            sq = search_query.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado['alumno'].str.lower().str.contains(sq) |
                df_filtrado['curso'].str.lower().str.contains(sq) |
                df_filtrado['id_item'].str.lower().str.contains(sq) |
                df_filtrado['nombre_item'].str.lower().str.contains(sq)
            ]
            
        df_mostrar = df_filtrado.drop(columns=['fecha_dt', 'mes_año'], errors='ignore')
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

# -------------------------------------------------------------------
# PESTAÑA 4: GESTIÓN DE INVENTARIO
# -------------------------------------------------------------------
elif menu == "📦 Gestión de Inventario":
    st.header("📦 Administración del Inventario de Equipos")
    sub_tab1, sub_tab2 = st.tabs(["📋 Listado Actual de Inventario", "➕ Agregar Nuevo Recurso / Artículo"])
    
    with sub_tab1:
        df_inv = obtener_inventario()
        st.dataframe(df_inv, use_container_width=True, hide_index=True)
        st.info(f"Total de recursos registrados en inventario: **{len(df_inv)}**")
        
    with sub_tab2:
        st.subheader("Formulario de Alta de Insumo / Equipamiento")
        with st.form("form_nuevo_inv", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nuevo_id = st.text_input("ID o Código del Artículo *")
                nombre_eq = st.text_input("Nombre o Modelo del Recurso *")
            with c2:
                cat_opciones = ["Notebook", "Auriculares", "Cargador Extra", "Proyector", "Mouse/Adaptador", "Otro"]
                cat_elegida = st.selectbox("Categoría del Recurso", cat_opciones)
                if cat_elegida == "Otro": cat_elegida = st.text_input("Escribe la nueva categoría:")
                ubicacion_org = st.text_input("Ubicación de Origen *", value="Mueble 133")
            
            btn_guardar = st.form_submit_button("➕ Guardar Artículo en Inventario")
            if btn_guardar:
                if not nuevo_id.strip() or not nombre_eq.strip() or not ubicacion_org.strip() or not cat_elegida.strip():
                    st.error("⚠️ Completa los campos obligatorios para guardar el nuevo recurso.")
                else:
                    try:
                        supabase.table("inventario").insert({
                            "id_item": nuevo_id.strip(),
                            "nombre_equipo": nombre_eq.strip(),
                            "categoria": cat_elegida.strip(),
                            "ubicacion_origen": ubicacion_org.strip(),
                            "estado_item": "Disponible"
                        }).execute()
                        st.success(f"✅ ¡Artículo **{nombre_eq}** agregado exitosamente a la nube!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar. Verifica que el ID **{nuevo_id}** no exista previamente.")
