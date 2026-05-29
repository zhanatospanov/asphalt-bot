"""
Генерация Паспорт-накладной на асфальтобетонную смесь.
2 экземпляра на листе А4.
"""
import os, io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

def _reg():
    try:
        pdfmetrics.registerFont(TTFont("DJ",   os.path.join(FONTS_DIR, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DJ-B", os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")))
    except Exception:
        pass
_reg()

W, H = A4
HALF = H / 2


def _fmt_date(s):
    try:    return datetime.strptime(s, "%Y-%m-%d").strftime("%d.%m.%Y")
    except: return s

def _fmt_w(kg):
    return f"{int(round(kg))}"


def _draw_passport(c, trip, company, buyer, top_y):
    m  = 12 * mm
    rw = W - 2 * m
    lh = 5.5 * mm
    y  = top_y - 6 * mm

    doc_num   = trip.get("doc_number", "")
    trip_date = _fmt_date(trip.get("trip_date", ""))
    trip_time = trip.get("trip_time", "")
    vehicle   = trip.get("vehicle_number", "")
    grade     = trip.get("asphalt_grade", "")
    tare_kg   = trip.get("tare_kg", 0)
    gross_kg  = trip.get("gross_kg", 0)
    net_kg    = trip.get("net_kg", 0)
    temp_c    = trip.get("temperature", 160)
    obj_name  = trip.get("object_name", "")
    s_name    = company.get("name", "")
    s_bin     = company.get("bin", "")
    b_name    = buyer.get("name", "")
    b_bin     = buyer.get("bin", "")

    def txt(x, y_, s, bold=False, size=8, align="left"):
        c.setFont("DJ-B" if bold else "DJ", size)
        s = str(s)
        if align == "center": c.drawCentredString(x, y_, s)
        elif align == "right": c.drawRightString(x, y_, s)
        else: c.drawString(x, y_, s)

    def hline(y_, w=0.5):
        c.setLineWidth(w)
        c.line(m, y_, m + rw, y_)

    def box(x, y_, w, h, gray=None):
        c.setLineWidth(0.5)
        if gray is not None:
            c.setFillGray(gray); c.rect(x, y_, w, h, fill=1, stroke=1); c.setFillGray(0)
        else:
            c.rect(x, y_, w, h, fill=0, stroke=1)

    def ctxt(x, y_, w, h, s, bold=False, size=7.5, align="center", wrap=False):
        s = str(s)
        if wrap:
            style = ParagraphStyle(
                "cell",
                fontName="DJ-B" if bold else "DJ",
                fontSize=size,
                leading=size * 1.3,
                alignment=0,  # left
            )
            p = Paragraph(s, style)
            pw, ph = p.wrap(w - 4*mm, h)
            p.drawOn(c, x + 2*mm, y_ + h/2 - ph/2)
            return
        c.setFont("DJ-B" if bold else "DJ", size)
        ty = y_ + h/2 - size*0.36
        if align == "center":
            c.drawCentredString(x + w/2, ty, s)
        elif align == "right":
            c.drawRightString(x + w - 2*mm, ty, s)
        else:
            c.drawString(x + 2*mm, ty, s)

    # ── Заголовок ────────────────────────────────────────────────────────────
    txt(W/2, y, "ПАСПОРТ-НАКЛАДНАЯ", bold=True, size=11, align="center")
    y -= 5.5*mm
    txt(W/2, y, "на асфальтобетонную смесь", size=8.5, align="center")
    y -= 5*mm
    txt(m, y, f"№  {doc_num}", bold=True, size=9)
    txt(m+rw, y, f"от  {trip_date}", size=8.5, align="right")
    y -= 2*mm; hline(y, w=1.0); y -= 4*mm

    # ── Поставщик / покупатель ────────────────────────────────────────────────
    hw = rw/2 - 3*mm
    txt(m,         y, "Поставщик:", bold=True, size=7.5)
    txt(m+24*mm,   y, s_name, size=8)
    txt(m+hw+6*mm, y, "Покупатель:", bold=True, size=7.5)
    txt(m+hw+30*mm,y, b_name, size=8)
    y -= lh
    txt(m,         y, "БИН:", bold=True, size=7.5)
    txt(m+24*mm,   y, s_bin, size=8)
    txt(m+hw+6*mm, y, "БИН:", bold=True, size=7.5)
    txt(m+hw+30*mm,y, b_bin, size=8)
    y -= lh+2*mm; hline(y); y -= 4*mm

    # ── Инфо-строки ──────────────────────────────────────────────────────────
    def irow(label, value, y_):
        txt(m, y_, label, bold=True, size=7.5)
        txt(m+40*mm, y_, value, size=8)
        c.setLineWidth(0.4)
        c.line(m+39*mm, y_-1.2*mm, m+rw, y_-1.2*mm)
        return y_ - lh - 1*mm

    y = irow("Объект:", obj_name, y)
    y = irow("Номер транспорта:", vehicle, y)
    y = irow("Время выезда:", f"{trip_date}  {trip_time}", y)
    y = irow("Условия отгрузки:", "Самовывоз", y)
    y -= 2*mm

    # ── Таблица ───────────────────────────────────────────────────────────────
    # Ширины фиксированных колонок (однострочные заголовки, достаточно места)
    W1 =  8*mm   # №
    W3 = 20*mm   # Ед. изм.
    W4 = 32*mm   # Тара, кг
    W5 = 36*mm   # Общий вес, кг
    W6 = 32*mm   # Кол-во, кг
    W2 = rw - W1 - W3 - W4 - W5 - W6   # Наименование — остаток

    TH = 7*mm    # высота заголовка
    DR = 9*mm    # высота строки данных
    TR = 6*mm    # высота строки итого

    cols = [
        ("№",               W1, "center"),
        ("Наименование",    W2, "center"),
        ("Ед. изм.",        W3, "center"),
        ("Тара, кг",        W4, "center"),
        ("Общий вес, кг",   W5, "center"),
        ("Кол-во, кг",      W6, "center"),
    ]

    # Заголовок
    xc = m
    for (h, w, a) in cols:
        box(xc, y-TH, w, TH, gray=0.88)
        ctxt(xc, y-TH, w, TH, h, bold=True, size=6.5, align="center")
        xc += w
    y -= TH

    # Данные
    data = [
        ("1",            W1, "center"),
        (grade,          W2, "left"),
        ("кг",           W3, "center"),
        (_fmt_w(tare_kg), W4, "center"),
        (_fmt_w(gross_kg),W5, "center"),
        (_fmt_w(net_kg),  W6, "center"),
    ]
    xc = m
    for (v, w, a) in data:
        box(xc, y-DR, w, DR)
        ctxt(xc, y-DR, w, DR, v, size=7.5, align=a)
        xc += w
    y -= DR

    # Итого
    LW = W1+W2+W3
    itogo = [
        ("ИТОГО:", LW, "right"),
        (_fmt_w(tare_kg),  W4, "center"),
        (_fmt_w(gross_kg), W5, "center"),
        (_fmt_w(net_kg),   W6, "center"),
    ]
    xc = m
    for (v, w, a) in itogo:
        box(xc, y-TR, w, TR, gray=0.93)
        ctxt(xc, y-TR, w, TR, v, bold=True, size=7.5, align=a)
        xc += w
    y -= TR + 4*mm

    # ── Температура ──────────────────────────────────────────────────────────
    txt(m, y, f"Температура смеси при отгрузке:  {temp_c} °C", size=8)
    y -= lh+2*mm; hline(y); y -= 5*mm

    # ── Подписи ──────────────────────────────────────────────────────────────
    sw = rw/2 - 6*mm
    for (label, sx) in [("Весовщик:", m), ("Водитель:", m+sw+12*mm)]:
        txt(sx, y, label, bold=True, size=7.5)
        c.setLineWidth(0.5)
        c.line(sx+22*mm, y-1*mm,  sx+sw, y-1*mm)
        txt(sx+22*mm, y-5*mm, "(подпись)", size=6)
        c.line(sx+22*mm, y-8*mm,  sx+sw, y-8*mm)
        txt(sx+22*mm, y-12*mm, "(Ф.И.О.)", size=6)

    txt(m+rw-20*mm, y-14*mm, "М.П.", size=7, align="center")


def generate_all_docs(trip, company, buyer):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)

    _draw_passport(c, trip, company, buyer, top_y=H - 2*mm)

    c.setLineWidth(0.5); c.setDash([4,3])
    c.line(10*mm, HALF, W-10*mm, HALF)
    c.setDash([])
    c.setFont("DJ", 6)
    c.drawCentredString(W/2, HALF+1.5*mm, "линия отреза")

    _draw_passport(c, trip, company, buyer, top_y=HALF - 2*mm)

    c.save()
    return buf.getvalue()
