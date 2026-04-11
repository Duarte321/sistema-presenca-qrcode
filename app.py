import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, date, time
import pytz
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import json
import urllib.parse
from supabase import create_client, Client
import qrcode
from PIL import Image

st.set_page_config(page_title="Check-in QR Code", layout="wide")

st.markdown("""
<style>
.qr-box {
    background: white; border-radius: 18px; padding: 18px;
    display: inline-block; text-align: center;
    box-shadow: 0 4px 20px rgba(0,212,170,0.3);
}
</style>
""", unsafe_allow_html=True)

GITHUB_PAGES_URL = "https://duarte321.github.io/sistema-presenca-qrcode/leitor.html"

@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase_client = get_supabase()

def obter_hora_atual():
    return datetime.now(pytz.timezone("America/Cuiaba"))

def _parse_date(s): return datetime.strptime(s, "%Y-%m-%d").date()
def _parse_time(s): return datetime.strptime(s, "%H:%M").time()

@st.cache_data(ttl=30)
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

def limpar_presencas_reuniao(mid):
    try:
        supabase_client.table("presencas").delete().eq("meeting_id", str(mid)).execute()
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

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

def gerar_qr_acesso(url: str) -> Image.Image:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="#0f0f0f", back_color="white").convert("RGB")

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
    pdf.cell(0,8,"Por Cargo:",ln=True)
    for c,q in rc.items(): pdf.cell(0,6,tp(f"  - {c}: {q}"),ln=True)
    pdf.ln(4); pdf.cell(0,8,"Por Localidade:",ln=True)
    for l,q in rl.items(): pdf.cell(0,6,tp(f"  - {l}: {q}"),ln=True)
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

# ==========================
# INICIALIZACAO
# ==========================
df_participantes = carregar_dados_participantes()
if not df_participantes.empty:
    df_participantes = df_participantes.rename(
        columns={"id":"ID","nome":"Nome","cargo":"Cargo","localidade":"Localidade"})

reunioes = carregar_reunioes()

defaults = {
    "active_meeting_id": None,
    "lista_presenca": pd.DataFrame(columns=["ID","Nome","Cargo","Localidade","Horario"]),
    "ultimo_total": 0,
    "polling_ativo": False,
    "poll_count": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

hoje = date.today().strftime("%Y-%m-%d")

# --- Sidebar ---
with st.sidebar:
    st.header("Agenda de Reunioes")
    mostrar_passadas = st.checkbox("Mostrar passadas", value=False)
    reunioes_visiveis = [r for r in reunioes if mostrar_passadas or r.get("data","") >= hoje]
    reunioes_hoje = [r for r in reunioes if r.get("data") == hoje]
    if reunioes_hoje:
        st.markdown("**Hoje:**")
        for r in reunioes_hoje[:6]:
            if st.button(f"Iniciar: {r.get('hora','')} - {r.get('nome','')}", key=f"st_{r['id']}"):
                st.session_state.active_meeting_id = r["id"]
                st.session_state.lista_presenca = carregar_presencas_reuniao(r["id"])
                st.session_state.polling_ativo = True
                st.session_state.poll_count = 0
                st.rerun()
    st.divider()
    reuniao_selecionada_id = None
    if reunioes_visiveis:
        labels = [label_reuniao(r) for r in reunioes_visiveis]
        ids    = [r["id"] for r in reunioes_visiveis]
        di = ids.index(st.session_state.active_meeting_id) if st.session_state.active_meeting_id in ids else 0
        si = st.selectbox("Selecionar reuniao", range(len(ids)), format_func=lambda i: labels[i], index=di)
        reuniao_selecionada_id = ids[si]
    else:
        st.info("Nenhuma reuniao agendada.")
    if reuniao_selecionada_id:
        lbl = "Recarregar" if st.session_state.active_meeting_id == reuniao_selecionada_id else "Iniciar check-in"
        if st.button(lbl, type="primary"):
            st.session_state.active_meeting_id = reuniao_selecionada_id
            st.session_state.lista_presenca = carregar_presencas_reuniao(reuniao_selecionada_id)
            st.session_state.polling_ativo = True
            st.session_state.poll_count = 0
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
            op2=sorted(df_participantes["Cargo" if "Cargo" in df_participantes.columns else "cargo"].unique())
            vals=st.multiselect("Cargos",op2,default=[v for v in vals_def if v in op2])
        elif ft=="Por Localidade" and not df_participantes.empty:
            op2=sorted(df_participantes["Localidade" if "Localidade" in df_participantes.columns else "localidade"].unique())
            vals=st.multiselect("Localidades",op2,default=[v for v in vals_def if v in op2])
        elif ft=="Manual" and not df_participantes.empty:
            op2=sorted(df_participantes["Nome" if "Nome" in df_participantes.columns else "nome"].unique())
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
                st.session_state.polling_ativo=False
            st.success("Reuniao excluida!"); st.rerun()

# --- Reuniao Ativa ---
reuniao_ativa = None
if st.session_state.active_meeting_id:
    for r in reunioes:
        if r.get("id")==st.session_state.active_meeting_id:
            reuniao_ativa=r; break
    if not reuniao_ativa:
        st.session_state.active_meeting_id=None; st.rerun()

if not reuniao_ativa:
    st.title("Check-in QR Code")
    st.warning("Selecione uma reuniao no menu lateral e clique em Iniciar check-in.")
    st.stop()

# --- Cabecalho ---
st.title(f"Check-in: {reuniao_ativa.get('nome')}")
conv_df = filtrar_participantes_convocados(df_participantes, reuniao_ativa)
cid2 = "ID" if "ID" in conv_df.columns else "id"

total_conv = len(conv_df)
total_pres = len(st.session_state.lista_presenca)
cc1,cc2,cc3,cc4 = st.columns(4)
cc1.metric("Convocados", total_conv)
cc2.metric("Presentes",  total_pres)
cc3.metric("Faltantes",  max(0, total_conv - total_pres))
cc4.metric("Auto-refresh", "Ativo ✅" if st.session_state.polling_ativo else "Pausado ⏸")

st.divider()

# --- QR Code de Acesso ---
supa_url = st.secrets.get("SUPABASE_URL", "")
supa_key = st.secrets.get("SUPABASE_KEY", "")
nome_enc = urllib.parse.quote(reuniao_ativa.get("nome", ""))
leitor_url = (
    f"{GITHUB_PAGES_URL}"
    f"?u={urllib.parse.quote(supa_url)}"
    f"&k={urllib.parse.quote(supa_key)}"
    f"&m={urllib.parse.quote(str(reuniao_ativa['id']))}"
    f"&n={nome_enc}"
)

col_qr, col_info = st.columns([1, 2])
with col_qr:
    st.markdown("**Escaneie para abrir o leitor no celular:**")
    qr_img = gerar_qr_acesso(leitor_url)
    st.image(qr_img, width=220)

with col_info:
    st.markdown("### Como usar")
    st.markdown("""
**1.** Abra a camera do celular e aponte para o QR ao lado

**2.** O leitor abre automaticamente no celular

**3.** Aponte para o QR Code do cracha do membro

**4.** O registro aparece aqui automaticamente
""")
    if st.session_state.polling_ativo:
        st.success(f"Monitoramento ativo — ciclo #{st.session_state.poll_count}")
        if st.button("⏸ Pausar monitoramento"):
            st.session_state.polling_ativo = False
            st.rerun()
    else:
        st.warning("Monitoramento pausado")
        if st.button("▶ Ativar monitoramento", type="primary"):
            st.session_state.polling_ativo = True
            st.session_state.poll_count = 0
            st.rerun()
    st.markdown(f"[Abrir leitor diretamente]({leitor_url})")

st.divider()

# --- Lista de Presentes ---
if not st.session_state.lista_presenca.empty:
    st.markdown("### Resumo")
    rc = st.session_state.lista_presenca["Cargo"].value_counts()
    rl = st.session_state.lista_presenca["Localidade"].value_counts()
    c1,c2 = st.columns(2)
    c1.dataframe(rc, use_container_width=True)
    c2.dataframe(rl, use_container_width=True)
    st.divider()
    st.markdown("### Lista de Presentes")
    st.dataframe(
        st.session_state.lista_presenca[["Nome","Cargo","Localidade","Horario"]],
        use_container_width=True, hide_index=True)
    st.divider()
    cA,cB,cC = st.columns(3)
    arq = f"{reuniao_ativa.get('data','')}_{reuniao_ativa.get('hora','')}_{reuniao_ativa.get('nome','reuniao')}".replace(" ","_")
    with cA:
        if st.button("Gerar PDF"):
            st.download_button("Baixar PDF",
                data=gerar_pdf(st.session_state.lista_presenca,rc,rl,reuniao_ativa.get("nome","Reuniao")),
                file_name=f"{arq}.pdf", mime="application/pdf")
    with cB:
        if st.button("Gerar Excel"):
            st.download_button("Baixar Excel",
                data=gerar_excel(st.session_state.lista_presenca,rc,rl,reuniao_ativa.get("nome","Reuniao")),
                file_name=f"{arq}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with cC:
        if st.button("Limpar lista"):
            if limpar_presencas_reuniao(reuniao_ativa["id"]):
                st.session_state.lista_presenca = pd.DataFrame(
                    columns=["ID","Nome","Cargo","Localidade","Horario"])
                st.session_state.ultimo_total = 0
                st.rerun()
else:
    st.info("Nenhuma presenca registrada ainda. Aguardando leituras...")

# --- Polling NO FINAL (nao bloqueia renderizacao) ---
# Executa DEPOIS de tudo renderizado, ai faz rerun para atualizar
if st.session_state.polling_ativo:
    import time as _t
    st.session_state.poll_count += 1
    _t.sleep(5)
    # Recarrega presenças do Supabase
    nova_lista = carregar_presencas_reuniao(reuniao_ativa["id"])
    novo_total  = len(nova_lista)
    if novo_total != st.session_state.ultimo_total:
        st.session_state.lista_presenca = nova_lista
        st.session_state.ultimo_total   = novo_total
    st.rerun()
