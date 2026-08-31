import streamlit as st
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
    c.commit()
    return c

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
    if m: dt=datetime.strptime(m.group(1),"%d.%m.%Y").date().isoformat()
    if "Malis Gastronomiebedarf" in t: sup="Malis"
    elif "Botan" in t or "BOTAN" in t: sup="Botan"
    return inv,dt,sup

def product_name(desc):
    d=desc.lower()
    rules=[("coca-cola zero","Cola Zero 0,33"),("coca-cola","Cola 0,33"),("fanta orange","Fanta Orange 0,33"),("fanta exotic","Fanta Exotic 0,33"),("fanta mango","Fanta Mango 0,33"),("mezzo mix","Mezzo Mix 0,33"),("uludag","Uludağ 0,33"),("ayran","Ayran"),("capri","Capri-Sun"),("wasser","Su 0,50")]
    for k,v in rules:
        if k in d: return v
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
        pack=re.search(r"(\d+)x0[,\.]33",desc.replace(" ",""),re.I)
        if pack: q*=int(pack.group(1)); unit="adet"
        out.append({"product":product_name(desc),"qty":q,"unit":unit})
    return out

st.set_page_config(page_title="Berlin Döner Stok",page_icon="🥙",layout="wide")
db=con(); st.title("🥙 Berlin Döner – Stok Programı")
tabs=st.tabs(["📊 Özet","📄 Fatura Yükle","🧾 Satış Gir","📅 Eksik Haftalar","🗃️ Veriler"])
with tabs[0]:
    p=pd.read_sql_query("SELECT product,SUM(qty) Alınan FROM purchases GROUP BY product",db); s=pd.read_sql_query("SELECT product,SUM(qty) Satılan FROM sales GROUP BY product",db)
    if p.empty and s.empty: st.info("Henüz veri yok.")
    else:
        d=pd.merge(p,s,on="product",how="outer").fillna(0); d["Fark"]=d["Alınan"]-d["Satılan"]; d=d.rename(columns={"product":"Ürün"}); st.dataframe(d,use_container_width=True,hide_index=True)
with tabs[1]:
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
with tabs[2]:
    sd=st.date_input("Tarih",date.today()); pr=st.text_input("Ürün"); q=st.number_input("Satılan adet",min_value=0.0,step=1.0)
    if st.button("Satışı kaydet") and pr and q>0: db.execute("INSERT INTO sales(sale_date,product,qty) VALUES(?,?,?)",(sd.isoformat(),pr,q)); db.commit(); st.success("Satış kaydedildi.")
with tabs[3]:
    start=st.date_input("Başlangıç",date(2026,1,1),key="a"); end=st.date_input("Bitiş",date.today(),key="b"); invs=pd.read_sql_query("SELECT invoice_date FROM invoices",db); present=set()
    for x in invs.get("invoice_date",[]):
        try:
            d=datetime.strptime(x,"%Y-%m-%d").date()
            if start<=d<=end: present.add(monday(d))
        except: pass
    cur=monday(start); rows=[]
    while cur<=monday(end):
        rows.append({"Hafta":f"{cur.strftime('%d.%m.%Y')} – {(cur+timedelta(days=6)).strftime('%d.%m.%Y')}","Salı":(cur+timedelta(days=1)).strftime("%d.%m.%Y"),"Çarşamba":(cur+timedelta(days=2)).strftime("%d.%m.%Y"),"Durum":"VAR" if cur in present else "EKSİK"}); cur+=timedelta(days=7)
    w=pd.DataFrame(rows); only=st.checkbox("Sadece eksikler",True); st.dataframe(w[w.Durum=="EKSİK"] if only else w,use_container_width=True,hide_index=True)
with tabs[4]:
    st.subheader("Faturalar"); st.dataframe(pd.read_sql_query("SELECT invoice_no Rechnung, invoice_date Tarih, supplier Tedarikçi FROM invoices ORDER BY invoice_date",db),use_container_width=True,hide_index=True)
    st.subheader("Alışlar"); st.dataframe(pd.read_sql_query("SELECT invoice_no Rechnung, product Ürün, qty Miktar, unit Birim FROM purchases",db),use_container_width=True,hide_index=True)
    st.subheader("Satışlar"); st.dataframe(pd.read_sql_query("SELECT sale_date Tarih, product Ürün, qty Miktar FROM sales",db),use_container_width=True,hide_index=True)
db.close()
