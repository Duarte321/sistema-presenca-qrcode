import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, date, time
import pytz
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import json
from supabase import create_client, Client
from pyzbar.pyzbar import decode
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

st.set_page_config(page_title="Check-in Musical", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
/* Cards de feedback */
.card-ok {
    background: linear-gradient(135deg,#1a7a4a,#25a060);
    color:white; padding:20px 28px; border-radius:16px;
    font-size:1.5rem; font-weight:bold; text-align:center;
    margin:10px 0; box-shadow: 0 4px 16px rgba(37,160,96,0.4);
    animation: pulse 0.4s ease-in-out;
}
.card-warn {
    background: linear-gradient(135deg,#7a6200,#c9960c);
    color:white; padding:18px 24px; border-radius:16px;
    font-size:1.2rem; font-weight:bold; text-align:center; margin:10px 0;
}
.card-erro {
    background: linear-gradient(135deg,#7a1a1a,#c0392b);
    color:white; padding:18px 24px; border-radius:16px;
    font-size:1.2rem; font-weight:bold; text-align:center; margin:10px 0;
}
.card-aguard {
    background: linear-gradient(135deg,#1a3a5a,#1e6091);
    color:white; padding:16px 24px; border-radius:16px;
    font-size:1rem; text-align:center; margin:10px 0;
}
/* Destaque no ultimo registrado */
.ultimo-reg {
    background: #0d1b2a;
    border-left: 5px solid #00d4aa;
    padding: 14px 20px; border-radius: 10px;
    color: #e0f7f4; font-size: 1rem; margin: 8px 0;
}
/* Camera maior */
[data-testid="stCameraInput"] video,
[data-testid="stCameraInput"] img {
    border-radius: 14px !important;
    border: 3px solid #00d4aa !important;
}
@keyframes pulse {
    0%   { transform: scale(0.97); }
    60%  { transform: scale(1.02); }
    100% { transform: scale(1.00); }
}
</style>
""", unsafe_allow_html=True)

# ── Supabase ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase_client = get_supabase()

def obter_hora_atual():
    return datetime.now(pytz.timezone("America/Cuiaba"))

def _parse_date(s): return datetime.strptime(s, "%Y-%m-%d").date()
def _parse_time(s): return datetime.strptime(s, "%H:%M").time()

# ── Decodificador robusto de QR ───────────────────────────────────────────────
def decodificar_qr_robusto(img: Image.Image) -> str | None:
    """
    Tenta decodificar o QR Code com varios pre-processamentos
    para maximizar a taxa de leitura em fotos de baixa qualidade.
    """
    def tentar(im):
        resultado = decode(im)
        if resultado:
            return resultado[0].data.decode("utf-8").strip()
        return None

    # 1. Imagem original
    r = tentar(img)
    if r: return r

    # 2. Escala de cinza
    gray = img.convert("L")
    r = tentar(gray)
    if r: return r

    # 3. Aumentar contraste
    contraste = ImageEnhance.Contrast(gray).enhance(2.5)
    r = tentar(contraste)
    if r: return r

    # 4. Nitidez
    nitidez = ImageEnhance.Sharpness(gray).enhance(3.0)
    r = tentar(nitidez)
    if r: return r

    # 5. Redimensionar para 2x (ajuda em fotos pequenas)
    w, h = img.size
    grande = img.resize((w * 2, h * 2), Image.LANCZOS).convert("L")
    r = tentar(grande)
    if r: return r

    # 6. Binarizacao (threshold adaptativo)
    import numpy as np
    arr = np.array(contraste)
    _, binaria = (arr > 128), arr
    bin_img = Image.fromarray((arr > 128).astype(np.uint8) * 255)
    r = tentar(bin_img)
    if r: return r

    # 7. Inverter cores (QR claro em fundo escuro)
    invertida = Image.fromarray(255 - np.array(gray))
    r = tentar(invertida)
    if r: return r

    return None

# ── Participantes ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def carregar_dados_participantes():
    try:
        res = supabase_client.table("participantes").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.str.strip()
            return df
        return pd.DataFrame(columns=["id","nome","cargo","localidade"])
    except Exception as e:
        st.error(f"Erro: {e}"); return pd.DataFrame()

def filtrar_participantes_convocados(df, reuniao):
    if df.empty or not reuniao: return df
    tipo    = reuniao.get("filtro_tipo", "Todos")
    valores = reuniao.get("filtro_valores", [])
    cc = "Cargo" if "Cargo" in df.columns else "cargo"
    cl = "Localidade" if "Localidade" in df.columns else "localidade"
    cn = "Nome" if "Nome" in df.columns else "nome"
    if tipo == "Todos": return df
    if tipo == "Por Cargo": return df[df[cc].isin(valores)]
    if tipo == "Por Localidade": return df[df[cl].isin(valores)]
    if tipo == "Manual": return df[df[cn].isin(valores)]
    return df

# ── Presenças ─────────────────────────────────────────────────────────────────
def carregar_presencas_reuniao(mid):
    try:
        res = supabase_client.table("presencas").select("*").eq("meeting_id", str(mid)).execute()
        if not res.data:
            return pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"])
        df = pd.DataFrame(res.data).rename(columns={
            "id_participante":"ID","nome":"Nome","cargo":"Cargo",
            "localidade":"Localidade","horario":"Horario"})
        return df[["ID","Nome","Cargo","Localidade","Horario"]]
    except Exception as e:
        st.error(f"Erro: {e}")
        return pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"])

def salvar_presenca(mid, row):
    try:
        supabase_client.table("presencas").insert({
            "meeting_id": str(mid),
            "id_participante": str(row["ID"]),
            "nome": row["Nome"], "cargo": row["Cargo"],
            "localidade": row["Localidade"], "horario": row["Horario"],
            "data_registro": obter_hora_atual().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}"); return False

def limpar_presencas_reuniao(mid):
    try:
        supabase_client.table("presencas").delete().eq("meeting_id", str(mid)).execute()
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

# ── Reuniões ──────────────────────────────────────────────────────────────────
def carregar_reunioes():
    try:
        res = supabase_client.table("reunioes").select("*").order("data").execute()
        reunioes = res.data or []
        for r in reunioes:
            fv = r.get("filtro_valores")
            if isinstance(fv, str):
                try: r["filtro_valores"] = json.loads(fv)
                except: r["filtro_valores"] = []
            elif fv is None:
                r["filtro_valores"] = []
        return reunioes
    except Exception as e:
        st.error(f"Erro: {e}"); return []

def _gerar_id_reuniao():
    return obter_hora_atual().strftime("%Y%m%d%H%M%S%f")

def excluir_reuniao(reunioes, rid):
    try: supabase_client.table("reunioes").delete().eq("id", rid).execute()
    except Exception as e: st.error(f"Erro: {e}")
    return carregar_reunioes()

def atualizar_ou_criar_reuniao(reunioes, reuniao):
    if not reuniao.get("id"):
        reuniao["id"] = _gerar_id_reuniao()
        reuniao["criada_em"] = obter_hora_atual().isoformat(timespec="seconds")
    try: supabase_client.table("reunioes").upsert(reuniao).execute()
    except Exception as e: st.error(f"Erro: {e}")
    return carregar_reunioes()

def label_reuniao(r):
    return f"{r.get('data','?')} {r.get('hora','?')} - {r.get('nome','?')}"

# ── Registro central ──────────────────────────────────────────────────────────
def registrar_por_codigo(codigo, df_part, meeting_id):
    codigo = str(codigo).strip()
    if not codigo: return None, None
    ci = "ID" if "ID" in df_part.columns else "id"
    cn = "Nome" if "Nome" in df_part.columns else "nome"
    cc = "Cargo" if "Cargo" in df_part.columns else "cargo"
    cl = "Localidade" if "Localidade" in df_part.columns else "localidade"
    part = df_part[df_part[ci].astype(str).str.strip() == codigo]
    if part.empty:
        return "erro", f"Codigo '{codigo}' nao encontrado."
    nome = part.iloc[0][cn]
    id_p = str(part.iloc[0][ci]).strip()
    ja = st.session_state.lista_presenca
    if not ja.empty and id_p in ja["ID"].astype(str).values:
        return "duplicado", f"{nome} ja foi registrado antes."
    hora_reg = obter_hora_atual().strftime("%H:%M:%S")
    novo = {"ID": id_p, "Nome": nome,
            "Cargo": part.iloc[0][cc], "Localidade": part.iloc[0][cl],
            "Horario": hora_reg}
    if salvar_presenca(meeting_id, novo):
        st.session_state.lista_presenca = pd.concat(
            [st.session_state.lista_presenca, pd.DataFrame([novo])], ignore_index=True)
        st.session_state.ultimo_registrado = novo
        return "ok", nome
    return "erro", "Falha ao salvar no banco."

# ── Exportação ────────────────────────────────────────────────────────────────
def gerar_pdf(df_p, rc, rl, titulo):
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial","B",14)
            self.cell(0,10,f"Relatorio: {titulo}",0,1,"C")
            self.set_font("Arial","",10)
            self.cell(0,6,f"Gerado em: {obter_hora_atual().strftime('%d/%m/%Y %H:%M')}",0,1,"C")
            self.ln(4)
    pdf = PDF(); pdf.add_page()
    def tp(t):
        try: return str(t).encode("latin-1","replace").decode("latin-1")
        except: return str(t)
    pdf.set_font("Arial","B",12); pdf.cell(0,10,"RESUMO GERAL",ln=True)
    pdf.set_font("Arial",size=10)
    for c,q in rc.items(): pdf.cell(0,6,tp(f"  Cargo {c}: {q}"),ln=True)
    pdf.ln(4)
    for l,q in rl.items(): pdf.cell(0,6,tp(f"  Local {l}: {q}"),ln=True)
    pdf.ln(8); pdf.set_font("Arial","B",12)
    pdf.cell(0,10,"LISTA DE PRESENTES",ln=True)
    pdf.set_fill_color(200,220,255); pdf.set_font("Arial","B",8)
    cw=[60,50,50,30]
    for h2,w2 in zip(["Nome","Cargo","Localidade","Horario"],cw): pdf.cell(w2,8,h2,1,0,"C",1)
    pdf.ln(); pdf.set_font("Arial",size=7)
    for _,row in df_p.iterrows():
        pdf.cell(cw[0],8,tp(str(row["Nome"])[:35]),1)
        pdf.cell(cw[1],8,tp(str(row["Cargo"])[:28]),1)
        pdf.cell(cw[2],8,tp(str(row["Localidade"])[:28]),1)
        pdf.cell(cw[3],8,str(row["Horario"]),1,1)
    return bytes(pdf.output())

def gerar_excel(df_p, rc, rl, titulo):
    wb = Workbook(); wb.remove(wb.active)
    hf   = Font(name="Calibri",size=12,bold=True,color="FFFFFF")
    hfill= PatternFill(start_color="1F4E78",end_color="1F4E78",fill_type="solid")
    ha   = Alignment(horizontal="center",vertical="center",wrap_text=True)
    bd   = Border(left=Side(style="thin"),right=Side(style="thin"),
                  top=Side(style="thin"),bottom=Side(style="thin"))
    ws = wb.create_sheet("Resumo",0)
    ws["A1"] = f"Relatorio: {titulo}"; ws["A1"].font=Font(name="Calibri",size=14,bold=True)
    ws.merge_cells("A1:D1"); ws["A3"]="Resumo por Cargo"; ws["A3"].font=Font(bold=True)
    ws.append(["Cargo","Qtd"])
    for cell in ws[4]: cell.font=hf;cell.fill=hfill;cell.alignment=ha;cell.border=bd
    for c,q in rc.items():
        ws.append([c,int(q)])
        for cell in ws[ws.max_row]: cell.border=bd
    ws.append([]); ws.append(["Resumo por Localidade",""])
    ws[ws.max_row][0].font=Font(bold=True)
    ws.append(["Localidade","Qtd"])
    for cell in ws[ws.max_row]: cell.font=hf;cell.fill=hfill;cell.alignment=ha;cell.border=bd
    for l,q in rl.items():
        ws.append([l,int(q)])
        for cell in ws[ws.max_row]: cell.border=bd
    ws.column_dimensions["A"].width=40; ws.column_dimensions["B"].width=12
    wl = wb.create_sheet("Lista Nominal",1)
    wl.append(["ID","Nome","Cargo","Localidade","Horario"])
    for cell in wl[1]: cell.font=hf;cell.fill=hfill;cell.alignment=ha;cell.border=bd
    for r in df_p.itertuples(index=False):
        wl.append([r.ID,r.Nome,r.Cargo,r.Localidade,r.Horario])
        for cell in wl[wl.max_row]: cell.border=bd
    for col,w2 in zip(["A","B","C","D","E"],[12,35,20,25,12]):
        wl.column_dimensions[col].width=w2
    eb=BytesIO(); wb.save(eb); eb.seek(0)
    return eb.getvalue()

# ══════════════════════════════════════════════════════════════════════════════
# INICIALIZACAO
# ══════════════════════════════════════════════════════════════════════════════
df_participantes = carregar_dados_participantes()
if not df_participantes.empty:
    df_participantes = df_participantes.rename(
        columns={"id":"ID","nome":"Nome","cargo":"Cargo","localidade":"Localidade"})

reunioes = carregar_reunioes()
hoje = date.today().strftime("%Y-%m-%d")

defaults = {
    "active_meeting_id": None,
    "lista_presenca": pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"]),
    "feedback_status": None,
    "feedback_msg": "",
    "ultimo_registrado": None,
    "modo_continuo": True,
    "ultima_foto_hash": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Agenda")
    mostrar_passadas = st.checkbox("Mostrar passadas", value=False)
    reunioes_visiveis = [r for r in reunioes if mostrar_passadas or r.get("data","") >= hoje]
    reunioes_hoje = [r for r in reunioes if r.get("data") == hoje]
    if reunioes_hoje:
        st.markdown("**Hoje:**")
        for r in reunioes_hoje[:6]:
            if st.button(f"▶ {r.get('hora','')} - {r.get('nome','')}", key=f"st_{r['id']}"):
                st.session_state.active_meeting_id = r["id"]
                st.session_state.lista_presenca = carregar_presencas_reuniao(r["id"])
                st.session_state.feedback_status = None
                st.session_state.ultimo_registrado = None
                st.rerun()
    st.divider()
    reuniao_selecionada_id = None
    if reunioes_visiveis:
        labels = [label_reuniao(r) for r in reunioes_visiveis]
        ids    = [r["id"] for r in reunioes_visiveis]
        di = ids.index(st.session_state.active_meeting_id) if st.session_state.active_meeting_id in ids else 0
        si = st.selectbox("Reuniao", range(len(ids)), format_func=lambda i: labels[i], index=di)
        reuniao_selecionada_id = ids[si]
    else:
        st.info("Nenhuma reuniao agendada.")
    if reuniao_selecionada_id:
        lbl = "↺ Recarregar" if st.session_state.active_meeting_id == reuniao_selecionada_id else "▶ Iniciar check-in"
        if st.button(lbl, type="primary"):
            st.session_state.active_meeting_id = reuniao_selecionada_id
            st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_selecionada_id)
            st.session_state.feedback_status = None
            st.session_state.ultimo_registrado = None
            st.rerun()
    st.divider()
    st.header("Criar / Editar")
    modo = st.radio("Modo", ["Criar nova", "Editar selecionada"], index=1 if reuniao_selecionada_id else 0)
    rae = None
    if modo == "Editar selecionada" and reuniao_selecionada_id:
        for r in reunioes:
            if r.get("id") == reuniao_selecionada_id: rae = r; break
    nome_def   = rae.get("nome","") if rae else ""
    data_def   = _parse_date(rae.get("data",hoje)) if rae else date.today()
    hora_def   = _parse_time(rae.get("hora","19:30")) if rae else time(19,30)
    filtro_def = rae.get("filtro_tipo","Todos") if rae else "Todos"
    vals_def   = rae.get("filtro_valores",[]) if rae else []
    with st.form("form_reuniao"):
        ni  = st.text_input("Nome", value=nome_def, placeholder="Ex: Ensaio Regional")
        di2 = st.date_input("Data", value=data_def)
        hi  = st.time_input("Horario", value=hora_def)
        st.markdown("**Convocacao**")
        ops=["Todos","Por Cargo","Por Localidade","Manual"]
        ft = st.radio("Tipo", ops, index=ops.index(filtro_def) if filtro_def in ops else 0)
        vals=[]
        if ft=="Por Cargo" and not df_participantes.empty:
            op2=sorted(df_participantes["Cargo"].unique())
            vals=st.multiselect("Cargos",op2,default=[v for v in vals_def if v in op2])
        elif ft=="Por Localidade" and not df_participantes.empty:
            op2=sorted(df_participantes["Localidade"].unique())
            vals=st.multiselect("Localidades",op2,default=[v for v in vals_def if v in op2])
        elif ft=="Manual" and not df_participantes.empty:
            op2=sorted(df_participantes["Nome"].unique())
            vals=st.multiselect("Nomes",op2,default=[v for v in vals_def if v in op2])
        salvar=st.form_submit_button("Salvar")
    if salvar:
        if not ni.strip(): st.error("Informe o nome.")
        else:
            payload={"id":rae.get("id") if (modo=="Editar selecionada" and rae) else None,
                     "nome":ni.strip(),"data":di2.strftime("%Y-%m-%d"),
                     "hora":hi.strftime("%H:%M"),"filtro_tipo":ft,
                     "filtro_valores":vals if ft!="Todos" else []}
            reunioes=atualizar_ou_criar_reuniao(reunioes,payload)
            st.success("Reuniao salva!"); st.rerun()
    if modo=="Editar selecionada" and rae:
        st.divider()
        conf=st.checkbox("Confirmar exclusao")
        if st.button("Excluir reuniao", disabled=not conf):
            reunioes=excluir_reuniao(reunioes,rae["id"])
            if st.session_state.active_meeting_id==rae["id"]:
                st.session_state.active_meeting_id=None
            st.success("Reuniao excluida!"); st.rerun()

# ── Reuniao Ativa ──────────────────────────────────────────────────────────────
reuniao_ativa = None
if st.session_state.active_meeting_id:
    for r in reunioes:
        if r.get("id")==st.session_state.active_meeting_id:
            reuniao_ativa=r; break
    if not reuniao_ativa:
        st.session_state.active_meeting_id=None; st.rerun()

if not reuniao_ativa:
    st.title("Check-in Musical")
    st.warning("Selecione uma reuniao no menu lateral e clique em Iniciar check-in.")
    st.stop()

# ── Cabecalho ──────────────────────────────────────────────────────────────────
st.title(f"\U0001f3b5  {reuniao_ativa.get('nome')}")
st.caption(f"Data: {reuniao_ativa.get('data','?')}  |  Hora: {reuniao_ativa.get('hora','?')}")

conv_df    = filtrar_participantes_convocados(df_participantes, reuniao_ativa)
total_conv = len(conv_df)
total_pres = len(st.session_state.lista_presenca)
porc       = int(total_pres / total_conv * 100) if total_conv > 0 else 0

cc1,cc2,cc3,cc4 = st.columns(4)
cc1.metric("Convocados",  total_conv)
cc2.metric("Presentes",   total_pres, delta=f"+{total_pres}" if total_pres else None)
cc3.metric("Faltantes",   max(0, total_conv - total_pres))
cc4.metric("Presença",    f"{porc}%")
st.progress(porc / 100)
st.divider()

# ── Abas ───────────────────────────────────────────────────────────────────────
aba_cam, aba_manual, aba_lista = st.tabs([
    "📷  Câmera QR",
    "⌨️  Digitar / Buscar",
    "📋  Lista de Presentes"
])

# ──────────── ABA CAMERA ───────────────────────────────────────────────────────
with aba_cam:
    col_cam, col_result = st.columns([1, 1])

    with col_cam:
        st.markdown("##### 📷 Aponte para o QR Code do crachá")
        st.caption("Boa iluminação = leitura mais rápida. O sistema tenta 7 modos de leitura automaticamente.")

        # Modo continuo: a camera nao trava apos a leitura
        modo_continuo = st.toggle("🔄 Modo contínuo (pronto para próximo)",
                                   value=st.session_state.modo_continuo,
                                   help="Ativado: apos cada leitura a camera fica pronta pro proximo sem precisar clicar.")
        st.session_state.modo_continuo = modo_continuo

        foto = st.camera_input("", label_visibility="collapsed", key="cam_qr")

    with col_result:
        st.markdown("##### Resultado")

        # Processa nova foto apenas se for diferente da anterior
        if foto is not None:
            foto_hash = hash(foto.getvalue())
            if foto_hash != st.session_state.ultima_foto_hash:
                st.session_state.ultima_foto_hash = foto_hash
                img = Image.open(foto)
                codigo_qr = decodificar_qr_robusto(img)

                if codigo_qr:
                    status, msg = registrar_por_codigo(codigo_qr, df_participantes, reuniao_ativa["id"])
                    st.session_state.feedback_status = status
                    st.session_state.feedback_msg    = msg
                    if modo_continuo and status in ("ok", "duplicado"):
                        # Limpa a chave da camera para resetar o widget
                        if "cam_qr" in st.session_state:
                            del st.session_state["cam_qr"]
                    st.rerun()
                else:
                    st.session_state.feedback_status = "sem_qr"
                    st.session_state.feedback_msg    = "QR Code nao identificado. Tente com mais luz ou mais proximo."
                    st.rerun()

        # Feedback visual
        s = st.session_state.feedback_status
        m = st.session_state.feedback_msg
        ur = st.session_state.ultimo_registrado

        if s == "ok" and ur:
            st.markdown(f'<div class="card-ok">✅ Registrado!<br><span style="font-size:1.1rem">{ur["Nome"]}</span></div>', unsafe_allow_html=True)
            st.markdown(f"""
<div class="ultimo-reg">
🎸 <b>Instrumento/Cargo:</b> {ur["Cargo"]}<br>
📍 <b>Localidade:</b> {ur["Localidade"]}<br>
🕐 <b>Horario:</b> {ur["Horario"]}
</div>""", unsafe_allow_html=True)
            if modo_continuo:
                st.info("📸 Câmera pronta para o próximo crachá!")
        elif s == "duplicado":
            st.markdown(f'<div class="card-warn">⚠️ Já registrado!<br><span style="font-size:0.95rem">{m}</span></div>', unsafe_allow_html=True)
            if modo_continuo:
                st.info("📸 Câmera pronta para o próximo crachá!")
        elif s == "erro":
            st.markdown(f'<div class="card-erro">❌ {m}</div>', unsafe_allow_html=True)
        elif s == "sem_qr":
            st.markdown(f'<div class="card-aguard">📷 {m}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="card-aguard">📷 Aguardando foto do QR Code...</div>', unsafe_allow_html=True)

        # Mini contador atualizado
        st.markdown(f"---")
        st.metric("Total de presentes", len(st.session_state.lista_presenca))

        # Ultimo registrado (persistente)
        if ur and s == "ok":
            pass  # ja mostrado acima
        elif st.session_state.lista_presenca is not None and not st.session_state.lista_presenca.empty:
            ult = st.session_state.lista_presenca.iloc[-1]
            st.markdown(f'<div class="ultimo-reg">⏱ Último: <b>{ult["Nome"]}</b> — {ult["Horario"]}</div>', unsafe_allow_html=True)

# ──────────── ABA MANUAL ───────────────────────────────────────────────────────
with aba_manual:
    st.markdown("##### Digite o código do crachá ou busque pelo nome")
    tab_codigo, tab_nome = st.tabs(["🔢 Pelo Código", "🔍 Pelo Nome"])

    with tab_codigo:
        with st.form("form_manual", clear_on_submit=True):
            col_in, col_btn = st.columns([3,1])
            with col_in:
                codigo_digitado = st.text_input(
                    "Codigo", placeholder="Ex: LC005, CF001...",
                    label_visibility="collapsed"
                ).strip().upper()
            with col_btn:
                confirmar = st.form_submit_button("✔ Registrar", type="primary", use_container_width=True)
        if confirmar and codigo_digitado:
            status, msg = registrar_por_codigo(codigo_digitado, df_participantes, reuniao_ativa["id"])
            st.session_state.feedback_status = status
            st.session_state.feedback_msg    = msg
            st.rerun()
        # Feedback
        s, m = st.session_state.feedback_status, st.session_state.feedback_msg
        if s == "ok":
            ur = st.session_state.ultimo_registrado
            st.markdown(f'<div class="card-ok">✅ Registrado: {ur["Nome"] if ur else m}</div>', unsafe_allow_html=True)
        elif s == "duplicado":
            st.markdown(f'<div class="card-warn">⚠️ {m}</div>', unsafe_allow_html=True)
        elif s == "erro":
            st.markdown(f'<div class="card-erro">❌ {m}</div>', unsafe_allow_html=True)

    with tab_nome:
        if not df_participantes.empty:
            nome_busca = st.text_input("Nome:", placeholder="Digite parte do nome...")
            if nome_busca.strip():
                filtrado = df_participantes[
                    df_participantes["Nome"].str.contains(nome_busca.strip(), case=False, na=False)
                ][["ID","Nome","Cargo","Localidade"]]
                if not filtrado.empty:
                    st.dataframe(filtrado, hide_index=True, use_container_width=True)
                    codigo_sel = st.selectbox(
                        "Selecione:",
                        options=filtrado["ID"].tolist(),
                        format_func=lambda x: f"{x}  —  {filtrado[filtrado['ID']==x]['Nome'].values[0]}"
                    )
                    if st.button("✔ Registrar selecionado", type="primary"):
                        status, msg = registrar_por_codigo(str(codigo_sel), df_participantes, reuniao_ativa["id"])
                        st.session_state.feedback_status = status
                        st.session_state.feedback_msg    = msg
                        st.rerun()
                else:
                    st.info("Nenhum participante encontrado.")

# ──────────── ABA LISTA ─────────────────────────────────────────────────────────
with aba_lista:
    if not st.session_state.lista_presenca.empty:
        df_pres = st.session_state.lista_presenca
        rc = df_pres["Cargo"].value_counts()
        rl = df_pres["Localidade"].value_counts()
        c1,c2 = st.columns(2)
        c1.markdown("**Por Cargo**"); c1.dataframe(rc, use_container_width=True)
        c2.markdown("**Por Localidade**"); c2.dataframe(rl, use_container_width=True)
        st.divider()
        st.dataframe(df_pres[["Nome","Cargo","Localidade","Horario"]],
                     use_container_width=True, hide_index=True)
        st.divider()
        arq = f"{reuniao_ativa.get('data','')}_{reuniao_ativa.get('hora','')}_{reuniao_ativa.get('nome','reuniao')}".replace(" ","_")
        cA,cB,cC = st.columns(3)
        with cA:
            if st.button("Gerar PDF"):
                st.download_button("⬇ Baixar PDF",
                    data=gerar_pdf(df_pres,rc,rl,reuniao_ativa.get("nome","Reuniao")),
                    file_name=f"{arq}.pdf", mime="application/pdf")
        with cB:
            if st.button("Gerar Excel"):
                st.download_button("⬇ Baixar Excel",
                    data=gerar_excel(df_pres,rc,rl,reuniao_ativa.get("nome","Reuniao")),
                    file_name=f"{arq}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with cC:
            if st.button("🗑 Limpar lista"):
                if limpar_presencas_reuniao(reuniao_ativa["id"]):
                    st.session_state.lista_presenca = pd.DataFrame(
                        columns=["ID","Nome","Cargo","Localidade","Horario"])
                    st.session_state.ultimo_registrado = None
                    st.rerun()
    else:
        st.info("Nenhuma presenca registrada ainda.")
        if st.button("↺ Recarregar do banco"):
            st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_ativa["id"])
            st.rerun()
