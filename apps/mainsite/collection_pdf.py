import base64
import math
import os
from functools import partial
from io import BytesIO

import qrcode
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

font_path_rubik_regular = os.path.join(
    os.path.dirname(__file__), "static", "fonts", "Rubik-Regular.ttf"
)
font_path_rubik_medium = os.path.join(
    os.path.dirname(__file__), "static", "fonts", "Rubik-Medium.ttf"
)
font_path_rubik_bold = os.path.join(
    os.path.dirname(__file__), "static", "fonts", "Rubik-Bold.ttf"
)
font_path_rubik_italic = os.path.join(
    os.path.dirname(__file__), "static", "fonts", "Rubik-Italic.ttf"
)

pdfmetrics.registerFont(TTFont("Rubik-Regular", font_path_rubik_regular))
pdfmetrics.registerFont(TTFont("Rubik-Medium", font_path_rubik_medium))
pdfmetrics.registerFont(TTFont("Rubik-Bold", font_path_rubik_bold))
pdfmetrics.registerFont(TTFont("Rubik-Italic", font_path_rubik_italic))


class CollectionPDFCreator:
    def __init__(self):
        self.used_space = 0

    def add_title(self, first_page_content, title):
        first_page_content.append(Spacer(1, 50))
        title_style = ParagraphStyle(
            name="Title",
            fontSize=20,
            textColor="#492E98",
            fontName="Rubik-Bold",
            leading=30,
            alignment=TA_CENTER,
        )
        first_page_content.append(Spacer(1, 10))
        first_page_content.append(Paragraph(f"<strong>{title}</strong>", title_style))
        first_page_content.append(Spacer(1, 15))
        self.used_space += 105  # Three spacers and paragraph

    def add_description(self, first_page_content, description):
        description_style = ParagraphStyle(
            name="Description",
            fontSize=12,
            fontName="Rubik-Regular",
            leading=16.5,
            alignment=TA_CENTER,
            leftIndent=20,
            rightIndent=20,
        )
        first_page_content.append(Paragraph(description, description_style))
        line_char_count = 79
        line_height = 16.5
        num_lines = math.ceil(len(description) / line_char_count)
        self.used_space += num_lines * line_height

    def add_badges(self, first_page_content, badges):
        PAGE_WIDTH, PAGE_HEIGHT = A4
        CONTENT_WIDTH = PAGE_WIDTH - 40  # Accounting for margins
        ITEM_WIDTH = CONTENT_WIDTH / 3  # 3 items per row
        ITEM_HEIGHT = 1 * inch
        ITEM_MARGIN = 0.2 * inch

        rows = []
        current_row = []

        rowsPerPage = 6  # 18 badges

        for i, badge in enumerate(badges):
            b = BadgeCard(
                badge.image,
                badge.badgeclass.name,
                badge.badgeclass.issuer.name,
                badge.issued_on,
                width=ITEM_WIDTH - ITEM_MARGIN,
                height=ITEM_HEIGHT,
            )

            current_row.append(b)

            if len(current_row) == 3:
                rows.append(current_row)
                current_row = []

        if current_row:
            while len(current_row) < 3:
                current_row.append(Spacer(ITEM_WIDTH - ITEM_MARGIN, ITEM_HEIGHT))
            rows.append(current_row)

        for i, row in enumerate(rows):
            if i != 0 and i % rowsPerPage == 0:
                first_page_content.append(PageBreak())
                first_page_content.append(Spacer(1, 70))
                self.used_space = 0
            table = Table([row], colWidths=[ITEM_WIDTH - ITEM_MARGIN / 2] * 3)
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("RIGHTPADDING", (0, 0), (-1, -1), ITEM_MARGIN / 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), ITEM_MARGIN / 2),
                    ]
                )
            )

            first_page_content.append(table)
            first_page_content.append(Spacer(1, 10))
            self.used_space += ITEM_HEIGHT + 10

    def add_qrcode_section(
        self, first_page_content, entity_id, origin: str, qrCodeImage=None
    ):
        issued_by_style = ParagraphStyle(
            name="IssuedBy",
            fontSize=10,
            textColor="#323232",
            fontName="Rubik-Medium",
            alignment=TA_CENTER,
            backColor="#F5F5F5",
            leftIndent=-45,
            rightIndent=-45,
        )
        document_width, _ = A4

        qr_code_height = 0
        if qrCodeImage:
            if qrCodeImage.startswith("data:image"):
                qrCodeImage = qrCodeImage.split(",")[1]  # Entfernt das Präfix

            image = base64.b64decode(qrCodeImage)
            qrCodeImage = BytesIO(image)
            qrCodeImage = ImageReader(qrCodeImage)

            rounded_img = RoundedImage(
                img_path=qrCodeImage,
                width=57,
                height=57,
                border_color="#492E98",
                border_width=1,
                padding=1,
                radius=2 * mm,
            )

            img_table = Table([[rounded_img]], colWidths=[document_width])
            img_table.hAlign = "CENTER"
            img_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (0, 0), "CENTER"),
                        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F5")),
                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            -45,
                        ),  # Negative padding to extend beyond the document margin
                        ("RIGHTPADDING", (0, 0), (-1, -1), -45),
                        ("TOPPADDING", (0, 0), (-1, -1), 20),
                    ]
                )
            )
            first_page_content.append(img_table)
            qr_code_height = 57 + 20

        content_html = f"""
            <br/><p><font name="Rubik-Regular">
            Detaillierte Infos zu den <font name="Rubik-Bold">einzelnen Badges <br/>
            und den damit gestärkten Kompetenzen</font> erhalten Sie <br/> über den QR-Code oder diesen Link:
            <a href="{origin}/public/collections/{entity_id}"
            color="#1400FF"
            underline="true">Digitale Badge-Sammlung</a></font></p>
            <br/>
            <br/><br/>
        """

        first_page_content.append(Paragraph(content_html, issued_by_style))

        paragraph_height = 60
        self.used_space += qr_code_height + paragraph_height

    def header(self, canvas, doc, userName):
        canvas.saveState()
        header_height = 0

        oebLogo = ImageReader("{}images/logo-square.png".format(settings.STATIC_URL))

        if oebLogo is not None:
            canvas.drawImage(
                oebLogo,
                20,
                740,
                width=80,
                height=80,
                mask="auto",
                preserveAspectRatio=True,
            )
            header_height += 80

        canvas.setStrokeColor("#492E98")
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin + 100, 775, doc.leftMargin + doc.width, 775)
        header_height += 1
        canvas.setFont("Rubik-Medium", 12)
        max_length = 50
        line_height = 12
        # logic if a linebreak is needed
        if len(userName) > max_length:
            split_index = userName.rfind(" ", 0, max_length)
            if split_index == -1:
                split_index = max_length

            line1 = userName[:split_index]
            line2 = userName[split_index:].strip()

            canvas.drawString(doc.leftMargin + 100, 778 + line_height, line1)
            canvas.drawString(doc.leftMargin + 100, 778, line2)
            header_height += 2 * line_height
        else:
            canvas.drawString(doc.leftMargin + 100, 778, userName)
            header_height += line_height

        self.used_space += header_height
        canvas.restoreState()

    def generate_qr_code(self, collection, origin):
        # build the qr code in the backend

        qrCodeImageUrl = f"{origin}/public/collections/{collection.entity_id}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qrCodeImageUrl)
        qr.make(fit=True)
        qrCodeImage = qr.make_image(fill_color="black", back_color="white")

        buffered = BytesIO()
        qrCodeImage.save(buffered, format="PNG")
        qrCodeImageBase64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return qrCodeImageBase64

    def generate_pdf(self, collection, origin):
        buffer = BytesIO()
        self.used_space = 0

        first_page_content = []

        self.add_title(first_page_content, collection.name)
        self.add_description(first_page_content, collection.description)
        first_page_content.append(Spacer(1, 20 if collection.description else 50))
        self.add_badges(first_page_content, collection.assertions.all())
        if collection.published:
            # not enough space for qrcode on this page
            if self.used_space > 550:
                first_page_content.append(PageBreak())
                first_page_content.append(Spacer(1, 70))
                self.used_space = 0
            self.add_qrcode_section(
                first_page_content,
                collection.entity_id,
                origin,
                self.generate_qr_code(collection, origin),
            )

        # doc template with margins according to design doc
        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY))

        Story = []
        Story.extend(first_page_content)

        frame = Frame(
            doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal"
        )
        template = PageTemplate(
            id="header",
            frames=frame,
            onPage=partial(self.header, userName=collection.owner.get_full_name()),
        )
        doc.addPageTemplates([template])
        pageNumCanvas = partial(PageNumCanvas, origin=origin)
        doc.build(Story, canvasmaker=pageNumCanvas)
        pdfContent = buffer.getvalue()
        buffer.close()
        return pdfContent


class BadgeCard(Flowable):
    def __init__(
        self, image, title, issuer, issued_on, width=6 * inch, height=2 * inch
    ):
        Flowable.__init__(self)
        self.image = image
        self.title = title
        self.issuer = issuer
        self.issued_on = issued_on
        self.width = width
        self.height = height

    def truncate_text(self, text, max_chars):
        if len(text) > max_chars:
            return text[: max_chars - 3] + "..."
        return text

    def draw(self):
        self.canv.setStrokeColor("#492E98")
        self.canv.setLineWidth(1)

        radius = 10
        radius_pt = radius * 0.75
        self.canv.roundRect(0, 0, self.width, self.height, radius_pt, stroke=1, fill=0)

        img_size = 60 * 0.75
        img_x = 0.2 * inch
        img_y = (self.height - img_size) / 2
        try:
            if self.image:
                img = Image(self.image, width=img_size, height=img_size)
                img.drawOn(self.canv, img_x, img_y)
        except Exception as e:
            print(e)

        text_x = img_x + img_size + 0.15 * inch
        text_width = self.width - text_x - 0.15 * inch

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading3"],
            fontSize=8,
            leading=10,
            fontName="Rubik-Bold",
            textColor=colors.HexColor("#333333"),
            splitLongWords=1,
            spaceAfter=1,
        )
        issuer_style = ParagraphStyle(
            "IssuerStyle",
            parent=styles["BodyText"],
            fontSize=6.5,
            leading=8,
            fontName="Rubik-Regular",
            textColor=colors.HexColor("#323232"),
            splitLongWords=1,
            spaceAfter=1,
        )
        date_style = ParagraphStyle(
            "DateStyle",
            parent=styles["BodyText"],
            fontSize=6,
            leading=7,
            fontName="Rubik-Regular",
            textColor=colors.HexColor("#323232"),
        )

        title_text = self.truncate_text(self.title, 60)
        issuer_text = self.truncate_text(self.issuer, 90)
        date_text = self.issued_on.strftime("%d.%m.%Y")

        title_para = Paragraph(title_text, title_style)
        issuer_para = Paragraph(issuer_text, issuer_style)
        date_para = Paragraph(date_text, date_style)

        _, title_height = title_para.wrap(text_width, self.height)
        _, issuer_height = issuer_para.wrap(text_width, self.height)
        _, date_height = date_para.wrap(text_width, self.height)

        spacing = 2
        total_text_height = title_height + issuer_height + date_height + 2 * spacing

        if total_text_height > self.height - 10:
            title_style.fontSize -= 1
            issuer_style.fontSize -= 0.5
            date_style.fontSize -= 0.5

            title_para = Paragraph(title_text, title_style)
            issuer_para = Paragraph(issuer_text, issuer_style)
            date_para = Paragraph(date_text, date_style)

            _, title_height = title_para.wrap(text_width, self.height)
            _, issuer_height = issuer_para.wrap(text_width, self.height)
            _, date_height = date_para.wrap(text_width, self.height)
            total_text_height = title_height + issuer_height + date_height + 2 * spacing

        # Start drawing from vertical center
        current_y = (self.height + total_text_height) / 2

        title_para.drawOn(self.canv, text_x, current_y - title_height)
        current_y -= title_height + spacing

        issuer_para.drawOn(self.canv, text_x, current_y - issuer_height)
        current_y -= issuer_height + spacing

        date_para.drawOn(self.canv, text_x, current_y - date_height)


class RoundedImage(Flowable):
    def __init__(
        self, img_path, width, height, border_color, border_width, padding, radius
    ):
        super().__init__()
        self.img_path = img_path
        self.width = width
        self.height = height
        self.border_color = border_color
        self.border_width = border_width
        self.padding = padding
        self.radius = radius

    def draw(self):
        # Calculate total padding to prevent image overlap
        total_padding = self.padding + self.border_width + 1.8

        # Draw the rounded rectangle for the border
        canvas = self.canv
        canvas.setFillColor("white")
        canvas.setStrokeColor(self.border_color)
        canvas.setLineWidth(self.border_width)
        canvas.roundRect(
            0,  # Start at the lower-left corner of the Flowable
            0,
            self.width + 2 * total_padding,  # Width includes padding on both sides
            self.height + 2 * total_padding,  # Height includes padding on both sides
            self.radius,  # Radius for rounded corners,
            stroke=1,
            fill=1,
        )

        # Draw the image inside the rounded rectangle
        canvas.drawImage(
            self.img_path,
            total_padding,  # Offset by total padding to stay within rounded border
            total_padding,
            width=self.width,
            height=self.height,
            mask="auto",
        )


# Inspired by https://www.blog.pythonlibrary.org/2013/08/12/reportlab-how-to-add-page-numbers/
class PageNumCanvas(canvas.Canvas):
    """
    http://code.activestate.com/recipes/546511-page-x-of-y-with-reportlab/
    http://code.activestate.com/recipes/576832/
    """

    # ----------------------------------------------------------------------
    def __init__(self, *args, origin: str, **kwargs):
        """Constructor"""
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
        self.origin = origin

    # ----------------------------------------------------------------------
    def showPage(self):
        """
        On a page break, add information to the list
        """
        self.pages.append(dict(self.__dict__))
        self._startPage()

    # ----------------------------------------------------------------------
    def save(self):
        """
        Add the page number to each page (page x of y)
        """
        page_count = len(self.pages)

        for page in self.pages:
            self.__dict__.update(page)
            self.draw_page_number(page_count)
            canvas.Canvas.showPage(self)

        canvas.Canvas.save(self)

    # ----------------------------------------------------------------------
    def draw_page_number(self, page_count):
        """
        Add the page number
        """
        page = "%s / %s" % (self._pageNumber, page_count)
        self.setStrokeColor("#492E98")
        page_width = self._pagesize[0]
        self.line(10, 17.5, page_width / 2 - 20, 17.5)
        self.line(page_width / 2 + 20, 17.5, page_width - 10, 17.5)
        self.setFont("Rubik-Regular", 10)
        self.drawCentredString(page_width / 2, 15, page)
        if self._pageNumber == page_count:
            self.setFont("Rubik-Bold", 10)
            text_before = "ERSTELLT ÜBER "
            link_text = "OPENBADGES.EDUCATION"

            text_before_width = self.stringWidth(text_before, "Rubik-Bold", 10)
            link_text_width = self.stringWidth(link_text, "Rubik-Bold", 10)
            full_text_width = text_before_width + link_text_width

            x_start = (page_width - full_text_width) / 2

            self.drawString(x_start, 35, text_before)

            self.setFillColor("#1400FF")

            self.drawString(x_start + text_before_width, 35, link_text)

            link_x = x_start + text_before_width
            self.line(link_x, 34, link_x + link_text_width, 34)

            self.linkURL(
                self.origin,
                rect=(
                    x_start + text_before_width,
                    35,
                    x_start + text_before_width + link_text_width,
                    35 + 10,
                ),
                relative=0,
                thickness=0,
            )
            self.setLineWidth(3)
            self.line(10, 10, page_width - 10, 10)
