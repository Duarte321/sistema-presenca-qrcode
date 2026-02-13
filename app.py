import streamlit as st
import pandas as pd
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from fpdf import FPDF
from datetime import datetime, date, time
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
st.set_page_config(page_title="Check-in QR Code", layout="wide")

MEETINGS_FILE = "reunioes.json"
PRESENCE_FILE = "presencas.csv"
LEGACY_CONFIG_FILE = "reuniao_config.json"

# --- Funções de Data/Hora ---

def obter_hora_atual():
    fuso_mt = pytz.timezone("America/Cuiaba")
    return datetime.now(fuso_mt)

def _parse_date(iso_str: str) -> date:
    return datetime.strptime(iso_str, "%Y-%m-%d").date()

def _parse_time(hhmm_str: str) -> time:
    return datetime.strptime(hhmm_str, "%H:%M").time()

# --- Dados (Participantes) ---

@st.cache_data
def carregar_dados_participantes():
    try:
        df = pd.read_csv("participantes.csv", dtype=str)
        df.columns = df.columns.str.strip()
        return df
    except FileNotFoundError:
        st.error("Arquivo 'participantes.csv' não encontrado no repositório.")
        return pd.DataFrame()

# --- Persistência de Presença ---

def inicializar_arquivo_presenca():
    if not os.path.exists(PRESENCE_FILE):
        df = pd.DataFrame(columns=["meeting_id", "id_participante", "nome", "cargo", "localidade", "horario", "data_registro"])
        df.to_csv(PRESENCE_FILE, index=False)

def carregar_presencas_reuniao(meeting_id):
    inicializar_arquivo_presenca()
    try:
        df = pd.read_csv(PRESENCE_FILE, dtype=str)
        if df.empty:
            return pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])
        
        df_reuniao = df[df["meeting_id"] == str(meeting_id)]
        
        df_exibicao = df_reuniao.rename(columns={
            "id_participante": "ID",
            "nome": "Nome",
            "cargo": "Cargo",
            "localidade": "Localidade",
            "horario": "Horario"
        })
        return df_exibicao[["ID", "Nome", "Cargo", "Localidade", "Horario"]]
    except Exception as e:
        st.error(f"Erro ao carregar presenças: {e}")
        return pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])

def salvar_registro_presenca_csv(meeting_id, dados_participante):
    inicializar_arquivo_presenca()
    novo_registro = {
        "meeting_id": str(meeting_id),
        "id_participante": str(dados_participante["ID"]),
        "nome": dados_participante["Nome"],
        "cargo": dados_participante["Cargo"],
        "localidade": dados_participante["Localidade"],
        "horario": dados_participante["Horario"],
        "data_registro": obter_hora_atual().isoformat()
    }
    df_novo = pd.DataFrame([novo_registro])
    df_novo.to_csv(PRESENCE_FILE, mode='a', header=False, index=False)

def limpar_presencas_reuniao_csv(meeting_id):
    inicializar_arquivo_presenca()
    try:
        df = pd.read_csv(PRESENCE_FILE, dtype=str)
        df_novo = df[df["meeting_id"] != str(meeting_id)]
        df_novo.to_csv(PRESENCE_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Erro ao limpar presenças: {e}")
        return False

# --- Reuniões (agenda) ---

def carregar_reunioes():
    if os.path.exists(MEETINGS_FILE):
        try:
            with open(MEETINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []

def salvar_reunioes(reunioes):
    with open(MEETINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(reunioes, f, ensure_ascii=False, indent=2)

def _gerar_id_reuniao():
    return obter_hora_atual().strftime("%Y%m%d%H%M%S%f")

def migrar_legado_se_precisar(reunioes):
    if reunioes:
        return reunioes
    if not os.path.exists(LEGACY_CONFIG_FILE):
        return reunioes

    try:
        with open(LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
            legacy = json.load(f)
        reunioes.append({
            "id": _gerar_id_reuniao(),
            "nome": legacy.get("nome", "Reunião (importada)"),
            "data": legacy.get("data", str(date.today())),
            "hora": legacy.get("hora", "19:30"),
            "filtro_tipo": legacy.get("filtro_tipo", "Todos"),
            "filtro_valores": legacy.get("filtro_valores", []),
            "criada_em": obter_hora_atual().isoformat(timespec="seconds")
        })
        salvar_reunioes(reunioes)
        return reunioes
    except Exception:
        return reunioes

def excluir_reuniao(reunioes, reuniao_id):
    reunioes2 = [r for r in reunioes if r.get("id") != reuniao_id]
    salvar_reunioes(reunioes2)
    return reunioes2

def atualizar_ou_criar_reuniao(reunioes, reuniao):
    rid = reuniao.get("id")
    if not rid:
        reuniao["id"] = _gerar_id_reuniao()
        reuniao["criada_em"] = obter_hora_atual().isoformat(timespec="seconds")
        reunioes.append(reuniao)
    else:
        for i, r in enumerate(reunioes):
            if r.get("id") == rid:
                reuniao["criada_em"] = r.get("criada_em", reuniao.get("criada_em"))
                reunioes[i] = reuniao
                break
        else:
            reunioes.append(reuniao)

    def _key(x):
        try:
            return (x.get("data", "9999-12-31"), x.get("hora", "23:59"), x.get("nome", ""))
        except Exception:
            return ("9999-12-31", "23:59", "")

    reunioes = sorted(reunioes, key=_key)
    salvar_reunioes(reunioes)
    return reunioes

def label_reuniao(r):
    return f"{r.get('data','????-??-??')} {r.get('hora','??:??')} — {r.get('nome','(sem nome)')}"

# --- Convocação ---

def filtrar_participantes_convocados(df, reuniao):
    if df.empty:
        return df
    if not reuniao:
        return df

    tipo = reuniao.get("filtro_tipo", "Todos")
    valores = reuniao.get("filtro_valores", [])

    if tipo == "Todos":
        return df
    if tipo == "Por Cargo":
        return df[df["Cargo"].isin(valores)]
    if tipo == "Por Localidade":
        return df[df["Localidade"].isin(valores)]
    if tipo == "Manual":
        return df[df["Nome"].isin(valores)]
    return df

# --- QR (foto fallback) ---

def processar_qr_code_imagem(imagem):
    bytes_data = imagem.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    decoded_objects = decode(cv2_img)
    if decoded_objects:
        return decoded_objects[0].data.decode("utf-8").strip()
    return None

# --- Relatórios ---

def gerar_pdf(df_presenca, resumo_cargo, resumo_local, titulo_reuniao):
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 14)
            self.cell(0, 10, f"Relatório: {titulo_reuniao}", 0, 1, "C")
            self.set_font("Arial", "", 10)
            self.cell(0, 6, f"Gerado em: {obter_hora_atual().strftime('%d/%m/%Y %H:%M')}", 0, 1, "C")
            self.ln(4)

    pdf = PDF()
    pdf.add_page()

    def texto_pdf(texto):
        try:
            return str(texto).encode("latin-1", "replace").decode("latin-1")
        except Exception:
            return str(texto)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "RESUMO GERAL", ln=True)
    pdf.set_font("Arial", size=10)

    pdf.cell(0, 8, "Por Cargo:", ln=True)
    for cargo, qtd in resumo_cargo.items():
        pdf.cell(0, 6, texto_pdf(f"  - {cargo}: {qtd}"), ln=True)

    pdf.ln(4)
    pdf.cell(0, 8, "Por Localidade:", ln=True)
    for local, qtd in resumo_local.items():
        pdf.cell(0, 6, texto_pdf(f"  - {local}: {qtd}"), ln=True)

    pdf.ln(8)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "LISTA DE PRESENTES", ln=True)

    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 8)

    col_w = [60, 50, 50, 30]
    pdf.cell(col_w[0], 8, "Nome", 1, 0, "C", 1)
    pdf.cell(col_w[1], 8, "Cargo", 1, 0, "C", 1)
    pdf.cell(col_w[2], 8, "Localidade", 1, 0, "C", 1)
    pdf.cell(col_w[3], 8, "Horário", 1, 1, "C", 1)

    pdf.set_font("Arial", size=7)
    for _, row in df_presenca.iterrows():
        nome = str(row["Nome"])[:35]
        cargo = str(row["Cargo"])[:28]
        local = str(row["Localidade"])[:28]
        horario = str(row["Horario"])

        pdf.cell(col_w[0], 8, texto_pdf(nome), 1)
        pdf.cell(col_w[1], 8, texto_pdf(cargo), 1)
        pdf.cell(col_w[2], 8, texto_pdf(local), 1)
        pdf.cell(col_w[3], 8, horario, 1, 1)

    return bytes(pdf.output())

def gerar_excel(df_presenca, resumo_cargo, resumo_local, titulo_reuniao):
    workbook = Workbook()
    workbook.remove(workbook.active)

    header_font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

    ws_resumo = workbook.create_sheet("Resumo", 0)
    ws_resumo["A1"] = f"Relatório: {titulo_reuniao}"
    ws_resumo["A1"].font = Font(name="Calibri", size=14, bold=True)
    ws_resumo.merge_cells("A1:D1")

    ws_resumo["A3"] = "Resumo por Cargo"
    ws_resumo["A3"].font = Font(bold=True)
    ws_resumo.append(["Cargo", "Qtd"])

    for cell in ws_resumo[4]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    for cargo, qtd in resumo_cargo.items():
        ws_resumo.append([cargo, int(qtd)])
        for cell in ws_resumo[ws_resumo.max_row]:
            cell.border = border

    ws_resumo.append([])
    ws_resumo.append(["Resumo por Localidade", ""])
    ws_resumo[ws_resumo.max_row][0].font = Font(bold=True)
    ws_resumo.append(["Localidade", "Qtd"])

    for cell in ws_resumo[ws_resumo.max_row]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    for local, qtd in resumo_local.items():
        ws_resumo.append([local, int(qtd)])
        for cell in ws_resumo[ws_resumo.max_row]:
            cell.border = border

    ws_resumo.column_dimensions["A"].width = 40
    ws_resumo.column_dimensions["B"].width = 12

    ws_lista = workbook.create_sheet("Lista Nominal", 1)
    headers = ["ID", "Nome", "Cargo", "Localidade", "Horário"]
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

    ws_lista.column_dimensions["A"].width = 12
    ws_lista.column_dimensions["B"].width = 35
    ws_lista.column_dimensions["C"].width = 20
    ws_lista.column_dimensions["D"].width = 25
    ws_lista.column_dimensions["E"].width = 12

    excel_bytes = BytesIO()
    workbook.save(excel_bytes)
    excel_bytes.seek(0)
    return excel_bytes.getvalue()

# --- Check-in ---

def registrar_presenca(codigo_lido, df_participantes, ids_permitidos, meeting_id):
    participante = df_participantes[df_participantes["ID"] == codigo_lido]

    if participante.empty:
        st.error(f"❌ Código '{codigo_lido}' não encontrado no banco.")
        return False

    nome = participante.iloc[0]["Nome"]
    id_p = participante.iloc[0]["ID"]

    if ids_permitidos is not None and id_p not in ids_permitidos:
        st.error(f"⛔ {nome} NÃO consta na convocação desta reunião!")
        return False

    if id_p in st.session_state.lista_presenca["ID"].values:
        st.warning(f"⚠️ {nome} já está na lista.")
        return True # Retorna True para não travar o fluxo

    hora_registro = obter_hora_atual().strftime("%H:%M:%S")
    novo_registro = {
        "ID": id_p,
        "Nome": nome,
        "Cargo": participante.iloc[0]["Cargo"],
        "Localidade": participante.iloc[0]["Localidade"],
        "Horario": hora_registro,
    }

    salvar_registro_presenca_csv(meeting_id, novo_registro)

    st.session_state.lista_presenca = pd.concat(
        [st.session_state.lista_presenca, pd.DataFrame([novo_registro])],
        ignore_index=True,
    )
    
    st.toast(f"✅ {nome} registrado com sucesso!", icon="✅")
    return True

# ==========================
# APP
# ==========================

df_participantes = carregar_dados_participantes()
reunioes = migrar_legado_se_precisar(carregar_reunioes())

if "active_meeting_id" not in st.session_state:
    st.session_state.active_meeting_id = None

if "lista_presenca" not in st.session_state:
    st.session_state.lista_presenca = pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])
    
if "camera_key" not in st.session_state:
    st.session_state.camera_key = 0

hoje = date.today().strftime("%Y-%m-%d")

# --- Sidebar: Agenda ---
with st.sidebar:
    st.header("📅 Agenda de Reuniões")

    mostrar_passadas = st.checkbox("Mostrar passadas", value=False)

    reunioes_visiveis = []
    for r in reunioes:
        d = r.get("data", "")
        if mostrar_passadas or d >= hoje:
            reunioes_visiveis.append(r)

    reunioes_hoje = [r for r in reunioes if r.get("data") == hoje]
    if reunioes_hoje:
        st.markdown("**Hoje:**")
        for r in reunioes_hoje[:6]:
            if st.button(f"▶️ Iniciar: {r.get('hora','')} - {r.get('nome','')}", key=f"start_today_{r['id']}"):
                st.session_state.active_meeting_id = r["id"]
                st.session_state.lista_presenca = carregar_presencas_reuniao(r["id"])
                st.rerun()

    st.divider()

    if reunioes_visiveis:
        labels = [label_reuniao(r) for r in reunioes_visiveis]
        ids = [r["id"] for r in reunioes_visiveis]

        if st.session_state.active_meeting_id in ids:
            default_index = ids.index(st.session_state.active_meeting_id)
        else:
            default_index = 0

        sel_index = st.selectbox("Selecionar reunião", range(len(ids)), format_func=lambda i: labels[i], index=default_index)
        reuniao_selecionada_id = ids[sel_index]
    else:
        st.info("Nenhuma reunião agendada ainda.")
        reuniao_selecionada_id = None

    if reuniao_selecionada_id:
        label_btn = "▶️ Iniciar check-in"
        if st.session_state.active_meeting_id == reuniao_selecionada_id:
            label_btn = "🔄 Recarregar Check-in"

        if st.button(label_btn, type="primary"):
            st.session_state.active_meeting_id = reuniao_selecionada_id
            st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_selecionada_id)
            st.rerun()

    st.divider()

    # --- Sidebar: Criar/Editar ---
    st.header("🛠️ Criar / Editar")

    modo = st.radio("Modo", ["Criar nova", "Editar selecionada"], index=1 if reuniao_selecionada_id else 0)

    reuniao_atual_edicao = None
    if modo == "Editar selecionada" and reuniao_selecionada_id:
        for r in reunioes:
            if r.get("id") == reuniao_selecionada_id:
                reuniao_atual_edicao = r
                break

    nome_def = reuniao_atual_edicao.get("nome", "") if reuniao_atual_edicao else ""
    data_def = _parse_date(reuniao_atual_edicao.get("data", hoje)) if reuniao_atual_edicao else date.today()
    hora_def = _parse_time(reuniao_atual_edicao.get("hora", "19:30")) if reuniao_atual_edicao else time(19, 30)
    filtro_def = reuniao_atual_edicao.get("filtro_tipo", "Todos") if reuniao_atual_edicao else "Todos"
    valores_def = reuniao_atual_edicao.get("filtro_valores", []) if reuniao_atual_edicao else []

    with st.form("form_reuniao"):
        nome_input = st.text_input("Nome", value=nome_def, placeholder="Ex: Ensaio Regional")
        data_input = st.date_input("Data", value=data_def)
        hora_input = st.time_input("Horário", value=hora_def)

        st.markdown("**Convocação**")
        opcoes_radio = ["Todos", "Por Cargo", "Por Localidade", "Manual"]
        idx = opcoes_radio.index(filtro_def) if filtro_def in opcoes_radio else 0
        filtro_tipo = st.radio("Tipo", opcoes_radio, index=idx)

        valores = []
        if filtro_tipo == "Por Cargo" and not df_participantes.empty:
            opcoes = sorted(df_participantes["Cargo"].unique().tolist())
            valores = st.multiselect("Cargos", opcoes, default=[v for v in valores_def if v in opcoes])
        elif filtro_tipo == "Por Localidade" and not df_participantes.empty:
            opcoes = sorted(df_participantes["Localidade"].unique().tolist())
            valores = st.multiselect("Localidades", opcoes, default=[v for v in valores_def if v in opcoes])
        elif filtro_tipo == "Manual" and not df_participantes.empty:
            opcoes = sorted(df_participantes["Nome"].unique().tolist())
            valores = st.multiselect("Nomes", opcoes, default=[v for v in valores_def if v in opcoes])

        salvar = st.form_submit_button("💾 Salvar")

    if salvar:
        if not nome_input.strip():
            st.error("Informe o nome da reunião.")
        else:
            payload = {
                "id": reuniao_atual_edicao.get("id") if (modo == "Editar selecionada" and reuniao_atual_edicao) else None,
                "nome": nome_input.strip(),
                "data": data_input.strftime("%Y-%m-%d"),
                "hora": hora_input.strftime("%H:%M"),
                "filtro_tipo": filtro_tipo,
                "filtro_valores": valores if filtro_tipo != "Todos" else [],
            }
            reunioes = atualizar_ou_criar_reuniao(reunioes, payload)
            st.success("Reunião salva!")
            st.rerun()

    if modo == "Editar selecionada" and reuniao_atual_edicao:
        st.divider()
        confirmar = st.checkbox("Confirmar exclusão")
        if st.button("🗑️ Excluir reunião", disabled=not confirmar):
            reunioes = excluir_reuniao(reunioes, reuniao_atual_edicao["id"])
            if st.session_state.active_meeting_id == reuniao_atual_edicao["id"]:
                st.session_state.active_meeting_id = None
                st.rerun()
            st.success("Reunião excluída!")
            st.rerun()

# --- Lógica de Reunião Ativa ---
reuniao_ativa = None
if st.session_state.active_meeting_id:
    for r in reunioes:
        if r.get("id") == st.session_state.active_meeting_id:
            reuniao_ativa = r
            break
    
    if not reuniao_ativa:
        st.session_state.active_meeting_id = None
        st.rerun()

    if st.session_state.lista_presenca.empty:
         st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_ativa["id"])

if not reuniao_ativa:
    st.title("📲 Check-in")
    st.warning("Selecione uma reunião na agenda (menu lateral) e clique em 'Iniciar check-in'.")
    st.stop()

# --- Check-in ---
st.title(f"📲 {reuniao_ativa.get('nome')}")

# Definindo variáveis necessárias antes de serem usadas nos Tabs
convocados_df = filtrar_participantes_convocados(df_participantes, reuniao_ativa)
ids_permitidos = set(convocados_df["ID"].values.tolist()) if not convocados_df.empty else set()

# Abas restauradas conforme pedido
tab_auto, tab_manual = st.tabs(["⚡ Leitura Automática", "📷 Câmera Manual / Foto"])

with tab_auto:
    st.markdown("Aponte a câmera para ler automaticamente.")
    
    # Verifica se o componente carregou
    if qrcode_scanner:
        # Usa o componente original que o usuário gostava
        qr_code_auto = qrcode_scanner(key="scanner_auto")
        if qr_code_auto:
            if registrar_presenca(qr_code_auto, df_participantes, ids_permitidos, reuniao_ativa["id"]):
                 st.rerun()
    else:
        st.error("Componente de scanner automático não instalado corretamente.")

with tab_manual:
    st.markdown("Recomendado para celulares (Android/iOS) - Compatibilidade Total")
    # Mantém o modo foto simples e robusto
    key_camera = f"camera_{st.session_state.camera_key}"
    img = st.camera_input("📷 Tirar Foto", key=key_camera)

    if img:
        codigo = processar_qr_code_imagem(img)
        if codigo:
            sucesso = registrar_presenca(codigo, df_participantes, ids_permitidos, reuniao_ativa["id"])
            if sucesso:
                st.session_state.camera_key += 1
                st.rerun()
        else:
            st.error("QR Code não detectado na imagem. Tente aproximar ou melhorar a luz.")

# --- Área de Resultados ---
if not st.session_state.lista_presenca.empty:
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Presente", len(st.session_state.lista_presenca))
    with col2:
        # Mostra o último registrado
        ultimo = st.session_state.lista_presenca.iloc[-1]
        st.metric("Último Registro", f"{ultimo['Nome'].split()[0]} ({ultimo['Horario'][:5]})")

    with st.expander("Ver lista completa e exportar"):
        st.dataframe(
            st.session_state.lista_presenca[["Nome", "Cargo", "Horario"]],
            use_container_width=True,
            hide_index=True,
        )

        colA, colB, colC = st.columns(3)
        nome_arquivo = f"{reuniao_ativa.get('data','')}_{reuniao_ativa.get('hora','')}_{reuniao_ativa.get('nome','reuniao')}".replace(" ", "_")
        
        with colA:
            if st.button("📄 PDF"):
                # Recalcula resumos para o relatório
                resumo_cargo = st.session_state.lista_presenca["Cargo"].value_counts()
                resumo_local = st.session_state.lista_presenca["Localidade"].value_counts()
                pdf_data = gerar_pdf(st.session_state.lista_presenca, resumo_cargo, resumo_local, reuniao_ativa.get("nome", "Reunião"))
                st.download_button("Baixar PDF", data=pdf_data, file_name=f"{nome_arquivo}.pdf", mime="application/pdf")
        with colB:
            if st.button("📋 Excel"):
                resumo_cargo = st.session_state.lista_presenca["Cargo"].value_counts()
                resumo_local = st.session_state.lista_presenca["Localidade"].value_counts()
                excel_data = gerar_excel(st.session_state.lista_presenca, resumo_cargo, resumo_local, reuniao_ativa.get("nome", "Reunião"))
                st.download_button("Baixar Excel", data=excel_data, file_name=f"{nome_arquivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with colC:
             if st.button("🗑️ Limpar"):
                if limpar_presencas_reuniao_csv(reuniao_ativa["id"]):
                    st.session_state.lista_presenca = pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])
                    st.rerun()
