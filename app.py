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
        # Lê o CSV forçando todas as colunas como texto para evitar erros
        df = pd.read_csv("participantes.csv", dtype=str)
        # Garante que não tenha espaços extras nos nomes das colunas
        df.columns = df.columns.str.strip()
        return df
    except FileNotFoundError:
        st.error("Arquivo 'participantes.csv' não encontrado no repositório.")
        return pd.DataFrame()

def processar_qr_code(imagem):
    bytes_data = imagem.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    decoded_objects = decode(cv2_img)
    if decoded_objects:
        return decoded_objects[0].data.decode("utf-8")
    return None

def gerar_pdf(df_presenca, resumo_cargo, resumo_local):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, f"Relatório de Presença - {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)
    
    # Resumo Geral
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "RESUMO GERAL", ln=True)
    pdf.set_font("Arial", size=10)
    
    pdf.cell(190, 8, "Por Cargo:", ln=True)
    for cargo, qtd in resumo_cargo.items():
        pdf.cell(190, 6, f"  - {cargo}: {qtd}", ln=True)
    
    pdf.ln(5)
    pdf.cell(190, 8, "Por Localidade:", ln=True)
    for local, qtd in resumo_local.items():
        pdf.cell(190, 6, f"  - {local}: {qtd}", ln=True)

    pdf.ln(10)
    
    # Tabela Nominal
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "LISTA DE PRESENTES", ln=True)
    
    # Configuração da Tabela
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 8) # Fonte menor para caber tudo
    
    # Cabeçalho Tabela
    pdf.cell(60, 8, "Nome", 1, 0, 'C', 1)
    pdf.cell(50, 8, "Cargo", 1, 0, 'C', 1)
    pdf.cell(50, 8, "Localidade", 1, 0, 'C', 1)
    pdf.cell(30, 8, "Horário", 1, 1, 'C', 1)
    
    # Dados Tabela
    pdf.set_font("Arial", size=7)
    for index, row in df_presenca.iterrows():
        # Truncar textos longos para não quebrar o PDF
        nome = (row['Nome'][:35] + '..') if len(str(row['Nome'])) > 35 else str(row['Nome'])
        cargo = (row['Cargo'][:28] + '..') if len(str(row['Cargo'])) > 28 else str(row['Cargo'])
        local = (row['Localidade'][:28] + '..') if len(str(row['Localidade'])) > 28 else str(row['Localidade'])
        
        pdf.cell(60, 8, nome, 1)
        pdf.cell(50, 8, cargo, 1)
        pdf.cell(50, 8, local, 1)
        pdf.cell(30, 8, str(row['Horario']), 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

# --- Início do App ---
st.title("📲 Check-in Reunião CCB")

db_participantes = carregar_dados()

if 'lista_presenca' not in st.session_state:
    st.session_state.lista_presenca = pd.DataFrame(columns=['ID', 'Nome', 'Cargo', 'Localidade', 'Horario'])

st.markdown("### 📷 Escanear QR Code")
img_file_buffer = st.camera_input("Aponte para o QR Code")

if img_file_buffer:
    codigo_lido = processar_qr_code(img_file_buffer)
    
    if codigo_lido:
        # Busca pelo ID
        participante = db_participantes[db_participantes['ID'] == codigo_lido]
        
        if not participante.empty:
            nome = participante.iloc[0]['Nome']
            id_p = participante.iloc[0]['ID']
            
            if id_p not in st.session_state.lista_presenca['ID'].values:
                # CORREÇÃO AQUI: Usando 'Localidade' em vez de 'Comum'
                novo_registro = {
                    'ID': id_p,
                    'Nome': nome,
                    'Cargo': participante.iloc[0]['Cargo'],
                    'Localidade': participante.iloc[0]['Localidade'], # Ajustado
                    'Horario': datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.lista_presenca = pd.concat([st.session_state.lista_presenca, pd.DataFrame([novo_registro])], ignore_index=True)
                st.success(f"✅ {nome} registrado!")
            else:
                st.warning(f"⚠️ {nome} já está na lista.")
        else:
            st.error(f"❌ Código '{codigo_lido}' não encontrado no sistema.")

# Exibição
if not st.session_state.lista_presenca.empty:
    st.divider()
    st.markdown("### 📊 Resumo da Reunião")
    
    col1, col2 = st.columns(2)
    
    resumo_cargo = st.session_state.lista_presenca['Cargo'].value_counts()
    resumo_local = st.session_state.lista_presenca['Localidade'].value_counts() # Ajustado
    
    with col1:
        st.info("**Por Cargo**")
        st.dataframe(resumo_cargo)
        
    with col2:
        st.info("**Por Localidade**")
        st.dataframe(resumo_local)
    
    st.markdown("### 📝 Lista Nominal")
    st.dataframe(st.session_state.lista_presenca[['Nome', 'Cargo', 'Localidade', 'Horario']], use_container_width=True)
    
    st.divider()
    if st.button("📄 Gerar Relatório PDF"):
        pdf_bytes = gerar_pdf(st.session_state.lista_presenca, resumo_cargo, resumo_local)
        st.download_button("⬇️ Baixar PDF", pdf_bytes, "relatorio_presenca.pdf", "application/pdf")
