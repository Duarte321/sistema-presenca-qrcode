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
import time as time_module
from supabase import create_client, Client

# --- Configuração da Página ---
st.set_page_config(page_title="Check-in QR Code", layout="wide")

# --- Supabase ---
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase_client = get_supabase()

# --- Funções de Data/Hora ---

def obter_hora_atual():
    fuso_mt = pytz.timezone("America/Cuiaba")
    return datetime.now(fuso_mt)

def _parse_date(iso_str: str) -> date:
    return datetime.strptime(iso_str, "%Y-%m-%d").date()

def _parse_time(hhmm_str: str) -> time:
    return datetime.strptime(hhmm_str, "%H:%M").time()

# --- Dados (Participantes) ---

@st.cache_data(ttl=300)
def carregar_dados_participantes():
    try:
        res = supabase_client.table("participantes").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.str.strip()
            return df
        return pd.DataFrame(columns=["id", "nome", "cargo", "localidade"])
    except Exception as e:
        st.error(f"Erro ao carregar participantes: {e}")
        return pd.DataFrame()

# --- Persistência de Presença ---

def carregar_presencas_reuniao(meeting_id):
    try:
        res = supabase_client.table("presencas").select("*").eq("meeting_id", str(meeting_id)).execute()
        if not res.data:
            return pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])
        df = pd.DataFrame(res.data)
        df = df.rename(columns={
            "id_participante": "ID",
            "nome": "Nome",
            "cargo": "Cargo",
            "localidade": "Localidade",
            "horario": "Horario"
        })
        return df[["ID", "Nome", "Cargo", "Localidade", "Horario"]]
    except Exception as e:
        st.error(f"Erro ao carregar presenças: {e}")
        return pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])

def salvar_registro_presenca(meeting_id, dados_participante):
    try:
        supabase_client.table("presencas").insert({
            "meeting_id": str(meeting_id),
            "id_participante": str(dados_participante["ID"]),
            "nome": dados_participante["Nome"],
            "cargo": dados_participante["Cargo"],
            "localidade": dados_participante["Localidade"],
            "horario": dados_participante["Horario"],
            "data_registro": obter_hora_atual().isoformat()
        }).execute()
    except Exception as e:
        st.error(f"Erro ao salvar presença: {e}")

def limpar_presencas_reuniao(meeting_id):
    try:
        supabase_client.table("presencas").delete().eq("meeting_id", str(meeting_id)).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao limpar presenças: {e}")
        return False

# --- Reuniões (agenda) ---

def carregar_reunioes():
    try:
        res = supabase_client.table("reunioes").select("*").order("data").execute()
        reunioes = res.data or []
        for r in reunioes:
            if isinstance(r.get("filtro_valores"), str):
                try:
                    r["filtro_valores"] = json.loads(r["filtro_valores"])
                except Exception:
                    r["filtro_valores"] = []
            elif r.get("filtro_valores") is None:
                r["filtro_valores"] = []
        return reunioes
    except Exception as e:
        st.error(f"Erro ao carregar reuniões: {e}")
        return []

def _gerar_id_reuniao():
    return obter_hora_atual().strftime("%Y%m%d%H%M%S%f")

def excluir_reuniao(reunioes, reuniao_id):
    try:
        supabase_client.table("reunioes").delete().eq("id", reuniao_id).execute()
    except Exception as e:
        st.error(f"Erro ao excluir reunião: {e}")
    return carregar_reunioes()

def atualizar_ou_criar_reuniao(reunioes, reuniao):
    rid = reuniao.get("id")
    if not rid:
        reuniao["id"] = _gerar_id_reuniao()
        reuniao["criada_em"] = obter_hora_atual().isoformat(timespec="seconds")
    try:
        supabase_client.table("reunioes").upsert(reuniao).execute()
    except Exception as e:
        st.error(f"Erro ao salvar reunião: {e}")
    return carregar_reunioes()

def label_reuniao(r):
    return f"{r.get('data','????-??-??')} {r.get('hora','??:??')} — {r.get('nome','(sem nome)')}"

# --- Convocação ---

def filtrar_participantes_convocados(df, reuniao):
    if df.empty or not reuniao:
        return df
    tipo = reuniao.get("filtro_tipo", "Todos")
    valores = reuniao.get("filtro_valores", [])
    col_cargo = "Cargo" if "Cargo" in df.columns else "cargo"
    col_local = "Localidade" if "Localidade" in df.columns else "localidade"
    col_nome = "Nome" if "Nome" in df.columns else "nome"
    if tipo == "Todos":
        return df
    if tipo == "Por Cargo":
        return df[df[col_cargo].isin(valores)]
    if tipo == "Por Localidade":
        return df[df[col_local].isin(valores)]
    if tipo == "Manual":
        return df[df[col_nome].isin(valores)]
    return df

# --- QR Code via imagem (OpenCV + pyzbar) ---

def processar_qr_code_imagem(imagem):
    try:
        bytes_data = imagem.getvalue()
        cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
        if cv2_img is None:
            return None
        height, width = cv2_img.shape[:2]
        if width > 1200:
            scale = 1200 / width
            cv2_img = cv2.resize(cv2_img, (1200, int(height * scale)), interpolation=cv2.INTER_AREA)
        gray_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
        # Tenta decodificar direto
        decoded = decode(gray_img)
        if decoded:
            return decoded[0].data.decode("utf-8").strip()
        # Segunda tentativa com threshold adaptativo (melhora leitura em luz ruim)
        thresh = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        decoded = decode(thresh)
        if decoded:
            return decoded[0].data.decode("utf-8").strip()
        return None
    except Exception:
        return None

# --- Relatórios ---

def gerar_pdf(df_presenca, resumo_cargo, resumo_local, titulo_reuniao):
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 14)
            self.cell(0, 10, f"Relatorio: {titulo_reuniao}", 0, 1, "C")
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
    pdf.cell(col_w[3], 8, "Horario", 1, 1, "C", 1)
    pdf.set_font("Arial", size=7)
    for _, row in df_presenca.iterrows():
        pdf.cell(col_w[0], 8, texto_pdf(str(row["Nome"])[:35]), 1)
        pdf.cell(col_w[1], 8, texto_pdf(str(row["Cargo"])[:28]), 1)
        pdf.cell(col_w[2], 8, texto_pdf(str(row["Localidade"])[:28]), 1)
        pdf.cell(col_w[3], 8, str(row["Horario"]), 1, 1)
    return bytes(pdf.output())

def gerar_excel(df_presenca, resumo_cargo, resumo_local, titulo_reuniao):
    workbook = Workbook()
    workbook.remove(workbook.active)
    header_font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
    ws_resumo = workbook.create_sheet("Resumo", 0)
    ws_resumo["A1"] = f"Relatorio: {titulo_reuniao}"
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
    headers = ["ID", "Nome", "Cargo", "Localidade", "Horario"]
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
    col_id = "ID" if "ID" in df_participantes.columns else "id"
    col_nome = "Nome" if "Nome" in df_participantes.columns else "nome"
    col_cargo = "Cargo" if "Cargo" in df_participantes.columns else "cargo"
    col_local = "Localidade" if "Localidade" in df_participantes.columns else "localidade"

    participante = df_participantes[df_participantes[col_id] == codigo_lido]
    if participante.empty:
        st.error(f"❌ Código '{codigo_lido}' não encontrado no banco.")
        return False

    nome = participante.iloc[0][col_nome]
    id_p = participante.iloc[0][col_id]

    if ids_permitidos is not None and id_p not in ids_permitidos:
        st.error(f"⛔ {nome} NÃO consta na convocação desta reunião!")
        return False

    if id_p in st.session_state.lista_presenca["ID"].values:
        st.warning(f"⚠️ {nome} já está na lista.")
        return True

    hora_registro = obter_hora_atual().strftime("%H:%M:%S")
    novo_registro = {
        "ID": id_p,
        "Nome": nome,
        "Cargo": participante.iloc[0][col_cargo],
        "Localidade": participante.iloc[0][col_local],
        "Horario": hora_registro,
    }
    salvar_registro_presenca(meeting_id, novo_registro)
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
if not df_participantes.empty:
    col_map = {"id": "ID", "nome": "Nome", "cargo": "Cargo", "localidade": "Localidade"}
    df_participantes = df_participantes.rename(columns=col_map)

reunioes = carregar_reunioes()

if "active_meeting_id" not in st.session_state:
    st.session_state.active_meeting_id = None
if "lista_presenca" not in st.session_state:
    st.session_state.lista_presenca = pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])
if "camera_key" not in st.session_state:
    st.session_state.camera_key = 0
# Debounce: guarda o último código lido e o timestamp
if "ultimo_codigo_lido" not in st.session_state:
    st.session_state.ultimo_codigo_lido = None
if "ultimo_lido_ts" not in st.session_state:
    st.session_state.ultimo_lido_ts = 0.0

hoje = date.today().strftime("%Y-%m-%d")

# --- Sidebar: Agenda ---
with st.sidebar:
    st.header("📅 Agenda de Reuniões")
    mostrar_passadas = st.checkbox("Mostrar passadas", value=False)
    reunioes_visiveis = [r for r in reunioes if mostrar_passadas or r.get("data", "") >= hoje]

    reunioes_hoje = [r for r in reunioes if r.get("data") == hoje]
    if reunioes_hoje:
        st.markdown("**Hoje:**")
        for r in reunioes_hoje[:6]:
            if st.button(f"▶️ Iniciar: {r.get('hora','')} - {r.get('nome','')}", key=f"start_today_{r['id']}"):
                st.session_state.active_meeting_id = r["id"]
                st.session_state.lista_presenca = carregar_presencas_reuniao(r["id"])
                st.rerun()

    st.divider()

    reuniao_selecionada_id = None
    if reunioes_visiveis:
        labels = [label_reuniao(r) for r in reunioes_visiveis]
        ids = [r["id"] for r in reunioes_visiveis]
        default_index = ids.index(st.session_state.active_meeting_id) if st.session_state.active_meeting_id in ids else 0
        sel_index = st.selectbox("Selecionar reunião", range(len(ids)), format_func=lambda i: labels[i], index=default_index)
        reuniao_selecionada_id = ids[sel_index]
    else:
        st.info("Nenhuma reunião agendada ainda.")

    if reuniao_selecionada_id:
        label_btn = "🔄 Recarregar Check-in" if st.session_state.active_meeting_id == reuniao_selecionada_id else "▶️ Iniciar check-in"
        if st.button(label_btn, type="primary"):
            st.session_state.active_meeting_id = reuniao_selecionada_id
            st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_selecionada_id)
            st.rerun()

    st.divider()
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
            col_c = "Cargo" if "Cargo" in df_participantes.columns else "cargo"
            opcoes = sorted(df_participantes[col_c].unique().tolist())
            valores = st.multiselect("Cargos", opcoes, default=[v for v in valores_def if v in opcoes])
        elif filtro_tipo == "Por Localidade" and not df_participantes.empty:
            col_l = "Localidade" if "Localidade" in df_participantes.columns else "localidade"
            opcoes = sorted(df_participantes[col_l].unique().tolist())
            valores = st.multiselect("Localidades", opcoes, default=[v for v in valores_def if v in opcoes])
        elif filtro_tipo == "Manual" and not df_participantes.empty:
            col_n = "Nome" if "Nome" in df_participantes.columns else "nome"
            opcoes = sorted(df_participantes[col_n].unique().tolist())
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

convocados_df = filtrar_participantes_convocados(df_participantes, reuniao_ativa)
col_id_conv = "ID" if "ID" in convocados_df.columns else "id"
ids_permitidos = set(convocados_df[col_id_conv].values.tolist()) if not convocados_df.empty else set()

# -------------------------------------------------------
# CÂMERA ÚNICA — funciona em Android, iOS e Desktop
# Tira foto e processa QR automaticamente via OpenCV
# -------------------------------------------------------
st.markdown("### 📷 Aponte a câmera para o QR Code e tire a foto")
st.caption("Funciona em celular (Android/iOS) e computador. Após a foto, o registro é automático.")

camera_key = f"camera_{st.session_state.camera_key}"
img = st.camera_input("📸 Tirar foto do QR Code", key=camera_key)

if img:
    codigo = processar_qr_code_imagem(img)
    if codigo:
        agora = time_module.time()
        # Debounce: ignora se o mesmo código foi lido nos últimos 3 segundos
        mesmo_codigo = (codigo == st.session_state.ultimo_codigo_lido)
        dentro_do_cooldown = (agora - st.session_state.ultimo_lido_ts) < 3.0
        if mesmo_codigo and dentro_do_cooldown:
            st.info(f"⏳ Aguarde para registrar novamente.")
        else:
            st.session_state.ultimo_codigo_lido = codigo
            st.session_state.ultimo_lido_ts = agora
            sucesso = registrar_presenca(codigo, df_participantes, ids_permitidos, reuniao_ativa["id"])
            if sucesso:
                # Reseta câmera para nova leitura
                st.session_state.camera_key += 1
                st.rerun()
    else:
        st.warning("⚠️ QR Code não detectado. Tente melhorar a iluminação ou aproximar mais.")

# --- Área de Resultados ---
if not st.session_state.lista_presenca.empty:
    st.divider()
    st.markdown("### 📊 Resumo")
    resumo_cargo = st.session_state.lista_presenca["Cargo"].value_counts()
    resumo_local = st.session_state.lista_presenca["Localidade"].value_counts()
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.dataframe(resumo_cargo, use_container_width=True)
    with col_r2:
        st.dataframe(resumo_local, use_container_width=True)
    st.divider()
    st.markdown("### 📝 Lista de Presentes")
    st.dataframe(
        st.session_state.lista_presenca[["Nome", "Cargo", "Localidade", "Horario"]],
        use_container_width=True,
        hide_index=True,
    )
    st.divider()
    colA, colB, colC = st.columns(3)
    nome_arquivo = f"{reuniao_ativa.get('data','')}_{reuniao_ativa.get('hora','')}_{reuniao_ativa.get('nome','reuniao')}".replace(" ", "_")
    with colA:
        if st.button("📄 PDF"):
            pdf_data = gerar_pdf(st.session_state.lista_presenca, resumo_cargo, resumo_local, reuniao_ativa.get("nome", "Reunião"))
            st.download_button("Baixar PDF", data=pdf_data, file_name=f"{nome_arquivo}.pdf", mime="application/pdf")
    with colB:
        if st.button("📋 Excel"):
            excel_data = gerar_excel(st.session_state.lista_presenca, resumo_cargo, resumo_local, reuniao_ativa.get("nome", "Reunião"))
            st.download_button("Baixar Excel", data=excel_data, file_name=f"{nome_arquivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with colC:
        if st.button("🗑️ Limpar"):
            if limpar_presencas_reuniao(reuniao_ativa["id"]):
                st.session_state.lista_presenca = pd.DataFrame(columns=["ID", "Nome", "Cargo", "Localidade", "Horario"])
                st.rerun()
