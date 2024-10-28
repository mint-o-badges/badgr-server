import math
from django.urls import reverse
from django.conf import settings
from django.http import Http404
from django.views.generic import RedirectView

from django.core.exceptions import PermissionDenied

from backpack.models import BackpackCollection
from issuer.models import BadgeInstance, BadgeClass, Issuer, IssuerStaff
from badgeuser.models import BadgeUser

from rest_framework.decorators import (
    permission_classes,
    authentication_classes,
    api_view,
)

import requests
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import PCMYKColor
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Flowable, Paragraph, Spacer, Image, PageBreak,PageTemplate, BaseDocTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus.frames import Frame
from mainsite.utils import get_name
from operator import attrgetter
import os
from functools import partial
font_path_rubik_regular = os.path.join(os.path.dirname(__file__), 'Rubik-Regular.ttf')
font_path_rubik_medium = os.path.join(os.path.dirname(__file__), 'Rubik-Medium.ttf')
font_path_rubik_bold = os.path.join(os.path.dirname(__file__), 'Rubik-Bold.ttf')

pdfmetrics.registerFont(TTFont('Rubik-Regular', font_path_rubik_regular))
pdfmetrics.registerFont(TTFont('Rubik-Medium', font_path_rubik_medium))
pdfmetrics.registerFont(TTFont('Rubik-Bold', font_path_rubik_bold))

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
            self.canv.linkURL(f"http://data.europa.eu/{self.esco}", (self.x, self.y, self.width, self.height), relative=1, thickness=0)

        
        self.canv.setFillColor('#492E98')
        self.canv.setFont('Rubik-Regular', 14)
        studyload_width = self.canv.stringWidth(self.studyload)
        self.canv.drawString(self.x + 515 -(studyload_width + 10), self.y + 15, self.studyload)

        clockIcon = ImageReader("{}images/clock-icon.png".format(settings.STATIC_URL))
        self.canv.drawImage(clockIcon, self.x + 515 - (studyload_width + 35), self.y +12.5, width=15, height=15, mask="auto", preserveAspectRatio=True)


def AllPageSetup(canvas, doc, badgeImage=None):

    # Stelle den ursprünglichen Zustand des Canvas wieder her
    canvas.restoreState()
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

def header(canvas, doc, content, instituteName):
    canvas.saveState()

    # Institutsbild
    content.drawOn(canvas, doc.leftMargin, 750)

    # Zeichne die horizontale Linie unter dem Bild
    canvas.setStrokeColor("#492E98")  # Setze die Farbe der Linie
    canvas.setLineWidth(1)  # Setze die Linienbreite
    canvas.line(doc.leftMargin + 100, 775, doc.leftMargin + doc.width, 775)

    ## Institusname
    canvas.setFont('Rubik-Medium', 12)  # Setze die Schriftart auf Rubik-Bold und Größe auf 12
    canvas.drawString(doc.leftMargin + 100, 780, instituteName)

    canvas.restoreState()
    


def create_multi_page(response, first_page_content, competencies, name, badge_name,instituteName, badgeImage=None):
    """
    Create a multi-page pdf document
    """
    
    # Erstellen des SimpleDocTemplate mit einem Seitenrand von 40 Punkten
    doc = BaseDocTemplate(
        response,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
    
    Story = []

    # Add first page content to the story
    Story.extend(first_page_content)

    num_competencies = len(competencies)

    if num_competencies > 0:
            esco = any(c['escoID'] for c in competencies)
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

              studyload = "%s min" % competencies[i]['studyLoad']
              if competencies[i]['studyLoad'] > 120:
                  studyLoadInHours = competencies[i]['studyLoad'] / 60
                  studyload = "%s h" % int(studyLoadInHours)
              competency_name = competencies[i]['name']
              competency = competency_name
            #   competency = (competency_name[:35] + '...') if len(competency_name) > 35 else competency_name
              rounded_rect = RoundedRectFlowable(0, -10, 515, 45, 10, text=competency, strokecolor="#492E98", fillcolor="#F5F5F5", studyload= studyload, esco=competencies[i]['escoID'])    
              Story.append(rounded_rect)
              Story.append(Spacer(1, 10))   
                 
            if esco: 
                Story.append(Spacer(1, 10))
                text_style = ParagraphStyle(name='Text_Style', fontSize=12, leading=15.6, alignment=TA_LEFT, leftIndent=-35, rightIndent=-35)
                link_text = '<span><i>(E) = Kompetenz nach ESCO (European Skills, Competences, Qualifications and Occupations). <br/>' \
                    'Die Kompetenzbeschreibungen gemäß ESCO sind abrufbar über <a color="blue" href="https://esco.ec.europa.eu/de">https://esco.ec.europa.eu/de</a>.</i></span>'
                paragraph_with_link = Paragraph(link_text, text_style)
                Story.append(paragraph_with_link) 


    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    ## template for header
    template = PageTemplate(id='header', frames=frame ,onPage=partial(header, content= Image(badgeImage, width=80, height=80), instituteName=instituteName))
    ## adding template to all pages 
    doc.addPageTemplates([template])
    doc.build(Story, canvasmaker=PageNumCanvas)   
 
def addBadgeImage(first_page_content, badgeImage): 
    image_width = 180
    image_height = 180
    first_page_content.append(Image(badgeImage, width=image_width, height=image_height))

def add_recipient_name(first_page_content, name, issuedOn):
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

def add_title(first_page_content, badge_class_name):

    title_style = ParagraphStyle(name='Title', fontSize=20, textColor='#492E98', fontName="Rubik-Bold" , leading=30, alignment=TA_CENTER)
    first_page_content.append(Paragraph(f"<strong>{badge_class_name}</strong>", title_style))
    # if(len(badge_class_name) > 30):
    first_page_content.append(Spacer(1, 15))
    # else:
    #     first_page_content.append(Spacer(1, 35))

def truncate_text(text, max_words=70):
    words = text.split()
    if len(words) > max_words:
        return ' '.join(words[:max_words]) + '...'
    else:
        return text

def add_description(first_page_content, description):
    description_style = ParagraphStyle(name='Description', fontSize=12,fontName='Rubik-Regular',  leading=16.5, alignment=TA_CENTER, leftIndent=20, rightIndent=20)
    first_page_content.append(Paragraph(description, description_style))
    first_page_content.append(Spacer(1, 10))

def add_narrative(first_page_content, narrative):
    if narrative is not None:
        narrative_style = ParagraphStyle(name='Narrative', fontSize=11, leading=16.5, alignment=TA_CENTER)
        first_page_content.append(Paragraph(narrative, narrative_style))
        first_page_content.append(Spacer(1, 10)) 
    else: 
        first_page_content.append(Spacer(1, 35))       

def add_issuedBy(first_page_content, issued_by, issuerImage=None):

    # style of the issued by parapragh
    issued_by_style = ParagraphStyle(
        name='IssuedBy', 
        fontSize=10, 
        textColor='#323232', 
        fontName='Rubik-Medium', 
        alignment=TA_CENTER,
        backColor='#F5F5F5',
        spaceBefore=10,
        spaceAfter=10,
        leftIndent=-45,
        rightIndent=-45

    )

    # post raw html content
    content_html = f"""
        <div>
            <br/><span fontName="Rubik-Bold">ERSTELLT ÜBER <a href="https://openbadges.education" 
            color="#1400FF" 
            underline="true"
            >OPENBADGES.EDUCATION</a></span>
            <br/>
            <span fontName="Rubik-Regular"> Der digitale Badge kann über den QR-Code abgerufen werden </span>
             <br/><br/>
    """
    first_page_content.append(Paragraph(content_html, issued_by_style))

    
def add_issuerImage(first_page_content, issuerImage): 
    image_width = 60
    image_height = 60
    first_page_content.append(Image(issuerImage, width=image_width, height=image_height))



@api_view(["GET"])
@authentication_classes([TokenAuthentication, SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def pdf(request, *args, **kwargs):
    slug = kwargs["slug"]
    try:
        badgeinstance = BadgeInstance.objects.get(entity_id=slug)

        # Get emails of all issuer owners
        """ issuer= Issuer.objects.get(entity_id=badgeinstance.issuer.entity_id)
        issuer_owners = issuer.staff.filter(issuerstaff__role=IssuerStaff.ROLE_OWNER)
        issuer_owners_emails = list(map(attrgetter('primary_email'), issuer_owners)) """

        # User must be the recipient or an issuer staff with OWNER role
        # TODO: Check other recipient types 
        # Temporary commented out
        """ if request.user.email != badgeinstance.recipient_identifier and request.user.email not in issuer_owners_emails:
            raise PermissionDenied """
    except BadgeInstance.DoesNotExist:
        raise Http404
    try:
        badgeclass = BadgeClass.objects.get(
            entity_id=badgeinstance.badgeclass.entity_id
        )
    except BadgeClass.DoesNotExist:
        raise Http404

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="badge.pdf"'

    competencies = badgeclass.json["extensions:CompetencyExtension"]

    first_page_content = []

    try:
        name = get_name(badgeinstance)
    except BadgeUser.DoesNotExist:
        # To resolve the issue with old awarded badges that doesn't include recipient-name and only have recipient-email
        # We use email as this is the only identifier we have 
        name = badgeinstance.recipient_identifier
        # raise Http404

    add_recipient_name(first_page_content, name, badgeinstance.issued_on) 
    
    addBadgeImage(first_page_content, badgeclass.image)

    add_title(first_page_content, badgeclass.name)  

    add_description(first_page_content, badgeclass.description)

    add_narrative(first_page_content, badgeinstance.narrative)

    add_issuedBy(first_page_content, badgeinstance.issuer.name, issuerImage=badgeclass.issuer.image)    

    create_multi_page(response, first_page_content, competencies, name, badgeclass.name, badgeImage=badgeclass.issuer.image , instituteName=badgeinstance.issuer.name)

    return response


class RedirectSharedCollectionView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        share_hash = kwargs.get("share_hash", None)
        if not share_hash:
            raise Http404

        try:
            collection = BackpackCollection.cached.get_by_slug_or_entity_id_or_id(
                share_hash
            )
        except BackpackCollection.DoesNotExist:
            raise Http404
        return collection.public_url


class LegacyCollectionShareRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        new_pattern_name = self.request.resolver_match.url_name.replace("legacy_", "")
        kwargs.pop("pk")
        url = reverse(new_pattern_name, args=args, kwargs=kwargs)
        return url


class LegacyBadgeShareRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        badgeinstance = None
        share_hash = kwargs.get("share_hash", None)
        if not share_hash:
            raise Http404

        try:
            badgeinstance = BadgeInstance.cached.get_by_slug_or_entity_id_or_id(
                share_hash
            )
        except BadgeInstance.DoesNotExist:
            pass

        if not badgeinstance:
            # legacy badge share redirects need to support lookup by pk
            try:
                badgeinstance = BadgeInstance.cached.get(pk=share_hash)
            except (BadgeInstance.DoesNotExist, ValueError):
                pass

        if not badgeinstance:
            raise Http404

        return badgeinstance.public_url
