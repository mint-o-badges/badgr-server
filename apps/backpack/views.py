import math
from django.urls import reverse
from django.conf import settings
from django.http import Http404
from django.views.generic import RedirectView

from backpack.models import BackpackCollection
from issuer.models import BadgeInstance, BadgeClass
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
from reportlab.platypus import SimpleDocTemplate, Flowable, Table, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

class RoundedRectFlowable(Flowable):
    def __init__(self, x, y, width, height, radius, text, strokecolor):
        super().__init__()
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.radius = radius
        self.strokecolor = strokecolor
        self.text = text

    def draw(self):
        self.canv.setFillColor(self.strokecolor)
        self.canv.setStrokeColor(self.strokecolor)
        self.canv.roundRect(self.x, self.y, self.width, self.height, self.radius,
                             stroke=1, fill=0)
        
        self.canv.setFontSize(14)
        text_width = self.canv.stringWidth(self.text)
        text_x = self.x + (self.width - text_width) / 2 + 10
        text_y = self.y + (self.height - 14) / 2
        self.canv.drawString(text_x, text_y, self.text)

        svg_url = "{}images/clock_icon.svg".format(settings.STATIC_URL)
        response = requests.get(svg_url)
        svg_content = response.content

        with open('tempfile.svg', 'wb') as file:
            file.write(svg_content)

        drawing = svg2rlg('tempfile.svg')
        renderPDF.draw(drawing, self.canv, 10, -10)

        try:
            if drawing is not None:
               renderPDF.draw(drawing, self.canv, 10, -10)
        except Exception as e:
            print(e)
        
def AllPageSetup(canvas, doc):

    canvas.saveState()

    # Sunburst Background
    color = PCMYKColor(0, 0, 0, 5)  
    num_rays = 100
    ray_angle = 2 * math.pi / num_rays
    sweep_angle = ray_angle * 2

    page_width, page_height = A4
    mid_x = page_width / 2
    mid_y = page_height / 2
    radius = math.sqrt(mid_x**2 + mid_y**2)
    offset_y = 20
    mid_y_offset = mid_y - offset_y

    for i in range(num_rays):
        start_angle = sweep_angle * i
        end_angle = start_angle + ray_angle
        start_x = mid_x + radius * math.cos(start_angle)
        start_y = mid_y_offset + radius * math.sin(start_angle)
        end_x = mid_x + radius * math.cos(end_angle)
        end_y = mid_y_offset + radius * math.sin(end_angle)
        path = canvas.beginPath()
        path.moveTo(mid_x, mid_y_offset)
        path.arcTo(
            start_x,
            start_y,
            end_x,
            end_y,
            start_angle * 180 / math.pi,
        )
        canvas.setFillColor(color)
        canvas.setStrokeColor(color)
        canvas.drawPath(path, fill=1, stroke=1)

    # Header
    logo = ImageReader("{}images/Logo-New.png".format(settings.STATIC_URL))
    canvas.drawImage(logo, 10, 650, width=200, height=200, mask="auto", preserveAspectRatio=True)
    page_width = canvas._pagesize[0]
    canvas.setStrokeColor("#492E98")
    canvas.line(page_width / 2 - 100, 750, page_width / 2 + 250, 750)

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
        self.line(10, 10, page_width / 2 - 20, 10)
        self.line(page_width  / 2 + 20, 10, page_width - 10, 10)
        self.setFont("Helvetica", 9)
        self.drawCentredString(page_width / 2, 10, page)

def createMultiPage(response, first_page_content, competencies, first_name, last_name, badge_name):
    """
    Create a multi-page pdf document
    """
    
    doc = SimpleDocTemplate(response,pagesize=A4)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
    
    Story = []

    # Add first page content to the story
    Story.extend(first_page_content)

    num_competencies = len(competencies)

    if num_competencies > 0:
            esco = any(c['escoID'] for c in competencies)
            competenciesPerPage = 7

            Story.append(PageBreak())
            Story.append(Spacer(1, 75))

            title_style = ParagraphStyle(name='Title', fontSize=24, textColor='#492E98', alignment=TA_LEFT)
            text_style = ParagraphStyle(name='Text', fontSize=14, textColor='#492E98', alignment=TA_LEFT)

            Story.append(Paragraph("<strong>Kompetenzen</strong>", title_style))
            Story.append(Spacer(1, 25))


            text = "die <strong>%s %s</strong> mit dem Badge" % (first_name, last_name)
            Story.append(Paragraph(text, text_style))
            Story.append(Spacer(1, 20))


            text = " <strong>%s</strong> erworben hat:" % badge_name
            Story.append(Paragraph(text, text_style)) 
            Story.append(Spacer(1, 20)) 

            text_style = ParagraphStyle(name='Text', fontSize=18, leading=16, textColor='#492E98', alignment=TA_LEFT)      

            for i in range(num_competencies):
              if i != 0 and i % competenciesPerPage == 0: 
                Story.append(PageBreak())
                Story.append(Spacer(1, 75))
                Story.append(Paragraph("<strong>Kompetenzen</strong>", title_style))
                Story.append(Spacer(1, 25))

                text = "die <strong>%s %s</strong> mit dem Badge" % (first_name, last_name)
                Story.append(Paragraph(text, text_style))
                Story.append(Spacer(1, 20))


                text = " <strong>%s</strong> erworben hat:" % badge_name
                Story.append(Paragraph(text, text_style)) 
                Story.append(Spacer(1, 20)) 

              text = "%s Minuten" % competencies[i]['studyLoad']
              if competencies[i]['studyLoad'] > 120:
                  studyLoadInHours = competencies[i]['studyLoad'] / 120
                  text = "%s Stunden" % int(studyLoadInHours)
              rounded_rect = RoundedRectFlowable(0, -7.5, 120, 30, 15, text=text, strokecolor="#492E98")
              competency = competencies[i]['name']
              if competencies[i]['escoID'] is not None:
                    competency = competency + " *"
              info = (competency[:20] + '...') if len(competency) > 20 else competency
              tbl_data = [
                    [rounded_rect, Paragraph(info,text_style)]
              ]
              Story.append(Table(tbl_data, style=[('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))     
              Story.append(Spacer(1, 20))   
                 
            if esco: 
                Story.append(Spacer(1, 100))
                text_style = ParagraphStyle(name='Text_Style', fontSize=14, alignment=TA_LEFT)
                link_text = '<a href="https://esco.ec.europa.eu/de">* Kompetenz nach ESCO: https://esco.ec.europa.eu/de</a>'
                paragraph_with_link = Paragraph(link_text, text_style)
                Story.append(paragraph_with_link) 
           
    doc.build(Story, onFirstPage=AllPageSetup, onLaterPages=AllPageSetup, canvasmaker=PageNumCanvas)   

def addBadgeImage(first_page_content, badgeImage): 
    image_width = 250
    image_height = 250
    first_page_content.append(Image(badgeImage, width=image_width, height=image_height))

def add_recipient_name(first_page_content, first_name, last_name, issuedOn):
    first_page_content.append(Spacer(1, 50))
    recipient_style = ParagraphStyle(name='Recipient', fontSize=24, textColor='#492E98', alignment=TA_CENTER)
    
    recipient_name = f"<strong>{first_name} {last_name}</strong>"
    first_page_content.append(Paragraph(recipient_name, recipient_style))
    first_page_content.append(Spacer(1, 35))

    text_style = ParagraphStyle(name='Text_Style', fontSize=18, alignment=TA_CENTER)
    
    text = "hat am " + issuedOn.strftime("%d.%m.%Y")
    first_page_content.append(Paragraph(text, text_style))
    first_page_content.append(Spacer(1, 10))

    text = "den folgenden Badge erworben:"
    first_page_content.append(Paragraph(text, text_style))
    first_page_content.append(Spacer(1, 35))

def add_title(first_page_content, badge_class_name):

    title_style = ParagraphStyle(name='Title', fontSize=24, textColor='#492E98', leading=30, alignment=TA_CENTER)
    first_page_content.append(Paragraph(f"<strong>{badge_class_name}</strong>", title_style))
    first_page_content.append(Spacer(1, 35))

def truncate_text(text, max_words=50):
    words = text.split()
    if len(words) > max_words:
        return ' '.join(words[:max_words]) + '...'
    else:
        return text

def add_description(first_page_content, description):
    description_style = ParagraphStyle(name='Description', fontSize=14, leading=16, alignment=TA_CENTER)
    first_page_content.append(Paragraph(truncate_text(description), description_style))
    first_page_content.append(Spacer(1, 20))

def add_issuedBy(first_page_content, issued_by):
    issued_by_style = ParagraphStyle(name='Issued_By', fontSize=18, textColor='#492E98', alignment=TA_CENTER)
    text = "- Vergeben von: " + f"<strong>{issued_by}</strong> -"
    first_page_content.append(Paragraph(text, issued_by_style))
    first_page_content.append(Spacer(1, 15))

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
    except BadgeInstance.DoesNotExist:
        raise Http404
    try:
        badgeclass = BadgeClass.objects.get(
            entity_id=badgeinstance.badgeclass.entity_id
        )
    except BadgeClass.DoesNotExist:
        raise Http404

    try: 
        badgeuser = BadgeUser.objects.get(email=badgeinstance.recipient_identifier)  
    except BadgeUser.DoesNotExist:
        raise Http404

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="badge.pdf"'

    competencies = badgeclass.json["extensions:CompetencyExtension"]

    first_page_content = []

    first_name = badgeuser.first_name.capitalize()
    last_name = badgeuser.last_name.capitalize()

    add_recipient_name(first_page_content, first_name, last_name, badgeinstance.issued_on) 

    addBadgeImage(first_page_content, badgeclass.image)

    add_title(first_page_content, badgeclass.name)  

    add_description(first_page_content, badgeclass.description)

    add_issuedBy(first_page_content, badgeinstance.issuer.name)

    try:
        add_issuerImage(first_page_content, badgeclass.issuer.image)
    except: 
        pass    

    createMultiPage(response, first_page_content, competencies, first_name, last_name, badgeclass.name)

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
