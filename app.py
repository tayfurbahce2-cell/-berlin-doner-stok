import streamlit as st
import streamlit.components.v1 as components
import sqlite3, re, io
from datetime import date, datetime, timedelta
import pandas as pd
from pypdf import PdfReader

DB="stok.db"

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
    return "\n".join((p.extract_text() or "") for p in r.pages)

def meta(t):
    inv=dt=None; sup="Bilinmiyor"
    for p in [r"Rechnungs[- ]?Nr\.?\s*([A-Z0-9\-]+)",r"Rechnung Nr\.?\s*([A-Z0-9\-]+)"]:
        m=re.search(p,t,re.I)
        if m: inv=m.group(1); break
    m=re.search(r"Rechnungsdatum\s*(\d{2}\.\d{2}\.\d{4})",t,re.I)
    if not m: m=re.search(r"Lieferdatum\s*(\d{2}\.\d{2}\.\d{4})",t,re.I)
    if m: dt=datetime.strptime(m.group(1),"%d.%m.%Y").date().isoformat()
    if "Malis Gastronomiebedarf" in t: sup="Malis"
    elif "Botan" in t or "BOTAN" in t: sup="Botan"
    return inv,dt,sup

def product_name(desc):
    d=desc.lower()
    if "coca cola" in d or "coca-cola" in d:
        if "1 l" in d or "1l" in d or "x1 l" in d: return "Cola 1L"
        return "Cola 0,33 (Cola+Zero)"
    if "fanta" in d:
        if "1 l" in d or "1l" in d: return "Fanta 1L"
        return "Fanta 0,33 (tüm çeşitler)"
    if "mezzo mix" in d:
        if "1 l" in d or "1l" in d: return "Mezzo Mix 1L"
        return "Mezzo Mix 0,33"
    if "uludag" in d: return "Uludağ 0,33"
    if "ayran" in d: return "Ayran"
    if "capri" in d: return "Capri-Sun"
    if "wasser" in d: return "Su 0,50"
    if "sprite" in d and ("1 l" in d or "1l" in d): return "Sprite 1L"
    return desc[:80]

def parse_lines(t):
    out=[]
    for line in t.splitlines():
        s=" ".join(line.split())
        m=re.match(r"^\d+\.\s+\S+\s+(.+?)\s+(\d+,\d+)\s+Stk\b",s,re.I)
        if not m: continue
        desc=m.group(1)
        if "leergut" in desc.lower(): continue
        q=float(m.group(2).replace(",",".")); unit="paket/koli"
        compact=desc.replace(" ","")
        pack=re.search(r"(\d+)x0[,\.]33",compact,re.I)
        if pack: q*=int(pack.group(1)); unit="adet"
        out.append({"product":product_name(desc),"qty":q,"unit":unit})
    return out

def import_existing(db):
    done=db.execute("SELECT value FROM settings WHERE key='existing_import_v1'").fetchone()
    if done: return False
    purchases={
      "Cola 0,33 (Cola+Zero)":1944,"Fanta 0,33 (tüm çeşitler)":1392,"Mezzo Mix 0,33":288,
      "Uludağ 0,33":792,"Su 0,50":840,"Ayran":1320,"Capri-Sun":590,"Cola 1L":312,
      "Fanta 1L":84,"Mezzo Mix 1L":120,"Sprite 1L":96,
      "Mayonez":1460,"Gold Ketchup":600,"Curry Ketchup":310,"Kırmızı Soğan":320,
      "Beyaz Lahana":240,"Domates":48,"Beyaz Peynir":144,"Kızartma Yağı":225,
      "Chicken Nuggets":39,"Currywurst":310,"Best Burger":960,"Üçgen Yufka":1900
    }
    for product,qty in purchases.items():
        unit="adet"
        if product in ["Mayonez","Gold Ketchup","Curry Ketchup","Kırmızı Soğan","Beyaz Lahana","Domates","Beyaz Peynir","Chicken Nuggets"]: unit="kg"
        if product=="Kızartma Yağı": unit="L"
        db.execute("INSERT INTO purchases(invoice_no,product,qty,unit) VALUES(?,?,?,?)",("IMPORT-TOPLAM",product,qty,unit))
    sales={"Cola 0,33 (Cola+Zero)":2710,"Fanta 0,33 (tüm çeşitler)":1278,"Mezzo Mix 0,33":351,
           "Uludağ 0,33":1002,"Su 0,50":371,"Ayran":1647,"Capri-Sun":487,"Cola 1L":154,
           "Mezzo Mix 1L":22,"Uludağ 1L":15}
    for product,qty in sales.items():
        db.execute("INSERT INTO sales(sale_date,product,qty) VALUES(?,?,?)",("2026-08-31",product,qty))
    invoice_dates=[
      ("RE26001344","2026-01-07","Botan"),("RE26003022","2026-01-14","Botan"),("RE26006619","2026-01-28","Botan"),
      ("RE26008549","2026-02-04","Botan"),("RE26010481","2026-02-11","Botan"),("RE26012402","2026-02-18","Botan"),("RE26014193","2026-02-25","Botan"),
      ("RE26016232","2026-03-04","Botan"),("IMPORT-20260318","2026-03-18","Botan"),("RE26022368","2026-03-25","Botan"),
      ("RE26024580","2026-04-01","Botan"),("RE26026509","2026-04-08","Botan"),("RE26028670","2026-04-15","Botan"),("RE26030753","2026-04-22","Botan"),
      ("RE26058585","2026-07-15","Botan"),("IMPORT-20260722","2026-07-22","Botan"),("RE26063334","2026-07-29","Botan"),
      ("RE26065873","2026-08-05","Botan"),("RE26068314","2026-08-12","Botan"),("RE26070839","2026-08-19","Botan"),("IMPORT-20260826","2026-08-26","Botan"),
      ("RE-5983","2026-07-18","Malis")]
    for no,dt,sup in invoice_dates:
        db.execute("INSERT OR IGNORE INTO invoices(invoice_no,invoice_date,supplier,file_name) VALUES(?,?,?,?)",(no,dt,sup,"Sohbetten aktarıldı"))
    db.execute("INSERT INTO settings(key,value) VALUES('existing_import_v1','1')")
    db.commit(); return True

st.set_page_config(page_title="Berlin Döner Stok",page_icon="🥙",layout="wide")
components.html("""
<script>
(function(){
  const d = window.parent.document; const head = d.head;
  function meta(name, content){ let m=head.querySelector('meta[name="'+name+'"]'); if(!m){m=d.createElement('meta');m.name=name;head.appendChild(m);} m.content=content; }
  meta('apple-mobile-web-app-capable','yes'); meta('apple-mobile-web-app-status-bar-style','black-translucent');
  meta('apple-mobile-web-app-title','Döner Stok'); meta('mobile-web-app-capable','yes'); meta('theme-color','#111111');
  let manifest=head.querySelector('link[rel="manifest"]'); if(!manifest){manifest=d.createElement('link');manifest.rel='manifest';head.appendChild(manifest);} manifest.href='/app/static/manifest.json';
  d.title='Berlin Döner Stok';
})();
</script>
""", height=0)

db=con(); st.title("🥙 Berlin Döner – Stok Programı")
st.caption("📱 Safari/Chrome → Paylaş → Ana Ekrana Ekle")
tabs=st.tabs(["📊 Ana Sayfa","⬇️ Eski Verileri Aktar","📄 Fatura Yükle","🧾 Satış Gir","📅 Eksik Haftalar","🗃️ Veriler"])

with tabs[0]:
    p=pd.read_sql_query("SELECT product, SUM(qty) AS qty, MAX(unit) AS unit FROM purchases GROUP BY product ORDER BY product",db)
    s=pd.read_sql_query("SELECT product, SUM(qty) AS qty FROM sales GROUP BY product ORDER BY product",db)
    if p.empty and s.empty:
        st.info("Henüz veri yok. 'Eski Verileri Aktar' bölümüne gir.")
    else:
        st.subheader("📦 Toplam Alınan Malzemeler")
        if p.empty:
            st.write("Henüz alış kaydı yok.")
        else:
            for _,r in p.iterrows():
                q=int(r['qty']) if float(r['qty']).is_integer() else round(float(r['qty']),2)
                st.write(f"**{r['product']}** — {q} {r['unit'] or ''}")

        st.divider()
        st.subheader("🧾 Toplam Satılanlar")
        if s.empty:
            st.write("Henüz satış kaydı yok.")
        else:
            for _,r in s.iterrows():
                q=int(r['qty']) if float(r['qty']).is_integer() else round(float(r['qty']),2)
                st.write(f"**{r['product']}** — {q} adet")

        st.divider()
        st.subheader("⚖️ Alınan / Satılan / Fark")
        pp=p[['product','qty']].rename(columns={'qty':'Alınan'}) if not p.empty else pd.DataFrame(columns=['product','Alınan'])
        ss=s[['product','qty']].rename(columns={'qty':'Satılan'}) if not s.empty else pd.DataFrame(columns=['product','Satılan'])
        d=pd.merge(pp,ss,on='product',how='outer').fillna(0)
        d['Fark']=d['Alınan']-d['Satılan']; d=d.rename(columns={'product':'Ürün'})
        st.dataframe(d,use_container_width=True,hide_index=True)
        st.caption("Fark + ise alış satıştan fazla; - ise POS satışı bilinen alıştan fazla.")

with tabs[1]:
    st.subheader("Bu sohbetteki eski verileri tek seferde aktar")
    st.write("21 Botan faturanın haftaları, Malis'ten 360 Uludağ dahil içecek alış toplamları, temel stok toplamları ve 6 POS içecek raporu eklenir.")
    done=db.execute("SELECT value FROM settings WHERE key='existing_import_v1'").fetchone()
    if done: st.success("Eski veriler zaten aktarıldı. İkinci kez eklenmez.")
    elif st.button("✅ Eski verilerimi şimdi aktar",type="primary",use_container_width=True):
        if import_existing(db): st.success("Tamamlandı."); st.rerun()

with tabs[2]:
    f=st.file_uploader("PDF fatura seç",type=["pdf"])
    if f:
        t=pdf_text(f); inv,dt,sup=meta(t); c1,c2,c3=st.columns(3); inv=c1.text_input("Rechnung No",inv or ""); dt=c2.text_input("Tarih YYYY-MM-DD",dt or ""); sup=c3.text_input("Tedarikçi",sup)
        rows=parse_lines(t); df=pd.DataFrame(rows if rows else [{"product":"","qty":0.0,"unit":"adet"}]); df=st.data_editor(df,num_rows="dynamic",use_container_width=True)
        if st.button("Faturayı kaydet",type="primary"):
            try:
                db.execute("INSERT INTO invoices(invoice_no,invoice_date,supplier,file_name) VALUES(?,?,?,?)",(inv,dt,sup,f.name))
                for _,r in df.iterrows():
                    if str(r["product"]).strip() and float(r["qty"])!=0: db.execute("INSERT INTO purchases(invoice_no,product,qty,unit) VALUES(?,?,?,?)",(inv,str(r["product"]),float(r["qty"]),str(r["unit"])))
                db.commit(); st.success("Kaydedildi.")
            except sqlite3.IntegrityError: st.error("Bu Rechnung zaten kayıtlı; tekrar sayılmadı.")

with tabs[3]:
    sd=st.date_input("Tarih",date.today()); pr=st.text_input("Ürün"); q=st.number_input("Satılan adet",min_value=0.0,step=1.0)
    if st.button("Satışı kaydet") and pr and q>0: db.execute("INSERT INTO sales(sale_date,product,qty) VALUES(?,?,?)",(sd.isoformat(),pr,q)); db.commit(); st.success("Satış kaydedildi.")

with tabs[4]:
    start=st.date_input("Başlangıç",date(2026,1,1),key="a"); end=st.date_input("Bitiş",date.today(),key="b"); invs=pd.read_sql_query("SELECT invoice_date FROM invoices WHERE supplier='Botan'",db); present=set()
    for x in invs.get("invoice_date",[]):
        try:
            d=datetime.strptime(x,"%Y-%m-%d").date()
            if start<=d<=end: present.add(monday(d))
        except: pass
    cur=monday(start); rows=[]
    while cur<=monday(end):
        rows.append({"Hafta":f"{cur.strftime('%d.%m.%Y')} – {(cur+timedelta(days=6)).strftime('%d.%m.%Y')}","Salı":(cur+timedelta(days=1)).strftime("%d.%m.%Y"),"Çarşamba":(cur+timedelta(days=2)).strftime("%d.%m.%Y"),"Durum":"VAR" if cur in present else "EKSİK"}); cur+=timedelta(days=7)
    w=pd.DataFrame(rows); only=st.checkbox("Sadece eksikler",True); st.dataframe(w[w.Durum=="EKSİK"] if only else w,use_container_width=True,hide_index=True)

with tabs[5]:
    st.subheader("Faturalar"); st.dataframe(pd.read_sql_query("SELECT invoice_no Rechnung, invoice_date Tarih, supplier Tedarikçi FROM invoices ORDER BY invoice_date",db),use_container_width=True,hide_index=True)
    st.subheader("Alışlar"); st.dataframe(pd.read_sql_query("SELECT invoice_no Rechnung, product Ürün, qty Miktar, unit Birim FROM purchases",db),use_container_width=True,hide_index=True)
    st.subheader("Satışlar"); st.dataframe(pd.read_sql_query("SELECT sale_date Tarih, product Ürün, qty Miktar FROM sales",db),use_container_width=True,hide_index=True)

db.close()
