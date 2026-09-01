import streamlit as st
import streamlit.components.v1 as components
import sqlite3, re, io, hmac
from datetime import date, datetime, timedelta
import pandas as pd
from pypdf import PdfReader

DB='stok.db'

def con():
    c=sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, invoice_no TEXT UNIQUE, invoice_date TEXT, supplier TEXT, file_name TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY, invoice_no TEXT, product TEXT, qty REAL, unit TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY, sale_date TEXT, product TEXT, qty REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    c.commit(); return c

def monday(d): return d-timedelta(days=d.weekday())

def pdf_text(f):
    r=PdfReader(io.BytesIO(f.getvalue()))
    return '\n'.join((p.extract_text() or '') for p in r.pages)

def meta(t):
    inv=dt=None; sup='Bilinmiyor'
    for p in [r'Rechnungs[- ]?Nr\.?\s*([A-Z0-9\-]+)',r'Rechnung Nr\.?\s*([A-Z0-9\-]+)']:
        m=re.search(p,t,re.I)
        if m: inv=m.group(1); break
    m=re.search(r'Rechnungsdatum\s*(\d{2}\.\d{2}\.\d{4})',t,re.I) or re.search(r'Lieferdatum\s*(\d{2}\.\d{2}\.\d{4})',t,re.I)
    if m: dt=datetime.strptime(m.group(1),'%d.%m.%Y').date().isoformat()
    if 'Malis Gastronomiebedarf' in t: sup='Malis'
    elif 'Botan' in t or 'BOTAN' in t: sup='Botan'
    return inv,dt,sup

def product_name(desc):
    d=desc.lower()
    if 'coca cola' in d or 'coca-cola' in d:
        return 'Cola 1L' if ('1 l' in d or '1l' in d or 'x1 l' in d) else 'Cola 0,33 (Cola+Zero)'
    if 'fanta' in d: return 'Fanta 1L' if ('1 l' in d or '1l' in d) else 'Fanta 0,33 (tüm çeşitler)'
    if 'mezzo mix' in d: return 'Mezzo Mix 1L' if ('1 l' in d or '1l' in d) else 'Mezzo Mix 0,33'
    if 'uludag' in d: return 'Uludağ 0,33'
    if 'ayran' in d: return 'Ayran'
    if 'capri' in d: return 'Capri-Sun'
    if 'wasser' in d: return 'Su 0,50'
    if 'sprite' in d and ('1 l' in d or '1l' in d): return 'Sprite 1L'
    return desc[:80]

def parse_lines(t):
    out=[]
    for line in t.splitlines():
        s=' '.join(line.split())
        m=re.match(r'^\d+\.\s+\S+\s+(.+?)\s+(\d+,\d+)\s+Stk\b',s,re.I)
        if not m: continue
        desc=m.group(1)
        if 'leergut' in desc.lower(): continue
        q=float(m.group(2).replace(',','.')); unit='paket/koli'
        pack=re.search(r'(\d+)x0[,\.]33',desc.replace(' ',''),re.I)
        if pack: q*=int(pack.group(1)); unit='adet'
        out.append({'product':product_name(desc),'qty':q,'unit':unit})
    return out

def import_existing(db):
    if db.execute("SELECT value FROM settings WHERE key='existing_import_v1'").fetchone(): return False
    purchases={'Cola 0,33 (Cola+Zero)':1944,'Fanta 0,33 (tüm çeşitler)':1392,'Mezzo Mix 0,33':288,'Uludağ 0,33':792,'Su 0,50':840,'Ayran':1320,'Capri-Sun':590,'Cola 1L':312,'Fanta 1L':84,'Mezzo Mix 1L':120,'Sprite 1L':96,'Mayonez':1460,'Gold Ketchup':600,'Curry Ketchup':310,'Kırmızı Soğan':320,'Beyaz Lahana':240,'Domates':48,'Beyaz Peynir':144,'Kızartma Yağı':225,'Chicken Nuggets':39,'Currywurst':310,'Best Burger':960,'Üçgen Yufka':1900}
    for product,qty in purchases.items():
        unit='adet'
        if product in ['Mayonez','Gold Ketchup','Curry Ketchup','Kırmızı Soğan','Beyaz Lahana','Domates','Beyaz Peynir','Chicken Nuggets']: unit='kg'
        if product=='Kızartma Yağı': unit='L'
        db.execute('INSERT INTO purchases(invoice_no,product,qty,unit) VALUES(?,?,?,?)',('IMPORT-TOPLAM',product,qty,unit))
    sales={'Cola 0,33 (Cola+Zero)':2710,'Fanta 0,33 (tüm çeşitler)':1278,'Mezzo Mix 0,33':351,'Uludağ 0,33':1002,'Su 0,50':371,'Ayran':1647,'Capri-Sun':487,'Cola 1L':154,'Mezzo Mix 1L':22,'Uludağ 1L':15}
    for product,qty in sales.items(): db.execute('INSERT INTO sales(sale_date,product,qty) VALUES(?,?,?)',('2026-08-31',product,qty))
    invoice_dates=[('RE26001344','2026-01-07','Botan'),('RE26003022','2026-01-14','Botan'),('RE26006619','2026-01-28','Botan'),('RE26008549','2026-02-04','Botan'),('RE26010481','2026-02-11','Botan'),('RE26012402','2026-02-18','Botan'),('RE26014193','2026-02-25','Botan'),('RE26016232','2026-03-04','Botan'),('IMPORT-20260318','2026-03-18','Botan'),('RE26022368','2026-03-25','Botan'),('RE26024580','2026-04-01','Botan'),('RE26026509','2026-04-08','Botan'),('RE26028670','2026-04-15','Botan'),('RE26030753','2026-04-22','Botan'),('RE26058585','2026-07-15','Botan'),('IMPORT-20260722','2026-07-22','Botan'),('RE26063334','2026-07-29','Botan'),('RE26065873','2026-08-05','Botan'),('RE26068314','2026-08-12','Botan'),('RE26070839','2026-08-19','Botan'),('IMPORT-20260826','2026-08-26','Botan'),('RE-5983','2026-07-18','Malis')]
    for no,dt,sup in invoice_dates: db.execute('INSERT OR IGNORE INTO invoices(invoice_no,invoice_date,supplier,file_name) VALUES(?,?,?,?)',(no,dt,sup,'Sohbetten aktarıldı'))
    db.execute("INSERT INTO settings(key,value) VALUES('existing_import_v1','1')"); db.commit(); return True

st.set_page_config(page_title='Berlin Döner Stok',page_icon='🥙',layout='centered',initial_sidebar_state='collapsed')

st.markdown('''<style>
#MainMenu, footer, header {visibility:hidden}.block-container{padding:1rem 1rem 6.5rem;max-width:520px}.stApp{background:#070707;color:#fff}
:root{--red:#ef1b14;--panel:#141414;--border:#292929;--muted:#8f8f8f}
.brand{display:flex;align-items:center;gap:12px;margin:6px 0 18px}.brand-logo{width:48px;height:48px;border-radius:16px;background:linear-gradient(145deg,#ef1b14,#8f0905);display:flex;align-items:center;justify-content:center;font-size:26px;box-shadow:0 10px 28px rgba(239,27,20,.28)}.brand-title{font-size:22px;font-weight:900}.brand-sub{font-size:12px;color:var(--muted)}
.hero{background:radial-gradient(circle at 85% 20%,rgba(239,27,20,.22),transparent 38%),linear-gradient(145deg,#1b1b1b,#0d0d0d);border:1px solid #303030;border-radius:24px;padding:20px;margin-bottom:15px;box-shadow:0 18px 40px rgba(0,0,0,.35)}.hero-kicker{font-size:11px;font-weight:800;letter-spacing:.12em;color:#ff4a43}.hero h2{font-size:27px;margin:7px 0 4px}.hero p{color:#aaa;margin:0;font-size:13px}
.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:12px 0 18px}.metric-card{background:#121212;border:1px solid var(--border);border-radius:18px;padding:13px 10px}.metric-label{font-size:10px;color:#929292}.metric-value{font-size:22px;font-weight:900;margin-top:4px}.metric-value.red{color:#ff3b34}
.section-title{font-size:16px;font-weight:850;margin:20px 0 9px}.stock-card{display:flex;justify-content:space-between;align-items:center;background:#121212;border:1px solid #282828;border-radius:18px;padding:13px 14px;margin:8px 0}.stock-left{font-size:14px;font-weight:700}.stock-right{text-align:right;font-size:18px;font-weight:900}.stock-unit{font-size:10px;color:#8a8a8a;font-weight:600}.pill{display:inline-block;font-size:10px;padding:4px 7px;border-radius:999px;background:#28100f;color:#ff625c;border:1px solid #4a1715;margin-top:4px}
.stButton>button{width:100%;border-radius:15px;min-height:46px;background:#171717;color:#fff;border:1px solid #333;font-weight:800}.stButton>button[kind='primary']{background:linear-gradient(135deg,#ef1b14,#b50c07);border:0;box-shadow:0 8px 20px rgba(239,27,20,.2)}
.stTextInput input,.stNumberInput input,.stDateInput input{background:#101010!important;color:#fff!important;border:1px solid #333!important;border-radius:14px!important}.stFileUploader{background:#111;border:1px solid #292929;border-radius:18px;padding:8px}
[data-testid='stDataFrame']{border:1px solid #292929;border-radius:18px;overflow:hidden}.stAlert{border-radius:16px}
div[role='radiogroup']{position:fixed;bottom:10px;left:50%;transform:translateX(-50%);z-index:9999;background:rgba(17,17,17,.96);backdrop-filter:blur(18px);border:1px solid #303030;border-radius:22px;padding:7px 9px;width:min(94vw,500px);display:flex!important;justify-content:space-between;box-shadow:0 14px 40px rgba(0,0,0,.5)}div[role='radiogroup'] label{padding:7px 5px!important;border-radius:14px;flex:1;justify-content:center}div[role='radiogroup'] label:has(input:checked){background:#26100f}div[role='radiogroup'] p{font-size:11px!important;white-space:nowrap}div[role='radiogroup'] [data-testid='stMarkdownContainer']{text-align:center}div[role='radiogroup'] div[data-testid='stWidgetLabel']{display:none}
@media(max-width:420px){.block-container{padding-left:.75rem;padding-right:.75rem}.metric-value{font-size:19px}.brand-title{font-size:20px}}
</style>''',unsafe_allow_html=True)

components.html("""<script>(function(){const d=window.parent.document,h=d.head;function m(n,c){let x=h.querySelector('meta[name="'+n+'"]');if(!x){x=d.createElement('meta');x.name=n;h.appendChild(x)}x.content=c}m('apple-mobile-web-app-capable','yes');m('apple-mobile-web-app-status-bar-style','black-translucent');m('apple-mobile-web-app-title','Döner Stok');m('theme-color','#070707');d.title='Berlin Döner Stok';})();</script>""",height=0)

try: APP_PIN=str(st.secrets['APP_PIN'])
except Exception:
    st.error('🔒 PIN ayarı eksik. Streamlit Secrets içine APP_PIN ekle.'); st.stop()
if 'pin_ok' not in st.session_state: st.session_state.pin_ok=False
if not st.session_state.pin_ok:
    st.markdown("<div style='height:8vh'></div><div style='display:flex;justify-content:center'><div class='brand-logo' style='width:84px;height:84px;font-size:44px;border-radius:26px'>🥙</div></div><div style='text-align:center;font-size:30px;font-weight:950;margin-top:16px'>BERLIN <span style='color:#ef1b14'>DÖNER</span></div><div style='text-align:center;color:#888;font-size:12px;letter-spacing:.22em;margin:4px 0 25px'>STOK TAKİP</div>",unsafe_allow_html=True)
    pin=st.text_input('PIN',type='password',max_chars=4,placeholder='••••',label_visibility='collapsed')
    if st.button('Giriş Yap',type='primary'):
        if hmac.compare_digest(pin,APP_PIN): st.session_state.pin_ok=True; st.rerun()
        else: st.error('PIN yanlış.')
    st.stop()

db=con()
p=pd.read_sql_query('SELECT product,SUM(qty) qty,MAX(unit) unit FROM purchases GROUP BY product ORDER BY product',db)
s=pd.read_sql_query('SELECT product,SUM(qty) qty FROM sales GROUP BY product ORDER BY product',db)

h1,h2=st.columns([5,1])
with h1: st.markdown("<div class='brand'><div class='brand-logo'>🥙</div><div><div class='brand-title'>Berlin Döner</div><div class='brand-sub'>Stok Takip • Yönetim Paneli</div></div></div>",unsafe_allow_html=True)
with h2:
    if st.button('⏻',help='Çıkış'): st.session_state.pin_ok=False; st.rerun()

nav=st.radio('Menü',['🏠 Ana','📄 Fatura','🧾 Satış','📅 Haftalar','🗃️ Veriler','⚙️ Aktar'],horizontal=True,label_visibility='collapsed')

if nav=='🏠 Ana':
    st.markdown("<div class='hero'><div class='hero-kicker'>CANLI STOK PANELİ</div><h2>Stok sende,<br>kontrol sende.</h2><p>Alış, satış ve farkları tek ekranda gör.</p></div>",unsafe_allow_html=True)
    buy=float(p.qty.sum()) if not p.empty else 0; sell=float(s.qty.sum()) if not s.empty else 0
    st.markdown(f"<div class='metric-grid'><div class='metric-card'><div class='metric-label'>ALINAN</div><div class='metric-value'>{buy:,.0f}</div></div><div class='metric-card'><div class='metric-label'>SATILAN</div><div class='metric-value'>{sell:,.0f}</div></div><div class='metric-card'><div class='metric-label'>FARK</div><div class='metric-value red'>{buy-sell:,.0f}</div></div></div>",unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📦 Toplam Alınan Malzemeler</div>",unsafe_allow_html=True)
    if p.empty: st.info('Henüz alış kaydı yok.')
    else:
        for _,r in p.iterrows():
            q=int(r.qty) if float(r.qty).is_integer() else round(float(r.qty),2)
            st.markdown(f"<div class='stock-card'><div><div class='stock-left'>{r.product}</div><span class='pill'>ALINAN</span></div><div class='stock-right'>{q}<div class='stock-unit'>{r.unit or ''}</div></div></div>",unsafe_allow_html=True)
    st.markdown("<div class='section-title'>🧾 Toplam Satılanlar</div>",unsafe_allow_html=True)
    if s.empty: st.info('Henüz satış kaydı yok.')
    else:
        for _,r in s.iterrows():
            q=int(r.qty) if float(r.qty).is_integer() else round(float(r.qty),2)
            st.markdown(f"<div class='stock-card'><div><div class='stock-left'>{r.product}</div><span class='pill'>SATILAN</span></div><div class='stock-right'>{q}<div class='stock-unit'>adet</div></div></div>",unsafe_allow_html=True)
    st.markdown("<div class='section-title'>⚖️ Alınan / Satılan / Fark</div>",unsafe_allow_html=True)
    pp=p[['product','qty']].rename(columns={'qty':'Alınan'}) if not p.empty else pd.DataFrame(columns=['product','Alınan'])
    ss=s[['product','qty']].rename(columns={'qty':'Satılan'}) if not s.empty else pd.DataFrame(columns=['product','Satılan'])
    d=pd.merge(pp,ss,on='product',how='outer').fillna(0); d['Fark']=d['Alınan']-d['Satılan']; d=d.rename(columns={'product':'Ürün'})
    st.dataframe(d,use_container_width=True,hide_index=True)

elif nav=='📄 Fatura':
    st.markdown("<div class='hero'><div class='hero-kicker'>FATURA</div><h2>Yeni fatura yükle</h2><p>PDF seç, kontrol et ve stoğa kaydet.</p></div>",unsafe_allow_html=True)
    f=st.file_uploader('PDF fatura seç',type=['pdf'])
    if f:
        t=pdf_text(f); inv,dt,sup=meta(t)
        inv=st.text_input('Rechnung No',inv or ''); dt=st.text_input('Tarih YYYY-MM-DD',dt or ''); sup=st.text_input('Tedarikçi',sup)
        rows=parse_lines(t); df=pd.DataFrame(rows if rows else [{'product':'','qty':0.0,'unit':'adet'}]); df=st.data_editor(df,num_rows='dynamic',use_container_width=True)
        if st.button('Faturayı Kaydet',type='primary'):
            try:
                db.execute('INSERT INTO invoices(invoice_no,invoice_date,supplier,file_name) VALUES(?,?,?,?)',(inv,dt,sup,f.name))
                for _,r in df.iterrows():
                    if str(r['product']).strip() and float(r['qty'])!=0: db.execute('INSERT INTO purchases(invoice_no,product,qty,unit) VALUES(?,?,?,?)',(inv,str(r['product']),float(r['qty']),str(r['unit'])))
                db.commit(); st.success('Fatura kaydedildi.')
            except sqlite3.IntegrityError: st.error('Bu Rechnung zaten kayıtlı; tekrar sayılmadı.')

elif nav=='🧾 Satış':
    st.markdown("<div class='hero'><div class='hero-kicker'>SATIŞ</div><h2>Satış kaydı ekle</h2><p>POS satışını hızlıca gir.</p></div>",unsafe_allow_html=True)
    sd=st.date_input('Tarih',date.today()); pr=st.text_input('Ürün'); q=st.number_input('Satılan adet',min_value=0.0,step=1.0)
    if st.button('Satışı Kaydet',type='primary') and pr and q>0:
        db.execute('INSERT INTO sales(sale_date,product,qty) VALUES(?,?,?)',(sd.isoformat(),pr,q)); db.commit(); st.success('Satış kaydedildi.')

elif nav=='📅 Haftalar':
    st.markdown("<div class='hero'><div class='hero-kicker'>FATURA KONTROL</div><h2>Eksik haftalar</h2><p>Botan faturası olmayan haftaları bul.</p></div>",unsafe_allow_html=True)
    start=st.date_input('Başlangıç',date(2026,1,1)); end=st.date_input('Bitiş',date.today()); invs=pd.read_sql_query("SELECT invoice_date FROM invoices WHERE supplier='Botan'",db); present=set()
    for x in invs.get('invoice_date',[]):
        try:
            dd=datetime.strptime(x,'%Y-%m-%d').date()
            if start<=dd<=end: present.add(monday(dd))
        except: pass
    cur=monday(start); rows=[]
    while cur<=monday(end):
        rows.append({'Hafta':f"{cur.strftime('%d.%m.%Y')} – {(cur+timedelta(days=6)).strftime('%d.%m.%Y')}",'Salı':(cur+timedelta(days=1)).strftime('%d.%m.%Y'),'Çarşamba':(cur+timedelta(days=2)).strftime('%d.%m.%Y'),'Durum':'VAR' if cur in present else 'EKSİK'}); cur+=timedelta(days=7)
    w=pd.DataFrame(rows); only=st.checkbox('Sadece eksikler',True); st.dataframe(w[w.Durum=='EKSİK'] if only else w,use_container_width=True,hide_index=True)

elif nav=='🗃️ Veriler':
    st.markdown("<div class='hero'><div class='hero-kicker'>KAYITLAR</div><h2>Tüm veriler</h2><p>Fatura, alış ve satış kayıtları.</p></div>",unsafe_allow_html=True)
    st.markdown('#### Faturalar'); st.dataframe(pd.read_sql_query('SELECT invoice_no Rechnung, invoice_date Tarih, supplier Tedarikçi FROM invoices ORDER BY invoice_date',db),use_container_width=True,hide_index=True)
    st.markdown('#### Alışlar'); st.dataframe(pd.read_sql_query('SELECT invoice_no Rechnung, product Ürün, qty Miktar, unit Birim FROM purchases',db),use_container_width=True,hide_index=True)
    st.markdown('#### Satışlar'); st.dataframe(pd.read_sql_query('SELECT sale_date Tarih, product Ürün, qty Miktar FROM sales',db),use_container_width=True,hide_index=True)

elif nav=='⚙️ Aktar':
    st.markdown("<div class='hero'><div class='hero-kicker'>İLK KURULUM</div><h2>Eski verileri aktar</h2><p>Sohbette hesaplanan eski kayıtları tek seferde ekle.</p></div>",unsafe_allow_html=True)
    done=db.execute("SELECT value FROM settings WHERE key='existing_import_v1'").fetchone()
    if done: st.success('Eski veriler zaten aktarıldı. İkinci kez eklenmez.')
    elif st.button('Eski Verilerimi Aktar',type='primary'):
        if import_existing(db): st.success('Tamamlandı.'); st.rerun()

db.close()
