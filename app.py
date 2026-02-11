import streamlit as st
import pandas as pd
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from fpdf import FPDF
from datetime import datetime
import pytz
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import json
import os
try:
    from streamlit_qrcode_scanner import qrcode_scanner
except ImportError:
    qrcode_scanner = None

# --- Configuração da Página ---
st.set_page_config(page_title="Check-in QR Code", layout="centered")
CONFIG_FILE = "reuniao_config.json"

# --- Funções Auxiliares ---

@st.cache_data
def carregar_dados():
    try:
        df = pd.read_csv("participantes.csv", dtype=str)
        df.columns = df.columns.str.strip()
        return df
    except FileNotFoundError:
        st.error("Arquivo 'participantes.csv' não encontrado no repositório.")
        return pd.DataFrame()

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def salvar_config(nome, data, hora, filtro_tipo, filtro_valores):
    config = {
        "nome": nome,
        "data": str(data),
        "hora": str(hora),
        "filtro_tipo": filtro_tipo,
        "filtro_valores": filtro_valores
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    return config

def filtrar_participantes_convocados(df, config):
    if not config:
        return df 
    
    tipo = config.get("filtro_tipo", "Todos")
    valores = config.get("filtro_valores", [])
    
    if tipo == "Todos":
        return df
    elif tipo == "Por Cargo":
        return df[df['Cargo'].isin(valores)]
    elif tipo == "Por Localidade":
        return df[df['Localidade'].isin(valores)]
    elif tipo == "Manual":
        return df[df['Nome'].isin(valores)]
    
    return df

def processar_qr_code_imagem(imagem):
    bytes_data = imagem.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    decoded_objects = decode(cv2_img)
    if decoded_objects:
        return decoded_objects[0].data.decode("utf-8").strip()
    return None

def obter_hora_atual():
    fuso_mt = pytz.timezone('America/Cuiaba')
    return datetime.now(fuso_mt)

# --- Geradores de Relatório ---

def gerar_pdf(df_presenca, resumo_cargo, resumo_local, nome_reuniao):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 14)
            data_hoje = obter_hora_atual().strftime('%d/%m/%Y')
            self.cell(0, 10, f'Relatorio: {nome_reuniao}', 0, 1, 'C')
            self.set_font('Arial', '', 10)
            self.cell(0, 5, f'Gerado em: {data_hoje}', 0, 1, 'C')
            self.ln(5)

    pdf = PDF()
    pdf.add_page()
    
    def texto_pdf(texto):
        try:
            return str(texto).encode('latin-1', 'replace').decode('latin-1')
        except:
            return str(texto)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "RESUMO GERAL", ln=True)
    pdf.set_font("Arial", size=10)
    
    pdf.cell(0, 8, "Por Cargo:", ln=True)
    for cargo, qtd in resumo_cargo.items():
        pdf.cell(0, 6, texto_pdf(f"  - {cargo}: {qtd}"), ln=True)
    
    pdf.ln(5)
    pdf.cell(0, 8, "Por Localidade:", ln=True)
    for local, qtd in resumo_local.items():
        pdf.cell(0, 6, texto_pdf(f"  - {local}: {qtd}"), ln=True)

    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "LISTA DE PRESENTES", ln=True)
    
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 8)
    
    col_w = [60, 50, 50, 30]
    pdf.cell(col_w[0], 8, "Nome", 1, 0, 'C', 1)
    pdf.cell(col_w[1], 8, "Cargo", 1, 0, 'C', 1)
    pdf.cell(col_w[2], 8, "Localidade", 1, 0, 'C', 1)
    pdf.cell(col_w[3], 8, "Horario", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", size=7)
    for index, row in df_presenca.iterrows():
        nome = str(row['Nome'])[:35]
        cargo = str(row['Cargo'])[:28]
        local = str(row['Localidade'])[:28]
        horario = str(row['Horario'])
        
        pdf.cell(col_w[0], 8, texto_pdf(nome), 1)
        pdf.cell(col_w[1], 8, texto_pdf(cargo), 1)
        pdf.cell(col_w[2], 8, texto_pdf(local), 1)
        pdf.cell(col_w[3], 8, horario, 1, 1)
    
    return bytes(pdf.output())

def gerar_excel(df_presenca, resumo_cargo, resumo_local, nome_reuniao):
    workbook = Workbook()
    workbook.remove(workbook.active)
    
    header_font = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    ws_resumo = workbook.create_sheet("Resumo", 0)
    ws_resumo['A1'] = f"Relatório: {nome_reuniao}"
    ws_resumo['A1'].font = Font(name='Calibri', size=14, bold=True)
    ws_resumo.merge_cells('A1:D1')
    
    row = 4
    ws_resumo['A4'] = "Cargo"
    ws_resumo['B4'] = "Qtd"
    for cell in [ws_resumo['A4'], ws_resumo['B4']]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
        
    for cargo, qtd in resumo_cargo.items():
        ws_resumo.append([cargo, int(qtd)])
        for cell in ws_resumo[ws_resumo.max_row]:
            cell.border = border
            cell.alignment = Alignment(horizontal='center')
            
    ws_lista = workbook.create_sheet("Lista Nominal", 1)
    headers = ['ID', 'Nome', 'Cargo', 'Localidade', 'Horário']
    ws_lista.append(headers)
    for cell in ws_lista[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
        
    for r in df_presenca.itertuples(index=False):
        ws_lista.append([r.ID, r.Nome, r.Cargo, r.Localidade, r.Horario])
        for cell in ws_lista[ws_lista.max_row]:
            cell.border = border
            cell.alignment = Alignment(horizontal='left')
            
    excel_bytes = BytesIO()
    workbook.save(excel_bytes)
    excel_bytes.seek(0)
    return excel_bytes.getvalue()

def registrar_presenca(codigo_lido, db_participantes, ids_permitidos):
    participante_geral = db_participantes[db_participantes['ID'] == codigo_lido]
    
    if not participante_geral.empty:
        nome = participante_geral.iloc[0]['Nome']
        id_p = participante_geral.iloc[0]['ID']
        
        if id_p in ids_permitidos:
            if id_p not in st.session_state.lista_presenca['ID'].values:
                hora_mt = obter_hora_atual().strftime("%H:%M:%S")
                novo_registro = {
                    'ID': id_p,
                    'Nome': nome,
                    'Cargo': participante_geral.iloc[0]['Cargo'],
                    'Localidade': participante_geral.iloc[0]['Localidade'],
                    'Horario': hora_mt
                }
                novo_df = pd.DataFrame([novo_registro])
                st.session_state.lista_presenca = pd.concat([st.session_state.lista_presenca, novo_df], ignore_index=True)
                st.success(f"✅ {nome} registrado com sucesso!")
                return True
            else:
                st.warning(f"⚠️ {nome} já está na lista.")
                return False
        else:
            st.error(f"⛔ {nome} NÃO consta na lista de convocação para esta reunião!")
            return False
    else:
        st.error(f"❌ Código '{codigo_lido}' não encontrado no banco de dados.")
        return False

# --- Início do App ---
db_participantes = carregar_dados()
config_reuniao = carregar_config()

# --- SIDEBAR: Configuração da Reunião ---
st.sidebar.header("⚙️ Configurar Reunião")

if config_reuniao:
    nome_padrao = config_reuniao.get("nome", "")
    data_padrao_str = config_reuniao.get("data", datetime.now().strftime('%Y-%m-%d'))
    hora_padrao_str = config_reuniao.get("hora", "19:30")
    filtro_padrao = config_reuniao.get("filtro_tipo", "Todos")
    valores_padrao = config_reuniao.get("filtro_valores", [])
    try:
        data_padrao = datetime.strptime(data_padrao_str, '%Y-%m-%d').date()
        hora_padrao = datetime.strptime(hora_padrao_str, '%H:%M').time()
    except:
        data_padrao = datetime.now().date()
        hora_padrao = datetime.now().time()
else:
    nome_padrao = ""
    data_padrao = datetime.now().date()
    hora_padrao = datetime.now().time()
    filtro_padrao = "Todos"
    valores_padrao = []

with st.sidebar.form("form_reuniao"):
    nome_input = st.text_input("Nome da Reunião", value=nome_padrao, placeholder="Ex: Ensaio Regional")
    data_input = st.date_input("Data", value=data_padrao)
    hora_input = st.time_input("Horário", value=hora_padrao)
    
    st.divider()
    st.markdown("**Quem deve participar?**")
    filtro_tipo = st.radio("Convocar por:", ["Todos", "Por Cargo", "Por Localidade", "Manual"], index=["Todos", "Por Cargo", "Por Localidade", "Manual"].index(filtro_padrao))
    
    opcoes_filtro = []
    if filtro_tipo == "Por Cargo":
        opcoes = db_participantes['Cargo'].unique().tolist() if not db_participantes.empty else []
        opcoes_filtro = st.multiselect("Selecione os Cargos:", options=opcoes, default=valores_padrao if filtro_tipo=="Por Cargo" else [])
    elif filtro_tipo == "Por Localidade":
        opcoes = db_participantes['Localidade'].unique().tolist() if not db_participantes.empty else []
        opcoes_filtro = st.multiselect("Selecione as Localidades:", options=opcoes, default=valores_padrao if filtro_tipo=="Por Localidade" else [])
    elif filtro_tipo == "Manual":
        opcoes = db_participantes['Nome'].unique().tolist() if not db_participantes.empty else []
        opcoes_filtro = st.multiselect("Selecione os Nomes:", options=opcoes, default=valores_padrao if filtro_tipo=="Manual" else [])
    
    submitted = st.form_submit_button("💾 Salvar Configuração")
    
    if submitted:
        if not nome_input:
            st.error("Digite um nome para a reunião!")
        else:
            valores_salvar = opcoes_filtro if filtro_tipo != "Todos" else []
            novo_config = salvar_config(nome_input, data_input, hora_input, filtro_tipo, valores_salvar)
            config_reuniao = novo_config
            st.success("Configuração salva com sucesso!")
            st.rerun()

# --- Lógica Principal ---

if config_reuniao:
    st.title(f"📲 {config_reuniao['nome']}")
    st.info(f"📅 **Data:** {config_reuniao['data']} às {config_reuniao['hora']} | 👥 **Convocação:** {config_reuniao['filtro_tipo']}")
else:
    st.title("📲 Check-in Genérico")
    st.warning("⚠️ Nenhuma reunião configurada. Use o menu lateral para criar uma.")

# Lista de Convocados (Filtrada)
convocados_df = filtrar_participantes_convocados(db_participantes, config_reuniao)
ids_permitidos = convocados_df['ID'].values if not convocados_df.empty else []

if 'lista_presenca' not in st.session_state:
    st.session_state.lista_presenca = pd.DataFrame(columns=['ID', 'Nome', 'Cargo', 'Localidade', 'Horario'])

st.divider()
st.markdown("### 📷 Leitura de QR Code")

# Abas para escolher o método
tab_auto, tab_manual = st.tabs(["⚡ Leitura Automática", "📷 Câmera Manual / Foto"])

with tab_auto:
    st.markdown("**Aponte a câmera para ler automaticamente:**")
    if qrcode_scanner:
        # Biblioteca aceita apenas key, sem parâmetros de tamanho
        qr_code_auto = qrcode_scanner(key='scanner_auto')
        
        if qr_code_auto:
            registrar_presenca(qr_code_auto, db_participantes, ids_permitidos)
    else:
        st.warning("Biblioteca 'streamlit-qrcode-scanner' não instalada. Use a aba Manual.")

with tab_manual:
    st.markdown("**Tire uma foto do QR Code:**")
    img_file_buffer = st.camera_input("Tirar Foto")
    if img_file_buffer:
        codigo_lido = processar_qr_code_imagem(img_file_buffer)
        if codigo_lido:
            registrar_presenca(codigo_lido, db_participantes, ids_permitidos)

# Exibição e Exportação
if not st.session_state.lista_presenca.empty:
    st.divider()
    st.markdown("### 📊 Resumo")
    
    col1, col2 = st.columns(2)
    resumo_cargo = st.session_state.lista_presenca['Cargo'].value_counts()
    resumo_local = st.session_state.lista_presenca['Localidade'].value_counts()
    
    with col1:
        st.dataframe(resumo_cargo, use_container_width=True)
    with col2:
        st.dataframe(resumo_local, use_container_width=True)
    
    st.markdown("### 📝 Lista de Presentes")
    st.dataframe(st.session_state.lista_presenca[['Nome', 'Cargo', 'Localidade', 'Horario']], use_container_width=True, hide_index=True)
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    
    nome_arquivo = config_reuniao['nome'].replace(" ", "_") if config_reuniao else "reuniao_generica"
    
    with col1:
        if st.button("📄 PDF"):
            pdf_data = gerar_pdf(st.session_state.lista_presenca, resumo_cargo, resumo_local, nome_arquivo)
            st.download_button("Baixar PDF", data=pdf_data, file_name=f"{nome_arquivo}.pdf", mime="application/pdf")
    
    with col2:
        if st.button("📋 Excel"):
            excel_data = gerar_excel(st.session_state.lista_presenca, resumo_cargo, resumo_local, nome_arquivo)
            st.download_button("Baixar Excel", data=excel_data, file_name=f"{nome_arquivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
    with col3:
        if st.button("🗑️ Limpar"):
            st.session_state.lista_presenca = pd.DataFrame(columns=['ID', 'Nome', 'Cargo', 'Localidade', 'Horario'])
            st.rerun()
