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
import plotly.express as px

st.set_page_config(
    page_title="CCB Musical — Check-in",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═════════════════════ CSS GLOBAL ═════════════════════
st.markdown("""
<style>
/* ===== BASE ===== */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1530 50%, #0a0e1a 100%);
    min-height: 100vh;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1530 0%, #111827 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.25) !important;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: rgba(99,102,241,0.15) !important;
    border: 1px solid rgba(99,102,241,0.4) !important;
    color: #c7d2fe !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}

/* ===== BANNER ===== */
.banner {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4c1d95 100%);
    border: 1px solid rgba(139,92,246,0.4);
    border-radius: 20px;
    padding: 22px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 18px;
    box-shadow: 0 8px 32px rgba(99,102,241,0.3);
}
.banner-icon { font-size: 2.6rem; }
.banner-title { color:#fff; font-size:1.7rem; font-weight:800; margin:0; }
.banner-sub   { color:#a5b4fc; font-size:0.9rem; margin:4px 0 0; }

/* ===== METRIC CARDS ===== */
.metric-row { display:flex; gap:14px; margin-bottom:18px; flex-wrap:wrap; }
.metric-card {
    flex:1; min-width:120px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius:16px; padding:18px 14px;
    text-align:center;
    transition: transform 0.2s, box-shadow 0.2s;
}
.metric-card:hover { transform:translateY(-3px); box-shadow:0 8px 24px rgba(0,0,0,0.3); }
.metric-value { font-size:2.2rem; font-weight:800; margin:0; line-height:1; }
.metric-label { font-size:0.76rem; text-transform:uppercase; letter-spacing:1px; margin-top:5px; opacity:0.7; }
.mc-blue   .metric-value { color:#60a5fa; }
.mc-green  .metric-value { color:#34d399; }
.mc-red    .metric-value { color:#f87171; }
.mc-purple .metric-value { color:#a78bfa; }
.mc-purple { border-color:rgba(167,139,250,0.3) !important; }
.mc-blue   { border-color:rgba(96,165,250,0.3)  !important; }
.mc-green  { border-color:rgba(52,211,153,0.3)  !important; }
.mc-red    { border-color:rgba(248,113,113,0.3) !important; }

/* ===== PROGRESS ===== */
.prog-wrap {
    background:rgba(255,255,255,0.08);
    border-radius:99px; height:10px;
    margin:0 0 26px; overflow:hidden;
    box-shadow:inset 0 2px 4px rgba(0,0,0,0.3);
}
.prog-fill {
    height:100%; border-radius:99px;
    background:linear-gradient(90deg,#6366f1,#8b5cf6,#06b6d4);
    transition:width 0.6s ease;
    box-shadow:0 0 12px rgba(99,102,241,0.6);
}

/* ===== FEEDBACK ===== */
.fb-ok {
    background:linear-gradient(135deg,#064e3b,#065f46);
    border:1px solid #34d399; border-radius:18px;
    padding:22px 28px; text-align:center; margin:12px 0;
    box-shadow:0 0 24px rgba(52,211,153,0.25);
    animation:bounceIn 0.4s ease;
}
.fb-ok .fb-title { color:#6ee7b7; font-size:1.1rem; font-weight:600; }
.fb-ok .fb-nome  { color:#fff;    font-size:1.5rem; font-weight:800; margin:4px 0; }
.fb-warn { background:linear-gradient(135deg,#451a03,#78350f); border:1px solid #f59e0b; border-radius:18px; padding:18px 24px; text-align:center; margin:12px 0; }
.fb-warn .fb-title { color:#fcd34d; font-size:1rem; font-weight:700; }
.fb-erro { background:linear-gradient(135deg,#450a0a,#7f1d1d); border:1px solid #f87171; border-radius:18px; padding:18px 24px; text-align:center; margin:12px 0; }
.fb-erro .fb-title { color:#fca5a5; font-size:1rem; font-weight:700; }
.fb-idle { background:rgba(99,102,241,0.08); border:1px dashed rgba(99,102,241,0.4); border-radius:18px; padding:18px 24px; text-align:center; margin:12px 0; }
.fb-idle .fb-title { color:#a5b4fc; font-size:0.95rem; }

/* ===== MEMBRO CARD ===== */
.membro-card {
    background:rgba(255,255,255,0.05);
    border:1px solid rgba(99,102,241,0.3);
    border-left:4px solid #6366f1;
    border-radius:12px; padding:14px 18px; margin:10px 0;
}
.membro-card .m-nome { color:#e2e8f0; font-size:1rem; font-weight:700; }
.membro-card .m-det  { color:#94a3b8; font-size:0.85rem; margin-top:4px; }

/* ===== REUNIAO CARD ===== */
.reuniao-card {
    background:linear-gradient(135deg,rgba(99,102,241,0.12),rgba(139,92,246,0.08));
    border:1px solid rgba(99,102,241,0.35);
    border-radius:20px; padding:26px 28px; margin:12px 0;
    transition:transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}
.reuniao-card:hover { transform:translateY(-4px); box-shadow:0 12px 36px rgba(99,102,241,0.25); border-color:rgba(139,92,246,0.6); }
.reuniao-card .rc-hora { color:#a5b4fc; font-size:1rem; font-weight:600; margin:0 0 6px; letter-spacing:1px; }
.reuniao-card .rc-nome { color:#fff;    font-size:1.45rem; font-weight:800; margin:0 0 10px; }
.reuniao-card .rc-data { color:#64748b; font-size:0.85rem; }
.reuniao-hoje-badge {
    display:inline-block;
    background:linear-gradient(90deg,#22c55e,#16a34a);
    color:white; font-size:0.68rem; font-weight:700;
    letter-spacing:1px; padding:2px 10px; border-radius:99px;
    margin-left:8px; vertical-align:middle;
}

/* ===== BOTAO VOLTAR ===== */
.btn-voltar-wrap { margin-bottom:18px; }
.btn-nav-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin: 18px 0;
}
.btn-nav-item {
    background: rgba(99,102,241,0.12);
    border: 1.5px solid rgba(99,102,241,0.4);
    border-radius: 16px;
    padding: 22px 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    color: #c7d2fe;
    font-weight: 700;
    font-size: 1rem;
}
.btn-nav-item:hover {
    background: rgba(99,102,241,0.25);
    border-color: rgba(139,92,246,0.7);
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(99,102,241,0.3);
}
.btn-nav-item .nav-icon { font-size: 2rem; margin-bottom: 8px; }
.btn-nav-item .nav-label { font-size: 0.9rem; letter-spacing: 0.5px; }

/* ===== FORMULARIO REUNIAO ===== */
.form-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 18px;
    padding: 24px 28px;
    margin-bottom: 20px;
}

/* ===== CAMERA ===== */
[data-testid="stCameraInput"] > div {
    border-radius:18px !important; overflow:hidden !important;
    border:2px solid rgba(99,102,241,0.5) !important;
    box-shadow:0 0 20px rgba(99,102,241,0.2) !important;
}

/* ===== TABS ===== */
[data-testid="stTabs"] [role="tab"] {
    background:rgba(255,255,255,0.04) !important;
    border-radius:10px 10px 0 0 !important;
    color:#94a3b8 !important; font-weight:600 !important;
    padding:10px 22px !important;
    border:1px solid rgba(255,255,255,0.08) !important;
    border-bottom:none !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    background:linear-gradient(135deg,rgba(99,102,241,0.25),rgba(139,92,246,0.2)) !important;
    color:#c7d2fe !important; border-color:rgba(99,102,241,0.5) !important;
}

/* ===== DATAFRAME ===== */
[data-testid="stDataFrame"] { border-radius:12px !important; overflow:hidden !important; border:1px solid rgba(255,255,255,0.08) !important; }

/* ===== SECTION HEADER ===== */
.sec-header {
    color:#c7d2fe; font-size:0.75rem; font-weight:700;
    text-transform:uppercase; letter-spacing:2px;
    margin:18px 0 10px; display:flex; align-items:center; gap:8px;
}
.sec-header::after { content:''; flex:1; height:1px; background:rgba(99,102,241,0.3); }

/* ===== BOTOES ===== */
.stButton > button {
    border-radius:12px !important; font-weight:600 !important; transition:all 0.2s !important;
}
.stButton > button[kind="primary"] {
    background:linear-gradient(135deg,#6366f1,#8b5cf6) !important;
    border:none !important;
    box-shadow:0 4px 14px rgba(99,102,241,0.4) !important;
    color:white !important;
}
.stButton > button[kind="primary"]:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 6px 20px rgba(99,102,241,0.55) !important;
}

/* ===== INPUT ===== */
.stTextInput input {
    background:rgba(255,255,255,0.06) !important;
    border:1px solid rgba(99,102,241,0.35) !important;
    border-radius:10px !important; color:#e2e8f0 !important;
}
.stTextInput input:focus {
    border-color:#6366f1 !important;
    box-shadow:0 0 0 3px rgba(99,102,241,0.2) !important;
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb { background:rgba(99,102,241,0.4); border-radius:99px; }

/* ===== ANIMATIONS ===== */
@keyframes bounceIn {
    0%   { transform:scale(0.9); opacity:0; }
    60%  { transform:scale(1.04); opacity:1; }
    100% { transform:scale(1); }
}
@keyframes fadeSlide {
    from { opacity:0; transform:translateY(8px); }
    to   { opacity:1; transform:translateY(0); }
}
.fade-slide { animation:fadeSlide 0.35s ease; }

[data-testid="stMetric"] { background:rgba(255,255,255,0.04) !important; border:1px solid rgba(255,255,255,0.1) !important; border-radius:14px !important; padding:14px !important; }
[data-testid="stMetricValue"] { color:#a5b4fc !important; }
[data-testid="stMetricLabel"] { color:#64748b !important; font-size:0.78rem !important; }

#MainMenu, footer, header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)


# ════════════════════ HELPERS ════════════════════
def sec(icone, texto):
    st.markdown(f'<p class="sec-header">{icone}&nbsp;{texto}</p>', unsafe_allow_html=True)

def metric_card(valor, label, cor):
    return f'<div class="metric-card mc-{cor}"><p class="metric-value">{valor}</p><p class="metric-label">{label}</p></div>'

def botao_voltar(destino="home", label="⬅  Voltar"):
    if st.button(label, key=f"voltar_{destino}_{id(destino)}", use_container_width=False):
        st.session_state.pagina = destino
        st.session_state.feedback_status = None
        st.rerun()


# ════════════════════ SUPABASE ════════════════════
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase_client = get_supabase()

def obter_hora_atual():
    return datetime.now(pytz.timezone("America/Cuiaba"))

def _parse_date(s): return datetime.strptime(s, "%Y-%m-%d").date()
def _parse_time(s): return datetime.strptime(s, "%H:%M").time()


# ════════════════════ QR ROBUSTO ════════════════════
def decodificar_qr_robusto(img: Image.Image):
    def tentar(im):
        r = decode(im)
        return r[0].data.decode("utf-8").strip() if r else None
    for fn in [
        lambda i: i,
        lambda i: i.convert("L"),
        lambda i: ImageEnhance.Contrast(i.convert("L")).enhance(2.5),
        lambda i: ImageEnhance.Sharpness(i.convert("L")).enhance(3.0),
        lambda i: i.resize((i.width*2, i.height*2), Image.LANCZOS).convert("L"),
        lambda i: Image.fromarray((np.array(ImageEnhance.Contrast(i.convert("L")).enhance(2.5)) > 128).astype(np.uint8)*255),
        lambda i: Image.fromarray(255 - np.array(i.convert("L"))),
    ]:
        try:
            r = tentar(fn(img))
            if r: return r
        except: pass
    return None


# ════════════════════ DADOS ════════════════════
@st.cache_data(ttl=60)
def carregar_dados_participantes():
    try:
        res = supabase_client.table("participantes").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data); df.columns = df.columns.str.strip(); return df
        return pd.DataFrame(columns=["id","nome","cargo","localidade"])
    except Exception as e:
        st.error(f"Erro: {e}"); return pd.DataFrame()

def filtrar_convocados(df, reuniao):
    if df.empty or not reuniao: return df
    tipo = reuniao.get("filtro_tipo","Todos")
    vals = reuniao.get("filtro_valores",[])
    if tipo=="Por Cargo":      return df[df["Cargo"].isin(vals)]
    if tipo=="Por Localidade": return df[df["Localidade"].isin(vals)]
    if tipo=="Manual":         return df[df["Nome"].isin(vals)]
    return df

def carregar_presencas_reuniao(mid):
    try:
        res = supabase_client.table("presencas").select("*").eq("meeting_id",str(mid)).execute()
        if not res.data: return pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"])
        df = pd.DataFrame(res.data).rename(columns={
            "id_participante":"ID","nome":"Nome","cargo":"Cargo",
            "localidade":"Localidade","horario":"Horario"})
        return df[["ID","Nome","Cargo","Localidade","Horario"]]
    except Exception as e:
        st.error(f"Erro: {e}"); return pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"])

def salvar_presenca(mid, row):
    try:
        supabase_client.table("presencas").insert({
            "meeting_id":str(mid), "id_participante":str(row["ID"]),
            "nome":row["Nome"], "cargo":row["Cargo"],
            "localidade":row["Localidade"], "horario":row["Horario"],
            "data_registro":obter_hora_atual().isoformat()
        }).execute(); return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

def limpar_presencas_reuniao(mid):
    try: supabase_client.table("presencas").delete().eq("meeting_id",str(mid)).execute(); return True
    except Exception as e: st.error(f"Erro: {e}"); return False

def carregar_reunioes():
    try:
        res = supabase_client.table("reunioes").select("*").order("data").execute()
        reunioes = res.data or []
        for r in reunioes:
            fv = r.get("filtro_valores")
            if isinstance(fv,str):
                try: r["filtro_valores"]=json.loads(fv)
                except: r["filtro_valores"]=[]
            elif fv is None: r["filtro_valores"]=[]
        return reunioes
    except Exception as e: st.error(f"Erro: {e}"); return []

def atualizar_ou_criar_reuniao(reunioes, reuniao):
    if not reuniao.get("id"):
        reuniao["id"]=obter_hora_atual().strftime("%Y%m%d%H%M%S%f")
        reuniao["criada_em"]=obter_hora_atual().isoformat(timespec="seconds")
    try: supabase_client.table("reunioes").upsert(reuniao).execute()
    except Exception as e: st.error(f"Erro: {e}")
    return carregar_reunioes()

def excluir_reuniao(reunioes, rid):
    try: supabase_client.table("reunioes").delete().eq("id",rid).execute()
    except Exception as e: st.error(f"Erro: {e}")
    return carregar_reunioes()

def label_reuniao(r): return f"{r.get('data','?')} • {r.get('hora','?')} — {r.get('nome','?')}"

def registrar_por_codigo(codigo, df_part, meeting_id):
    codigo = str(codigo).strip()
    if not codigo: return None, None
    part = df_part[df_part["ID"].astype(str).str.strip()==codigo]
    if part.empty: return "erro", f"Código '{codigo}' não encontrado."
    nome = part.iloc[0]["Nome"]; id_p = str(part.iloc[0]["ID"]).strip()
    ja = st.session_state.lista_presenca
    if not ja.empty and id_p in ja["ID"].astype(str).values:
        return "duplicado", f"{nome} já foi registrado."
    hora_reg = obter_hora_atual().strftime("%H:%M:%S")
    novo = {"ID":id_p, "Nome":nome, "Cargo":part.iloc[0]["Cargo"],
            "Localidade":part.iloc[0]["Localidade"], "Horario":hora_reg}
    if salvar_presenca(meeting_id, novo):
        st.session_state.lista_presenca = pd.concat(
            [st.session_state.lista_presenca, pd.DataFrame([novo])], ignore_index=True)
        st.session_state.ultimo_registrado = novo
        return "ok", nome
    return "erro", "Falha ao salvar."


# ════════════════════ EXPORT ════════════════════
def gerar_pdf(df_p, rc, rl, titulo):
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial","B",14)
            self.cell(0,10,f"Relatorio: {titulo}",0,1,"C")
            self.set_font("Arial","",10)
            self.cell(0,6,f"Gerado em: {obter_hora_atual().strftime('%d/%m/%Y %H:%M')}",0,1,"C")
            self.ln(4)
    pdf=PDF(); pdf.add_page()
    def tp(t):
        try: return str(t).encode("latin-1","replace").decode("latin-1")
        except: return str(t)
    pdf.set_font("Arial","B",12); pdf.cell(0,10,"RESUMO",ln=True)
    pdf.set_font("Arial",size=10)
    for c,q in rc.items(): pdf.cell(0,6,tp(f"  {c}: {q}"),ln=True)
    for l,q in rl.items(): pdf.cell(0,6,tp(f"  {l}: {q}"),ln=True)
    pdf.ln(6); pdf.set_font("Arial","B",12); pdf.cell(0,10,"PRESENTES",ln=True)
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

def gerar_pdf_relatorio_geral(df_rel, titulo, data_ini, data_fim, total_reunioes, total_presencas):
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial","B",14)
            self.cell(0,10,tp(f"Relatorio Geral: {titulo}"),0,1,"C")
            self.set_font("Arial","",10)
            self.cell(0,6,f"Periodo: {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}",0,1,"C")
            self.cell(0,6,f"Gerado em: {obter_hora_atual().strftime('%d/%m/%Y %H:%M')}",0,1,"C")
            self.ln(4)
    def tp(t):
        try: return str(t).encode("latin-1","replace").decode("latin-1")
        except: return str(t)
    pdf=PDF(); pdf.add_page()
    pdf.set_font("Arial","B",12); pdf.cell(0,8,"RESUMO DO PERIODO",ln=True)
    pdf.set_font("Arial",size=10)
    pdf.cell(0,6,f"  Total de Reunioes: {total_reunioes}",ln=True)
    pdf.cell(0,6,f"  Total de Presencas: {total_presencas}",ln=True)
    pdf.cell(0,6,f"  Total de Participantes: {len(df_rel)}",ln=True)
    pdf.ln(4)
    pdf.set_font("Arial","B",12); pdf.cell(0,8,"RANKING DE PRESENCAS",ln=True)
    pdf.set_fill_color(200,220,255); pdf.set_font("Arial","B",8)
    cw2=[8,60,40,20,18]
    for h2,w2 in zip(["#","Nome","Cargo","Presencas","Freq%"],cw2): pdf.cell(w2,8,h2,1,0,"C",1)
    pdf.ln(); pdf.set_font("Arial",size=7)
    for i,(_,row) in enumerate(df_rel.iterrows(),1):
        pdf.cell(cw2[0],8,str(i),1)
        pdf.cell(cw2[1],8,tp(str(row["Nome"])[:38]),1)
        pdf.cell(cw2[2],8,tp(str(row["Cargo"])[:25]),1)
        pdf.cell(cw2[3],8,str(int(row["Presencas"])),1,0,"C")
        pdf.cell(cw2[4],8,f"{row['Frequencia_%']:.1f}%",1,1,"C")
    return bytes(pdf.output())

def gerar_excel(df_p, rc, rl, titulo):
    wb=Workbook(); wb.remove(wb.active)
    hf=Font(name="Calibri",size=12,bold=True,color="FFFFFF")
    hfill=PatternFill(start_color="1F4E78",end_color="1F4E78",fill_type="solid")
    ha=Alignment(horizontal="center",vertical="center",wrap_text=True)
    bd=Border(left=Side(style="thin"),right=Side(style="thin"),top=Side(style="thin"),bottom=Side(style="thin"))
    ws=wb.create_sheet("Resumo",0)
    ws["A1"]=f"Relatorio: {titulo}"; ws["A1"].font=Font(name="Calibri",size=14,bold=True)
    ws.merge_cells("A1:D1"); ws["A3"]="Por Cargo"; ws["A3"].font=Font(bold=True)
    ws.append(["Cargo","Qtd"])
    for cell in ws[4]: cell.font=hf;cell.fill=hfill;cell.alignment=ha;cell.border=bd
    for c,q in rc.items():
        ws.append([c,int(q)])
        for cell in ws[ws.max_row]: cell.border=bd
    ws.append([]); ws.append(["Por Localidade",""]); ws[ws.max_row][0].font=Font(bold=True)
    ws.append(["Localidade","Qtd"])
    for cell in ws[ws.max_row]: cell.font=hf;cell.fill=hfill;cell.alignment=ha;cell.border=bd
    for l,q in rl.items():
        ws.append([l,int(q)])
        for cell in ws[ws.max_row]: cell.border=bd
    ws.column_dimensions["A"].width=40; ws.column_dimensions["B"].width=12
    wl=wb.create_sheet("Lista",1)
    wl.append(["ID","Nome","Cargo","Localidade","Horario"])
    for cell in wl[1]: cell.font=hf;cell.fill=hfill;cell.alignment=ha;cell.border=bd
    for r in df_p.itertuples(index=False):
        wl.append([r.ID,r.Nome,r.Cargo,r.Localidade,r.Horario])
        for cell in wl[wl.max_row]: cell.border=bd
    for col,w2 in zip(["A","B","C","D","E"],[12,35,20,25,12]):
        wl.column_dimensions[col].width=w2
    eb=BytesIO(); wb.save(eb); eb.seek(0); return eb.getvalue()

def gerar_excel_relatorio_geral(df_rel, titulo, data_ini, data_fim, total_reunioes, total_presencas):
    wb=Workbook(); wb.remove(wb.active)
    hf=Font(name="Calibri",size=11,bold=True,color="FFFFFF")
    hfill=PatternFill(start_color="1F4E78",end_color="1F4E78",fill_type="solid")
    ha=Alignment(horizontal="center",vertical="center",wrap_text=True)
    bd=Border(left=Side(style="thin"),right=Side(style="thin"),top=Side(style="thin"),bottom=Side(style="thin"))
    ws=wb.create_sheet("Relatorio Geral",0)
    ws["A1"]=f"Relatorio Geral — {titulo}"
    ws["A1"].font=Font(name="Calibri",size=14,bold=True)
    ws.merge_cells("A1:F1")
    ws["A2"]=f"Periodo: {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
    ws.merge_cells("A2:F2")
    ws["A3"]=f"Gerado em: {obter_hora_atual().strftime('%d/%m/%Y %H:%M')}"
    ws.merge_cells("A3:F3")
    ws.append([])
    ws.append(["Total Reunioes",total_reunioes,"Total Presencas",total_presencas,"Participantes",len(df_rel)])
    ws.append([])
    headers=["#","ID","Nome","Cargo","Localidade","Presencas","Frequencia %"]
    ws.append(headers)
    for cell in ws[ws.max_row]: cell.font=hf;cell.fill=hfill;cell.alignment=ha;cell.border=bd
    for i,(_,row) in enumerate(df_rel.iterrows(),1):
        ws.append([i,str(row["ID"]),row["Nome"],row["Cargo"],row["Localidade"],int(row["Presencas"]),float(row["Frequencia_%"])])
        for cell in ws[ws.max_row]: cell.border=bd
    for col,w2 in zip(["A","B","C","D","E","F","G"],[5,10,35,22,25,12,14]):
        ws.column_dimensions[col].width=w2
    eb=BytesIO(); wb.save(eb); eb.seek(0); return eb.getvalue()


# ════════════════════ RELATÓRIO GERAL — FUNÇÕES ════════════════════
def carregar_presencas_periodo(data_ini, data_fim):
    try:
        res = (
            supabase_client.table("presencas")
            .select("*")
            .gte("data_registro", f"{data_ini}T00:00:00")
            .lte("data_registro", f"{data_fim}T23:59:59")
            .execute()
        )
        if not res.data:
            return pd.DataFrame()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar presenças do período: {e}")
        return pd.DataFrame()

def carregar_reunioes_periodo(data_ini, data_fim):
    try:
        res = (
            supabase_client.table("reunioes")
            .select("*")
            .gte("data", str(data_ini))
            .lte("data", str(data_fim))
            .execute()
        )
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar reuniões do período: {e}")
        return pd.DataFrame()

def montar_relatorio_geral(df_pres, df_participantes, total_reunioes):
    if df_participantes.empty:
        return pd.DataFrame()
    base = df_participantes[["ID","Nome","Cargo","Localidade"]].copy()
    if df_pres.empty:
        base["Presencas"] = 0
        base["Frequencia_%"] = 0.0
        return base.sort_values(["Presencas","Nome"], ascending=[False,True]).reset_index(drop=True)
    freq = (
        df_pres.groupby(["id_participante","nome","cargo","localidade"])
        .size()
        .reset_index(name="Presencas")
        .rename(columns={"id_participante":"ID","nome":"Nome","cargo":"Cargo","localidade":"Localidade"})
    )
    rel = base.merge(freq[["ID","Presencas"]], on="ID", how="left")
    rel["Presencas"] = rel["Presencas"].fillna(0).astype(int)
    rel["Frequencia_%"] = rel["Presencas"].apply(
        lambda x: round((x / total_reunioes) * 100, 2) if total_reunioes > 0 else 0.0
    )
    return rel.sort_values(["Presencas","Nome"], ascending=[False,True]).reset_index(drop=True)


# ════════════════════ INIT SESSION STATE ════════════════════
df_participantes = carregar_dados_participantes()
if not df_participantes.empty:
    df_participantes = df_participantes.rename(
        columns={"id":"ID","nome":"Nome","cargo":"Cargo","localidade":"Localidade"})

reunioes = carregar_reunioes()
hoje = date.today().strftime("%Y-%m-%d")

defaults = {
    "pagina":            "home",
    "active_meeting_id": None,
    "lista_presenca":    pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"]),
    "feedback_status":   None,
    "feedback_msg":      "",
    "ultimo_registrado": None,
    "modo_continuo":     True,
    "ultima_foto_hash":  None,
    "reuniao_edit_id":   None,
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v


# ════════════════════ SIDEBAR ════════════════════
with st.sidebar:
    st.markdown('<div style="text-align:center;padding:10px 0 4px"><span style="font-size:2rem">🎵</span><br><span style="color:#a5b4fc;font-weight:800">CCB Musical</span></div>', unsafe_allow_html=True)
    st.caption("Menu auxiliar")
    st.divider()
    if st.button("🏠  Início", use_container_width=True):
        st.session_state.pagina = "home"; st.rerun()
    if st.button("➕  Nova Reunião", use_container_width=True):
        st.session_state.pagina = "nova_reuniao"; st.rerun()
    if st.button("📋  Lista de Presenças", use_container_width=True):
        st.session_state.pagina = "lista"; st.rerun()
    if st.button("📊  Relatórios Gerais", use_container_width=True):
        st.session_state.pagina = "relatorios_gerais"; st.rerun()


# ═══════════════════════════════════════════════════════════
#  PÁGINA: HOME
# ═══════════════════════════════════════════════════════════
if st.session_state.pagina == "home":

    st.markdown("""
<div style="text-align:center;margin-bottom:30px;padding-top:10px">
  <div style="font-size:4rem;margin-bottom:10px">🎵</div>
  <h1 style="color:#a5b4fc;font-size:2.2rem;font-weight:800;margin:0">CCB Musical</h1>
  <p style="color:#64748b;font-size:1rem;margin:8px 0 0">Sistema de Controle de Presença</p>
</div>
""", unsafe_allow_html=True)

    reunioes_hoje    = [r for r in reunioes if r.get("data")==hoje]
    reunioes_futuras = [r for r in reunioes if r.get("data","")>hoje]

    # ── BOTÕES PRINCIPAIS (4 colunas) ──
    sec("⚡", "AÇÕES RÁPIDAS")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        if st.button("➕\n\nNova Reunião", use_container_width=True, type="primary"):
            st.session_state.pagina = "nova_reuniao"; st.rerun()
    with col_b:
        if st.button("✏️\n\nEditar Reunião", use_container_width=True):
            st.session_state.pagina = "editar_reuniao"; st.rerun()
    with col_c:
        if st.button("📋\n\nVer Presenças", use_container_width=True):
            st.session_state.pagina = "lista"; st.rerun()
    with col_d:
        if st.button("📊\n\nRelatórios Gerais", use_container_width=True):
            st.session_state.pagina = "relatorios_gerais"; st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── REUNIÕES DE HOJE ──
    if reunioes_hoje:
        sec("📅", "REUNIÕES DE HOJE — CLIQUE PARA INICIAR")
        cols = st.columns(min(len(reunioes_hoje), 3))
        for i, r in enumerate(reunioes_hoje):
            with cols[i % len(cols)]:
                st.markdown(f"""
<div class="reuniao-card">
  <p class="rc-hora">🕐 {r.get('hora','?')}</p>
  <p class="rc-nome">{r.get('nome','?')}</p>
  <p class="rc-data">📅 {r.get('data','?')} <span class="reuniao-hoje-badge">HOJE</span></p>
</div>
""", unsafe_allow_html=True)
                if st.button(f"▶  Iniciar Check-in", key=f"home_hoje_{r['id']}", type="primary", use_container_width=True):
                    st.session_state.active_meeting_id = r["id"]
                    st.session_state.lista_presenca    = carregar_presencas_reuniao(r["id"])
                    st.session_state.feedback_status   = None
                    st.session_state.ultimo_registrado = None
                    st.session_state.pagina            = "checkin"
                    st.rerun()

    elif reunioes_futuras:
        sec("📆", "PRÓXIMAS REUNIÕES")
        cols = st.columns(min(len(reunioes_futuras[:3]), 3))
        for i, r in enumerate(reunioes_futuras[:3]):
            with cols[i % len(cols)]:
                st.markdown(f"""
<div class="reuniao-card">
  <p class="rc-hora">🕐 {r.get('hora','?')}</p>
  <p class="rc-nome">{r.get('nome','?')}</p>
  <p class="rc-data">📅 {r.get('data','?')}</p>
</div>
""", unsafe_allow_html=True)
                if st.button(f"▶  Iniciar Check-in", key=f"home_fut_{r['id']}", type="primary", use_container_width=True):
                    st.session_state.active_meeting_id = r["id"]
                    st.session_state.lista_presenca    = carregar_presencas_reuniao(r["id"])
                    st.session_state.feedback_status   = None
                    st.session_state.ultimo_registrado = None
                    st.session_state.pagina            = "checkin"
                    st.rerun()
    else:
        _, col_c2, _ = st.columns([1,2,1])
        with col_c2:
            st.markdown("""
<div style="background:rgba(99,102,241,0.08);border:1px dashed rgba(99,102,241,0.4);
            border-radius:20px;padding:40px 32px;text-align:center;">
  <div style="font-size:3rem;margin-bottom:12px">📭</div>
  <p style="color:#a5b4fc;font-size:1.1rem;font-weight:600;margin:0">Nenhuma reunião agendada</p>
  <p style="color:#475569;font-size:0.9rem;margin:10px 0 0">Use o botão <b style="color:#c7d2fe">➕ Nova Reunião</b> acima</p>
</div>
""", unsafe_allow_html=True)

    st.stop()


# ═══════════════════════════════════════════════════════════
#  PÁGINA: NOVA REUNIÃO
# ═══════════════════════════════════════════════════════════
elif st.session_state.pagina == "nova_reuniao":

    if st.button("⬅  Voltar ao Início", key="voltar_nova"):
        st.session_state.pagina = "home"; st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    sec("➕", "CRIAR NOVA REUNIÃO")

    with st.form("form_nova_reuniao"):
        ni  = st.text_input("Nome da Reunião", placeholder="Ex: Ensaio Regional")
        di2 = st.date_input("Data", value=date.today())
        hi  = st.time_input("Horário", value=time(19,30))
        ops = ["Todos","Por Cargo","Por Localidade","Manual"]
        ft  = st.selectbox("Convocação", ops)
        vals = []
        if ft=="Por Cargo" and not df_participantes.empty:
            vals = st.multiselect("Cargos", sorted(df_participantes["Cargo"].unique()))
        elif ft=="Por Localidade" and not df_participantes.empty:
            vals = st.multiselect("Localidades", sorted(df_participantes["Localidade"].unique()))
        elif ft=="Manual" and not df_participantes.empty:
            vals = st.multiselect("Participantes", sorted(df_participantes["Nome"].unique()))

        col_s, col_c3 = st.columns(2)
        with col_s:
            salvar = st.form_submit_button("💾  Salvar Reunião", type="primary", use_container_width=True)
        with col_c3:
            cancelar = st.form_submit_button("✖  Cancelar", use_container_width=True)

    if cancelar:
        st.session_state.pagina = "home"; st.rerun()

    if salvar:
        if not ni.strip():
            st.error("⚠️ Informe o nome da reunião.")
        else:
            payload = {"id":None, "nome":ni.strip(),
                       "data":di2.strftime("%Y-%m-%d"), "hora":hi.strftime("%H:%M"),
                       "filtro_tipo":ft, "filtro_valores":vals if ft!="Todos" else []}
            reunioes = atualizar_ou_criar_reuniao(reunioes, payload)
            st.success("✅ Reunião criada com sucesso!")
            st.session_state.pagina = "home"; st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════
#  PÁGINA: EDITAR REUNIÃO
# ═══════════════════════════════════════════════════════════
elif st.session_state.pagina == "editar_reuniao":

    if st.button("⬅  Voltar ao Início", key="voltar_editar"):
        st.session_state.pagina = "home"; st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    sec("✏️", "EDITAR / EXCLUIR REUNIÃO")

    reunioes_visiveis = [r for r in reunioes if r.get("data","")>=hoje]
    if not reunioes_visiveis:
        reunioes_visiveis = reunioes

    if not reunioes_visiveis:
        st.info("Nenhuma reunião cadastrada."); st.stop()

    labels = [label_reuniao(r) for r in reunioes_visiveis]
    ids    = [r["id"] for r in reunioes_visiveis]
    di_sel = 0
    if st.session_state.reuniao_edit_id in ids:
        di_sel = ids.index(st.session_state.reuniao_edit_id)

    si = st.selectbox("Selecione a reunião:", range(len(ids)),
                      format_func=lambda i: labels[i], index=di_sel)
    rae = reunioes_visiveis[si]
    st.session_state.reuniao_edit_id = rae["id"]

    nome_def   = rae.get("nome","")
    data_def   = _parse_date(rae.get("data",hoje))
    hora_def   = _parse_time(rae.get("hora","19:30"))
    filtro_def = rae.get("filtro_tipo","Todos")
    vals_def   = rae.get("filtro_valores",[])

    with st.form("form_editar_reuniao"):
        ni  = st.text_input("Nome", value=nome_def)
        di2 = st.date_input("Data", value=data_def)
        hi  = st.time_input("Horário", value=hora_def)
        ops = ["Todos","Por Cargo","Por Localidade","Manual"]
        ft  = st.selectbox("Convocação", ops, index=ops.index(filtro_def) if filtro_def in ops else 0)
        vals = []
        if ft=="Por Cargo" and not df_participantes.empty:
            op2=sorted(df_participantes["Cargo"].unique())
            vals=st.multiselect("Cargos",op2,default=[v for v in vals_def if v in op2])
        elif ft=="Por Localidade" and not df_participantes.empty:
            op2=sorted(df_participantes["Localidade"].unique())
            vals=st.multiselect("Localidades",op2,default=[v for v in vals_def if v in op2])
        elif ft=="Manual" and not df_participantes.empty:
            op2=sorted(df_participantes["Nome"].unique())
            vals=st.multiselect("Participantes",op2,default=[v for v in vals_def if v in op2])

        col_s2, col_c4 = st.columns(2)
        with col_s2:
            salvar = st.form_submit_button("💾  Salvar Alterações", type="primary", use_container_width=True)
        with col_c4:
            cancelar = st.form_submit_button("✖  Cancelar", use_container_width=True)

    if cancelar:
        st.session_state.pagina = "home"; st.rerun()

    if salvar:
        if not ni.strip():
            st.error("⚠️ Informe o nome.")
        else:
            payload = {"id":rae["id"],"nome":ni.strip(),
                       "data":di2.strftime("%Y-%m-%d"),"hora":hi.strftime("%H:%M"),
                       "filtro_tipo":ft,"filtro_valores":vals if ft!="Todos" else []}
            reunioes = atualizar_ou_criar_reuniao(reunioes, payload)
            st.success("✅ Reunião atualizada!"); st.session_state.pagina="home"; st.rerun()

    st.markdown("---")
    sec("🗑️", "EXCLUIR REUNIÃO")
    conf = st.checkbox("⚠️ Confirmar exclusão desta reunião")
    if st.button("🗑  Excluir", disabled=not conf, use_container_width=True):
        reunioes = excluir_reuniao(reunioes, rae["id"])
        if st.session_state.active_meeting_id == rae["id"]:
            st.session_state.active_meeting_id = None
        st.success("Excluída!"); st.session_state.pagina="home"; st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════
#  PÁGINA: CHECK-IN
# ═══════════════════════════════════════════════════════════
elif st.session_state.pagina == "checkin":

    reuniao_ativa = None
    if st.session_state.active_meeting_id:
        for r in reunioes:
            if r.get("id")==st.session_state.active_meeting_id:
                reuniao_ativa=r; break

    if not reuniao_ativa:
        st.warning("Nenhuma reunião selecionada.")
        if st.button("⬅  Voltar ao Início", key="volt_checkin_sem"):
            st.session_state.pagina="home"; st.rerun()
        st.stop()

    col_back, col_titulo = st.columns([1, 5])
    with col_back:
        if st.button("⬅  Voltar", key="volt_checkin", use_container_width=True):
            st.session_state.pagina="home"; st.rerun()

    conv_df    = filtrar_convocados(df_participantes, reuniao_ativa)
    total_conv = len(conv_df)
    total_pres = len(st.session_state.lista_presenca)
    porc       = int(total_pres / total_conv * 100) if total_conv > 0 else 0
    faltantes  = max(0, total_conv - total_pres)

    st.markdown(f"""
<div class="banner">
<div class="banner-icon">🎵</div>
<div>
<p class="banner-title">{reuniao_ativa.get('nome','Reunião')}</p>
<p class="banner-sub">📅&nbsp; {reuniao_ativa.get('data','?')} &nbsp;&nbsp;🕐&nbsp; {reuniao_ativa.get('hora','?')}</p>
</div>
</div>
""", unsafe_allow_html=True)

    st.markdown(
        f'<div class="metric-row">'
        f'{metric_card(total_conv,  "Convocados",  "blue")}'
        f'{metric_card(total_pres,  "Presentes",   "green")}'
        f'{metric_card(faltantes,   "Faltantes",   "red")}'
        f'<div class="metric-card mc-purple"><p class="metric-value" style="color:#a78bfa">{porc}%</p><p class="metric-label">Presença</p></div>'
        f'</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="prog-wrap"><div class="prog-fill" style="width:{porc}%"></div></div>',
        unsafe_allow_html=True
    )

    sec("🧭", "NAVEGAR")
    nb1, nb2, nb3, nb4 = st.columns(4)
    with nb1:
        if st.button("📷  Câmera QR", use_container_width=True, key="nav_cam"):
            st.session_state.aba_checkin = "cam"
    with nb2:
        if st.button("⌨️  Digitar Código", use_container_width=True, key="nav_dig"):
            st.session_state.aba_checkin = "manual"
    with nb3:
        if st.button(f"📋  Presentes ({total_pres})", use_container_width=True, key="nav_lista"):
            st.session_state.aba_checkin = "lista"
    with nb4:
        if st.button("↺  Recarregar", use_container_width=True, key="nav_reload"):
            st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_ativa["id"])
            st.rerun()

    if "aba_checkin" not in st.session_state:
        st.session_state.aba_checkin = "cam"

    aba_cam, aba_manual, aba_lista_pres = st.tabs([
        "📷  Câmera QR",
        "⌨️  Digitar / Buscar",
        f"📋  Presentes ({total_pres})",
    ])

    with aba_cam:
        col_cam, col_result = st.columns([5, 4], gap="large")
        with col_cam:
            sec("📷", "APONTE PARA O QR CODE")
            st.caption("💡 Mantenha o crachá bem iluminado e a ~15cm da câmera.")
            modo_continuo = st.toggle("🔄 Modo contínuo", value=st.session_state.modo_continuo,
                                      help="Após cada leitura a câmera reseta automaticamente.")
            st.session_state.modo_continuo = modo_continuo
            foto = st.camera_input("", label_visibility="collapsed", key="cam_qr")

        with col_result:
            sec("✨", "RESULTADO")
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
                        if modo_continuo and status in ("ok","duplicado"):
                            if "cam_qr" in st.session_state: del st.session_state["cam_qr"]
                        st.rerun()
                    else:
                        st.session_state.feedback_status = "sem_qr"
                        st.session_state.feedback_msg    = "QR Code não identificado. Tente com mais luz."
                        st.rerun()

            s  = st.session_state.feedback_status
            m  = st.session_state.feedback_msg
            ur = st.session_state.ultimo_registrado

            if s=="ok" and ur:
                st.markdown(f"""
<div class="fb-ok">
<p class="fb-title">✅ Presença Registrada!</p>
<p class="fb-nome">{ur['Nome']}</p>
</div>
<div class="membro-card fade-slide">
<p class="m-nome">🎸 {ur['Cargo']}</p>
<p class="m-det">📍 {ur['Localidade']}&nbsp;&nbsp;•&nbsp;&nbsp;🕐 {ur['Horario']}</p>
</div>""", unsafe_allow_html=True)
                if modo_continuo:
                    st.markdown('<div class="fb-idle"><p class="fb-title">📸 Câmera pronta para o próximo crachá!</p></div>', unsafe_allow_html=True)
            elif s=="duplicado":
                st.markdown(f'<div class="fb-warn"><p class="fb-title">⚠️ Já registrado!<br><span style="font-size:0.9rem;font-weight:400">{m}</span></p></div>', unsafe_allow_html=True)
                if modo_continuo: st.markdown('<div class="fb-idle"><p class="fb-title">📸 Pronto para o próximo!</p></div>', unsafe_allow_html=True)
            elif s=="erro":
                st.markdown(f'<div class="fb-erro"><p class="fb-title">❌ {m}</p></div>', unsafe_allow_html=True)
            elif s=="sem_qr":
                st.markdown(f'<div class="fb-warn"><p class="fb-title">📣 {m}</p></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="fb-idle"><p class="fb-title">📷 Aguardando foto do QR Code...</p></div>', unsafe_allow_html=True)

            if not (s=="ok" and ur) and not st.session_state.lista_presenca.empty:
                ult = st.session_state.lista_presenca.iloc[-1]
                st.markdown(f'<div class="membro-card" style="margin-top:16px"><p class="m-nome" style="color:#94a3b8;font-size:0.8rem">⏱ Último registrado</p><p class="m-nome">{ult["Nome"]}</p><p class="m-det">{ult["Horario"]}</p></div>', unsafe_allow_html=True)

    with aba_manual:
        tab_cod, tab_nome = st.tabs(["🔢 Pelo Código", "🔍 Pelo Nome"])
        with tab_cod:
            sec("🔢", "DIGITAR CÓDIGO")
            with st.form("form_manual", clear_on_submit=True):
                c1, c2 = st.columns([3,1])
                with c1:
                    cod = st.text_input("", placeholder="Ex: LC005, CF001...",
                                        label_visibility="collapsed").strip().upper()
                with c2:
                    ok = st.form_submit_button("✔ Registrar", type="primary", use_container_width=True)
            if ok and cod:
                status, msg = registrar_por_codigo(cod, df_participantes, reuniao_ativa["id"])
                st.session_state.feedback_status = status
                st.session_state.feedback_msg    = msg
                st.rerun()
            s,m,ur = st.session_state.feedback_status, st.session_state.feedback_msg, st.session_state.ultimo_registrado
            if s=="ok" and ur:
                st.markdown(f'<div class="fb-ok"><p class="fb-title">✅ Registrado!</p><p class="fb-nome">{ur["Nome"]}</p></div>', unsafe_allow_html=True)
            elif s=="duplicado": st.markdown(f'<div class="fb-warn"><p class="fb-title">⚠️ {m}</p></div>', unsafe_allow_html=True)
            elif s=="erro":      st.markdown(f'<div class="fb-erro"><p class="fb-title">❌ {m}</p></div>', unsafe_allow_html=True)

        with tab_nome:
            sec("🔍", "BUSCAR POR NOME")
            if not df_participantes.empty:
                nome_busca = st.text_input("", placeholder="Digite parte do nome...", label_visibility="collapsed")
                if nome_busca.strip():
                    filtrado = df_participantes[
                        df_participantes["Nome"].str.contains(nome_busca.strip(), case=False, na=False)
                    ][["ID","Nome","Cargo","Localidade"]]
                    if not filtrado.empty:
                        st.dataframe(filtrado, hide_index=True, use_container_width=True)
                        sel = st.selectbox("Selecione:", options=filtrado["ID"].tolist(),
                                           format_func=lambda x: f"{x}  —  {filtrado[filtrado['ID']==x]['Nome'].values[0]}")
                        if st.button("✔ Registrar selecionado", type="primary"):
                            status, msg = registrar_por_codigo(str(sel), df_participantes, reuniao_ativa["id"])
                            st.session_state.feedback_status = status
                            st.session_state.feedback_msg    = msg
                            st.rerun()
                    else:
                        st.info("🔍 Nenhum participante encontrado.")

    with aba_lista_pres:
        if not st.session_state.lista_presenca.empty:
            df_pres = st.session_state.lista_presenca
            rc = df_pres["Cargo"].value_counts()
            rl = df_pres["Localidade"].value_counts()

            sec("📊", "RESUMO")
            r1, r2 = st.columns(2)
            with r1:
                st.markdown("**🎸 Por Cargo**")
                st.dataframe(rc.rename("Qtd").reset_index().rename(columns={"index":"Cargo"}),
                             hide_index=True, use_container_width=True)
            with r2:
                st.markdown("**📍 Por Localidade**")
                st.dataframe(rl.rename("Qtd").reset_index().rename(columns={"index":"Localidade"}),
                             hide_index=True, use_container_width=True)

            sec("👥", "LISTA COMPLETA")
            st.dataframe(
                df_pres[["Nome","Cargo","Localidade","Horario"]].reset_index(drop=True),
                hide_index=True, use_container_width=True,
                column_config={
                    "Nome":       st.column_config.TextColumn("👤 Nome"),
                    "Cargo":      st.column_config.TextColumn("🎸 Cargo"),
                    "Localidade": st.column_config.TextColumn("📍 Local"),
                    "Horario":    st.column_config.TextColumn("🕐 Horário"),
                }
            )

            sec("📄", "EXPORTAR")
            arq = f"{reuniao_ativa.get('data','')}_{reuniao_ativa.get('nome','reuniao')}".replace(" ","_")
            cA, cB, cC = st.columns(3)
            with cA:
                st.download_button("⬇️ Baixar PDF", icon="📄",
                    data=gerar_pdf(df_pres,rc,rl,reuniao_ativa.get("nome","Reuniao")),
                    file_name=f"{arq}.pdf", mime="application/pdf", use_container_width=True)
            with cB:
                st.download_button("⬇️ Baixar Excel", icon="📊",
                    data=gerar_excel(df_pres,rc,rl,reuniao_ativa.get("nome","Reuniao")),
                    file_name=f"{arq}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
            with cC:
                conf_del = st.checkbox("⚠️ Confirmar limpeza")
                if st.button("🗑 Limpar lista", disabled=not conf_del, use_container_width=True):
                    if limpar_presencas_reuniao(reuniao_ativa["id"]):
                        st.session_state.lista_presenca    = pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"])
                        st.session_state.ultimo_registrado = None
                        st.rerun()
        else:
            st.markdown("""
<div style="text-align:center;padding:48px 0">
<div style="font-size:3rem">📋</div>
<p style="color:#64748b;font-size:1rem;margin-top:12px">Nenhuma presença registrada ainda.</p>
</div>
""", unsafe_allow_html=True)
            if st.button("↺ Recarregar do banco", use_container_width=True):
                st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_ativa["id"])
                st.rerun()

    st.markdown("---")
    if st.button("⬅  Voltar ao Início", key="volt_checkin_bottom", use_container_width=True):
        st.session_state.pagina = "home"; st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════
#  PÁGINA: LISTA DE PRESENÇAS (acesso direto)
# ═══════════════════════════════════════════════════════════
elif st.session_state.pagina == "lista":

    if st.button("⬅  Voltar ao Início", key="volt_lista"):
        st.session_state.pagina = "home"; st.rerun()

    sec("📋", "SELECIONAR REUNIÃO PARA VER PRESENÇAS")

    if not reunioes:
        st.info("Nenhuma reunião cadastrada."); st.stop()

    labels = [label_reuniao(r) for r in reunioes]
    ids    = [r["id"] for r in reunioes]
    si = st.selectbox("Reunião:", range(len(ids)), format_func=lambda i: labels[i])
    rid_sel = ids[si]

    df_pres = carregar_presencas_reuniao(rid_sel)

    if not df_pres.empty:
        rc = df_pres["Cargo"].value_counts()
        rl = df_pres["Localidade"].value_counts()

        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**🎸 Por Cargo**")
            st.dataframe(rc.rename("Qtd").reset_index().rename(columns={"index":"Cargo"}),
                         hide_index=True, use_container_width=True)
        with r2:
            st.markdown("**📍 Por Localidade**")
            st.dataframe(rl.rename("Qtd").reset_index().rename(columns={"index":"Localidade"}),
                         hide_index=True, use_container_width=True)

        st.dataframe(df_pres[["Nome","Cargo","Localidade","Horario"]].reset_index(drop=True),
                     hide_index=True, use_container_width=True)

        arq = f"{reunioes[si].get('data','')}_{reunioes[si].get('nome','reuniao')}".replace(" ","_")
        cA2, cB2 = st.columns(2)
        with cA2:
            st.download_button("⬇️ PDF", data=gerar_pdf(df_pres,rc,rl,reunioes[si].get("nome","")),
                               file_name=f"{arq}.pdf", mime="application/pdf", use_container_width=True)
        with cB2:
            st.download_button("⬇️ Excel", data=gerar_excel(df_pres,rc,rl,reunioes[si].get("nome","")),
                               file_name=f"{arq}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
    else:
        st.info("Nenhuma presença registrada nesta reunião.")

    st.stop()


# ═══════════════════════════════════════════════════════════
#  PÁGINA: RELATÓRIOS GERAIS
# ═══════════════════════════════════════════════════════════
elif st.session_state.pagina == "relatorios_gerais":

    if st.button("⬅  Voltar ao Início", key="volt_relatorios"):
        st.session_state.pagina = "home"; st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    sec("📊", "RELATÓRIOS GERAIS")

    # ── Período padrão = ano atual ──
    ano_atual = date.today().year
    periodo = st.date_input(
        "📅 Selecione o período",
        value=(date(ano_atual, 1, 1), date(ano_atual, 12, 31)),
        format="DD/MM/YYYY",
        help="Selecione data inicial e data final"
    )

    if not periodo or len(periodo) != 2:
        st.info("ℹ️ Selecione a data inicial e a data final para carregar o relatório.")
        st.stop()

    data_ini, data_fim = periodo

    with st.spinner("Carregando dados do período..."):
        df_reunioes_p = carregar_reunioes_periodo(data_ini, data_fim)
        df_pres_p     = carregar_presencas_periodo(data_ini, data_fim)

    total_reunioes  = len(df_reunioes_p)
    total_presencas = len(df_pres_p)
    df_rel = montar_relatorio_geral(df_pres_p, df_participantes, total_reunioes)

    # ── Métricas ──
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("📅 Reuniões", total_reunioes)
    with m2: st.metric("✅ Presenças", total_presencas)
    with m3: st.metric("👥 Participantes", len(df_participantes))
    with m4:
        media = round(df_rel["Frequencia_%"].mean(), 1) if not df_rel.empty else 0.0
        st.metric("📈 Freq. Média", f"{media}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Lista completa ──
    sec("👥", "LISTA COMPLETA DE MEMBROS")
    if not df_rel.empty:
        st.dataframe(
            df_rel[["ID","Nome","Cargo","Localidade","Presencas","Frequencia_%"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "ID":           st.column_config.TextColumn("ID"),
                "Nome":         st.column_config.TextColumn("Nome"),
                "Cargo":        st.column_config.TextColumn("Cargo"),
                "Localidade":   st.column_config.TextColumn("Localidade"),
                "Presencas":    st.column_config.NumberColumn("Presenças"),
                "Frequencia_%": st.column_config.NumberColumn("Frequência %", format="%.1f"),
            }
        )
    else:
        st.info("Nenhum dado encontrado para o período selecionado.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Gráfico: Ranking por membro ──
    sec("🏆", "RANKING DE PRESENÇAS — TODOS OS MEMBROS")
    if not df_rel.empty:
        fig1 = px.bar(
            df_rel,
            x="Nome",
            y="Presencas",
            color="Cargo",
            title=f"Presenças por membro ({data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')})",
            labels={"Nome": "Membro", "Presencas": "Presenças", "Cargo": "Cargo"},
            text="Presencas",
        )
        fig1.update_traces(textposition="outside", cliponaxis=False)
        fig1.update_layout(
            xaxis_tickangle=-45,
            xaxis_title="Membro",
            yaxis_title="Presenças",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500,
        )
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Sem dados para o gráfico de ranking.")

    # ── Gráfico: Presenças por mês ──
    sec("📈", "PRESENÇAS POR MÊS")
    if not df_pres_p.empty and "data_registro" in df_pres_p.columns:
        df_mes = df_pres_p.copy()
        df_mes["data_registro"] = pd.to_datetime(df_mes["data_registro"], errors="coerce")
        df_mes = df_mes.dropna(subset=["data_registro"])
        if not df_mes.empty:
            df_mes["Mes"] = df_mes["data_registro"].dt.to_period("M").astype(str)
            mensal = df_mes.groupby("Mes").size().reset_index(name="Presencas")
            fig2 = px.line(
                mensal, x="Mes", y="Presencas",
                markers=True,
                title=f"Total de presenças por mês ({data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')})",
                labels={"Mes": "Mês", "Presencas": "Presenças"},
            )
            fig2.update_traces(line_color="#6366f1", marker_color="#8b5cf6", fill="tozeroy", fillcolor="rgba(99,102,241,0.1)")
            fig2.update_layout(xaxis_title="Mês", yaxis_title="Presenças", height=380)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sem dados de mês para o período.")
    else:
        st.info("Sem registros de presença no período selecionado.")

    # ── Resumo por Cargo e Localidade ──
    if not df_rel.empty:
        sec("📋", "RESUMO POR CARGO E LOCALIDADE")
        rc_g = df_rel.groupby("Cargo")["Presencas"].sum().sort_values(ascending=False).reset_index()
        rl_g = df_rel.groupby("Localidade")["Presencas"].sum().sort_values(ascending=False).reset_index()
        r1c, r2c = st.columns(2)
        with r1c:
            st.markdown("**🎸 Por Cargo**")
            st.dataframe(rc_g, hide_index=True, use_container_width=True)
        with r2c:
            st.markdown("**📍 Por Localidade**")
            st.dataframe(rl_g, hide_index=True, use_container_width=True)

    # ── Exportação ──
    if not df_rel.empty:
        sec("📄", "EXPORTAR RELATÓRIO")
        titulo_rel = f"Relatorio_Geral_{data_ini.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}"
        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button(
                "⬇️ Baixar Excel", icon="📊",
                data=gerar_excel_relatorio_geral(df_rel, titulo_rel, data_ini, data_fim, total_reunioes, total_presencas),
                file_name=f"{titulo_rel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with ex2:
            st.download_button(
                "⬇️ Baixar PDF", icon="📄",
                data=gerar_pdf_relatorio_geral(df_rel, titulo_rel, data_ini, data_fim, total_reunioes, total_presencas),
                file_name=f"{titulo_rel}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    st.markdown("---")
    if st.button("⬅  Voltar ao Início", key="volt_relatorios_bottom", use_container_width=True):
        st.session_state.pagina = "home"; st.rerun()

    st.stop()
