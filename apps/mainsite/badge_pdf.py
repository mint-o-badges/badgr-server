from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import PCMYKColor
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Flowable, Paragraph, Spacer, Image, PageBreak,BaseDocTemplate,Table, TableStyle, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from svglib.svglib import svg2rlg
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.graphics import renderPDF
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from functools import partial
import base64
from io import BytesIO
import os
import qrcode
import math
from issuer.models import BadgeInstance, BadgeClass, Issuer, IssuerStaff
from badgeuser.models import BadgeUser
from mainsite.utils import get_name
from django.conf import settings

font_path_rubik_regular = os.path.join(os.path.dirname(__file__), 'Rubik-Regular.ttf')
font_path_rubik_medium = os.path.join(os.path.dirname(__file__), 'Rubik-Medium.ttf')
font_path_rubik_bold = os.path.join(os.path.dirname(__file__), 'Rubik-Bold.ttf')
font_path_rubik_italic = os.path.join(os.path.dirname(__file__), 'Rubik-Italic.ttf')

pdfmetrics.registerFont(TTFont('Rubik-Regular', font_path_rubik_regular))
pdfmetrics.registerFont(TTFont('Rubik-Medium', font_path_rubik_medium))
pdfmetrics.registerFont(TTFont('Rubik-Bold', font_path_rubik_bold))
pdfmetrics.registerFont(TTFont('Rubik-Italic', font_path_rubik_italic))

class BadgePDFCreator:
    def __init__(self):
        pass

    def add_badge_image(self, first_page_content, badgeImage): 
        image_width = 180
        image_height = 180
        first_page_content.append(Image(badgeImage, width=image_width, height=image_height))

    def add_recipient_name(self, first_page_content, name, issuedOn):
        first_page_content.append(Spacer(1, 58))
        recipient_style = ParagraphStyle(name='Recipient', fontSize=16, textColor='#492E98',fontName='Rubik-bold',  alignment=TA_CENTER)
        
        recipient_name = f"<strong>{name}</strong>"
        first_page_content.append(Paragraph(recipient_name, recipient_style))
        first_page_content.append(Spacer(1, 25))

        text_style = ParagraphStyle(name='Text_Style', fontSize=18, alignment=TA_CENTER)
        
        text = "hat am " + issuedOn.strftime("%d.%m.%Y")
        first_page_content.append(Paragraph(text, text_style))
        first_page_content.append(Spacer(1, 10))

        text = "den folgenden Badge erworben:"
        first_page_content.append(Paragraph(text, text_style))
        first_page_content.append(Spacer(1, 25))


    def add_title(self, first_page_content, badge_class_name):

        title_style = ParagraphStyle(name='Title', fontSize=20, textColor='#492E98', fontName="Rubik-Bold" , leading=30, alignment=TA_CENTER)
        first_page_content.append(Spacer(1, 10))
        first_page_content.append(Paragraph(f"<strong>{badge_class_name}</strong>", title_style))
        first_page_content.append(Spacer(1, 15))

    def truncate_text(text, max_words=70):
        words = text.split()
        if len(words) > max_words:
            return ' '.join(words[:max_words]) + '...'
        else:
            return text
        
    def add_dynamic_spacer(self, first_page_content, text):
        print(text)
        line_char_count = 79
        line_height = 16.5
        num_lines = math.ceil(len(text) / line_char_count)
        spacer_height = 175 - (num_lines - 1) * line_height
        first_page_content.append(Spacer(1, max(spacer_height, 0)))
                                

    def add_description(self, first_page_content, description):
        description_style = ParagraphStyle(name='Description', fontSize=12,fontName='Rubik-Regular',  leading=16.5, alignment=TA_CENTER, leftIndent=20, rightIndent=20)
        first_page_content.append(Paragraph(description, description_style))


    def add_narrative(self, first_page_content, narrative):
        if narrative is not None:
            first_page_content.append(Spacer(1, 10)) 
            narrative_style = ParagraphStyle(name='Narrative',fontName="Rubik-Italic",fontSize=12,textColor='#6B6B6B', leading=16.5, alignment=TA_CENTER, leftIndent=20, rightIndent=20)
            narrative = narrative[:280] + '...' if len(narrative) > 280 else narrative
            first_page_content.append(Paragraph(narrative, narrative_style))

    def add_issued_by(self, first_page_content, issued_by, qrCodeImage=None):
        # Style for the issued by paragraph
        issued_by_style = ParagraphStyle(
            name='IssuedBy', 
            fontSize=10, 
            textColor='#323232', 
            fontName='Rubik-Medium', 
            alignment=TA_CENTER,
            backColor='#F5F5F5',
            leftIndent=-45,
            rightIndent=-45
        )
        # use document width to calculate the table and its size
        document_width, _ = A4
        
        if qrCodeImage:
            if qrCodeImage.startswith("data:image"):
                qrCodeImage = qrCodeImage.split(",")[1]  # Entfernt das Präfix

            image = base64.b64decode(qrCodeImage)
            qrCodeImage = BytesIO(image)
            qrCodeImage = ImageReader(qrCodeImage)
            
            # Create a RoundedImage instance
            rounded_img = RoundedImage(
                img_path=qrCodeImage,
                width=50,                
                height=50,               
                border_color="#492E98",  
                border_width=1,           
                padding=1,                
                radius=4 * mm            
            )

            # Add rounded image to a centered table
            img_table = Table([[rounded_img]], colWidths=[document_width])
            img_table.hAlign = 'CENTER'  
            img_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5F5')),  
                ('LEFTPADDING', (0, 0), (-1, -1), -45),  # Negative padding to extend beyond the document margin
                ('RIGHTPADDING', (0, 0), (-1, -1), -45),
                ('TOPPADDING', (0, 0), (-1, -1), 20),  
            ]))
            first_page_content.append(img_table)

        # Add the simple html
        content_html = """
            <br/><span fontName="Rubik-Bold">ERSTELLT ÜBER <a href="https://openbadges.education" 
            color="#1400FF" 
            underline="true">OPENBADGES.EDUCATION</a></span>
            <br/>
            <span fontName="Rubik-Regular">Der digitale Badge kann über den QR-Code abgerufen werden</span>
            <br/><br/>
        """
        
        # Add content as a Paragraph to first_page_content
        first_page_content.append(Paragraph(content_html, issued_by_style))

        
    def add_issuer_image(self, first_page_content, issuerImage): 
        image_width = 60
        image_height = 60
        first_page_content.append(Image(issuerImage, width=image_width, height=image_height))

    ## draw header with image of institution and a hr
    def header(self, canvas, doc, content, instituteName):
        canvas.saveState()

        content.drawOn(canvas, doc.leftMargin, 750)

        canvas.setStrokeColor("#492E98") 
        canvas.setLineWidth(1)  
        canvas.line(doc.leftMargin + 100, 775, doc.leftMargin + doc.width, 775)

        ## name of institute barely above the hr that was just set
        canvas.setFont('Rubik-Medium', 12)
        max_length = 50  
        line_height = 12
        # logic if a linebreak is needed
        if len(instituteName) > max_length:
            split_index = instituteName.rfind(' ', 0, max_length)
            if split_index == -1: 
                split_index = max_length

            line1 = instituteName[:split_index]
            line2 = instituteName[split_index:].strip()  

            # have line height of 12 points
            canvas.drawString(doc.leftMargin + 100, 778 + line_height, line1)
            canvas.drawString(doc.leftMargin + 100, 778, line2)
        else:
            canvas.drawString(doc.leftMargin + 100, 778, instituteName)

        canvas.restoreState()
    
    def add_competencies (self, Story, competencies, name, badge_name):
        num_competencies = len(competencies)
        if num_competencies > 0:
                esco = any(c['framework']  for c in competencies)
                competenciesPerPage = 9

                Story.append(PageBreak())
                Story.append(Spacer(1, 70))

                title_style = ParagraphStyle(name='Title', fontSize=20,fontName="Rubik-Medium", textColor='#492E98', alignment=TA_LEFT)
                text_style = ParagraphStyle(name='Text', fontSize=18, leading=20, textColor='#323232', alignment=TA_LEFT)

                Story.append(Paragraph("Kompetenzen", title_style))
                Story.append(Spacer(1, 15))
                
                text = f"die <strong>{name}</strong> mit dem Badge <strong>{badge_name}</strong> erworben hat:"
                Story.append(Paragraph(text, text_style))
                Story.append(Spacer(1, 10))

                for i in range(num_competencies):
                    if i != 0 and i % competenciesPerPage == 0: 
                        Story.append(PageBreak())
                        Story.append(Spacer(1, 35))
                        Story.append(Paragraph("<strong>Kompetenzen</strong>", title_style))
                        Story.append(Spacer(1, 15))

                        text = f"die <strong>{name}</strong> mit dem Badge <strong>{badge_name}</strong> erworben hat:"

                        Story.append(Paragraph(text, text_style))
                        Story.append(Spacer(1, 20))

                
                    studyload = "%s:%s h" %  (math.floor(competencies[i]['studyLoad'] / 60), str(competencies[i]['studyLoad'] % 60).zfill(2))
                    competency_name = competencies[i]['name']
                    competency = competency_name
                    #   competency = (competency_name[:35] + '...') if len(competency_name) > 35 else competency_name
                    rounded_rect = RoundedRectFlowable(0, -10, 515, 45, 10, text=competency, strokecolor="#492E98", fillcolor="#F5F5F5", studyload= studyload, esco=competencies[i]['framework_identifier'])    
                    Story.append(rounded_rect)
                    Story.append(Spacer(1, 10))   
                        
                if esco: 
                    Story.append(Spacer(1, 10))
                    text_style = ParagraphStyle(name='Text_Style',fontName="Rubik-Italic", fontSize=10, leading=15.6, alignment=TA_CENTER, leftIndent=-35, rightIndent=-35)
                    link_text = '<span><i>(E) = Kompetenz nach ESCO (European Skills, Competences, Qualifications and Occupations). <br/>' \
                        'Die Kompetenzbeschreibungen gemäß ESCO sind abrufbar über <a color="blue" href="https://esco.ec.europa.eu/de">https://esco.ec.europa.eu/de</a>.</i></span>'
                    paragraph_with_link = Paragraph(link_text, text_style)
                    Story.append(paragraph_with_link) 

    def generate_qr_code(self, badge_instance, origin):
        ## build the qr code in the backend

        qrCodeImageUrl = f"{origin}/public/assertions/{badge_instance.slug}"
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
        qrCodeImageBase64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return qrCodeImageBase64

    def generate_pdf(self, badge_instance, badge_class, origin):
        # Create PDF with badge data
        buffer = BytesIO()
        competencies = badge_class.json["extensions:CompetencyExtension"]
        try:
            name = get_name(badge_instance)
        except BadgeUser.DoesNotExist:
            # To resolve the issue with old awarded badges that doesn't include recipient-name and only have recipient-email
            # We use email as this is the only identifier we have 
            name = badge_instance.recipient_identifier
            # raise Http404

        # build the first page
        first_page_content = []

        self.add_recipient_name(first_page_content, name, badge_instance.issued_on)
        self.add_badge_image(first_page_content, badge_class.image)
        self.add_title(first_page_content, badge_class.name)
        self.add_description(first_page_content, badge_class.description)
        self.add_narrative(first_page_content, badge_instance.narrative)
        narrative = badge_instance.narrative
        if narrative:
            narrative = narrative[:280] + '...' if len(narrative) > 280 else narrative
        self.add_dynamic_spacer(first_page_content, (badge_class.description or "") +  (narrative or ""))
        self.add_issued_by(first_page_content, badge_class.issuer.name, self.generate_qr_code(badge_instance, origin))


        # doc template with margins according to design doc
        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40
        )


        
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
        
        Story = []
        Story.extend(first_page_content)

        self.add_competencies(Story, competencies, name, badge_class.name)

        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')

        ## template for header
        template = PageTemplate(id='header', frames=frame ,onPage=partial(self.header, content= Image(badge_class.issuer.image, width=80, height=80), instituteName=badge_instance.issuer.name))
        ## adding template to all pages 
        doc.addPageTemplates([template])
        doc.build(Story, canvasmaker=PageNumCanvas)   
        pdfContent = buffer.getvalue()
        buffer.close()
        return pdfContent
    


## Class for rounded image as reportlabs table cell don't support rounded corners
## taken from AI 
class RoundedImage(Flowable):
    def __init__(self, img_path, width, height, border_color, border_width, padding, radius):
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
        canvas.setStrokeColor(self.border_color)
        canvas.setLineWidth(self.border_width)
        canvas.roundRect(
            0,  # Start at the lower-left corner of the Flowable
            0, 
            self.width + 2 * total_padding,  # Width includes padding on both sides
            self.height + 2 * total_padding,  # Height includes padding on both sides
            self.radius  # Radius for rounded corners
        )
        
        # Draw the image inside the rounded rectangle
        canvas.drawImage(
            self.img_path, 
            total_padding,  # Offset by total padding to stay within rounded border
            total_padding, 
            width=self.width, 
            height=self.height,
            mask='auto'
        )


class RoundedRectFlowable(Flowable):
    def __init__(self, x, y, width, height, radius, text, strokecolor, fillcolor, studyload, esco = ''):
        super().__init__()
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.radius = radius
        self.strokecolor = strokecolor
        self.fillcolor = fillcolor 
        self.text = text
        self.studyload = studyload
        self.esco = esco

    def split_text(self, text, max_width):
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            if self.canv.stringWidth(test_line, 'Rubik-Medium', 12) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        lines.append(current_line)
        return lines    
    

    def draw(self):
        self.canv.setFillColor(self.fillcolor)
        self.canv.setStrokeColor(self.strokecolor)
        self.canv.roundRect(self.x, self.y, self.width, self.height, self.radius,
                             stroke=1, fill=1)
        
        self.canv.setFillColor('#323232')
        text_width = self.canv.stringWidth(self.text)
        self.canv.setFont('Rubik-Medium', 12)
        if text_width > self.width - 175:
            available_text_width = self.width - 150
            y_text_position = self.y + 25
        else:
            available_text_width = self.width - 150
            y_text_position = self.y + 17.5

        text_lines = self.split_text(self.text, available_text_width)

        for line in text_lines:
            self.canv.drawString(self.x + 10, y_text_position, line)
            y_text_position -= 15 
        
        self.canv.setFillColor('blue')
        if self.esco:
            last_line_width = self.canv.stringWidth(text_lines[-1])
            self.canv.setFillColor('blue')
            self.canv.drawString(self.x + 10 + last_line_width, y_text_position + 15, " [E]")
            self.canv.linkURL(self.esco, (self.x, self.y, self.width, self.height), relative=1, thickness=0)

        
        self.canv.setFillColor('#492E98')
        self.canv.setFont('Rubik-Regular', 14)
        studyload_width = self.canv.stringWidth(self.studyload)
        self.canv.drawString(self.x + 450 -(studyload_width + 10), self.y + 15, self.studyload)

        clockIcon = ImageReader("{}images/clock-icon.png".format(settings.STATIC_URL))
        self.canv.drawImage(clockIcon, self.x + 450 - (studyload_width + 35), self.y +12.5, width=15, height=15, mask="auto", preserveAspectRatio=True)
        
# Inspired by https://www.blog.pythonlibrary.org/2013/08/12/reportlab-how-to-add-page-numbers/
class PageNumCanvas(canvas.Canvas):
    """
    http://code.activestate.com/recipes/546511-page-x-of-y-with-reportlab/
    http://code.activestate.com/recipes/576832/
    """
    #----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        """Constructor"""
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
        
    #----------------------------------------------------------------------
    def showPage(self):
        """
        On a page break, add information to the list
        """
        self.pages.append(dict(self.__dict__))
        self._startPage()
        
    #----------------------------------------------------------------------
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
        
    #----------------------------------------------------------------------
    def draw_page_number(self, page_count):
        """
        Add the page number
        """
        page = "%s / %s" % (self._pageNumber, page_count)
        self.setStrokeColor("#492E98")
        page_width = self._pagesize[0]
        self.line(10, 25, page_width / 2 - 20, 25)
        self.line(page_width  / 2 + 20, 25, page_width - 10, 25)
        self.setFont("Rubik-Regular", 14)
        self.drawCentredString(page_width / 2, 20, page)
        if self._pageNumber == page_count:
            self.setLineWidth(3)
            self.line(10, 10, page_width - 10, 10)
