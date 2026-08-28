"""Vector icon library. Icons are drawn, never rasterised, so they scale
with card size and a new one can be added per client."""
from reportlab.pdfbase import pdfmetrics

INK = (7/255,)*3


def draw_icon(c, cx, cy, size, fn, colour=INK, lw=1.9):
    s = size/24.0
    c.saveState()
    c.translate(cx, cy); c.scale(s, -s); c.translate(-12, -12)
    c.setLineWidth(lw/s); c.setLineCap(1); c.setLineJoin(1)
    c.setStrokeColorRGB(*colour); c.setFillColorRGB(*colour)
    fn(c); c.restoreState()


def poly(c, pts, close=True):
    p = c.beginPath(); p.moveTo(*pts[0])
    for q in pts[1:]: p.lineTo(*q)
    if close: p.close()
    c.drawPath(p)


def ic_user_star(c):
    c.circle(10, 8, 3.4, stroke=1, fill=0)
    p = c.beginPath(); p.moveTo(3.8, 20)
    p.curveTo(3.8, 15.2, 6.6, 13.2, 10, 13.2)
    p.curveTo(12.2, 13.2, 14.0, 14.0, 15.1, 15.4); c.drawPath(p)
    poly(c, [(18.3,15.4),(19.4,17.7),(21.9,18.0),(20.1,19.8),(20.6,22.2),
             (18.3,21.0),(16.0,22.2),(16.5,19.8),(14.7,18.0),(17.2,17.7)])

def ic_home(c):
    poly(c, [(3.5,10.5),(12,3.5),(20.5,10.5),(20.5,20.5),(3.5,20.5)])
    poly(c, [(9.5,20.5),(9.5,14),(14.5,14),(14.5,20.5)], close=False)

def ic_pin(c):
    p = c.beginPath(); p.moveTo(12, 21.5)
    p.curveTo(12, 21.5, 19.5, 15.2, 19.5, 9.8)
    p.curveTo(19.5, 5.6, 16.1, 2.5, 12, 2.5)
    p.curveTo(7.9, 2.5, 4.5, 5.6, 4.5, 9.8)
    p.curveTo(4.5, 15.2, 12, 21.5, 12, 21.5); c.drawPath(p)
    c.circle(12, 9.8, 2.8, stroke=1, fill=0)

def ic_spark(c):
    poly(c, [(11,3),(12.6,8.6),(18.2,10.2),(12.6,11.8),(11,17.4),
             (9.4,11.8),(3.8,10.2),(9.4,8.6)])
    poly(c, [(18.3,15.2),(19.1,17.6),(21.5,18.4),(19.1,19.2),(18.3,21.6),
             (17.5,19.2),(15.1,18.4),(17.5,17.6)])

def ic_calendar(c):
    c.roundRect(3.5, 5.0, 17, 15.5, 2.4, stroke=1, fill=0)
    poly(c, [(3.5,10),(20.5,10)], close=False)
    poly(c, [(8,2.6),(8,6.4)], close=False)
    poly(c, [(16,2.6),(16,6.4)], close=False)
    for x in (8, 12, 16): c.circle(x, 15, 0.9, stroke=0, fill=1)

def ic_card(c):
    c.roundRect(2.8, 5.5, 18.4, 13, 2.2, stroke=1, fill=0)
    poly(c, [(2.8,10),(21.2,10)], close=False)
    poly(c, [(6.4,14.6),(11.2,14.6)], close=False)

def ic_person(c):
    c.circle(12, 8.2, 3.6, stroke=1, fill=0)
    p = c.beginPath(); p.moveTo(4.6, 20.6)
    p.curveTo(4.6, 15.6, 8.0, 13.6, 12, 13.6)
    p.curveTo(16.0, 13.6, 19.4, 15.6, 19.4, 20.6); c.drawPath(p)

def ic_shield(c):
    poly(c, [(12,2.6),(20,5.8),(20,12),(12,21.4),(4,12),(4,5.8)])
    poly(c, [(8.6,12),(11.2,14.6),(15.6,9.6)], close=False)

def ic_check(c):
    c.circle(12, 12, 9.6, stroke=1, fill=0)
    poly(c, [(7.6,12.3),(10.7,15.4),(16.4,8.8)], close=False)

def ic_chart(c):
    poly(c, [(4,4),(4,20),(21,20)], close=False)
    for x, top in ((8.5,14),(13,10),(17.5,6)):
        poly(c, [(x,20),(x,top)], close=False)


def ic_db(c):
    c.ellipse(3.5, 3.0, 20.5, 7.6, stroke=1, fill=0)
    for dy in (0, 5.4, 10.8):
        p = c.beginPath()
        p.moveTo(3.5, 5.3+dy); p.lineTo(3.5, 10.7+dy)
        p.curveTo(3.5, 13.2+dy, 20.5, 13.2+dy, 20.5, 10.7+dy)
        p.lineTo(20.5, 5.3+dy); c.drawPath(p)


def ic_chat(c):
    c.roundRect(2.8, 5.0, 18.4, 13.4, 4.2, stroke=1, fill=0)
    poly(c, [(8.2, 18.4), (9.6, 22.0)], close=False)
    for x in (8.4, 12, 15.6):
        c.circle(x, 11.7, 0.95, stroke=0, fill=1)


def ic_code(c):
    c.roundRect(2.6, 4.4, 18.8, 13.6, 2.2, stroke=1, fill=0)
    poly(c, [(9.4, 8.6), (6.4, 11.2), (9.4, 13.8)], close=False)
    poly(c, [(14.6, 8.6), (17.6, 11.2), (14.6, 13.8)], close=False)
    poly(c, [(9.4, 21.0), (14.6, 21.0)], close=False)
    poly(c, [(12, 18.0), (12, 21.0)], close=False)


def ic_server(c):
    for dy in (0, 8.4):
        c.roundRect(3.2, 4.0+dy, 17.6, 7.0, 1.8, stroke=1, fill=0)
        c.circle(7.2, 7.5+dy, 0.95, stroke=0, fill=1)


def ic_cloud(c):
    p = c.beginPath(); p.moveTo(6.6, 18.0)
    p.curveTo(3.6, 18.0, 2.4, 15.4, 3.6, 13.2)
    p.curveTo(4.4, 11.7, 6.2, 11.2, 7.2, 11.5)
    p.curveTo(7.6, 7.4, 12.4, 5.6, 15.4, 7.8)
    p.curveTo(17.4, 9.2, 17.8, 11.4, 17.2, 12.6)
    p.curveTo(20.6, 12.6, 21.8, 15.6, 20.2, 17.2)
    p.curveTo(19.4, 18.0, 18.4, 18.0, 17.4, 18.0); p.close()
    c.drawPath(p)


def ic_cloud_up(c):
    ic_cloud(c)
    poly(c, [(12, 21.6), (12, 14.4)], close=False)
    poly(c, [(9.4, 16.8), (12, 14.2), (14.6, 16.8)], close=False)


def ic_search(c):
    c.circle(10.4, 10.4, 6.2, stroke=1, fill=0)
    poly(c, [(15.0, 15.0), (20.6, 20.6)], close=False)


def ic_mail(c):
    c.roundRect(2.8, 5.4, 18.4, 13.2, 2.2, stroke=1, fill=0)
    poly(c, [(3.4, 6.4), (12, 13.2), (20.6, 6.4)], close=False)


def ic_mobile(c):
    c.roundRect(6.6, 2.6, 10.8, 18.8, 2.6, stroke=1, fill=0)
    poly(c, [(10.4, 5.6), (13.6, 5.6)], close=False)
    c.circle(12, 18.4, 0.95, stroke=0, fill=1)


def ic_map(c):
    poly(c, [(2.8, 6.0), (8.8, 3.4), (15.2, 6.6), (21.2, 4.0),
             (21.2, 18.0), (15.2, 20.6), (8.8, 17.4), (2.8, 20.0)])
    poly(c, [(8.8, 3.4), (8.8, 17.4)], close=False)
    poly(c, [(15.2, 6.6), (15.2, 20.6)], close=False)
