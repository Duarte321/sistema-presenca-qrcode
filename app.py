import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from supabase import create_client, Client
from pyzbar.pyzbar import decode
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import plotly.express as px
import io

try:
    import qrcode
    QR_OK = True
except ImportError:
    QR_OK = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    RL_OK = True
except ImportError:
    RL_OK = False

st.set_page_config(
    page_title="CCB Musical — Check-in",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

CSS = """
<style>
/* ===== OCULTAR SIDEBAR E HEADER NATIVO ===== */
[data-testid="stSidebar"]          { display: none !important; }
[data-testid="collapsedControl"]   { display: none !important; }
#MainMenu, footer, header          { visibility: hidden !important; }

/* ===== FUNDO GERAL ===== */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1530 50%, #0a0e1a 100%) !important;
}

/* ===== INPUTS ===== */
input, textarea, [data-baseweb="input"] input {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(99,102,241,0.4) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}
input:focus, textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 2px rgba(99,102,241,0.25) !important;
}

/* ===== SELECT / DROPDOWN ===== */
[data-baseweb="select"] > div {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(99,102,241,0.4) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}

/* ===== BOTOES ===== */
.stButton > button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
    border: 1px solid rgba(99,102,241,0.5) !important;
    background: rgba(99,102,241,0.15) !important;
    color: #c7d2fe !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(99,102,241,0.4) !important;
    background: rgba(99,102,241,0.3) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    color: white !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.45) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(135deg, #818cf8, #a78bfa) !important;
    box-shadow: 0 6px 22px rgba(99,102,241,0.6) !important;
}

/* ===== MENU HORIZONTAL CUSTOMIZADO ===== */
.topnav {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(13,21,48,0.95);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 18px;
    padding: 10px 18px;
    margin-bottom: 24px;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    flex-wrap: wrap;
}
.topnav-logo {
    font-size: 1.4rem;
    font-weight: 800;
    color: #c7d2fe;
    margin-right: 12px;
    white-space: nowrap;
    letter-spacing: -0.5px;
}
.topnav-logo span { color: #818cf8; }
.topnav-sep {
    width: 1px; height: 32px;
    background: rgba(99,102,241,0.3);
    margin: 0 6px;
}
.nav-btn {
    display: flex; align-items: center; gap: 7px;
    padding: 9px 18px;
    border-radius: 12px;
    font-size: 0.88rem; font-weight: 600;
    color: #94a3b8;
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
    white-space: nowrap;
}
.nav-btn:hover {
    background: rgba(99,102,241,0.15);
    color: #c7d2fe;
    border-color: rgba(99,102,241,0.35);
}
.nav-btn.active {
    background: linear-gradient(135deg, rgba(99,102,241,0.30), rgba(139,92,246,0.22));
    color: #c7d2fe;
    border-color: rgba(99,102,241,0.6);
    box-shadow: 0 2px 12px rgba(99,102,241,0.3);
}
.nav-icon { font-size: 1.1rem; }

/* ===== TABS (sub-abas internas) ===== */
[data-testid="stTabs"] button[role="tab"] {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 10px 10px 0 0 !important;
    color: #94a3b8 !important;
    font-weight: 600 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-bottom: none !important;
    padding: 10px 22px !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(99,102,241,0.28), rgba(139,92,246,0.22)) !important;
    color: #c7d2fe !important;
    border-color: rgba(99,102,241,0.55) !important;
}

/* ===== DATAFRAME ===== */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid rgba(99,102,241,0.25) !important;
}

/* ===== METRIC ===== */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 14px !important;
    padding: 14px !important;
}
[data-testid="stMetricValue"] { color: #a5b4fc !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.78rem !important; }

/* ===== CAMERA INPUT ===== */
[data-testid="stCameraInput"] > div {
    border-radius: 16px !important;
    border: 2px solid rgba(99,102,241,0.5) !important;
    overflow: hidden !important;
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.4); border-radius: 99px; }

/* ===== ANIMACOES ===== */
@keyframes bounceIn {
    0%   { transform: scale(0.9); opacity: 0; }
    60%  { transform: scale(1.04); opacity: 1; }
    100% { transform: scale(1); }
}
@keyframes fadeSlide {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
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
    animation: fadeSlide 0.4s ease;
}
.banner-icon  { font-size: 2.6rem; }
.banner-title { color: #fff; font-size: 1.7rem; font-weight: 800; margin: 0; }
.banner-sub   { color: #a5b4fc; font-size: 0.9rem; margin: 4px 0 0; }

/* ===== METRIC ROW ===== */
.metric-row { display: flex; gap: 14px; margin-bottom: 18px; flex-wrap: wrap; }
.metric-card {
    flex: 1; min-width: 120px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; padding: 18px 14px;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
}
.metric-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
.metric-value { font-size: 2.2rem; font-weight: 800; margin: 0; line-height: 1; }
.metric-label { font-size: 0.76rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; opacity: 0.7; color: #e2e8f0; }
.mc-blue   { border-color: rgba(96,165,250,0.3)   !important; } .mc-blue   .metric-value { color: #60a5fa; }
.mc-green  { border-color: rgba(52,211,153,0.3)   !important; } .mc-green  .metric-value { color: #34d399; }
.mc-red    { border-color: rgba(248,113,113,0.3)  !important; } .mc-red    .metric-value { color: #f87171; }
.mc-purple { border-color: rgba(167,139,250,0.3)  !important; } .mc-purple .metric-value { color: #a78bfa; }

/* ===== PROGRESS ===== */
.prog-wrap {
    background: rgba(255,255,255,0.08);
    border-radius: 99px; height: 10px;
    margin: 0 0 26px; overflow: hidden;
}
.prog-fill {
    height: 100%; border-radius: 99px;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #06b6d4);
    box-shadow: 0 0 12px rgba(99,102,241,0.6);
}

/* ===== FEEDBACK CARDS ===== */
.fb-ok {
    background: linear-gradient(135deg, #064e3b, #065f46);
    border: 1px solid #34d399; border-radius: 18px;
    padding: 22px 28px; text-align: center; margin: 12px 0;
    box-shadow: 0 0 24px rgba(52,211,153,0.25);
    animation: bounceIn 0.4s ease;
}
.fb-ok .fb-title { color: #6ee7b7; font-size: 1.1rem; font-weight: 600; }
.fb-ok .fb-nome  { color: #fff;    font-size: 1.5rem; font-weight: 800; margin: 4px 0; }
.fb-warn { background: linear-gradient(135deg,#451a03,#78350f); border: 1px solid #f59e0b; border-radius: 18px; padding: 18px 24px; text-align: center; margin: 12px 0; }
.fb-warn .fb-title { color: #fcd34d; font-size: 1rem; font-weight: 700; }
.fb-erro { background: linear-gradient(135deg,#450a0a,#7f1d1d); border: 1px solid #f87171; border-radius: 18px; padding: 18px 24px; text-align: center; margin: 12px 0; }
.fb-erro .fb-title { color: #fca5a5; font-size: 1rem; font-weight: 700; }
.fb-idle { background: rgba(99,102,241,0.08); border: 1px dashed rgba(99,102,241,0.4); border-radius: 18px; padding: 18px 24px; text-align: center; margin: 12px 0; }
.fb-idle .fb-title { color: #a5b4fc; font-size: 0.95rem; }

/* ===== REUNIAO CARD ===== */
.reuniao-card {
    background: linear-gradient(135deg,rgba(99,102,241,0.12),rgba(139,92,246,0.08));
    border: 1px solid rgba(99,102,241,0.35);
    border-radius: 20px; padding: 26px 28px; margin: 12px 0;
    transition: transform 0.2s, box-shadow 0.2s;
}
.reuniao-card:hover { transform: translateY(-4px); box-shadow: 0 12px 36px rgba(99,102,241,0.25); }
.reuniao-card .rc-hora { color: #a5b4fc; font-size: 1rem; font-weight: 600; margin: 0 0 6px; }
.reuniao-card .rc-nome { color: #fff; font-size: 1.45rem; font-weight: 800; margin: 0 0 10px; }
.reuniao-card .rc-data { color: #64748b; font-size: 0.85rem; }
.reuniao-hoje-badge {
    display: inline-block;
    background: linear-gradient(90deg,#22c55e,#16a34a);
    color: white; font-size: 0.68rem; font-weight: 700;
    padding: 2px 10px; border-radius: 99px; margin-left: 8px;
}

/* ===== SEC HEADER ===== */
.sec-header {
    color: #c7d2fe; font-size: 0.75rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 2px;
    margin: 18px 0 10px; display: flex; align-items: center; gap: 8px;
}
.sec-header::after { content: ''; flex: 1; height: 1px; background: rgba(99,102,241,0.3); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------------------------------------
# SUPABASE
# -------------------------------------------------------
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = get_supabase()
BR = pytz.timezone("America/Cuiaba")

def agora_br():
    return datetime.now(BR)

# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------
def load_participantes():
    res = supabase.table("participantes").select("*").order("nome").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def load_reunioes():
    res = supabase.table("reunioes").select("*").execute()
    return res.data or []

def load_presencas(meeting_id=None):
    q = supabase.table("presencas").select("*, participantes(nome, cargo, localidade, instrumento)")
    if meeting_id:
        q = q.eq("meeting_id", meeting_id)
    return q.execute().data or []

# -------------------------------------------------------
# PDF QR CODE
# -------------------------------------------------------
def gerar_pdf_membros(membros: list) -> bytes:
    NAVY  = colors.HexColor("#1a2f5e")
    WHITE = colors.white
    GRAY  = colors.HexColor("#555555")
    BLACK = colors.black
    LIGHT = colors.HexColor("#f5f5f5")
    hs = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10, textColor=WHITE, alignment=TA_CENTER)
    ns = ParagraphStyle("n", fontName="Helvetica-Bold", fontSize=11, textColor=BLACK, alignment=TA_LEFT, leading=14)
    ls = ParagraphStyle("l", fontName="Helvetica",      fontSize=9,  textColor=GRAY,  alignment=TA_LEFT)
    cs = ParagraphStyle("c", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY,  alignment=TA_CENTER)
    buf_pdf = io.BytesIO()
    doc = SimpleDocTemplate(buf_pdf, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []
    for m in membros:
        qr = qrcode.QRCode(version=2, box_size=6, border=2)
        qr.add_data(m["id"]); qr.make(fit=True)
        qi = qr.make_image(fill_color="black", back_color="white")
        bq = io.BytesIO(); qi.save(bq, format="PNG"); bq.seek(0)
        ri = RLImage(bq, width=3.5*cm, height=3.5*cm)
        instr = m.get("instrumento") or ""
        local = m.get("localidade") or ""
        info = [Paragraph(m["nome"], ns), Spacer(1,4),
                Paragraph(f'<font color="#555">Cargo: </font><b>{m["cargo"]}</b>', ls),
                Paragraph(f'<font color="#555">Local: </font><b>{local}</b>', ls),
                Paragraph(f'<font color="#555">Instr.: </font><b>{instr}</b>', ls)]
        card = Table([[Paragraph("CHECK-IN QR CODE — MUSICAL CCB", hs),""], [ri, info], [Paragraph(m["id"], cs),""]], colWidths=[4*cm,12*cm])
        card.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),NAVY),("SPAN",(0,0),(-1,0)),
            ("TOPPADDING",(0,0),(-1,0),6),("BOTTOMPADDING",(0,0),(-1,0),6),
            ("VALIGN",(0,1),(-1,1),"MIDDLE"),("ALIGN",(0,1),(0,1),"CENTER"),
            ("LEFTPADDING",(1,1),(1,1),10),("TOPPADDING",(0,1),(-1,1),8),("BOTTOMPADDING",(0,1),(-1,1),8),
            ("SPAN",(0,2),(-1,2)),("BACKGROUND",(0,2),(-1,2),LIGHT),
            ("TOPPADDING",(0,2),(-1,2),6),("BOTTOMPADDING",(0,2),(-1,2),6),
            ("BOX",(0,0),(-1,-1),1,NAVY),
        ]))
        story.append(card); story.append(Spacer(1,0.8*cm))
    doc.build(story); buf_pdf.seek(0)
    return buf_pdf.read()

# -------------------------------------------------------
# MENU HORIZONTAL NO TOPO
# -------------------------------------------------------
PAGINAS = [
    ("home",     "🏠", "Home"),
    ("checkin",  "📷", "Check-in"),
    ("relat",    "📊", "Relatórios"),
    ("membros",  "👥", "Membros"),
]

if "pagina" not in st.session_state:
    st.session_state.pagina = "home"

def nav_html(atual):
    btns = ""
    for key, icon, label in PAGINAS:
        cls = "nav-btn active" if atual == key else "nav-btn"
        btns += f'<span class="{cls}" id="navbtn_{key}"><span class="nav-icon">{icon}</span>{label}</span>'
    return f"""
    <div class="topnav">
        <span class="topnav-logo">🎵 <span>CCB</span> Musical</span>
        <div class="topnav-sep"></div>
        {btns}
    </div>"""

st.markdown(nav_html(st.session_state.pagina), unsafe_allow_html=True)

cols_nav = st.columns(len(PAGINAS))
for i, (key, icon, label) in enumerate(PAGINAS):
    with cols_nav[i]:
        if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
            st.session_state.pagina = key
            st.rerun()

pagina = st.session_state.pagina

# ===================================================
# HOME
# ===================================================
if pagina == "home":
    st.markdown('''
    <div class="banner">
        <span class="banner-icon">🎵</span>
        <div>
            <p class="banner-title">CCB Musical — Check-in</p>
            <p class="banner-sub">Sistema de controle de presença</p>
        </div>
    </div>''', unsafe_allow_html=True)

    df_p      = load_participantes()
    reunioes  = load_reunioes()
    presencas = load_presencas()
    total_m   = len(df_p)
    total_r   = len(reunioes)
    total_pr  = len(presencas)
    perc      = round(total_pr / total_m * 100) if total_m else 0

    st.markdown(f'''
    <div class="metric-row">
        <div class="metric-card mc-blue">  <p class="metric-value">{total_m}</p>  <p class="metric-label">Membros</p></div>
        <div class="metric-card mc-purple"><p class="metric-value">{total_r}</p>  <p class="metric-label">Reuniões</p></div>
        <div class="metric-card mc-green"> <p class="metric-value">{total_pr}</p> <p class="metric-label">Presenças</p></div>
        <div class="metric-card mc-red">   <p class="metric-value">{perc}%</p>  <p class="metric-label">Freq. Geral</p></div>
    </div>''', unsafe_allow_html=True)

    st.markdown('<div class="sec-header">📅 Próximas Reuniões</div>', unsafe_allow_html=True)
    hoje = agora_br().date()
    for r in reunioes:
        data_r = date.fromisoformat(r["data"]) if isinstance(r["data"], str) else r["data"]
        badge  = '<span class="reuniao-hoje-badge">HOJE</span>' if data_r == hoje else ""
        st.markdown(f'''
        <div class="reuniao-card">
            <p class="rc-hora">{r.get("horario","")} {badge}</p>
            <p class="rc-nome">{r["nome"]}</p>
            <p class="rc-data">{data_r.strftime("%d/%m/%Y")}</p>
        </div>''', unsafe_allow_html=True)

# ===================================================
# CHECK-IN
# ===================================================
elif pagina == "checkin":
    st.markdown('''
    <div class="banner">
        <span class="banner-icon">📷</span>
        <div>
            <p class="banner-title">Check-in</p>
            <p class="banner-sub">Escaneie o QR Code ou digite o código do membro</p>
        </div>
    </div>''', unsafe_allow_html=True)

    reunioes = load_reunioes()
    if not reunioes:
        st.warning("Nenhuma reunião cadastrada."); st.stop()

    sel     = st.selectbox("Selecione a reunião", [r["nome"] for r in reunioes])
    reuniao = next(r for r in reunioes if r["nome"] == sel)
    tab_cam, tab_cod = st.tabs(["📸 Câmera", "⌨️ Código Manual"])

    def registrar_presenca(codigo, meeting_id):
        codigo = codigo.upper().strip()
        res = supabase.table("participantes").select("*").eq("id", codigo).execute()
        if not res.data: return None, "not_found"
        membro = res.data[0]
        chk = supabase.table("presencas").select("id").eq("id_participante", codigo).eq("meeting_id", meeting_id).execute()
        if chk.data: return membro, "duplicate"
        supabase.table("presencas").insert({
            "id_participante": codigo, "meeting_id": meeting_id,
            "nome": membro["nome"], "cargo": membro["cargo"],
            "localidade": membro["localidade"],
            "horario": agora_br().strftime("%H:%M:%S"),
            "data_registro": agora_br().strftime("%Y-%m-%d")
        }).execute()
        return membro, "ok"

    with tab_cam:
        img_file = st.camera_input("Aponte a câmera para o QR Code")
        if img_file:
            img = Image.open(img_file).convert("L")
            img = ImageEnhance.Contrast(img).enhance(2.5)
            img = img.filter(ImageFilter.SHARPEN)
            decoded = decode(np.array(img))
            if decoded:
                cod = decoded[0].data.decode("utf-8").strip()
                m, status = registrar_presenca(cod, reuniao["id"])
                if   status == "ok":        st.markdown(f'<div class="fb-ok"><p class="fb-title">✅ Check-in realizado!</p><p class="fb-nome">{m["nome"]}</p><p style="color:#6ee7b7">{m["cargo"]} — {m["localidade"]}</p></div>', unsafe_allow_html=True)
                elif status == "duplicate": st.markdown(f'<div class="fb-warn"><p class="fb-title">⚠️ Já registrado: {m["nome"]}</p></div>', unsafe_allow_html=True)
                else:                       st.markdown('<div class="fb-erro"><p class="fb-title">❌ Código não encontrado</p></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="fb-idle"><p class="fb-title">QR Code não detectado — tente novamente</p></div>', unsafe_allow_html=True)

    with tab_cod:
        cod_manual = st.text_input("Digite o código (ex: CF001)", key="cod_manual").upper().strip()
        if st.button("✅ Registrar", type="primary", key="btn_manual"):
            if cod_manual:
                m, status = registrar_presenca(cod_manual, reuniao["id"])
                if   status == "ok":        st.markdown(f'<div class="fb-ok"><p class="fb-title">✅ Check-in realizado!</p><p class="fb-nome">{m["nome"]}</p></div>', unsafe_allow_html=True)
                elif status == "duplicate": st.markdown(f'<div class="fb-warn"><p class="fb-title">⚠️ Já registrado: {m["nome"]}</p></div>', unsafe_allow_html=True)
                else:                       st.markdown('<div class="fb-erro"><p class="fb-title">❌ Código não encontrado</p></div>', unsafe_allow_html=True)

# ===================================================
# RELATÓRIOS
# ===================================================
elif pagina == "relat":
    st.markdown('''
    <div class="banner">
        <span class="banner-icon">📊</span>
        <div>
            <p class="banner-title">Relatórios</p>
            <p class="banner-sub">Visualize a frequência e presenças</p>
        </div>
    </div>''', unsafe_allow_html=True)

    reunioes = load_reunioes()
    df_p     = load_participantes()
    if not reunioes:
        st.info("Nenhuma reunião cadastrada."); st.stop()

    sel       = st.selectbox("Reunião", [r["nome"] for r in reunioes])
    reuniao   = next(r for r in reunioes if r["nome"] == sel)
    presencas = load_presencas(reuniao["id"])

    ids_pres = {p["id_participante"] for p in presencas}
    total = len(df_p); pres = len(ids_pres); ause = total - pres
    perc  = round(pres / total * 100) if total else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Membros", total)
    c2.metric("Presentes",     pres)
    c3.metric("Ausentes",      ause)
    st.markdown(f'<div class="prog-wrap"><div class="prog-fill" style="width:{perc}%"></div></div>', unsafe_allow_html=True)
    st.caption(f"Frequência: {perc}%")

    if presencas:
        df_pres = pd.DataFrame([{
            "Nome":        p["participantes"]["nome"],
            "Cargo":       p["participantes"]["cargo"],
            "Localidade":  p["participantes"]["localidade"],
            "Instrumento": p["participantes"].get("instrumento", ""),
            "Hora":        p.get("horario", "")
        } for p in presencas])
        st.dataframe(df_pres, use_container_width=True)
        fig = px.pie(df_pres, names="Instrumento", title="Presenças por Instrumento",
                     color_discrete_sequence=px.colors.sequential.Plasma_r)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0")
        st.plotly_chart(fig, use_container_width=True)

        xlsx_buf = BytesIO()
        wb = Workbook(); ws = wb.active; ws.title = "Presenças"
        headers = list(df_pres.columns)
        fill_h = PatternFill("solid", fgColor="1a2f5e"); font_h = Font(color="FFFFFF", bold=True)
        for ci, h in enumerate(headers, 1):
            cell = ws.cell(1, ci, h); cell.fill = fill_h; cell.font = font_h
            cell.alignment = Alignment(horizontal="center")
        for ri, row in df_pres.iterrows():
            for ci, val in enumerate(row, 1): ws.cell(ri+2, ci, val)
        for col in ws.columns: ws.column_dimensions[col[0].column_letter].width = 22
        wb.save(xlsx_buf); xlsx_buf.seek(0)
        st.download_button("⬇️ Exportar Excel", xlsx_buf,
                           file_name=f"presencas_{sel}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ===================================================
# GERENCIAR MEMBROS
# ===================================================
elif pagina == "membros":
    st.markdown('''
    <div class="banner">
        <span class="banner-icon">👥</span>
        <div>
            <p class="banner-title">Gerenciar Membros</p>
            <p class="banner-sub">Incluir, editar, excluir e gerar QR Code PDF</p>
        </div>
    </div>''', unsafe_allow_html=True)

    INSTRUMENTOS = ["CLARINETE","FLAUTA","ÓRGÃO","SAXOFONE ALTO","SAXOFONE TENOR",
                    "TROMBONE","TROMPETE","TUBA","VIOLINO","VIOLONCELO"]
    CARGOS = ["ENCARREGADO REGIONAL","ENCARREGADO LOCAL",
              "SECRETÁRIO DO GEM","INSTRUTOR","EXAMINADORA DE ORGANISTAS"]

    df  = load_participantes()
    aba = st.tabs(["📋 Lista","➕ Incluir","✏️ Editar","🗑️ Excluir","🖨️ Gerar PDF"])

    with aba[0]:
        st.markdown(f"**{len(df)} membros cadastrados**")
        col_f1, col_f2 = st.columns(2)
        filtro_cargo = col_f1.selectbox("Filtrar por cargo",       ["Todos"]+CARGOS,       key="f_cargo")
        filtro_instr = col_f2.selectbox("Filtrar por instrumento", ["Todos"]+INSTRUMENTOS, key="f_instr")
        df_view = df.copy()
        if filtro_cargo != "Todos": df_view = df_view[df_view["cargo"]       == filtro_cargo]
        if filtro_instr != "Todos": df_view = df_view[df_view["instrumento"] == filtro_instr]
        cols_show = [c for c in ["id","nome","cargo","instrumento","localidade"] if c in df_view.columns]
        st.dataframe(df_view[cols_show], use_container_width=True, hide_index=True)

    with aba[1]:
        st.markdown("##### Novo Membro")
        n_id    = st.text_input("ID (ex: AB030)", key="n_id").upper().strip()
        n_nome  = st.text_input("Nome completo",  key="n_nome").upper().strip()
        n_cargo = st.selectbox("Cargo",           CARGOS,       key="n_cargo")
        n_instr = st.selectbox("Instrumento",     INSTRUMENTOS, key="n_instr")
        n_local = st.text_input("Localidade",      key="n_local").upper().strip()
        if st.button("➕ Incluir Membro", type="primary", key="btn_incluir"):
            if not n_id or not n_nome or not n_local:
                st.warning("Preencha ID, Nome e Localidade.")
            else:
                chk = supabase.table("participantes").select("id").eq("id", n_id).execute()
                if chk.data:
                    st.error(f"ID {n_id} já existe!")
                else:
                    supabase.table("participantes").insert({"id":n_id,"nome":n_nome,"cargo":n_cargo,"instrumento":n_instr,"localidade":n_local}).execute()
                    st.success(f"✅ {n_nome} incluído com sucesso!")
                    st.rerun()

    with aba[2]:
        if df.empty:
            st.info("Nenhum membro cadastrado.")
        else:
            opts  = df["id"] + " — " + df["nome"]
            sel_e = st.selectbox("Selecione o membro", opts, key="sel_editar")
            mid   = sel_e.split(" — ")[0]
            mrow  = df[df["id"] == mid].iloc[0]
            e_nome  = st.text_input("Nome",       value=mrow["nome"],      key="e_nome").upper().strip()
            e_cargo = st.selectbox("Cargo", CARGOS, index=CARGOS.index(mrow["cargo"]) if mrow["cargo"] in CARGOS else 0, key="e_cargo")
            instr_val = mrow.get("instrumento") or ""
            e_instr = st.selectbox("Instrumento", INSTRUMENTOS, index=INSTRUMENTOS.index(instr_val) if instr_val in INSTRUMENTOS else 0, key="e_instr")
            e_local = st.text_input("Localidade", value=mrow["localidade"], key="e_local").upper().strip()
            if st.button("💾 Salvar Alterações", type="primary", key="btn_editar"):
                supabase.table("participantes").update({"nome":e_nome,"cargo":e_cargo,"instrumento":e_instr,"localidade":e_local}).eq("id",mid).execute()
                st.success(f"✅ {e_nome} atualizado!"); st.rerun()

    with aba[3]:
        if df.empty:
            st.info("Nenhum membro cadastrado.")
        else:
            opts_d = df["id"] + " — " + df["nome"]
            sel_d  = st.selectbox("Selecione o membro para excluir", opts_d, key="sel_excluir")
            mid_d  = sel_d.split(" — ")[0]
            st.warning(f"⚠️ Tem certeza que deseja excluir **{sel_d}**? Isso também remove as presenças vinculadas.")
            if st.button("🗑️ Confirmar Exclusão", type="primary", key="btn_excluir"):
                supabase.table("presencas").delete().eq("id_participante", mid_d).execute()
                supabase.table("participantes").delete().eq("id", mid_d).execute()
                st.success(f"✅ Membro {mid_d} excluído."); st.rerun()

    with aba[4]:
        if not QR_OK or not RL_OK:
            st.error("Bibliotecas qrcode e/ou reportlab não instaladas.")
        else:
            opcao = st.radio("Opção", ["Todos os membros","Selecionar específicos"], key="pdf_opcao")
            if opcao == "Selecionar específicos":
                opts_p  = df["id"] + " — " + df["nome"]
                sels_p  = st.multiselect("Membros", opts_p, key="pdf_sels")
                ids_sel = [s.split(" — ")[0] for s in sels_p]
                df_sel  = df[df["id"].isin(ids_sel)]
            else:
                df_sel = df
            if st.button("🖨️ Gerar PDF", type="primary", key="btn_pdf"):
                if df_sel.empty:
                    st.warning("Nenhum membro selecionado.")
                else:
                    with st.spinner("Gerando PDF..."):
                        pdf_bytes = gerar_pdf_membros(df_sel.to_dict(orient="records"))
                    st.download_button("⬇️ Baixar PDF", data=pdf_bytes, file_name="qrcodes_membros.pdf", mime="application/pdf")
                    st.success(f"✅ PDF gerado com {len(df_sel)} cartão(ões)!")
