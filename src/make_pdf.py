from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from layout import NOTE_CENTERS, PDF, ROW_CENTERS

WIDTH, HEIGHT, SCALE = 612, 792, 3
font_candidates = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]

def font(size, bold):
    for regular, heavy in font_candidates:
        try:
            return ImageFont.truetype(heavy if bold else regular, size * SCALE)
        except OSError:
            pass
    return ImageFont.load_default(size=size * SCALE)


def main():
    image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), "white")
    draw = ImageDraw.Draw(image)

    def text(x, y, value, size=14, bold=False, color="#152839"):
        draw.text((x * SCALE, y * SCALE), value, font=font(size, bold),
                  fill=color, anchor="lm")

    def band(top, bottom, color):
        draw.rectangle((50 * SCALE, top * SCALE, 562 * SCALE, bottom * SCALE), fill=color)

    text(52, 52, "DEMONSTRATION SPECIFICATION   /   DEMO-STEEL-01", 11, True, "#176863")
    text(50, 91, "Steel plate requirements", 29, True)
    text(52, 125, "Table 1. Tensile strength by grade", 15)
    band(163, 205, "#17374b")
    columns = (65, 217, 336, 460)
    for x, label in zip(columns, ("Grade", "Min (MPa)", "Max (MPa)", "Notes")):
        text(x, 184, label, 14, True, "white")
    for i, (y, row) in enumerate(zip(ROW_CENTERS, [
        ("DEMO-355", "470", "630", "A,B"),
        ("DEMO-420", "520", "680", "B"),
        ("DEMO-500", "580", "750", "NONE"),
    ])):
        band(y - 20, y + 20, "#edf4f5" if i % 2 == 0 else "#f7f9fb")
        for x, value in zip(columns, row):
            text(x, y, value, 16)
    text(52, 369, "Table 1 notes", 16, True)
    text(54, NOTE_CENTERS[0], "Note A: For t > 40 mm, replace minimum with 450 MPa.")
    text(54, NOTE_CENTERS[1], "Note B: For t > 60 mm, replace maximum with 610 MPa.")
    text(54, 482, "t = nominal plate thickness. Notes apply only to marked rows.", 12)
    band(713, 714, "#cddbe1")
    text(52, 738, "Synthetic data for OCR and reasoning demos only.", 11)
    text(521, 738, "1 / 1", 11)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    canvas = Canvas(str(PDF), pagesize=(WIDTH, HEIGHT))
    canvas.setTitle("DEMO-STEEL-01 | Steel plate requirements")
    canvas.drawImage(ImageReader(buffer), 0, 0, width=WIDTH, height=HEIGHT)
    canvas.showPage()
    canvas.save()


if __name__ == "__main__":
    main()
