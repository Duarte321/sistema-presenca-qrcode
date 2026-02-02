import streamlit as st
import pandas as pd
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from fpdf import FPDF
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Check-in QR Code", layout="centered")

# --- Funções Auxiliares ---

def carregar_dados():
    # Carrega a lista de participantes autorizados
    try:
        return pd.read_csv("participantes.csv", dtype=str)
    except FileNotFoundError:
        st.error("Arquivo 'participantes.csv' não encontrado no repositório.")
        return pd.DataFrame()

def processar_qr_code(imagem):
    # Decodifica QR Code da imagem da câmera
    bytes_data = imagem.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    decoded_objects = decode(cv2_img)
    
    if decoded_objects:
        return decoded_objects[0].data.decode("utf-8")
    return None

def gerar_pdf(df_presenca, resumo_cargo, resumo_comum):
    pdf = FPDF()
    pdf.add_page()
    
    # Título
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, f"Relatório de Presença - {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)
    
    # Resumo Geral
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "RESUMO GERAL", ln=True)
    pdf.set_font("Arial", size=10)
    
    # Resumo Cargos
    pdf.cell(190, 8, "Por Cargo:", ln=True)
    for cargo, qtd in resumo_cargo.items():
        pdf.cell(190, 6, f"  - {cargo}: {qtd}", ln=True)
    
    pdf.ln(5)
    # Resumo Locais
    pdf.cell(190, 8, "Por Localidade (Comum):", ln=True)
    for comum, qtd in resumo_comum.items():
        pdf.cell(190, 6, f"  - {comum}: {qtd}", ln=True)

    pdf.ln(10)
    
    # Tabela Nominal
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "LISTA DE PRESENTES", ln=True)
    
    # Cabeçalho da Tabela
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(60, 8, "Nome", 1, 0, 'C', 1)
    pdf.cell(50, 8, "Cargo", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Comum", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Horário", 1, 1, 'C', 1)
    
    # Linhas da Tabela
    pdf.set_font("Arial", size=10)
    for index, row in df_presenca.iterrows():
        pdf.cell(60, 8, str(row['Nome']), 1)
        pdf.cell(50, 8, str(row['Cargo']), 1)
        pdf.cell(40, 8, str(row['Comum']), 1)
        pdf.cell(40, 8, str(row['Horario']), 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

# --- Início do App ---
st.title("📲 Check-in Reunião CCB")

# Carregar banco de dados
db_participantes = carregar_dados()

# Inicializar estado da sessão para guardar presenças
if 'lista_presenca' not in st.session_state:
    st.session_state.lista_presenca = pd.DataFrame(columns=['ID', 'Nome', 'Cargo', 'Comum', 'Horario'])

# Área de Escaneamento
st.markdown("### 📷 Escanear QR Code")
img_file_buffer = st.camera_input("Aponte para o QR Code")

if img_file_buffer:
    codigo_lido = processar_qr_code(img_file_buffer)
    
    if codigo_lido:
        # Verifica se o código existe no banco de dados
        participante = db_participantes[db_participantes['ID'] == codigo_lido]
        
        if not participante.empty:
            nome = participante.iloc[0]['Nome']
            id_p = participante.iloc[0]['ID']
            
            # Verifica se já não marcou presença
            if id_p not in st.session_state.lista_presenca['ID'].values:
                novo_registro = {
                    'ID': id_p,
                    'Nome': nome,
                    'Cargo': participante.iloc[0]['Cargo'],
                    'Comum': participante.iloc[0]['Comum'],
                    'Horario': datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.lista_presenca = pd.concat([st.session_state.lista_presenca, pd.DataFrame([novo_registro])], ignore_index=True)
                st.success(f"✅ {nome} registrado com sucesso!")
            else:
                st.warning(f"⚠️ {nome} já está na lista.")
        else:
            st.error("❌ Código QR não encontrado no sistema.")
    else:
        st.warning("Não foi possível ler o QR Code. Tente aproximar ou melhorar a iluminação.")

# Exibição de Resumos e Lista
if not st.session_state.lista_presenca.empty:
    st.divider()
    st.markdown("### 📊 Resumo da Reunião")
    
    col1, col2 = st.columns(2)
    
    # Cálculos
    resumo_cargo = st.session_state.lista_presenca['Cargo'].value_counts()
    resumo_comum = st.session_state.lista_presenca['Comum'].value_counts()
    
    with col1:
        st.info("**Por Cargo**")
        st.dataframe(resumo_cargo)
        
    with col2:
        st.info("**Por Localidade**")
        st.dataframe(resumo_comum)
    
    st.markdown("### 📝 Lista Nominal")
    st.dataframe(st.session_state.lista_presenca[['Nome', 'Cargo', 'Comum', 'Horario']], use_container_width=True)
    
    # Botão PDF
    st.divider()
    if st.button("📄 Gerar Relatório PDF"):
        pdf_bytes = gerar_pdf(st.session_state.lista_presenca, resumo_cargo, resumo_comum)
        st.download_button(
            label="⬇️ Baixar PDF da Reunião",
            data=pdf_bytes,
            file_name="relatorio_presenca.pdf",
            mime="application/pdf"
        )
