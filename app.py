import streamlit as st
import pandas as pd
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from fpdf import FPDF
from datetime import datetime
import pytz  # Biblioteca para fuso horário
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# --- Configuração da Página ---
st.set_page_config(page_title="Check-in QR Code", layout="centered")

# --- Funções Auxiliares ---

# Cache para não recarregar o CSV a cada clique (otimização)
@st.cache_data
def carregar_dados():
    try:
        # Lê o CSV forçando todas as colunas como texto
        df = pd.read_csv("participantes.csv", dtype=str)
        # Remove espaços dos nomes das colunas
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
        # .strip() remove espaços em branco antes ou depois do código
        return decoded_objects[0].data.decode("utf-8").strip()
    return None

def obter_hora_atual():
    # Define o fuso horário de Mato Grosso (Cuiabá)
    fuso_mt = pytz.timezone('America/Cuiaba')
    return datetime.now(fuso_mt)

def gerar_pdf(df_presenca, resumo_cargo, resumo_local):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            # Título com data formatada
            data_hoje = obter_hora_atual().strftime('%d/%m/%Y')
            self.cell(0, 10, f'Relatorio de Presenca - {data_hoje}', 0, 1, 'C')
            self.ln(5)

    pdf = PDF()
    pdf.add_page()
    
    # Função auxiliar para tratar texto (acentos)
    def texto_pdf(texto):
        try:
            return str(texto).encode('latin-1', 'replace').decode('latin-1')
        except:
            return str(texto)

    # Resumo Geral
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
    
    # Tabela Nominal
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "LISTA DE PRESENTES", ln=True)
    
    # Configuração da Tabela
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 8)
    
    # Cabeçalho Tabela
    col_w = [60, 50, 50, 30] # Larguras das colunas
    pdf.cell(col_w[0], 8, "Nome", 1, 0, 'C', 1)
    pdf.cell(col_w[1], 8, "Cargo", 1, 0, 'C', 1)
    pdf.cell(col_w[2], 8, "Localidade", 1, 0, 'C', 1)
    pdf.cell(col_w[3], 8, "Horario", 1, 1, 'C', 1)
    
    # Dados Tabela
    pdf.set_font("Arial", size=7)
    for index, row in df_presenca.iterrows():
        # Truncar textos longos para não quebrar o layout
        nome = str(row['Nome'])[:35]
        cargo = str(row['Cargo'])[:28]
        local = str(row['Localidade'])[:28]
        horario = str(row['Horario'])
        
        pdf.cell(col_w[0], 8, texto_pdf(nome), 1)
        pdf.cell(col_w[1], 8, texto_pdf(cargo), 1)
        pdf.cell(col_w[2], 8, texto_pdf(local), 1)
        pdf.cell(col_w[3], 8, horario, 1, 1)
    
    # Retorna os bytes do PDF diretamente
    return bytes(pdf.output())

def gerar_excel(df_presenca, resumo_cargo, resumo_local):
    """
    Gera uma planilha Excel com os dados de presença, resumos e estilos profissionais
    """
    workbook = Workbook()
    
    # Remove a planilha padrão e cria novas
    workbook.remove(workbook.active)
    
    # Estilos
    header_font = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # --- PLANILHA 1: RESUMO ---
    ws_resumo = workbook.create_sheet("Resumo", 0)
    
    # Título
    ws_resumo['A1'] = f"Relatório de Presença - {obter_hora_atual().strftime('%d/%m/%Y')}"
    ws_resumo['A1'].font = Font(name='Calibri', size=14, bold=True)
    ws_resumo.merge_cells('A1:D1')
    
    ws_resumo['A3'] = "RESUMO POR CARGO"
    ws_resumo['A3'].font = Font(size=11, bold=True)
    
    row = 4
    ws_resumo['A4'] = "Cargo"
    ws_resumo['B4'] = "Quantidade"
    for cell in [ws_resumo['A4'], ws_resumo['B4']]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    for cargo, qtd in resumo_cargo.items():
        ws_resumo[f'A{row}'] = cargo
        ws_resumo[f'B{row}'] = int(qtd)
        for col in ['A', 'B']:
            ws_resumo[f'{col}{row}'].border = border
            ws_resumo[f'{col}{row}'].alignment = Alignment(horizontal='center')
        row += 1
    
    # Resumo por Localidade
    row += 2
    ws_resumo[f'A{row}'] = "RESUMO POR LOCALIDADE"
    ws_resumo[f'A{row}'].font = Font(size=11, bold=True)
    
    row += 1
    ws_resumo[f'A{row}'] = "Localidade"
    ws_resumo[f'B{row}'] = "Quantidade"
    for cell in [ws_resumo[f'A{row}'], ws_resumo[f'B{row}']]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    row += 1
    for local, qtd in resumo_local.items():
        ws_resumo[f'A{row}'] = local
        ws_resumo[f'B{row}'] = int(qtd)
        for col in ['A', 'B']:
            ws_resumo[f'{col}{row}'].border = border
            ws_resumo[f'{col}{row}'].alignment = Alignment(horizontal='center')
        row += 1
    
    # Ajusta largura das colunas
    ws_resumo.column_dimensions['A'].width = 40
    ws_resumo.column_dimensions['B'].width = 15
    
    # --- PLANILHA 2: LISTA NOMINAL ---
    ws_lista = workbook.create_sheet("Lista Nominal", 1)
    
    # Cabeçalho
    headers = ['ID', 'Nome', 'Cargo', 'Localidade', 'Horário']
    for col_num, header in enumerate(headers, 1):
        cell = ws_lista.cell(row=1, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    # Dados
    for row_num, (index, row) in enumerate(df_presenca.iterrows(), 2):
        ws_lista.cell(row=row_num, column=1, value=row['ID'])
        ws_lista.cell(row=row_num, column=2, value=row['Nome'])
        ws_lista.cell(row=row_num, column=3, value=row['Cargo'])
        ws_lista.cell(row=row_num, column=4, value=row['Localidade'])
        ws_lista.cell(row=row_num, column=5, value=row['Horario'])
        
        for col_num in range(1, 6):
            cell = ws_lista.cell(row=row_num, column=col_num)
            cell.border = border
            cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Ajusta largura das colunas
    ws_lista.column_dimensions['A'].width = 12
    ws_lista.column_dimensions['B'].width = 35
    ws_lista.column_dimensions['C'].width = 20
    ws_lista.column_dimensions['D'].width = 25
    ws_lista.column_dimensions['E'].width = 12
    
    # Salva em bytes
    excel_bytes = BytesIO()
    workbook.save(excel_bytes)
    excel_bytes.seek(0)
    
    return excel_bytes.getvalue()

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
                # Pega a hora correta de MT
                hora_mt = obter_hora_atual().strftime("%H:%M:%S")
                
                novo_registro = {
                    'ID': id_p,
                    'Nome': nome,
                    'Cargo': participante.iloc[0]['Cargo'],
                    'Localidade': participante.iloc[0]['Localidade'],
                    'Horario': hora_mt
                }
                # Correção para evitar aviso de concatenação futura do Pandas
                novo_df = pd.DataFrame([novo_registro])
                st.session_state.lista_presenca = pd.concat([st.session_state.lista_presenca, novo_df], ignore_index=True)
                st.success(f"✅ {nome} registrado com sucesso!")
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
    resumo_local = st.session_state.lista_presenca['Localidade'].value_counts()
    
    with col1:
        st.info("**Por Cargo**")
        st.dataframe(resumo_cargo, use_container_width=True)
        
    with col2:
        st.info("**Por Localidade**")
        st.dataframe(resumo_local, use_container_width=True)
    
    st.markdown("### 📝 Lista Nominal")
    st.dataframe(
        st.session_state.lista_presenca[['Nome', 'Cargo', 'Localidade', 'Horario']], 
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    st.markdown("### 💾 Exportar Dados")
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("📄 Gerar PDF"):
            pdf_bytes = gerar_pdf(st.session_state.lista_presenca, resumo_cargo, resumo_local)
            st.download_button(
                label="⬇️ Baixar PDF",
                data=pdf_bytes,
                file_name=f"presenca_{obter_hora_atual().strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
    
    with col_btn2:
        if st.button("📋 Gerar Excel"):
            excel_bytes = gerar_excel(st.session_state.lista_presenca, resumo_cargo, resumo_local)
            st.download_button(
                label="⬇️ Baixar Excel",
                data=excel_bytes,
                file_name=f"presenca_{obter_hora_atual().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col_btn3:
        if st.button("🗑️ Limpar Lista"):
            st.session_state.lista_presenca = pd.DataFrame(columns=['ID', 'Nome', 'Cargo', 'Localidade', 'Horario'])
            st.rerun()
