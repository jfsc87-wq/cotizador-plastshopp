import streamlit as st
import pandas as pd
from fpdf import FPDF
import os
import requests
from io import BytesIO
from PIL import Image

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cotizador PLASTSHOPP", layout="wide")

# --- CONFIGURACIÓN GOOGLE SHEETS ---
ID_HOJA = "1zJBMghvaKFAK6aE-5scERf4YdgpC5rwPTUpsf-sImyw"
URL_LECTURA = f"https://docs.google.com/spreadsheets/d/{ID_HOJA}/gviz/tq?tqx=out:csv"
URL_PUENTE = "https://script.google.com/macros/s/AKfycbyLaofNe-WSPMQYGUR9pqprEfCFIrzWk2SZBn8Oi_o-4QZdMm1Vewt1GjOUndSKlSi0/exec"

# Función para cargar y LIMPIAR datos desde la nube
@st.cache_data(ttl=60)
def cargar_datos():
    try:
        df = pd.read_csv(URL_LECTURA)
        df.columns = df.columns.str.strip()
        
        columnas_precios = [
            'PV ALMACEN CON FACT', 'PRECIO REMISION AL X MAYOR', 
            'PRECIO REMISION AL DETAL', 'PV DISTRIB CON FACT'
        ]
        for col in columnas_precios:
            if col in df.columns:
                df[col] = df[col].astype(str).replace(r'[\$,.]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# Función para guardar datos en la nube
def guardar_dato_en_nube(nombre_prod, columna_destino, nuevo_valor):
    params = {"producto": nombre_prod, "columna": columna_destino, "valor": nuevo_valor}
    try:
        with st.spinner("Actualizando base de datos en la nube..."):
            response = requests.get(URL_PUENTE, params=params, timeout=10)
            if response.status_code == 200:
                st.success(f"✅ {columna_destino} actualizada con éxito.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Error en el servidor de Google.")
    except Exception as e:
        st.error(f"Error de conexión: {e}")

# --- CLASE PARA EL DISEÑO DEL PDF ---
class PDF(FPDF):
    def header(self):
        try:
            if os.path.exists("logo.png"):
                self.image("logo.png", 10, 8, 33)
        except: pass
        self.set_font('helvetica', 'B', 12)
        self.set_text_color(0, 160, 208) 
        self.cell(0, 5, 'PLASTSHOPP S.A.S', align='R', ln=True)
        self.set_text_color(0, 0, 0)
        self.set_font('helvetica', '', 9)
        self.cell(0, 5, 'NIT: 901.854.467-9', align='R', ln=True)
        self.cell(0, 5, 'WhatsApp: 310 8648172', align='R', ln=True)
        self.cell(0, 5, 'www.plastshoppsas.com', align='R', ln=True)
        self.set_draw_color(0, 160, 208) 
        self.set_line_width(0.5)         
        self.line(10, 42, 200, 42)       
        self.ln(20)
        
    def footer(self):
        self.set_y(-25)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.line(10, self.get_y(), 200, self.get_y())
        self.cell(0, 10, 'Esta cotización tiene una validez de 15 dias calendario.', align='C', ln=True)
        self.cell(0, 10, f'Pagina {self.page_no()}', align='R')

# --- INICIALIZACIÓN ---
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

df = cargar_datos()

if df is not None:
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1:
        if os.path.exists("logo.png"): st.image("logo.png", width=120)
    with col_l2:
        st.title("Sistema de Cotización - PLASTSHOPP")

    # --- FILTROS ---
    with st.sidebar:
        st.header("Filtros")
        cat_sel = st.selectbox("Categoría", ["Todas"] + sorted(df['CATEGORIA'].unique().tolist()))
        df_f = df[df['CATEGORIA'] == cat_sel] if cat_sel != "Todas" else df.copy()
        marca_sel = st.selectbox("Marca", ["Todas"] + sorted(df_f['MARCA'].dropna().unique().tolist()))
        if marca_sel != "Todas": df_f = df_f[df_f['MARCA'] == marca_sel]

    # --- SELECCIÓN PRODUCTO ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 2])
        with c1:
            prod_sel = st.selectbox("Seleccione un Producto", df_f['PRODUCTO'].unique())
            fila = df[df['PRODUCTO'] == prod_sel].iloc[0]
            
            url_foto = fila.get('IMAGEN', "")
            if pd.isna(url_foto) or url_foto == "":
                st.warning("⚠️ Sin imagen.")
                link_i = st.text_input("Pegar link de imagen:")
                if st.button("💾 Guardar Link"):
                    guardar_dato_en_nube(prod_sel, 'IMAGEN', link_i)
            else:
                st.image(url_foto, width=180)

            desc_actual = fila.get('DESCRIPCION', "")
            if pd.isna(desc_actual) or desc_actual == "":
                desc_i = st.text_area("Añadir descripción:")
                if st.button("💾 Guardar Descripción"):
                    guardar_dato_en_nube(prod_sel, 'DESCRIPCION', desc_i)
            else:
                st.info(f"**Detalle:** {desc_actual}")
                if st.button("✏️ Editar"):
                    guardar_dato_en_nube(prod_sel, 'DESCRIPCION', "")

        with c2:
            cant = st.number_input("Cantidad", min_value=1, value=1)
            
        with c3:
            tipo_p = st.selectbox("Lista de Precio", [
                'PV ALMACEN CON FACT', 'PRECIO REMISION AL X MAYOR', 
                'PRECIO REMISION AL DETAL', 'PV DISTRIB CON FACT'
            ])
            if st.button("➕ Añadir a Cotización", use_container_width=True):
                p_unit = float(fila[tipo_p])
                iva = p_unit * 0.19 if "CON FACT" in tipo_p else 0
                st.session_state.carrito.append({
                    "Producto": prod_sel,
                    "Descripcion": desc_actual if not pd.isna(desc_actual) else "",
                    "Cant": cant,
                    "Unit": p_unit,
                    "Total": (p_unit + iva) * cant,
                    "URL": url_foto
                })
                st.toast("Añadido!")

    # --- SECCIÓN DE CLIENTE Y NÚMERO DE COTIZACIÓN ---
    st.divider()
    st.subheader("📋 Información de la Cotización")
    col_cli1, col_cli2, col_cli3 = st.columns([1, 2, 2])

    num_cotiz = col_cli1.text_input("N° Cotización", "001") 
    nombre_cli = col_cli2.text_input("Nombre del Cliente", "Cliente General")
    nit_cli = col_cli3.text_input("NIT / Cédula", "000.000.000")

    if st.session_state.carrito:
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car[["Producto", "Cant", "Unit", "Total"]].style.format({"Unit": "${:,.0f}", "Total": "${:,.0f}"}))
        
        total_final = df_car['Total'].sum()
        st.markdown(f"### 💰 Total Cotización: **${total_final:,.0f}**")

        if st.button("📄 Generar Cotización PDF", use_container_width=True):
            pdf = PDF()
            pdf.add_page()
            
            def clean(t):
                repl = {'á':'a','é':'e','í':'i','ó':'o','ú':'u','ñ':'n','Á':'A','É':'E','Í':'I','Ó':'O','Ú':'U','Ñ':'N'}
                txt = str(t)
                for k,v in repl.items(): txt = txt.replace(k,v)
                return txt

            # ENCABEZADO DE COTIZACIÓN EN EL PDF
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(200, 0, 0) # Rojo para el número
            pdf.cell(0, 8, f"COTIZACIÓN N. {num_cotiz}", align='R', ln=True)
            pdf.set_text_color(0, 0, 0)
            
            pdf.ln(2)
            pdf.set_font('helvetica', 'B', 10)
            pdf.cell(0, 6, f"CLIENTE: {clean(nombre_cli).upper()}", ln=True)
            pdf.cell(0, 6, f"NIT/CC: {nit_cli}", ln=True)
            pdf.cell(0, 6, f"FECHA: {pd.Timestamp.now().strftime('%d/%m/%Y')}", ln=True)
            pdf.ln(5)

            # Títulos Tabla
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font('helvetica', 'B', 9)
            pdf.cell(30, 10, 'Foto', 1, 0, 'C', True)
            pdf.cell(75, 10, 'Producto / Detalle', 1, 0, 'C', True)
            pdf.cell(15, 10, 'Cant', 1, 0, 'C', True)
            pdf.cell(35, 10, 'V. Unit', 1, 0, 'C', True)
            pdf.cell(35, 10, 'Total', 1, 1, 'C', True)

            pdf.set_font('helvetica', '', 9)
            for item in st.session_state.carrito:
                x, y = pdf.get_x(), pdf.get_y()
                foto_ok = False
                if item['URL'] and str(item['URL']).startswith('http'):
                    try:
                        res = requests.get(item['URL'], timeout=5)
                        img = Image.open(BytesIO(res.content)).convert("RGB")
                        pdf.image(img, x + 2, y + 2, w=26, h=21)
                        foto_ok = True
                    except: pass
                
                pdf.set_xy(x, y)
                pdf.cell(30, 25, "" if foto_ok else "S.F", border=1, align='C')
                
                pdf.set_xy(x + 30, y)
                pdf.cell(75, 25, "", border=1)
                pdf.set_xy(x + 31, y + 2)
                pdf.set_font('helvetica', 'B', 8)
                pdf.multi_cell(73, 4, clean(item['Producto'][:60]))
                pdf.set_font('helvetica', 'I', 7)
                pdf.set_text_color(80, 80, 80)
                pdf.set_xy(x + 31, y + 10)
                pdf.multi_cell(73, 3.5, clean(item['Descripcion'][:180]))
                pdf.set_text_color(0, 0, 0)
                
                pdf.set_xy(x + 105, y)
                pdf.set_font('helvetica', '', 9)
                pdf.cell(15, 25, str(item['Cant']), 1, 0, 'C')
                pdf.cell(35, 25, f"$ {item['Unit']:,.0f}", 1, 0, 'R')
                pdf.cell(35, 25, f"$ {item['Total']:,.0f}", 1, 1, 'R')

            pdf.ln(5)
            pdf.set_font('helvetica', 'B', 11)
            pdf.cell(155, 10, 'TOTAL COTIZADO:', 0, 0, 'R')
            pdf.cell(35, 10, f"$ {total_final:,.0f}", 0, 1, 'R')

            st.download_button("📩 Descargar PDF", data=pdf.output(dest='S'), file_name=f"Cotizacion_{num_cotiz}_{nombre_cli}.pdf", mime="application/pdf")

        if st.button("🗑️ Vaciar Carrito"):
            st.session_state.carrito = []
            st.rerun()