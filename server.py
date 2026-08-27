#!/usr/bin/env python3
import os, json, io, urllib.request, urllib.parse, time, secrets, re
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parent

def load_env_file():
    env=ROOT/'.env'
    if not env.exists(): return
    for raw in env.read_text(encoding='utf-8').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,v=line.split('=',1); k=k.strip(); v=v.strip().strip('"').strip("'")
        if k and k not in os.environ: os.environ[k]=v
load_env_file()
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
if Path(FONT).exists():
    pdfmetrics.registerFont(TTFont('DV',FONT)); pdfmetrics.registerFont(TTFont('DVB',FONTB)); BASEFONT='DV'; BOLD='DVB'
else: BASEFONT='Helvetica'; BOLD='Helvetica-Bold'
TOKEN=os.environ.get('TELEGRAM_BOT_TOKEN','').strip(); CHAT_ID=os.environ.get('TELEGRAM_CHAT_ID','').strip()

def money(n): return f"{round(float(n)):,}".replace(',',' ')+' сум'

def esc(s):
    return str(s if s is not None else '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def tg_request(method, fields=None, files=None):
    if not TOKEN or not CHAT_ID: raise RuntimeError('Telegram не настроен: задайте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID')
    fields=fields or {}
    if not files:
        data=urllib.parse.urlencode(fields).encode()
        req=urllib.request.Request(f'https://api.telegram.org/bot{TOKEN}/{method}',data=data,method='POST')
    else:
        boundary='----SarmatBoundary'+secrets.token_hex(8); chunks=[]
        for k,v in fields.items(): chunks += [f'--{boundary}\r\n'.encode(), f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode(), str(v).encode(), b'\r\n']
        for name,(filename,content,ctype) in files.items():
            chunks += [f'--{boundary}\r\n'.encode(), f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(), f'Content-Type: {ctype}\r\n\r\n'.encode(), content, b'\r\n']
        chunks.append(f'--{boundary}--\r\n'.encode()); data=b''.join(chunks)
        req=urllib.request.Request(f'https://api.telegram.org/bot{TOKEN}/{method}',data=data,method='POST',headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(req,timeout=20) as r: result=json.loads(r.read().decode())
    if not result.get('ok'): raise RuntimeError(result.get('description','Telegram API error'))
    return result

def tg_send(text): return tg_request('sendMessage', {'chat_id':CHAT_ID,'text':text})
def tg_send_pdf(pdf_bytes, filename, caption): return tg_request('sendDocument', {'chat_id':CHAT_ID,'caption':caption}, {'document':(filename,pdf_bytes,'application/pdf')})

def make_pdf(payload):
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=30,leftMargin=30,topMargin=105,bottomMargin=45)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RU',fontName=BASEFONT,fontSize=7.2,leading=9.2,textColor=colors.HexColor('#111111')))
    styles.add(ParagraphStyle(name='RUB',parent=styles['RU'],fontName=BOLD))
    styles.add(ParagraphStyle(name='H',parent=styles['RU'],fontName=BOLD,fontSize=10.5,leading=12.5,textColor=colors.HexColor('#0b2438')))
    styles.add(ParagraphStyle(name='Small',parent=styles['RU'],fontSize=6.7,leading=8.2))
    styles.add(ParagraphStyle(name='CPTitle',fontName=BOLD,fontSize=19,leading=22,textColor=colors.HexColor('#0b2438'),alignment=1))
    styles.add(ParagraphStyle(name='Gold',fontName=BOLD,fontSize=10,leading=12,textColor=colors.HexColor('#c7972e'),alignment=1))
    c=payload.get('customer',{}); oid=payload.get('orderId','SARMAT-ORDER'); order=payload.get('order',[])
    story=[]
    story += [Spacer(1,8), Paragraph('КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ',styles['CPTitle']), Spacer(1,5), Paragraph('Поставка и монтаж металлических и противопожарных дверей.',styles['Gold']), Spacer(1,8)]
    story.append(Paragraph(f'<b>№ {esc(oid)}</b><br/>Дата: {datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y")}',styles['RU']))
    story.append(Spacer(1,8))
    story.append(Paragraph('<b>Уважаемые коллеги!</b><br/>ООО «SARMAT DOORS» предлагает изготовление, поставку и монтаж металлических и противопожарных дверей по представленному перечню. Все позиции изготавливаются индивидуально по размерам и техническим требованиям.',styles['RU']))
    story.append(Spacer(1,7)); story.append(Paragraph('ОСНОВНЫЕ ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ',styles['Gold']))
    bullets=['Полотно двери — холоднокатаная сталь; толщина указывается индивидуально в каждой позиции.','Коробка — холоднокатаная сталь; толщина указывается индивидуально в каждой позиции.','Заполнение противопожарных дверей — каменная вата высокой плотности с учетом требований конструкции и испытаний.','Противопожарные двери комплектуются необходимыми уплотнениями и доводчиками согласно соответствующей позиции.','Для технических дверей класс огнестойкости не применяется. Антипаника не предусматривается.','Противопожарные двери SARMAT DOORS имеют сертификаты пожарной безопасности и протоколы испытаний на соответствующий предел огнестойкости.']
    story.append(Paragraph('<br/>'.join('• '+esc(x) for x in bullets),styles['Small'])); story.append(Spacer(1,7)); story.append(Paragraph('СТОИМОСТЬ',styles['Gold'])); story.append(Spacer(1,4))
    headers=['№','Наименование','Размер, м','Кол-во','Примечание','Цена за 1 шт., сум','Сумма, сум']
    rows=[[Paragraph(esc(h),styles['RUB']) for h in headers]]
    total=0; door_subtotal=0; install_total=0; total_qty=0
    for i,x in enumerate(order,1):
        qty=int(x.get('qty',1)); pos=float(x.get('total',0))*qty; inst_total=float(x.get('inst',0))*qty; total+=pos; door_subtotal += pos-inst_total; install_total += inst_total; total_qty+=qty
        dtype=x.get('doorType','Противопожарная'); cls='—' if dtype=='Техническая' else x.get('cls','—')
        name=f"Дверь {dtype.lower()} SARMAT DOORS" + (f" {cls}" if cls!='—' else '')
        note=(f"Открывание: {x.get('opening','—')}; полотно {x.get('leafMm','—')} мм; коробка {x.get('frameMm','—')} мм; "
              f"фурнитура: {x.get('hwText','—')}; доводчик: {'да' if x.get('closer') else 'нет'}; RAL: {x.get('ralText','—')}; "
              f"монтаж: {'да' if x.get('inst') else 'нет'}")
        if x.get('comment'): note += f"; {x['comment']}"
        unit=pos/qty if qty else 0
        vals=[str(i),name,f"{float(x.get('w',0))/1000:.2f}×{float(x.get('h',0))/1000:.2f}",str(qty),note,money(unit).replace(' сум',''),money(pos).replace(' сум','')]
        rows.append([Paragraph(esc(v),styles['Small']) for v in vals])
    col=[22,105,58,40,205,60,60]
    t=Table(rows,colWidths=col,repeatRows=1)
    t.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#c9cfd3')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8a126')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('ALIGN',(0,1),(0,-1),'CENTER'),('ALIGN',(2,1),(3,-1),'CENTER'),('ALIGN',(5,1),(6,-1),'RIGHT')]))
    story.append(t); story.append(Spacer(1,6))
    story.append(Table([[Paragraph('<b>ИТОГО:</b>',styles['RUB']),Paragraph(f'<b>{money(total)}</b>',styles['RUB'])]],colWidths=[430,120],style=[('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#777777')),('ALIGN',(1,0),(1,0),'RIGHT'),('BACKGROUND',(0,0),(-1,-1),colors.white),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(Spacer(1,8)); story.append(Paragraph('<b>УСЛОВИЯ ПОСТАВКИ И ОПЛАТЫ</b>',styles['H'])); story.append(Spacer(1,3))
    terms=[['Монтаж, доставка и пена','600 000 сум за 1 дверь — отдельная позиция, если включена.'],['Стоимость дверей',money(door_subtotal)],['Общая стоимость с монтажом, доставкой и пеной',money(total)],['Оплата','70% — предоплата; 30% — до поставки товара.'],['Цена','Указанные цены рассчитаны с учетом НДС.'],['Сроки поставки и изготовления','Согласовывается при подписании заказа и утверждении рабочих размеров.'],['Гарантия 1 год','Предоставляется на изготовленные изделия и выполненные монтажные работы согласно договору.']]
    tt=Table([[Paragraph(esc(a),styles['RUB']),Paragraph(esc(b),styles['RU'])] for a,b in terms],colWidths=[170,380])
    tt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#c9cfd3')),('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#f1f1f1')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); story.append(tt); story.append(Spacer(1,15))
    story.append(Paragraph('С уважением,<br/>Директор ООО «SARMAT DOORS»',styles['RU'])); story.append(Spacer(1,2)); story.append(Paragraph('______________________________',styles['RU'])); story.append(Paragraph('Сапаркумов Нурлан Ергешевич',styles['RU']))
    sig=ROOT/'signature_clean.png'; stamp=ROOT/'stamp_clean.png'
    if sig.exists() or stamp.exists():
        imgs=[]
        if sig.exists(): imgs.append(ImageReader(str(sig)))
        if stamp.exists(): imgs.append(ImageReader(str(stamp)))
        if imgs:
            # Images are drawn by the page callback below, so they stay on the final page only.
            pass
    def header_footer(canv, doc):
        canv.saveState(); W,H=A4
        header=ROOT/'header_template.png'
        if header.exists(): canv.drawImage(str(header),0,H-86,width=W,height=70,preserveAspectRatio=False,mask='auto')
        else:
            canv.setFillColor(colors.HexColor('#061a2b')); canv.rect(0,H-70,W,70,fill=1,stroke=0)
            canv.setFillColor(colors.white); canv.setFont(BOLD,15); canv.drawString(42,H-42,'SARMAT DOORS')
        canv.setStrokeColor(colors.HexColor('#d7b25a')); canv.line(36,H-91,W-36,H-91)
        canv.setFillColor(colors.HexColor('#666666')); canv.setFont(BASEFONT,7); canv.drawCentredString(W/2,18,'ООО "SARMAT DOORS"  •  ИНН 313 122 742  •  Р/С 2020 8000 9074 8926 7001  •  МФО 01071')
        if doc.page==1: canv.setFont(BASEFONT,7); canv.drawRightString(W-35,H-103,'')
        # Signature + stamp on final page only; round stamp kept 1:1.
        if doc.page==len(getattr(doc,'_sarmat_pages',[])) if False else False: pass
        canv.restoreState()
    # Build first, then overlay signature/stamp on last page using a second pass.
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)
    raw=buf.getvalue()
    # Add signature/stamp to last page without touching other pages.
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        r=PdfReader(io.BytesIO(raw)); ovbuf=io.BytesIO(); cc=canvas.Canvas(ovbuf,pagesize=A4); W,H=A4
        if sig.exists(): cc.drawImage(str(sig),38,67,width=125,height=75,mask='auto',preserveAspectRatio=True)
        if stamp.exists(): cc.drawImage(str(stamp),145,65,width=70,height=70,mask='auto',preserveAspectRatio=True)
        cc.save(); ov=PdfReader(io.BytesIO(ovbuf.getvalue())); r.pages[-1].merge_page(ov.pages[0]); w=PdfWriter(); [w.add_page(p) for p in r.pages]; out=io.BytesIO(); w.write(out); return out.getvalue()
    except Exception:
        return raw

RATE={}; RATE_WINDOW=60; RATE_MAX=20; MAX_BODY=1024*1024
class Handler(SimpleHTTPRequestHandler):
    def _json(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        ip=self.client_address[0]; now=time.time(); hist=[t for t in RATE.get(ip,[]) if now-t<RATE_WINDOW]
        if len(hist)>=RATE_MAX: return self._json(429,{'ok':False,'error':'Слишком много запросов. Попробуйте позже.'})
        hist.append(now); RATE[ip]=hist
        try: n=int(self.headers.get('Content-Length','0'))
        except: n=0
        if n<1 or n>MAX_BODY: return self._json(413,{'ok':False,'error':'Некорректный размер запроса'})
        body=self.rfile.read(n)
        try: p=json.loads(body.decode())
        except: return self._json(400,{'ok':False,'error':'Некорректный JSON'})
        if self.path=='/api/pdf':
            try:
                b=make_pdf(p); self.send_response(200); self.send_header('Content-Type','application/pdf'); self.send_header('Content-Disposition',f"attachment; filename={p.get('orderId','SARMAT_DOORS')}.pdf"); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
            except Exception as e: self._json(500,{'ok':False,'error':str(e)})
            return
        if self.path=='/api/order':
            try:
                total=sum(float(x['total'])*int(x['qty']) for x in p['order']); qty=sum(int(x['qty']) for x in p['order'])
                lines=[f"🟢 SARMAT DOORS — новая заявка",f"№ {p['orderId']}",f"Клиент: {p['customer'].get('company','')} / {p['customer'].get('person','')}",f"Телефон: {p['customer'].get('phone','')}",f"Дверей: {qty}",f"Позиций: {len(p['order'])}",f"Итого: {money(total)}",'']
                for i,x in enumerate(p['order'],1): lines += [f"Позиция {i}: {x.get('doorType','Противопожарная')} {x.get('cls','—')} {x['w']}×{x['h']} · {x['qty']} шт.",f"Открывание: {x.get('opening','—')} · Сталь: {x.get('leafMm','—')}/{x.get('frameMm','—')} мм · RAL: {x.get('ralText','—')}",f"Фурнитура: {x.get('hwText','—')}",f"Доводчик: {'Да — '+money(400000) if x.get('closer') else 'Нет'}",f"Примечание: {x.get('comment') or '—'}",'']
                pdf=make_pdf(p); tg_send('\n'.join(lines)); tg_send_pdf(pdf,f"{p['orderId']}_SARMAT_DOORS.pdf",f"Коммерческое предложение {p['orderId']} · {qty} дверей · {money(total)}")
                return self._json(200,{'ok':True,'orderId':p['orderId'],'pdfSent':True})
            except Exception: return self._json(502,{'ok':False,'error':'Не удалось отправить заявку в Telegram. Проверьте настройки бота или повторите попытку.'})
        if self.path=='/api/health': return self._json(200,{'ok':True,'telegramConfigured':bool(TOKEN and CHAT_ID),'pdf':True})
        if self.path=='/api/telegram-test':
            try: tg_send('🟢 ТЕСТ TELEGRAM — SARMAT DOORS\nСвязь сайта с рабочей группой проверена.'); return self._json(200,{'ok':True})
            except Exception as e: return self._json(502,{'ok':False,'error':str(e)})
        self._json(404,{'ok':False,'error':'Not found'})
    def log_message(self,format,*args): pass
if __name__=='__main__':
    os.chdir(ROOT); port=int(os.environ.get('PORT','8080')); print(f'SARMAT DOORS B2B READY-15: http://0.0.0.0:{port}'); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
