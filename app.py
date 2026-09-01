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

def import_new_invoices_v2(db):
    rows={
      'RE26004854':('2026-01-21',[('Mayonez',100,'kg'),('Gold Ketchup',40,'kg'),('Curry Ketchup',10,'kg'),('Kızartma Yağı',45,'L'),('Beyaz Peynir',16,'kg'),('Chicken Nuggets',3,'kg'),('Currywurst',20,'adet'),('Best Burger',80,'adet'),('Chili',1,'kg'),('Sarımsak Granül',2,'kg'),('Paprika',1.6,'kg'),('Dill',1,'kg'),('Pommes Tuzu',2,'kg'),('Cola 0,33 (Cola+Zero)',120,'adet'),('Uludağ 0,33',24,'adet'),('Fanta 0,33 (tüm çeşitler)',72,'adet'),('Ayran',60,'adet'),('Capri-Sun',80,'adet'),('Kırmızı Soğan',10,'kg'),('Domates',18,'kg')]),
      'RE26018328':('2026-03-11',[('Mayonez',80,'kg'),('Gold Ketchup',30,'kg'),('Curry Ketchup',10,'kg'),('Kızartma Yağı',30,'L'),('Beyaz Peynir',16,'kg'),('Best Burger',80,'adet'),('Chicken Nuggets',4,'kg'),('Currywurst',20,'adet'),('Dill',1,'kg'),('Chili',2,'kg'),('Paprika',2,'kg'),('Sarımsak Granül',1,'kg'),('Lolipop',100,'adet'),('Cola 1L',12,'adet'),('Cola 0,33 (Cola+Zero)',96,'adet'),('Fanta 0,33 (tüm çeşitler)',72,'adet'),('Mezzo Mix 0,33',24,'adet'),('Su 0,50',72,'adet'),('Ayran',60,'adet'),('Hamburger Box Küçük',100,'adet'),('Beyaz Lahana',15,'kg'),('Porsiyon Ketchup',100,'adet'),('Porsiyon Mayonez',100,'adet'),('Burger Dressing',1,'adet'),('Snack Ketchup',1,'adet')]),
      'RE26032904':('2026-04-29',[('Mayonez',80,'kg'),('Gold Ketchup',30,'kg'),('Curry Ketchup',20,'kg'),('Kızartma Yağı',30,'L'),('Best Burger',80,'adet'),('Chicken Nuggets',2,'kg'),('Dill',1,'kg'),('Chili',2,'kg'),('Sarımsak Granül',1,'kg'),('Paprika',0.8,'kg'),('Porsiyon Kabı',250,'adet'),('Porsiyon Mayonez',100,'adet'),('Cola 1L',24,'adet'),('Fanta 1L',12,'adet'),('Snack Box',125,'adet'),('Cola 0,33 (Cola+Zero)',72,'adet'),('Fanta 0,33 (tüm çeşitler)',72,'adet'),('Uludağ 0,33',48,'adet'),('Ayran',40,'adet'),('Capri-Sun',40,'adet'),('Su 0,50',48,'adet'),('Lolipop',100,'adet'),('Snack Ketchup',1,'adet'),('Burger Dressing',2,'adet')]),
      'RE26035275':('2026-05-06',[('Mayonez',80,'kg'),('Curry Ketchup',20,'kg'),('Gold Ketchup',20,'kg'),('Beyaz Peynir',16,'kg'),('Kızartma Yağı',30,'L'),('Snack Ketchup',1,'adet'),('Burger Dressing',1,'adet'),('Üçgen Yufka',400,'adet'),('Chicken Nuggets',3,'kg'),('Best Burger',80,'adet'),('Currywurst',10,'adet'),('Paprika',0.8,'kg'),('Sarımsak Granül',1,'kg'),('Chili',2,'kg'),('Pommes Tuzu',2,'kg'),('Dill',1,'kg'),('Cola 0,33 (Cola+Zero)',72,'adet'),('Uludağ 0,33',48,'adet'),('Fanta 0,33 (tüm çeşitler)',72,'adet'),('Mezzo Mix 0,33',24,'adet'),('Su 0,50',48,'adet'),('Kırmızı Soğan',10,'kg'),('Ayran',40,'adet'),('Capri-Sun',40,'adet'),('Beyaz Lahana',15,'kg')]),
      'RE26037598':('2026-05-13',[('Mayonez',90,'kg'),('Gold Ketchup',40,'kg'),('Curry Ketchup',10,'kg'),('Kızartma Yağı',30,'L'),('Snack Ketchup',1,'adet'),('Burger Dressing',1,'adet'),('Best Burger',80,'adet'),('Chicken Nuggets',3,'kg'),('Currywurst',10,'adet'),('Sarımsak Granül',1,'kg'),('Paprika',0.8,'kg'),('Chili',2,'kg'),('Kağıt Havlu',5000,'adet'),('Cola 1L',12,'adet'),('Mezzo Mix 1L',12,'adet'),('Fanta 1L',12,'adet'),('Cola 0,33 (Cola+Zero)',120,'adet'),('Fanta 0,33 (tüm çeşitler)',24,'adet'),('Uludağ 0,33',24,'adet'),('Mezzo Mix 0,33',24,'adet'),('Su 0,50',48,'adet'),('Capri-Sun',40,'adet'),('Beyaz Lahana',15,'kg'),('Ayran',60,'adet')]),
      'RE26039743':('2026-05-20',[('Mayonez',80,'kg'),('Gold Ketchup',40,'kg'),('Curry Ketchup',20,'kg'),('Kızartma Yağı',30,'L'),('Beyaz Peynir',16,'kg'),('Burger Dressing',2,'adet'),('Snack Ketchup',2,'adet'),('Best Burger',80,'adet'),('Chicken Nuggets',2,'kg'),('Currywurst',20,'adet'),('Chili',2,'kg'),('Sarımsak Granül',2,'kg'),('Paprika',0.8,'kg'),('Dill',1,'kg'),('Bardak 0,2L',100,'adet'),('Hamburger Box Maxi',125,'adet'),('Porsiyon Mayonez',100,'adet'),('Cola 1L',12,'adet'),('Sprite 1L',12,'adet'),('Cola 0,33 (Cola+Zero)',72,'adet'),('Uludağ 0,33',24,'adet'),('Mezzo Mix 0,33',24,'adet'),('Fanta 0,33 (tüm çeşitler)',48,'adet'),('Ayran',60,'adet'),('Su 0,50',48,'adet'),('Capri-Sun',80,'adet'),('Beyaz Lahana',15,'kg'),('Lolipop',100,'adet')]),
      'RE26042012':('2026-05-27',[('Mayonez',100,'kg'),('Gold Ketchup',30,'kg'),('Curry Ketchup',10,'kg'),('Kızartma Yağı',15,'L'),('Burger Dressing',2,'adet'),('Snack Ketchup',1,'adet'),('Porsiyon Ketchup',100,'adet'),('Chicken Nuggets',2,'kg'),('Currywurst',10,'adet'),('Best Burger',80,'adet'),('Paprika',1.6,'kg'),('Sarımsak Granül',1,'kg'),('Chili',2,'kg'),('Pommes Tuzu',2,'kg'),('Hamburger Box Küçük',100,'adet'),('Hamburger Box Maxi',125,'adet'),('Snack Box',125,'adet'),('Salata Kabı',100,'adet'),('Cola 1L',12,'adet'),('Cola 0,33 (Cola+Zero)',96,'adet'),('Uludağ 0,33',48,'adet'),('Fanta 0,33 (tüm çeşitler)',48,'adet'),('Su 0,50',48,'adet'),('Ayran',40,'adet'),('Capri-Sun',80,'adet')]),
      'RE26044428':('2026-06-03',[('Mayonez',80,'kg'),('Gold Ketchup',30,'kg'),('Curry Ketchup',20,'kg'),('Kızartma Yağı',30,'L'),('Beyaz Peynir',16,'kg'),('Chicken Nuggets',4,'kg'),('Best Burger',80,'adet'),('Snack Ketchup',1,'adet'),('Burger Dressing',1,'adet'),('Dill',1,'kg'),('Sarımsak Granül',1,'kg'),('Chili',2,'kg'),('Porsiyon Kabı',500,'adet'),('Cola 1L',12,'adet'),('Mezzo Mix 1L',12,'adet'),('Cola 0,33 (Cola+Zero)',120,'adet'),('Fanta 0,33 (tüm çeşitler)',48,'adet'),('Uludağ 0,33',24,'adet'),('Mezzo Mix 0,33',24,'adet'),('Su 0,50',24,'adet'),('Ayran',60,'adet'),('Capri-Sun',40,'adet'),('Beyaz Lahana',15,'kg'),('Paprika',0.8,'kg'),('Taze Patates',30,'kg')]),
      'RE26046623':('2026-06-10',[('Mayonez',70,'kg'),('Gold Ketchup',40,'kg'),('Curry Ketchup',20,'kg'),('Kızartma Yağı',15,'L'),('Üçgen Yufka',400,'adet'),('Snack Ketchup',1,'adet'),('Burger Dressing',1,'adet'),('Chicken Nuggets',3,'kg'),('Currywurst',20,'adet'),('Çatal',1000,'adet'),('Paprika',0.8,'kg'),('Sarımsak Granül',1,'kg'),('Chili',1,'kg'),('Porsiyon Mayonez',100,'adet'),('Porsiyon Ketchup',100,'adet'),('Cola 1L',12,'adet'),('Sprite 1L',12,'adet'),('Cola 0,33 (Cola+Zero)',96,'adet'),('Fanta 0,33 (tüm çeşitler)',96,'adet'),('Uludağ 0,33',24,'adet'),('Su 0,50',48,'adet'),('Ayran',60,'adet'),('Capri-Sun',40,'adet'),('Beyaz Lahana',15,'kg'),('Hamburger Box Küçük',100,'adet')]),
      'RE26048801':('2026-06-17',[('Mayonez',60,'kg'),('Pommes Tuzu',2,'kg'),('Capri-Sun',40,'adet'),('Beyaz Lahana',15,'kg'),('Cola 1L',12,'adet'),('Su 0,50',48,'adet'),('Ayran',40,'adet'),('Fanta 0,33 (tüm çeşitler)',120,'adet'),('Cola 0,33 (Cola+Zero)',96,'adet'),('Mezzo Mix 0,33',24,'adet'),('Gold Ketchup',30,'kg'),('Dill',1,'kg'),('Sprite 1L',12,'adet'),('Paprika',0.8,'kg'),('Sarımsak Granül',1,'kg'),('Chili',2,'kg'),('Beyaz Peynir',16,'kg'),('Currywurst',10,'adet'),('Chicken Nuggets',3,'kg'),('Best Burger',80,'adet'),('Curry Ketchup',10,'kg'),('Burger Dressing',1,'adet'),('Kızartma Yağı',30,'L'),('Snack Ketchup',2,'adet')]),
      'RE26056188':('2026-07-08',[('Curry Ketchup',20,'kg'),('Paprika',0.8,'kg'),('Mezzo Mix 0,33',24,'adet'),('Hamburger Box Küçük',100,'adet'),('Hamburger Box Maxi',125,'adet'),('Snack Box',125,'adet'),('Ayran',60,'adet'),('Capri-Sun',40,'adet'),('Su 0,50',72,'adet'),('Fanta 0,33 (tüm çeşitler)',120,'adet'),('Cola 0,33 (Cola+Zero)',120,'adet'),('Uludağ 0,33',48,'adet'),('Gold Ketchup',30,'kg'),('Sarımsak Granül',1,'kg'),('Cola 1L',24,'adet'),('Best Burger',80,'adet'),('Pommes Tuzu',2,'kg'),('Chili',1,'kg'),('Currywurst',10,'adet'),('Mayonez',80,'kg'),('Kızartma Yağı',15,'L'),('Beyaz Peynir',16,'kg'),('Chicken Nuggets',5,'kg'),('Porsiyon Mayonez',100,'adet'),('Burger Dressing',1,'adet'),('Porsiyon Ketchup',100,'adet'),('Snack Ketchup',2,'adet'),('Lolipop',100,'adet')])
    }
    added=0
    for no,(dt,items) in rows.items():
        if db.execute('SELECT 1 FROM invoices WHERE invoice_no=?',(no,)).fetchone(): continue
        db.execute('INSERT INTO invoices(invoice_no,invoice_date,supplier,file_name) VALUES(?,?,?,?)',(no,dt,'Botan','Sohbetten yeni fatura'))
        for product,qty,unit in items: db.execute('INSERT INTO purchases(invoice_no,product,qty,unit) VALUES(?,?,?,?)',(no,product,qty,unit))
        added+=1
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('new_invoices_v2','1')"); db.commit(); return added

st.set_page_config(page_title='Berlin Döner Stok',page_icon='🥙',layout='centered',initial_sidebar_state='collapsed')
st.markdown('''<style>#MainMenu,footer,header{visibility:hidden}.block-container{padding:1rem 1rem 6.5rem;max-width:520px}.stApp{background:#070707;color:#fff}:root{--red:#ef1b14;--muted:#8f8f8f}.brand{display:flex;align-items:center;gap:12px;margin:6px 0 18px}.brand-logo{width:48px;height:48px;border-radius:16px;background:linear-gradient(145deg,#ef1b14,#8f0905);display:flex;align-items:center;justify-content:center;font-size:26px}.brand-title{font-size:22px;font-weight:900}.brand-sub{font-size:12px;color:var(--muted)}.hero{background:radial-gradient(circle at 85% 20%,rgba(239,27,20,.22),transparent 38%),linear-gradient(145deg,#1b1b1b,#0d0d0d);border:1px solid #303030;border-radius:24px;padding:20px;margin-bottom:15px}.hero-kicker{font-size:11px;font-weight:800;letter-spacing:.12em;color:#ff4a43}.hero h2{font-size:27px;margin:7px 0 4px}.hero p{color:#aaa;margin:0;font-size:13px}.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:12px 0 18px}.metric-card{background:#121212;border:1px solid #292929;border-radius:18px;padding:13px 10px}.metric-label{font-size:10px;color:#929292}.metric-value{font-size:22px;font-weight:900;margin-top:4px}.metric-value.red{color:#ff3b34}.section-title{font-size:16px;font-weight:850;margin:20px 0 9px}.stock-card{display:flex;justify-content:space-between;align-items:center;background:#121212;border:1px solid #282828;border-radius:18px;padding:13px 14px;margin:8px 0}.stock-left{font-size:14px;font-weight:700}.stock-right{text-align:right;font-size:18px;font-weight:900}.stock-unit{font-size:10px;color:#8a8a8a;font-weight:600}.stButton>button{width:100%;border-radius:15px;min-height:46px;background:#171717;color:#fff;border:1px solid #333;font-weight:800}.stButton>button[kind=primary]{background:linear-gradient(135deg,#ef1b14,#b50c07);border:0}.stTextInput input,.stNumberInput input,.stDateInput input{background:#101010!important;color:#fff!important;border:1px solid #333!important;border-radius:14px!important}[data-testid=stDataFrame]{border:1px solid #292929;border-radius:18px;overflow:hidden}div[role=radiogroup]{position:fixed;bottom:10px;left:50%;transform:translateX(-50%);z-index:9999;background:rgba(17,17,17,.96);border:1px solid #303030;border-radius:22px;padding:7px 9px;width:min(94vw,500px);display:flex!important;justify-content:space-between}div[role=radiogroup] label{padding:7px 5px!important;border-radius:14px;flex:1;justify-content:center}div[role=radiogroup] label:has(input:checked){background:#26100f}div[role=radiogroup] p{font-size:11px!important;white-space:nowrap}</style>''',unsafe_allow_html=True)
components.html("""<script>(function(){const d=window.parent.document,h=d.head;function m(n,c){let x=h.querySelector('meta[name="'+n+'"]');if(!x){x=d.createElement('meta');x.name=n;h.appendChild(x)}x.content=c}m('apple-mobile-web-app-capable','yes');m('apple-mobile-web-app-status-bar-style','black-translucent');m('apple-mobile-web-app-title','Döner Stok');m('theme-color','#070707');d.title='Berlin Döner Stok';})();</script>""",height=0)
try: APP_PIN=str(st.secrets['APP_PIN'])
except Exception: st.error('🔒 PIN ayarı eksik. Streamlit Secrets içine APP_PIN ekle.'); st.stop()
if 'pin_ok' not in st.session_state: st.session_state.pin_ok=False
if not st.session_state.pin_ok:
    st.markdown("<div style='height:8vh'></div><div style='text-align:center;font-size:72px'>🥙</div><div style='text-align:center;font-size:30px;font-weight:900'>BERLIN <span style='color:#ef1b14'>DÖNER</span></div><div style='text-align:center;color:#888;font-size:12px;letter-spacing:.22em;margin:4px 0 25px'>STOK TAKİP</div>",unsafe_allow_html=True)
    pin=st.text_input('PIN',type='password',max_chars=4,placeholder='••••',label_visibility='collapsed')
    if st.button('Giriş Yap',type='primary'):
        if hmac.compare_digest(pin,APP_PIN): st.session_state.pin_ok=True; st.rerun()
        else: st.error('PIN yanlış.')
    st.stop()

db=con(); import_new_invoices_v2(db)
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
            st.markdown(f"<div class='stock-card'><div class='stock-left'>{r['product']}</div><div class='stock-right'>{q}<div class='stock-unit'>{r['unit'] or ''}</div></div></div>",unsafe_allow_html=True)
    st.markdown("<div class='section-title'>🧾 Toplam Satılanlar</div>",unsafe_allow_html=True)
    if not s.empty:
        for _,r in s.iterrows():
            q=int(r.qty) if float(r.qty).is_integer() else round(float(r.qty),2)
            st.markdown(f"<div class='stock-card'><div class='stock-left'>{r['product']}</div><div class='stock-right'>{q}<div class='stock-unit'>adet</div></div></div>",unsafe_allow_html=True)
    pp=p[['product','qty']].rename(columns={'qty':'Alınan'}) if not p.empty else pd.DataFrame(columns=['product','Alınan']); ss=s[['product','qty']].rename(columns={'qty':'Satılan'}) if not s.empty else pd.DataFrame(columns=['product','Satılan'])
    d=pd.merge(pp,ss,on='product',how='outer').fillna(0); d['Fark']=d['Alınan']-d['Satılan']; d=d.rename(columns={'product':'Ürün'})
    st.markdown("<div class='section-title'>⚖️ Alınan / Satılan / Fark</div>",unsafe_allow_html=True); st.dataframe(d,use_container_width=True,hide_index=True)
elif nav=='📄 Fatura':
    st.subheader('📄 Fatura Yükle'); f=st.file_uploader('PDF fatura seç',type=['pdf'])
    if f:
        t=pdf_text(f); inv,dt,sup=meta(t); inv=st.text_input('Rechnung No',inv or ''); dt=st.text_input('Tarih YYYY-MM-DD',dt or ''); sup=st.text_input('Tedarikçi',sup)
        rows=parse_lines(t); df=pd.DataFrame(rows if rows else [{'product':'','qty':0.0,'unit':'adet'}]); df=st.data_editor(df,num_rows='dynamic',use_container_width=True)
        if st.button('Faturayı kaydet',type='primary'):
            try:
                db.execute('INSERT INTO invoices(invoice_no,invoice_date,supplier,file_name) VALUES(?,?,?,?)',(inv,dt,sup,f.name))
                for _,r in df.iterrows():
                    if str(r['product']).strip() and float(r['qty'])!=0: db.execute('INSERT INTO purchases(invoice_no,product,qty,unit) VALUES(?,?,?,?)',(inv,str(r['product']),float(r['qty']),str(r['unit'])))
                db.commit(); st.success('Kaydedildi.'); st.rerun()
            except sqlite3.IntegrityError: st.error('Bu Rechnung zaten kayıtlı; tekrar sayılmadı.')
elif nav=='🧾 Satış':
    st.subheader('🧾 Satış Gir'); sd=st.date_input('Tarih',date.today()); pr=st.text_input('Ürün'); q=st.number_input('Satılan adet',min_value=0.0,step=1.0)
    if st.button('Satışı kaydet',type='primary') and pr and q>0: db.execute('INSERT INTO sales(sale_date,product,qty) VALUES(?,?,?)',(sd.isoformat(),pr,q)); db.commit(); st.success('Satış kaydedildi.'); st.rerun()
elif nav=='📅 Haftalar':
    st.subheader('📅 Eksik Botan Haftaları'); start=st.date_input('Başlangıç',date(2026,1,1),key='a'); end=st.date_input('Bitiş',date.today(),key='b'); invs=pd.read_sql_query("SELECT invoice_date FROM invoices WHERE supplier='Botan'",db); present=set()
    for x in invs.get('invoice_date',[]):
        try:
            dd=datetime.strptime(x,'%Y-%m-%d').date()
            if start<=dd<=end: present.add(monday(dd))
        except: pass
    cur=monday(start); rows=[]
    while cur<=monday(end): rows.append({'Hafta':f"{cur.strftime('%d.%m.%Y')} – {(cur+timedelta(days=6)).strftime('%d.%m.%Y')}",'Salı':(cur+timedelta(days=1)).strftime('%d.%m.%Y'),'Çarşamba':(cur+timedelta(days=2)).strftime('%d.%m.%Y'),'Durum':'VAR' if cur in present else 'EKSİK'}); cur+=timedelta(days=7)
    w=pd.DataFrame(rows); only=st.checkbox('Sadece eksikler',True); st.dataframe(w[w.Durum=='EKSİK'] if only else w,use_container_width=True,hide_index=True)
elif nav=='🗃️ Veriler':
    st.subheader('Faturalar'); st.dataframe(pd.read_sql_query('SELECT invoice_no Rechnung, invoice_date Tarih, supplier Tedarikçi FROM invoices ORDER BY invoice_date',db),use_container_width=True,hide_index=True)
    st.subheader('Alışlar'); st.dataframe(pd.read_sql_query('SELECT invoice_no Rechnung, product Ürün, qty Miktar, unit Birim FROM purchases',db),use_container_width=True,hide_index=True)
    st.subheader('Satışlar'); st.dataframe(pd.read_sql_query('SELECT sale_date Tarih, product Ürün, qty Miktar FROM sales',db),use_container_width=True,hide_index=True)
elif nav=='⚙️ Aktar':
    st.subheader('Eski Verileri Aktar'); done=db.execute("SELECT value FROM settings WHERE key='existing_import_v1'").fetchone()
    if done: st.success('Eski veriler zaten aktarıldı.')
    elif st.button('Eski verilerimi şimdi aktar',type='primary'):
        if import_existing(db): st.success('Tamamlandı.'); st.rerun()
    st.info('Yeni yüklediğin 11 Botan faturası otomatik eklendi. Aynı Rechnung numarası ikinci kez sayılmaz.')
db.close()