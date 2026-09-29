import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
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

# --- CONEXIÓN A NEON (POSTGRESQL) ---
@st.cache_resource
def init_db_engine():
    # Cadena de conexión desde .streamlit/secrets.toml
    db_url = st.secrets["postgres"]["url"]
    return create_engine(db_url)

engine = init_db_engine()

# --- CREACIÓN E INICIALIZACIÓN DE TABLAS ---
def init_tables():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS inventario (
                id_item VARCHAR(50) PRIMARY KEY,
                nombre_equipo VARCHAR(100) NOT NULL,
                categoria VARCHAR(50) NOT NULL,
                ubicacion_origen VARCHAR(100) NOT NULL,
                estado_item VARCHAR(30) NOT NULL DEFAULT 'Disponible'
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prestamos (
                id SERIAL PRIMARY KEY,
                id_item VARCHAR(50) NOT NULL,
                nombre_item VARCHAR(100) NOT NULL,
                categoria VARCHAR(50) NOT NULL,
                alumno VARCHAR(100) NOT NULL,
                curso VARCHAR(50) NOT NULL,
                origen VARCHAR(100) NOT NULL,
                aula_destino VARCHAR(100) NOT NULL,
                con_cargador VARCHAR(150),
                fecha_prestamo VARCHAR(50) NOT NULL,
                fecha_devolucion VARCHAR(50),
                estado VARCHAR(30) NOT NULL DEFAULT 'En Uso'
            );
        """))

init_tables()

def init_db_data():
    df_inv = obtener_inventario()
    if df_inv.empty and os.path.exists("Registro de Notebooks.xlsx"):
        try:
            df = pd.read_excel("Registro de Notebooks.xlsx", sheet_name="Notebooks")
            with engine.begin() as conn:
                for _, row in df.iterrows():
                    conn.execute(text("""
                        INSERT INTO inventario (id_item, nombre_equipo, categoria, ubicacion_origen, estado_item)
                        VALUES (:id, :nombre, 'Notebook', :ubicacion, 'Disponible')
                        ON CONFLICT (id_item) DO NOTHING;
                    """), {
                        "id": str(row['ID_Notebook']).strip(),
                        "nombre": str(row['Marca y equipo']).strip(),
                        "ubicacion": str(row['Ubicacion']).strip()
                    })
        except Exception as e:
            st.error(f"Error cargando Excel inicial: {e}")

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_inventario():
    with engine.connect() as conn:
        return pd.read_sql(text("SELECT * FROM inventario"), conn)

def obtener_items_disponibles(categoria):
    with engine.connect() as conn:
        return pd.read_sql(
            text("SELECT * FROM inventario WHERE categoria = :cat AND estado_item = 'Disponible'"),
            conn,
            params={"cat": categoria}
        )

def obtener_prestamos_activos():
    with engine.connect() as conn:
        return pd.read_sql(
            text("SELECT * FROM prestamos WHERE estado = 'En Uso' ORDER BY id DESC"),
            conn
        )

init_db_data()

# --- INTERFAZ PRINCIPAL ---
st.title("💻 Sistema de Préstamos de Equipamiento Escolar")
st.markdown("Gestión digital e informatizada en la nube (Neon PostgreSQL).")

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
            
            st.subheader("2. Selección de Recurso y Accesorios")
            col_sel1, col_sel2 = st.columns(2)
            
            with col_sel1:
                item_label = st.selectbox("Seleccionar Recurso Disponible", list(options_dict.keys()))
                selected_item = options_dict[item_label]
            
            auricular_seleccionado = None
            lleva_cargador = False
            lleva_mouse = False
            lleva_auriculares = False

            with col_sel2:
                if categoria_sel == "Notebook":
                    st.write("**Accesorios a incluir:**")
                    c_a1, c_a2, c_a3 = st.columns(3)
                    with c_a1: lleva_cargador = st.checkbox("🔌 Cargador")
                    with c_a2: lleva_mouse = st.checkbox("🖱️️ Mouse")
                    with c_a3: lleva_auriculares = st.checkbox("🎧 Auriculares")
                    
                    if lleva_auriculares:
                        df_auric = obtener_items_disponibles("Auriculares")
                        if df_auric.empty:
                            st.warning("⚠️ No hay auriculares disponibles.")
                        else:
                            opts_auric = [f"{r['id_item']} | {r['nombre_equipo']}" for _, r in df_auric.iterrows()]
                            auricular_seleccionado = st.selectbox("Seleccionar Auriculares:", opts_auric)

            with st.form("form_datos_alumno", clear_on_submit=True):
                st.subheader("3. Datos del Préstamo y Alumno")
                col1, col2 = st.columns(2)
                
                with col1:
                    alumno = st.text_input("Nombre y Apellido del Alumno/a *")
                    curso = st.text_input("Curso / División del Alumno/a *")
                
                with col2:
                    origen = st.text_input("De dónde salió el Recurso *", value=selected_item['ubicacion_origen'])
                    aula_destino = st.text_input("Aula / Espacio de Destino *")
                
                submitted = st.form_submit_button("✅ Registrar y Prestar Recurso")
                
                if submitted:
                    if not alumno.strip() or not curso.strip() or not origen.strip() or not aula_destino.strip():
                        st.error("⚠️ Por favor completa todos los campos obligatorios (*).")
                    else:
                        if categoria_sel == "Notebook":
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

                        fecha_actual = obtener_fecha_hora_actual().strftime("%Y-%m-%d %H:%M:%S")
                        item_id = selected_item['id_item']
                        item_nombre = selected_item['nombre_equipo']
                        
                        with engine.begin() as conn:
                            # Insertar préstamo
                            conn.execute(text("""
                                INSERT INTO prestamos (id_item, nombre_item, categoria, alumno, curso, origen, aula_destino, con_cargador, fecha_prestamo, estado)
                                VALUES (:id_item, :nombre, :cat, :alumno, :curso, :origen, :destino, :acc, :fecha, 'En Uso')
                            """), {
                                "id_item": item_id, "nombre": item_nombre, "cat": categoria_sel,
                                "alumno": alumno.strip(), "curso": curso.strip(), "origen": origen.strip(),
                                "destino": aula_destino.strip(), "acc": accesorios_str, "fecha": fecha_actual
                            })
                            
                            # Actualizar estado del ítem principal
                            conn.execute(text("UPDATE inventario SET estado_item = 'En Uso' WHERE id_item = :id"), {"id": item_id})
                            
                            # Actualizar auriculares si corresponde
                            if categoria_sel == "Notebook" and lleva_auriculares and auricular_seleccionado:
                                auric_id = auricular_seleccionado.split(" | ")[0]
                                conn.execute(text("UPDATE inventario SET estado_item = 'En Uso' WHERE id_item = :id"), {"id": auric_id})
                        
                        st.success(f"🎉 ¡Préstamo registrado exitosamente para **{alumno}**!")
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
                        
                        with engine.begin() as conn:
                            # Actualizar estado del préstamo
                            conn.execute(text("""
                                UPDATE prestamos SET estado = 'Devuelto', fecha_devolucion = :f_dev WHERE id = :id
                            """), {"f_dev": fecha_dev, "id": row['id']})
                            
                            # Liberar ítem principal
                            conn.execute(text("UPDATE inventario SET estado_item = 'Disponible' WHERE id_item = :id"), {"id": row['id_item']})
                            
                            # Liberar auriculares si aplica
                            acc_text = str(row['con_cargador'])
                            if "Auriculares (" in acc_text:
                                try:
                                    auric_id = acc_text.split("Auriculares (")[1].split(" |")[0]
                                    conn.execute(text("UPDATE inventario SET estado_item = 'Disponible' WHERE id_item = :id"), {"id": auric_id})
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
    with engine.connect() as conn:
        df_todos = pd.read_sql(text("SELECT * FROM prestamos ORDER BY id DESC"), conn)
    
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
                        with engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO inventario (id_item, nombre_equipo, categoria, ubicacion_origen, estado_item)
                                VALUES (:id, :nombre, :cat, :ubi, 'Disponible')
                            """), {
                                "id": nuevo_id.strip(),
                                "nombre": nombre_eq.strip(),
                                "cat": cat_elegida.strip(),
                                "ubi": ubicacion_org.strip()
                            })
                        st.success(f"✅ ¡Artículo **{nombre_eq}** agregado exitosamente a la base de datos!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar. Verifica que el ID **{nuevo_id}** no exista previamente.")
