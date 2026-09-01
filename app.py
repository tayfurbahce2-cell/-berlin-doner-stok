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

st.set_page_config(page_title='Berlin Döner Stok',page_icon='🥙',layout='wide',initial_sidebar_state='collapsed')

st.markdown('''<style>
#MainMenu, footer, header {visibility:hidden;}
.block-container{padding-top:1.2rem;padding-bottom:5rem;max-width:900px}
.stApp{background:linear-gradient(180deg,#070707 0%,#0c0c0c 100%);color:#f5f5f5}
h1,h2,h3{letter-spacing:-.02em}.app-title{font-size:28px;font-weight:800;margin:0}.app-sub{color:#999;font-size:13px;margin-top:-4px}
.hero{border:1px solid #2a2a2a;background:linear-gradient(135deg,#171717,#0d0d0d);border-radius:22px;padding:18px 18px 16px;margin:8px 0 18px;box-shadow:0 12px 30px rgba(0,0,0,.28)}
.hero-badge{display:inline-block;background:#E10600;color:white;border-radius:999px;padding:5px 10px;font-weight:700;font-size:12px}.hero h2{margin:10px 0 4px}.hero p{color:#aaa;margin:0}
.card{border:1px solid #2a2a2a;background:#141414;border-radius:18px;padding:14px 15px;margin:8px 0}.card .name{font-weight:700}.card .num{font-size:23px;font-weight:800;color:#fff}.muted{color:#8e8e8e;font-size:12px}.red{color:#ff2a22}
div[data-testid='stMetric']{background:#141414;border:1px solid #292929;padding:14px;border-radius:18px}div[data-testid='stMetricLabel']{color:#aaa}div[data-testid='stMetricValue']{font-weight:800}
.stButton>button{border-radius:14px;border:1px solid #3a3a3a;background:#171717;color:white;font-weight:700;min-height:44px}.stButton>button[kind='primary']{background:#E10600;border-color:#E10600}.stButton>button:hover{border-color:#E10600;color:white}
.stTextInput input,.stNumberInput input,.stDateInput input{border-radius:14px!important;background:#111!important;color:white!important;border:1px solid #333!important}
div[data-baseweb='tab-list']{gap:8px;overflow-x:auto;scrollbar-width:none}button[data-baseweb='tab']{background:#141414;border:1px solid #292929;border-radius:14px;padding:8px 12px;color:#bbb}button[aria-selected='true']{background:#E10600!important;color:#fff!important;border-color:#E10600!important}
[data-testid='stDataFrame']{border-radius:16px;overflow:hidden;border:1px solid #2a2a2a}
</style>''',unsafe_allow_html=True)

components.html("""<script>(function(){const d=window.parent.document,h=d.head;function m(n,c){let x=h.querySelector('meta[name="'+n+'"]');if(!x){x=d.createElement('meta');x.name=n;h.appendChild(x)}x.content=c}m('apple-mobile-web-app-capable','yes');m('apple-mobile-web-app-status-bar-style','black-translucent');m('apple-mobile-web-app-title','Döner Stok');m('theme-color','#080808');d.title='Berlin Döner Stok';})();</script>""",height=0)

try: APP_PIN=str(st.secrets['APP_PIN'])
except Exception:
    st.error('🔒 PIN ayarı eksik. Streamlit Secrets içine APP_PIN ekle.'); st.stop()
if 'pin_ok' not in st.session_state: st.session_state.pin_ok=False
if not st.session_state.pin_ok:
    st.markdown("<div style='height:8vh'></div><div style='text-align:center;font-size:72px'>🥙</div><div style='text-align:center;font-size:30px;font-weight:900;color:#E10600'>BERLIN DÖNER</div><div style='text-align:center;font-weight:800;letter-spacing:.18em'>STOK TAKİP</div><p style='text-align:center;color:#888;margin-top:20px'>4 haneli PIN kodunu gir</p>",unsafe_allow_html=True)
    a,b,c=st.columns([1,2,1])
    with b:
        pin=st.text_input('PIN',type='password',max_chars=4,placeholder='••••',label_visibility='collapsed')
        if st.button('Giriş Yap',type='primary',use_container_width=True):
            if hmac.compare_digest(pin,APP_PIN): st.session_state.pin_ok=True; st.rerun()
            else: st.error('PIN yanlış.')
    st.stop()

db=con()
head1,head2=st.columns([5,1])
with head1:
    st.markdown("<div class='app-title'>🥙 Berlin Döner</div><div class='app-sub'>Stok Takip • Yönetim Paneli</div>",unsafe_allow_html=True)
with head2:
    if st.button('⏻',help='Çıkış'): st.session_state.pin_ok=False; st.rerun()

p=pd.read_sql_query('SELECT product,SUM(qty) qty,MAX(unit) unit FROM purchases GROUP BY product ORDER BY product',db)
s=pd.read_sql_query('SELECT product,SUM(qty) qty FROM sales GROUP BY product ORDER BY product',db)

tabs=st.tabs(['⌂ Ana Sayfa','📄 Fatura','🧾 Satış','📅 Haftalar','🗃️ Veriler','⚙️ Aktar'])
with tabs[0]:
    st.markdown("<div class='hero'><span class='hero-badge'>CANLI STOK</span><h2>Stok sende, kontrol sende.</h2><p>Alış, satış ve farkları tek ekranda gör.</p></div>",unsafe_allow_html=True)
    total_buy=float(p['qty'].sum()) if not p.empty else 0
    total_sell=float(s['qty'].sum()) if not s.empty else 0
    c1,c2,c3=st.columns(3)
    c1.metric('Toplam Alınan',f'{total_buy:,.0f}')
    c2.metric('Toplam Satılan',f'{total_sell:,.0f}')
    c3.metric('Net Fark',f'{total_buy-total_sell:,.0f}')
    st.markdown('### 📦 Toplam Alınan Malzemeler')
    if p.empty: st.info('Henüz alış kaydı yok.')
    else:
        for _,r in p.iterrows():
            q=int(r.qty) if float(r.qty).is_integer() else round(float(r.qty),2)
            st.markdown(f"<div class='card'><div class='name'>{r.product}</div><div class='num'>{q} <span class='muted'>{r.unit or ''}</span></div></div>",unsafe_allow_html=True)
    st.markdown('### 🧾 Toplam Satılanlar')
    if s.empty: st.info('Henüz satış kaydı yok.')
    else:
        for _,r in s.iterrows():
            q=int(r.qty) if float(r.qty).is_integer() else round(float(r.qty),2)
            st.markdown(f"<div class='card'><div class='name'>{r.product}</div><div class='num'>{q} <span class='muted'>adet</span></div></div>",unsafe_allow_html=True)
    st.markdown('### ⚖️ Alınan / Satılan / Fark')
    pp=p[['product','qty']].rename(columns={'qty':'Alınan'}) if not p.empty else pd.DataFrame(columns=['product','Alınan'])
    ss=s[['product','qty']].rename(columns={'qty':'Satılan'}) if not s.empty else pd.DataFrame(columns=['product','Satılan'])
    d=pd.merge(pp,ss,on='product',how='outer').fillna(0); d['Fark']=d['Alınan']-d['Satılan']; d=d.rename(columns={'product':'Ürün'})
    st.dataframe(d,use_container_width=True,hide_index=True)

with tabs[1]:
    st.markdown('### 📄 Fatura Yükle')
    f=st.file_uploader('PDF fatura seç',type=['pdf'])
    if f:
        t=pdf_text(f); inv,dt,sup=meta(t)
        c1,c2,c3=st.columns(3); inv=c1.text_input('Rechnung No',inv or ''); dt=c2.text_input('Tarih YYYY-MM-DD',dt or ''); sup=c3.text_input('Tedarikçi',sup)
        rows=parse_lines(t); df=pd.DataFrame(rows if rows else [{'product':'','qty':0.0,'unit':'adet'}]); df=st.data_editor(df,num_rows='dynamic',use_container_width=True)
        if st.button('Faturayı Kaydet',type='primary',use_container_width=True):
            try:
                db.execute('INSERT INTO invoices(invoice_no,invoice_date,supplier,file_name) VALUES(?,?,?,?)',(inv,dt,sup,f.name))
                for _,r in df.iterrows():
                    if str(r['product']).strip() and float(r['qty'])!=0: db.execute('INSERT INTO purchases(invoice_no,product,qty,unit) VALUES(?,?,?,?)',(inv,str(r['product']),float(r['qty']),str(r['unit'])))
                db.commit(); st.success('Kaydedildi.')
            except sqlite3.IntegrityError: st.error('Bu Rechnung zaten kayıtlı; tekrar sayılmadı.')

with tabs[2]:
    st.markdown('### 🧾 Satış Gir')
    sd=st.date_input('Tarih',date.today()); pr=st.text_input('Ürün'); q=st.number_input('Satılan adet',min_value=0.0,step=1.0)
    if st.button('Satışı Kaydet',type='primary',use_container_width=True) and pr and q>0:
        db.execute('INSERT INTO sales(sale_date,product,qty) VALUES(?,?,?)',(sd.isoformat(),pr,q)); db.commit(); st.success('Satış kaydedildi.')

with tabs[3]:
    st.markdown('### 📅 Eksik Fatura Haftaları')
    start=st.date_input('Başlangıç',date(2026,1,1),key='a'); end=st.date_input('Bitiş',date.today(),key='b')
    invs=pd.read_sql_query("SELECT invoice_date FROM invoices WHERE supplier='Botan'",db); present=set()
    for x in invs.get('invoice_date',[]):
        try:
            dd=datetime.strptime(x,'%Y-%m-%d').date()
            if start<=dd<=end: present.add(monday(dd))
        except: pass
    cur=monday(start); rows=[]
    while cur<=monday(end):
        rows.append({'Hafta':f"{cur.strftime('%d.%m.%Y')} – {(cur+timedelta(days=6)).strftime('%d.%m.%Y')}",'Salı':(cur+timedelta(days=1)).strftime('%d.%m.%Y'),'Çarşamba':(cur+timedelta(days=2)).strftime('%d.%m.%Y'),'Durum':'VAR' if cur in present else 'EKSİK'}); cur+=timedelta(days=7)
    w=pd.DataFrame(rows); only=st.toggle('Sadece eksikleri göster',True); st.dataframe(w[w.Durum=='EKSİK'] if only else w,use_container_width=True,hide_index=True)

with tabs[4]:
    st.markdown('### 🗃️ Veriler')
    st.caption('Faturalar'); st.dataframe(pd.read_sql_query('SELECT invoice_no Rechnung,invoice_date Tarih,supplier Tedarikçi FROM invoices ORDER BY invoice_date',db),use_container_width=True,hide_index=True)
    st.caption('Alışlar'); st.dataframe(pd.read_sql_query('SELECT invoice_no Rechnung,product Ürün,qty Miktar,unit Birim FROM purchases',db),use_container_width=True,hide_index=True)
    st.caption('Satışlar'); st.dataframe(pd.read_sql_query('SELECT sale_date Tarih,product Ürün,qty Miktar FROM sales',db),use_container_width=True,hide_index=True)

with tabs[5]:
    st.markdown('### ⚙️ Eski Verileri Aktar')
    done=db.execute("SELECT value FROM settings WHERE key='existing_import_v1'").fetchone()
    if done: st.success('Eski veriler zaten aktarıldı.')
    elif st.button('Eski Verilerimi Şimdi Aktar',type='primary',use_container_width=True):
        if import_existing(db): st.success('Tamamlandı.'); st.rerun()

db.close()
