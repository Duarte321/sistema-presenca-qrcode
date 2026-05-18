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
[data-testid="stSidebar"],
[data-testid="collapsedControl"] { display: none !important; }
#MainMenu, footer, header         { visibility: hidden !important; }

.stApp {
    background: #0e1c2a !important;
    font-family: 'Inter','Segoe UI',sans-serif !important;
}
.block-container {
    padding: 0 1.4rem 2rem !important;
    max-width: 1080px !important;
}

/* ===== TOPBAR ===== */
.ccb-topbar {
    background: linear-gradient(90deg,#0b1622 0%,#1C3D5A 100%);
    border-bottom: 2px solid #5DB196;
    padding: 12px 22px;
    display: flex; align-items: center; justify-content: space-between;
    margin: -1rem -1.4rem 0;
    position: sticky; top: 0; z-index: 999;
}
.logo-icon  { font-size:1.3rem; margin-right:9px; }
.logo-text  { font-size:.95rem; font-weight:800; color:#fff; letter-spacing:.4px; display:inline; }
.logo-sub   { font-size:.65rem; color:#98CDBD; letter-spacing:1.4px; text-transform:uppercase; margin-left:2px; display:block; }
.ccb-badge  {
    background:rgba(93,177,150,.14);
    border:1px solid #5DB196; border-radius:99px;
    padding:3px 13px; color:#98CDBD;
    font-size:.68rem; font-weight:700;
    letter-spacing:1px; text-transform:uppercase;
}

/* ===== NAV: so os botoes reais, estilizados como pills ===== */
/* Wrapper das colunas de nav: sem padding extra */
div[data-testid="stHorizontalBlock"].nav-row {
    gap: 6px !important;
    padding: 12px 0 4px !important;
    border-bottom: 1px solid rgba(93,177,150,.15) !important;
    margin-bottom: 18px !important;
}

/* Botoes do nav */
.nav-row div[data-testid="column"] .stButton > button {
    width: 100% !important;
    padding: 10px 6px !important;
    border-radius: 10px !important;
    font-size: .78rem !important;
    font-weight: 700 !important;
    letter-spacing: .5px !important;
    text-transform: uppercase !important;
    color: #A5A5A5 !important;
    background: rgba(255,255,255,.03) !important;
    border: 1px solid rgba(255,255,255,.07) !important;
    transition: all .17s !important;
    min-height: 42px !important;
}
.nav-row div[data-testid="column"] .stButton > button:hover {
    background: rgba(93,177,150,.1) !important;
    color: #98CDBD !important;
    border-color: rgba(93,177,150,.35) !important;
}
/* Botao ativo: injeta via JS no session_state — usamos data-active via CSS hack */
.nav-row div[data-testid="column"] .stButton > button[data-active="true"],
.nav-active .stButton > button {
    background: linear-gradient(135deg,#1C3D5A,#49656C) !important;
    color: #fff !important;
    border-color: #5DB196 !important;
    box-shadow: 0 2px 10px rgba(93,177,150,.25) !important;
}

/* ===== PAGE HEADER ===== */
.page-header {
    display:flex; align-items:center; gap:12px;
    padding:14px 20px;
    background: linear-gradient(135deg,#132233,#1C3D5A 60%,#2a5240);
    border:1px solid rgba(93,177,150,.28);
    border-radius:14px; margin-bottom:18px;
    animation: fadeUp .3s ease;
}
.ph-icon  { font-size:1.7rem; }
.ph-title { color:#fff; font-size:1.2rem; font-weight:800; margin:0; }
.ph-sub   { color:#98CDBD; font-size:.78rem; margin:2px 0 0; }

/* ===== STAT CARDS ===== */
.stat-row { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px; }
.stat-card {
    flex:1; min-width:100px;
    background:rgba(28,61,90,.32);
    border:1px solid rgba(93,177,150,.18);
    border-radius:13px; padding:14px 10px;
    text-align:center; transition:transform .18s;
}
.stat-card:hover { transform:translateY(-2px); }
.stat-val { font-size:1.9rem; font-weight:800; margin:0; line-height:1; }
.stat-lbl { font-size:.65rem; text-transform:uppercase; letter-spacing:1.5px; margin-top:5px; color:#A5A5A5; }
.sv-blue  { color:#60b4d4; } .sv-green { color:#5DB196; }
.sv-teal  { color:#98CDBD; } .sv-gray  { color:#A5A5A5; }

/* ===== BARRA DE PROGRESSO ===== */
.prog-wrap {
    background:rgba(255,255,255,.05); border-radius:99px;
    height:7px; margin:0 0 6px; overflow:hidden;
}
.prog-fill {
    height:100%; border-radius:99px;
    background:linear-gradient(90deg,#1C3D5A,#49656C,#5DB196);
    transition:width .6s ease;
}
.prog-txt { color:#A5A5A5; font-size:.72rem; margin:0 0 18px; }

/* ===== SEC LABEL ===== */
.sec-label {
    color:#5DB196; font-size:.65rem; font-weight:800;
    text-transform:uppercase; letter-spacing:2px;
    margin:16px 0 9px;
    display:flex; align-items:center; gap:7px;
}
.sec-label::after { content:''; flex:1; height:1px; background:rgba(93,177,150,.18); }

/* ===== REUNIAO CARD ===== */
.re-card {
    background:rgba(28,61,90,.22);
    border:1px solid rgba(93,177,150,.17);
    border-left:3px solid #5DB196;
    border-radius:11px; padding:13px 18px;
    margin:7px 0; display:flex;
    align-items:center; justify-content:space-between;
    transition:all .18s;
}
.re-card:hover { background:rgba(28,61,90,.42); transform:translateX(3px); }
.re-nome { color:#e2e8f0; font-size:.95rem; font-weight:700; margin:0; }
.re-meta { color:#A5A5A5; font-size:.74rem; margin:2px 0 0; }
.badge-h { background:#5DB196; color:#0e1c2a; font-size:.6rem; font-weight:800; padding:2px 9px; border-radius:99px; text-transform:uppercase; letter-spacing:1px; }
.badge-f { background:rgba(93,177,150,.1); color:#98CDBD; border:1px solid rgba(93,177,150,.28); font-size:.6rem; font-weight:700; padding:2px 9px; border-radius:99px; }

/* ===== FEEDBACK ===== */
.fb-ok   { background:linear-gradient(135deg,#0a2e20,#0d3d29); border:1px solid #5DB196; border-radius:13px; padding:18px 22px; text-align:center; margin:10px 0; animation:bounceIn .35s ease; }
.fb-ok .fb-t  { color:#98CDBD; font-size:.95rem; font-weight:600; }
.fb-ok .fb-n  { color:#fff; font-size:1.3rem; font-weight:800; margin:4px 0; }
.fb-ok .fb-s  { color:#5DB196; font-size:.82rem; }
.fb-warn { background:rgba(120,83,0,.28); border:1px solid #d4a017; border-radius:13px; padding:14px 18px; text-align:center; margin:10px 0; }
.fb-warn .fb-t { color:#f5d070; font-size:.9rem; font-weight:700; }
.fb-erro { background:rgba(120,0,0,.28); border:1px solid #c0392b; border-radius:13px; padding:14px 18px; text-align:center; margin:10px 0; }
.fb-erro .fb-t { color:#f1948a; font-size:.9rem; font-weight:700; }
.fb-idle { background:rgba(28,61,90,.18); border:1px dashed rgba(93,177,150,.28); border-radius:13px; padding:14px 18px; text-align:center; margin:10px 0; }
.fb-idle .fb-t { color:#98CDBD; font-size:.84rem; }

/* ===== INPUTS / SELECT ===== */
input, textarea, [data-baseweb="input"] input {
    background:rgba(28,61,90,.28) !important;
    border:1px solid rgba(93,177,150,.28) !important;
    border-radius:8px !important; color:#e2e8f0 !important;
}
input:focus, textarea:focus {
    border-color:#5DB196 !important;
    box-shadow:0 0 0 2px rgba(93,177,150,.18) !important;
}
[data-baseweb="select"] > div {
    background:rgba(28,61,90,.28) !important;
    border:1px solid rgba(93,177,150,.28) !important;
    border-radius:8px !important; color:#e2e8f0 !important;
}

/* ===== BOTOES GERAIS ===== */
.stButton > button {
    border-radius:8px !important; font-weight:600 !important;
    transition:all .17s !important;
    background:rgba(28,61,90,.38) !important;
    border:1px solid rgba(93,177,150,.28) !important;
    color:#98CDBD !important;
}
.stButton > button:hover {
    background:rgba(73,101,108,.48) !important;
    border-color:#5DB196 !important;
    transform:translateY(-1px) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
    background:linear-gradient(135deg,#1C3D5A,#49656C) !important;
    border:1px solid #5DB196 !important; color:#fff !important;
    box-shadow:0 3px 10px rgba(93,177,150,.22) !important;
}
.stButton > button[kind="primary"]:hover {
    background:linear-gradient(135deg,#234d72,#5DB196) !important;
    box-shadow:0 5px 16px rgba(93,177,150,.38) !important;
}

/* ===== TABS INTERNAS ===== */
[data-testid="stTabs"] button[role="tab"] {
    background:rgba(28,61,90,.22) !important;
    border-radius:8px 8px 0 0 !important;
    color:#A5A5A5 !important; font-size:.79rem !important;
    font-weight:600 !important;
    border:1px solid rgba(93,177,150,.1) !important;
    border-bottom:none !important; padding:8px 14px !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background:linear-gradient(135deg,#1C3D5A,#49656C) !important;
    color:#fff !important; border-color:#5DB196 !important;
}

/* ===== DATAFRAME / METRIC ===== */
[data-testid="stDataFrame"] {
    border-radius:10px !important;
    border:1px solid rgba(93,177,150,.18) !important;
    overflow:hidden !important;
}
[data-testid="stMetric"] {
    background:rgba(28,61,90,.28) !important;
    border:1px solid rgba(93,177,150,.18) !important;
    border-radius:11px !important; padding:12px !important;
}
[data-testid="stMetricValue"] { color:#5DB196 !important; }
[data-testid="stMetricLabel"] { color:#A5A5A5 !important; font-size:.73rem !important; }

/* ===== CAMERA ===== */
[data-testid="stCameraInput"] > div {
    border-radius:13px !important;
    border:2px solid rgba(93,177,150,.38) !important;
    overflow:hidden !important;
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:rgba(255,255,255,.02); }
::-webkit-scrollbar-thumb { background:rgba(93,177,150,.32); border-radius:99px; }

/* ===== ANIMS ===== */
@keyframes fadeUp   { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
@keyframes bounceIn { 0%{transform:scale(.9);opacity:0} 60%{transform:scale(1.03);opacity:1} 100%{transform:scale(1)} }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------------------------------------
# SUPABASE
# -------------------------------------------------------
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase: Client = get_supabase()
BR = pytz.timezone("America/Cuiaba")

def agora_br(): return datetime.now(BR)

def load_participantes():
    r = supabase.table("participantes").select("*").order("nome").execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def load_reunioes():
    return supabase.table("reunioes").select("*").execute().data or []

def load_presencas(meeting_id=None):
    q = supabase.table("presencas").select("*, participantes(nome,cargo,localidade,instrumento)")
    if meeting_id: q = q.eq("meeting_id", meeting_id)
    return q.execute().data or []

def gerar_pdf_membros(membros: list) -> bytes:
    NAVY=colors.HexColor("#1C3D5A"); TEAL=colors.HexColor("#5DB196")
    GRAY=colors.HexColor("#555555"); BLACK=colors.black
    LIGHT=colors.HexColor("#f0f5f3"); WHITE=colors.white
    hs=ParagraphStyle("h",fontName="Helvetica-Bold",fontSize=10,textColor=WHITE,alignment=TA_CENTER)
    ns=ParagraphStyle("n",fontName="Helvetica-Bold",fontSize=11,textColor=BLACK,alignment=TA_LEFT,leading=14)
    ls=ParagraphStyle("l",fontName="Helvetica",fontSize=9,textColor=GRAY,alignment=TA_LEFT)
    cs=ParagraphStyle("c",fontName="Helvetica-Bold",fontSize=13,textColor=NAVY,alignment=TA_CENTER)
    buf_pdf=io.BytesIO()
    doc=SimpleDocTemplate(buf_pdf,pagesize=A4,rightMargin=1.5*cm,leftMargin=1.5*cm,topMargin=1.5*cm,bottomMargin=1.5*cm)
    story=[]
    for m in membros:
        qr=qrcode.QRCode(version=2,box_size=6,border=2)
        qr.add_data(m["id"]); qr.make(fit=True)
        qi=qr.make_image(fill_color="#1C3D5A",back_color="white")
        bq=io.BytesIO(); qi.save(bq,format="PNG"); bq.seek(0)
        ri=RLImage(bq,width=3.5*cm,height=3.5*cm)
        info=[Paragraph(m["nome"],ns),Spacer(1,4),
              Paragraph(f'<font color="#555">Cargo:</font> <b>{m["cargo"]}</b>',ls),
              Paragraph(f'<font color="#555">Local:</font> <b>{m.get("localidade","")}</b>',ls),
              Paragraph(f'<font color="#555">Instr.:</font> <b>{m.get("instrumento","")}</b>',ls)]
        card=Table([[Paragraph("QR CODE DE CHECK-IN — CCB MUSICAL",hs),""],
                    [ri,info],[Paragraph(m["id"],cs),""]],colWidths=[4*cm,12*cm])
        card.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),NAVY),("SPAN",(0,0),(-1,0)),
            ("TOPPADDING",(0,0),(-1,0),6),("BOTTOMPADDING",(0,0),(-1,0),6),
            ("VALIGN",(0,1),(-1,1),"MIDDLE"),("ALIGN",(0,1),(0,1),"CENTER"),
            ("LEFTPADDING",(1,1),(1,1),10),("TOPPADDING",(0,1),(-1,1),8),("BOTTOMPADDING",(0,1),(-1,1),8),
            ("SPAN",(0,2),(-1,2)),("BACKGROUND",(0,2),(-1,2),LIGHT),
            ("TOPPADDING",(0,2),(-1,2),6),("BOTTOMPADDING",(0,2),(-1,2),6),
            ("BOX",(0,0),(-1,-1),1.2,TEAL),
        ]))
        story.append(card); story.append(Spacer(1,0.7*cm))
    doc.build(story); buf_pdf.seek(0)
    return buf_pdf.read()

# -------------------------------------------------------
# NAVEGACAO — botoes nativos Streamlit, SEM HTML duplicado
# -------------------------------------------------------
PAGINAS = [
    ("home",    "🏠", "Painel"),
    ("checkin", "📷", "Check-in"),
    ("relat",   "📊", "Relatórios"),
    ("membros", "👥", "Membros"),
]

if "pagina" not in st.session_state:
    st.session_state.pagina = "home"

# Top bar HTML (somente visual, sem nav)
st.markdown('''
<div class="ccb-topbar">
  <div style="display:flex;align-items:center">
    <span class="logo-icon">🎵</span>
    <div>
      <span class="logo-text">CCB Musical</span>
      <span class="logo-sub">Congregação Cristã no Brasil</span>
    </div>
  </div>
  <span class="ccb-badge">Sistema de Presença</span>
</div>
''', unsafe_allow_html=True)

st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

# NAV: apenas botoes reais, dentro de um container estilizado
st.markdown('<div class="nav-row" style="display:flex;gap:6px;padding:10px 0 4px;border-bottom:1px solid rgba(93,177,150,.15);margin-bottom:16px"></div>', unsafe_allow_html=True)
cols_nav = st.columns(4)
for i, (key, icon, label) in enumerate(PAGINAS):
    with cols_nav[i]:
        ativo = st.session_state.pagina == key
        # botao ativo recebe kind=primary, inativo é normal
        if ativo:
            if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True, type="primary"):
                st.session_state.pagina = key; st.rerun()
        else:
            if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
                st.session_state.pagina = key; st.rerun()

st.markdown('<hr style="border:none;border-top:1px solid rgba(93,177,150,.15);margin:0 0 18px">', unsafe_allow_html=True)

pagina = st.session_state.pagina

# ===================================================
# HOME — SIMPLES E LIMPA
# ===================================================
if pagina == "home":
    df_p = load_participantes()
    reun = load_reunioes()
    pres = load_presencas()
    tm=len(df_p); tr=len(reun); tp=len(pres)
    pct=round(tp/tm*100) if tm else 0
    hoje=agora_br().date()

    # Saudacao
    hora=agora_br().hour
    if hora < 12: sauda="Bom dia"
    elif hora < 18: sauda="Boa tarde"
    else: sauda="Boa noite"

    st.markdown(f'''
    <div style="padding:18px 0 6px">
        <p style="color:#fff;font-size:1.5rem;font-weight:800;margin:0">{sauda}! 🎵</p>
        <p style="color:#5DB196;font-size:.82rem;margin:3px 0 0">CCB Musical — Congregação Cristã no Brasil</p>
    </div>
    ''', unsafe_allow_html=True)

    # 4 cards de stat
    st.markdown(f'''
    <div class="stat-row">
        <div class="stat-card"><p class="stat-val sv-blue">{tm}</p><p class="stat-lbl">Membros</p></div>
        <div class="stat-card"><p class="stat-val sv-teal">{tr}</p><p class="stat-lbl">Reuniões</p></div>
        <div class="stat-card"><p class="stat-val sv-green">{tp}</p><p class="stat-lbl">Presenças</p></div>
        <div class="stat-card"><p class="stat-val sv-gray">{pct}%</p><p class="stat-lbl">Frequência</p></div>
    </div>
    <div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div>
    <p class="prog-txt">Frequência geral: {pct}%</p>
    ''', unsafe_allow_html=True)

    # Proxima reuniao: mostra apenas a mais proxima
    reun_ord = sorted(reun, key=lambda x: x["data"])
    proxima = None
    for r in reun_ord:
        dr = date.fromisoformat(r["data"]) if isinstance(r["data"],str) else r["data"]
        if dr >= hoje:
            proxima = (r, dr); break

    st.markdown('<div class="sec-label">📅 Próxima Reunião</div>', unsafe_allow_html=True)
    if proxima:
        r, dr = proxima
        badge = '<span class="badge-h">Hoje</span>' if dr==hoje else f'<span class="badge-f">{dr.strftime("%d/%m")}</span>'
        st.markdown(f'''
        <div class="re-card">
            <div>
                <p class="re-nome">{r["nome"]}</p>
                <p class="re-meta">{r.get("horario","")} &nbsp;·&nbsp; {dr.strftime("%d/%m/%Y")}</p>
            </div>
            {badge}
        </div>''', unsafe_allow_html=True)
    else:
        st.info("Nenhuma reunião futura agendada.")

# ===================================================
# CHECK-IN
# ===================================================
elif pagina == "checkin":
    st.markdown('''
    <div class="page-header">
        <span class="ph-icon">📷</span>
        <div><p class="ph-title">Check-in</p>
        <p class="ph-sub">Escaneie ou digite o código do membro</p></div>
    </div>''', unsafe_allow_html=True)

    reun = load_reunioes()
    if not reun:
        st.warning("Nenhuma reunião cadastrada."); st.stop()

    sel = st.selectbox("📅 Selecione a reunião", [r["nome"] for r in reun])
    reuniao = next(r for r in reun if r["nome"]==sel)

    tab_cam, tab_cod = st.tabs(["📸  Câmera QR", "⌨️  Código Manual"])

    def registrar(codigo, mid):
        codigo = codigo.upper().strip()
        res = supabase.table("participantes").select("*").eq("id",codigo).execute()
        if not res.data: return None, "nf"
        m = res.data[0]
        dup = supabase.table("presencas").select("id").eq("id_participante",codigo).eq("meeting_id",mid).execute()
        if dup.data: return m, "dup"
        supabase.table("presencas").insert({
            "id_participante":codigo,"meeting_id":mid,
            "nome":m["nome"],"cargo":m["cargo"],"localidade":m["localidade"],
            "horario":agora_br().strftime("%H:%M:%S"),
            "data_registro":agora_br().strftime("%Y-%m-%d")
        }).execute()
        return m, "ok"

    with tab_cam:
        img = st.camera_input("Aponte a câmera para o QR Code")
        if img:
            pil = Image.open(img).convert("L")
            pil = ImageEnhance.Contrast(pil).enhance(2.5).filter(ImageFilter.SHARPEN)
            dec = decode(np.array(pil))
            if dec:
                cod = dec[0].data.decode().strip()
                m, s = registrar(cod, reuniao["id"])
                if   s=="ok":  st.markdown(f'<div class="fb-ok"><p class="fb-t">✅ Check-in realizado!</p><p class="fb-n">{m["nome"]}</p><p class="fb-s">{m["cargo"]} — {m["localidade"]}</p></div>',unsafe_allow_html=True)
                elif s=="dup": st.markdown(f'<div class="fb-warn"><p class="fb-t">⚠️ Já registrado: {m["nome"]}</p></div>',unsafe_allow_html=True)
                else:          st.markdown('<div class="fb-erro"><p class="fb-t">❌ Código não encontrado</p></div>',unsafe_allow_html=True)
            else:
                st.markdown('<div class="fb-idle"><p class="fb-t">QR Code não detectado — tente novamente</p></div>',unsafe_allow_html=True)

    with tab_cod:
        cod_m = st.text_input("Código (ex: CF001)",key="cod_m").upper().strip()
        if st.button("✅ Registrar Presença",type="primary",key="btn_manual"):
            if cod_m:
                m, s = registrar(cod_m, reuniao["id"])
                if   s=="ok":  st.markdown(f'<div class="fb-ok"><p class="fb-t">✅ Check-in realizado!</p><p class="fb-n">{m["nome"]}</p></div>',unsafe_allow_html=True)
                elif s=="dup": st.markdown(f'<div class="fb-warn"><p class="fb-t">⚠️ Já registrado: {m["nome"]}</p></div>',unsafe_allow_html=True)
                else:          st.markdown('<div class="fb-erro"><p class="fb-t">❌ Código não encontrado</p></div>',unsafe_allow_html=True)

# ===================================================
# RELATORIOS
# ===================================================
elif pagina == "relat":
    st.markdown('''
    <div class="page-header">
        <span class="ph-icon">📊</span>
        <div><p class="ph-title">Relatórios</p>
        <p class="ph-sub">Frequência e presenças por reunião</p></div>
    </div>''', unsafe_allow_html=True)

    reun=load_reunioes(); df_p=load_participantes()
    if not reun: st.info("Nenhuma reunião."); st.stop()

    sel=st.selectbox("📅 Reunião",[r["nome"] for r in reun])
    reuniao=next(r for r in reun if r["nome"]==sel)
    pres=load_presencas(reuniao["id"])
    ids_p={p["id_participante"] for p in pres}
    total=len(df_p); presente=len(ids_p); ausente=total-presente
    pct=round(presente/total*100) if total else 0

    t_res, t_grf, t_exp = st.tabs(["📋  Presenças","📈  Gráficos","⬇️  Exportar"])

    with t_res:
        c1,c2,c3=st.columns(3)
        c1.metric("Total",total); c2.metric("Presentes",presente); c3.metric("Ausentes",ausente)
        st.markdown(f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div><p class="prog-txt">Frequência: {pct}%</p>',unsafe_allow_html=True)
        if pres:
            df_pr=pd.DataFrame([{"Nome":p["participantes"]["nome"],"Cargo":p["participantes"]["cargo"],
                "Localidade":p["participantes"]["localidade"],"Instrumento":p["participantes"].get("instrumento",""),
                "Hora":p.get("horario","")} for p in pres])
            st.dataframe(df_pr,use_container_width=True,hide_index=True)
        else: st.info("Nenhuma presença registrada.")

    with t_grf:
        if pres:
            fig1=px.pie(df_pr,names="Instrumento",title="Por Instrumento",
                color_discrete_sequence=["#1C3D5A","#49656C","#5DB196","#98CDBD","#A5A5A5","#60b4d4"])
            fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color="#e2e8f0")
            st.plotly_chart(fig1,use_container_width=True)
            fig2=px.bar(df_pr,x="Cargo",title="Por Cargo",color_discrete_sequence=["#5DB196"])
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color="#e2e8f0")
            st.plotly_chart(fig2,use_container_width=True)
        else: st.info("Sem dados para gráfico.")

    with t_exp:
        if pres:
            xlsx_buf=BytesIO(); wb=Workbook(); ws=wb.active; ws.title="Presenças"
            fill_h=PatternFill("solid",fgColor="1C3D5A"); font_h=Font(color="FFFFFF",bold=True)
            for ci,h in enumerate(df_pr.columns,1):
                cell=ws.cell(1,ci,h); cell.fill=fill_h; cell.font=font_h
                cell.alignment=Alignment(horizontal="center")
            for ri,row in df_pr.iterrows():
                for ci,val in enumerate(row,1): ws.cell(ri+2,ci,val)
            for col in ws.columns: ws.column_dimensions[col[0].column_letter].width=22
            wb.save(xlsx_buf); xlsx_buf.seek(0)
            st.download_button("⬇️ Baixar Excel",xlsx_buf,
                file_name=f"presencas_{sel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        else: st.info("Nenhuma presença para exportar.")

# ===================================================
# MEMBROS
# ===================================================
elif pagina == "membros":
    st.markdown('''
    <div class="page-header">
        <span class="ph-icon">👥</span>
        <div><p class="ph-title">Membros</p>
        <p class="ph-sub">Cadastro, edição e QR Code PDF</p></div>
    </div>''', unsafe_allow_html=True)

    INSTRUMENTOS=["CLARINETE","FLAUTA","ÓRGÃO","SAXOFONE ALTO","SAXOFONE TENOR",
                  "TROMBONE","TROMPETE","TUBA","VIOLINO","VIOLONCELO"]
    CARGOS=["ENCARREGADO REGIONAL","ENCARREGADO LOCAL",
            "SECRETÁRIO DO GEM","INSTRUTOR","EXAMINADORA DE ORGANISTAS"]

    df=load_participantes()
    t_lista,t_add,t_edit,t_del,t_pdf=st.tabs([
        "📋  Lista","➕  Incluir","✏️  Editar","🗑️  Excluir","🖨️  PDF QR"
    ])

    with t_lista:
        st.markdown(f'<div class="sec-label">{len(df)} membros cadastrados</div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        fc=c1.selectbox("Cargo",["Todos"]+CARGOS,key="f_cargo")
        fi=c2.selectbox("Instrumento",["Todos"]+INSTRUMENTOS,key="f_instr")
        dv=df.copy()
        if fc!="Todos": dv=dv[dv["cargo"]==fc]
        if fi!="Todos": dv=dv[dv["instrumento"]==fi]
        cs=[c for c in ["id","nome","cargo","instrumento","localidade"] if c in dv.columns]
        st.dataframe(dv[cs],use_container_width=True,hide_index=True)

    with t_add:
        st.markdown('<div class="sec-label">Novo Membro</div>',unsafe_allow_html=True)
        col1,col2=st.columns(2)
        n_id   =col1.text_input("ID (ex: AB030)",key="n_id").upper().strip()
        n_nome =col2.text_input("Nome completo",key="n_nome").upper().strip()
        n_cargo=col1.selectbox("Cargo",CARGOS,key="n_cargo")
        n_instr=col2.selectbox("Instrumento",INSTRUMENTOS,key="n_instr")
        n_local=st.text_input("Localidade",key="n_local").upper().strip()
        if st.button("➕ Incluir Membro",type="primary",key="btn_add",use_container_width=True):
            if not n_id or not n_nome or not n_local:
                st.warning("Preencha ID, Nome e Localidade.")
            else:
                chk=supabase.table("participantes").select("id").eq("id",n_id).execute()
                if chk.data: st.error(f"ID {n_id} já existe!")
                else:
                    supabase.table("participantes").insert({"id":n_id,"nome":n_nome,"cargo":n_cargo,"instrumento":n_instr,"localidade":n_local}).execute()
                    st.success(f"✅ {n_nome} incluído!"); st.rerun()

    with t_edit:
        if df.empty: st.info("Nenhum membro cadastrado.")
        else:
            opts=df["id"]+" — "+df["nome"]
            sel_e=st.selectbox("Selecione",opts,key="sel_e")
            mid=sel_e.split(" — ")[0]
            mr=df[df["id"]==mid].iloc[0]
            col1,col2=st.columns(2)
            e_nome =col1.text_input("Nome",value=mr["nome"],key="e_nome").upper().strip()
            e_local=col2.text_input("Localidade",value=mr["localidade"],key="e_loc").upper().strip()
            e_cargo=col1.selectbox("Cargo",CARGOS,index=CARGOS.index(mr["cargo"]) if mr["cargo"] in CARGOS else 0,key="e_cargo")
            iv=mr.get("instrumento") or ""
            e_instr=col2.selectbox("Instrumento",INSTRUMENTOS,index=INSTRUMENTOS.index(iv) if iv in INSTRUMENTOS else 0,key="e_instr")
            if st.button("💾 Salvar Alterações",type="primary",key="btn_edit",use_container_width=True):
                supabase.table("participantes").update({"nome":e_nome,"cargo":e_cargo,"instrumento":e_instr,"localidade":e_local}).eq("id",mid).execute()
                st.success(f"✅ {e_nome} atualizado!"); st.rerun()

    with t_del:
        if df.empty: st.info("Nenhum membro cadastrado.")
        else:
            opts_d=df["id"]+" — "+df["nome"]
            sel_d=st.selectbox("Membro para excluir",opts_d,key="sel_d")
            mid_d=sel_d.split(" — ")[0]
            st.warning(f"⚠️ Excluir **{sel_d}**? Isso remove também todas as presenças vinculadas.")
            if st.button("🗑️ Confirmar Exclusão",type="primary",key="btn_del",use_container_width=True):
                supabase.table("presencas").delete().eq("id_participante",mid_d).execute()
                supabase.table("participantes").delete().eq("id",mid_d).execute()
                st.success(f"✅ {mid_d} excluído."); st.rerun()

    with t_pdf:
        if not QR_OK or not RL_OK:
            st.error("❌ Instale: pip install qrcode[pil] reportlab")
        else:
            opcao=st.radio("Selecionar",["Todos os membros","Membros específicos"],horizontal=True,key="pdf_op")
            if opcao=="Membros específicos":
                opts_p=df["id"]+" — "+df["nome"]
                sels_p=st.multiselect("Selecione",opts_p,key="pdf_sels")
                df_sel=df[df["id"].isin([s.split(" — ")[0] for s in sels_p])]
            else:
                df_sel=df
            st.markdown(f'<div class="sec-label">{len(df_sel)} membro(s)</div>',unsafe_allow_html=True)
            if st.button("🖨️ Gerar PDF com QR Codes",type="primary",key="btn_pdf",use_container_width=True):
                if df_sel.empty: st.warning("Nenhum membro selecionado.")
                else:
                    with st.spinner("Gerando PDF..."):
                        pdf_b=gerar_pdf_membros(df_sel.to_dict(orient="records"))
                    st.download_button("⬇️ Baixar PDF",data=pdf_b,
                        file_name="qrcodes_ccb.pdf",mime="application/pdf",use_container_width=True)
                    st.success(f"✅ {len(df_sel)} cartão(oes) gerado(s)!")
