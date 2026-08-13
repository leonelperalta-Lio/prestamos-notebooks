import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Gestión y Préstamo de Recursos",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONEXIÓN A LA BASE DE DATOS ---
DB_NAME = "gestion_recursos.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Tabla de Inventario (Notebooks, Auriculares, etc.)
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id_item TEXT PRIMARY KEY,
            nombre_equipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            ubicacion_origen TEXT NOT NULL,
            estado_item TEXT DEFAULT 'Disponible'
        )
    ''')
    
    # Tabla de Préstamos
    c.execute('''
        CREATE TABLE IF NOT EXISTS prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_item TEXT NOT NULL,
            nombre_item TEXT NOT NULL,
            categoria TEXT NOT NULL,
            alumno TEXT NOT NULL,
            curso TEXT NOT NULL,
            origen TEXT NOT NULL,
            aula_destino TEXT NOT NULL,
            con_cargador TEXT NOT NULL,
            fecha_prestamo TEXT NOT NULL,
            estado TEXT DEFAULT 'En Uso',
            fecha_devolucion TEXT,
            FOREIGN KEY (id_item) REFERENCES inventario (id_item)
        )
    ''')
    
    conn.commit()
    
    # Importar automáticamente desde Excel si la tabla inventario está vacía
    c.execute("SELECT COUNT(*) FROM inventario")
    count = c.fetchone()[0]
    if count == 0 and os.path.exists("Registro de Notebooks.xlsx"):
        try:
            df = pd.read_excel("Registro de Notebooks.xlsx", sheet_name="Notebooks")
            for _, row in df.iterrows():
                id_item = str(row['ID_Notebook']).strip()
                nombre = str(row['Marca y equipo']).strip()
                ubicacion = str(row['Ubicacion']).strip()
                c.execute('''
                    INSERT OR IGNORE INTO inventario (id_item, nombre_equipo, categoria, ubicacion_origen, estado_item)
                    VALUES (?, ?, 'Notebook', ?, 'Disponible')
                ''', (id_item, nombre, ubicacion))
            conn.commit()
        except Exception as e:
            st.error(f"Error al importar archivo Excel inicial: {e}")
            
    conn.close()

init_db()

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_inventario():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM inventario", conn)
    conn.close()
    return df

def obtener_items_disponibles(categoria):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM inventario WHERE categoria = ? AND estado_item = 'Disponible'", conn, params=(categoria,))
    conn.close()
    return df

# --- INTERFAZ PRINCIPAL DE LA APLICACIÓN ---
st.title("💻 Sistema de Préstamos de Equipamiento Escolar")
st.markdown("Gestión digital e informatizada para el préstamo de notebooks, auriculares y otros insumos dentro del centro.")

# Menú lateral para navegación
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
    
    # Cargar categorías disponibles en el inventario
    df_inv = obtener_inventario()
    
    if df_inv.empty:
        st.warning("⚠️ No hay elementos cargados en el inventario. Ve a 'Gestión de Inventario' para agregar ítems.")
    else:
        categorias = sorted(df_inv['categoria'].unique().tolist())
        
        col_cat, col_info = st.columns([1, 2])
        with col_cat:
            categoria_sel = st.selectbox("1. Tipo de Articulo a Prestar", categorias)
        
        # Obtener items disponibles para esa categoria
        df_disponibles = obtener_items_disponibles(categoria_sel)
        
        if df_disponibles.empty:
            st.error(f"❌ No hay {categoria_sel}s disponibles en este momento. Todas están en uso.")
        else:
            options_dict = {}
            for _, row in df_disponibles.iterrows():
                label = f"{row['id_item']} | {row['nombre_equipo']} ({row['ubicacion_origen']})"
                options_dict[label] = row
            
            with st.form("form_prestamo", clear_on_submit=True):
                st.subheader("2. Datos del Préstamo y Alumno")
                col1, col2 = st.columns(2)
                
                with col1:
                    item_label = st.selectbox("Seleccionar Recurso Disponible", list(options_dict.keys()))
                    alumno = st.text_input("Nombre y Apellido del Alumno/a *")
                    curso = st.text_input("Curso / División del Alumno/a (ej. 3° A, 5° II) *")
                
                with col2:
                    selected_item = options_dict[item_label]
                    origen_defecto = selected_item['ubicacion_origen']
                    
                    origen = st.text_input("De dónde salió la Notebook/Artículo *", value=origen_defecto)
                    aula_destino = st.text_input("Aula / Espacio de Destino (ej. Aula 12, Laboratorio) *")
                    
                    if categoria_sel == "Notebook":
                        lleva_cargador = st.checkbox("¿Se entrega CON cargador?", value=False)
                        cargador_str = "Con Cargador" if lleva_cargador else "Solo Notebook"
                    else:
                        cargador_str = "N/A"
                
                submitted = st.form_submit_button("✅ Registrar y Prestar Recurso")
                
                if submitted:
                    if not alumno.strip() or not curso.strip() or not origen.strip() or not aula_destino.strip():
                        st.error("⚠️ Por favor completa todos los campos obligatorios (*).")
                    else:
                        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        item_id = selected_item['id_item']
                        item_nombre = selected_item['nombre_equipo']
                        
                        conn = get_connection()
                        c = conn.cursor()
                        
                        # Registrar el préstamo
                        c.execute('''
                            INSERT INTO prestamos 
                            (id_item, nombre_item, categoria, alumno, curso, origen, aula_destino, con_cargador, fecha_prestamo, estado)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'En Uso')
                        ''', (item_id, item_nombre, categoria_sel, alumno.strip(), curso.strip(), origen.strip(), aula_destino.strip(), cargador_str, fecha_actual))
                        
                        # Cambiar estado en inventario
                        c.execute("UPDATE inventario SET estado_item = 'En Uso' WHERE id_item = ?", (item_id,))
                        
                        conn.commit()
                        conn.close()
                        
                        st.success(f"🎉 ¡Préstamo registrado exitosamente! Recurso **{item_nombre}** ({item_id}) asignado a **{alumno}**.")

# -------------------------------------------------------------------
# PESTAÑA 2: RECURSOS EN USO / DEVOLUCIÓN
# -------------------------------------------------------------------
elif menu == "🔄 Recursos en Uso / Devolución":
    st.header("🔄 Recursos Actualmente Prestados")
    
    conn = get_connection()
    df_activos = pd.read_sql_query("SELECT * FROM prestamos WHERE estado = 'En Uso' ORDER BY id DESC", conn)
    conn.close()
    
    if df_activos.empty:
        st.info("🎉 Excelente. No hay recursos prestados en este momento. Todo el material está disponible.")
    else:
        st.markdown(f"Hay **{len(df_activos)}** recurso(s) actualmente prestado(s).")
        
        # Filtro rápido por categoría
        cats = ["Todos"] + sorted(df_activos['categoria'].unique().tolist())
        cat_filtro = st.selectbox("Filtrar por categoría:", cats)
        
        if cat_filtro != "Todos":
            df_activos = df_activos[df_activos['categoria'] == cat_filtro]
            
        for idx, row in df_activos.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 3, 3, 2])
                
                with col1:
                    st.subheader(f"💻 {row['nombre_item']}")
                    st.caption(f"ID: **{row['id_item']}** | Categoria: {row['categoria']}")
                
                with col2:
                    st.markdown(f"👤 **Alumno:** {row['alumno']}")
                    st.markdown(f"🏫 **Curso:** {row['curso']}")
                
                with col3:
                    st.markdown(f"📍 **Origen:** {row['origen']} ➔ **Aula:** {row['aula_destino']}")
                    st.markdown(f"🔌 **Accesorios:** {row['con_cargador']}")
                    st.markdown(f"⏱️ **Fecha/Hora:** {row['fecha_prestamo']}")
                
                with col4:
                    if st.button("↩️ Devolver Recurso", key=f"dev_{row['id']}"):
                        fecha_dev = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        conn = get_connection()
                        c = conn.cursor()
                        
                        # Actualizar tabla de prestamos
                        c.execute("UPDATE prestamos SET estado = 'Devuelto', fecha_devolucion = ? WHERE id = ?", (fecha_dev, row['id']))
                        
                        # Actualizar estado del inventario
                        c.execute("UPDATE inventario SET estado_item = 'Disponible' WHERE id_item = ?", (row['id_item'],))
                        
                        conn.commit()
                        conn.close()
                        
                        st.success(f"✅ El recurso **{row['nombre_item']}** fue devuelto correctamente.")
                        st.rerun()
            st.divider()

# -------------------------------------------------------------------
# PESTAÑA 3: HISTÓRICO DE PRÉSTAMOS
# -------------------------------------------------------------------
elif menu == "📜 Histórico de Préstamos":
    st.header("📜 Histórico y Registro Completo de Préstamos")
    
    conn = get_connection()
    df_todos = pd.read_sql_query("SELECT * FROM prestamos ORDER BY id DESC", conn)
    conn.close()
    
    if df_todos.empty:
        st.info("No hay registros de préstamos archivados todavía.")
    else:
        # Buscador y filtros
        col_busqueda, col_filtro_est = st.columns([2, 1])
        with col_busqueda:
            search_query = st.text_input("🔍 Buscar por Alumno, Curso, ID o Nombre de equipo:")
        with col_filtro_est:
            estado_filtro = st.selectbox("Estado del préstamo:", ["Todos", "En Uso", "Devuelto"])
            
        df_filtrado = df_todos.copy()
        
        if estado_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['estado'] == estado_filtro]
            
        if search_query.strip():
            sq = search_query.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado['alumno'].str.lower().str.contains(sq) |
                df_filtrado['curso'].str.lower().str.contains(sq) |
                df_filtrado['id_item'].str.lower().str.contains(sq) |
                df_filtrado['nombre_item'].str.lower().str.contains(sq)
            ]
            
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        
        # Botón para descargar reporte en Excel
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Registro (CSV/Excel)",
            data=csv,
            file_name=f"historico_prestamos_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

# -------------------------------------------------------------------
# PESTAÑA 4: GESTIÓN DE INVENTARIO
# -------------------------------------------------------------------
elif menu == "📦 Gestión de Inventario":
    st.header("📦 Administración del Inventario de Equipos")
    st.markdown("Aquí puedes visualizar, agregar o modificar las notebooks, auriculares y otros artículos disponibles.")
    
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
                nuevo_id = st.text_input("ID o Código del Articulo (ej. AR02000... / AUR-001) *")
                nombre_eq = st.text_input("Nombre o Modelo del Recurso (ej. Bangho133-PC25 / Auriculares Redragon) *")
            
            with c2:
                cat_opciones = ["Notebook", "Auriculares", "Cargador Extra", "Proyector", "Mouse/Adaptador", "Otro"]
                cat_elegida = st.selectbox("Categoría del Recurso", cat_opciones)
                if cat_elegida == "Otro":
                    cat_elegida = st.text_input("Escribe la nueva categoría:")
                    
                ubicacion_org = st.text_input("Ubicación de Origen (ej. Mueble 133, Depósito A) *", value="Mueble 133")
            
            btn_guardar = st.form_submit_button("➕ Guardar Artículo en Inventario")
            
            if btn_guardar:
                if not nuevo_id.strip() or not nombre_eq.strip() or not ubicacion_org.strip() or not cat_elegida.strip():
                    st.error("⚠️ Completa los campos obligatorios para guardar el nuevo recurso.")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute('''
                            INSERT INTO inventario (id_item, nombre_equipo, categoria, ubicacion_origen, estado_item)
                            VALUES (?, ?, ?, ?, 'Disponible')
                        ''', (nuevo_id.strip(), nombre_eq.strip(), cat_elegida.strip(), ubicacion_org.strip()))
                        conn.commit()
                        st.success(f"✅ ¡Artículo **{nombre_eq}** ({nuevo_id}) agregado exitosamente al inventario!")
                    except sqlite3.IntegrityError:
                        st.error(f"❌ El ID **{nuevo_id}** ya existe en el inventario. Por favor utiliza un ID único.")
                    finally:
                        conn.close()