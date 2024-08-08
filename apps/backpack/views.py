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
from reportlab.platypus import SimpleDocTemplate, Flowable, Table, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from operator import attrgetter

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

    def draw(self):
        self.canv.setFillColor(self.fillcolor)
        self.canv.setStrokeColor(self.strokecolor)
        self.canv.roundRect(self.x, self.y, self.width, self.height, self.radius,
                             stroke=1, fill=1)
        
        self.canv.setFillColor('#323232')
        self.canv.setFont('Helvetica-Bold', 14)

        text_width = self.canv.stringWidth(self.text)
        name = self.text
        self.canv.drawString(self.x + 10, self.y + 15, name)
        
        self.canv.setFillColor('blue')
        if self.esco:
            self.canv.drawString(self.x + 10 + text_width, self.y + 15, " [E]")
            # the whole rectangle links to esco, instead of just the "[E]"
            self.canv.linkURL(f"http://data.europa.eu/{self.esco}", (self.x, self.y, self.width, self.height), relative=1, thickness=0)

        
        self.canv.setFillColor('#492E98')
        self.canv.setFont('Helvetica', 14)
        studyload_width = self.canv.stringWidth(self.studyload)
        self.canv.drawString(self.x + 450 -(studyload_width + 10), self.y + 15, self.studyload)

        svg_url = "{}images/clock_icon.svg".format(settings.STATIC_URL)
        response = requests.get(svg_url)
        svg_content = response.content

        with open('tempfile.svg', 'wb') as file:
            file.write(svg_content)

        drawing = svg2rlg('tempfile.svg')

        try:
            if drawing is not None:
               renderPDF.draw(drawing, self.canv, 450 - (studyload_width + 30), self.y + 12.5 )
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
    logo = ImageReader("{}images/Logo-Oeb.png".format(settings.STATIC_URL))
    canvas.drawImage(logo, 20, 675, width=150, height=150, mask="auto", preserveAspectRatio=True)
    page_width = canvas._pagesize[0]
    canvas.setStrokeColor("#492E98")
    canvas.line(page_width / 2 - 75, 750, page_width / 2 + 250, 750)

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

def create_multi_page(response, first_page_content, competencies, name, badge_name):
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
            competenciesPerPage = 5

            Story.append(PageBreak())
            Story.append(Spacer(1, 75))

            title_style = ParagraphStyle(name='Title', fontSize=24, textColor='#492E98', alignment=TA_LEFT)
            text_style = ParagraphStyle(name='Text', fontSize=18, leading=20, textColor='#323232', alignment=TA_LEFT)

            Story.append(Paragraph("<strong>Kompetenzen</strong>", title_style))
            Story.append(Spacer(1, 25))
            
            text = f"die <strong>{name}</strong> mit dem Badge <strong>{badge_name}</strong> erworben hat:"
            Story.append(Paragraph(text, text_style))
            Story.append(Spacer(1, 20))

            text_style = ParagraphStyle(name='Text', fontSize=18, leading=16, textColor='#492E98', alignment=TA_LEFT)      

            for i in range(num_competencies):
              if i != 0 and i % competenciesPerPage == 0: 
                Story.append(PageBreak())
                Story.append(Spacer(1, 75))
                Story.append(Paragraph("<strong>Kompetenzen</strong>", title_style))
                Story.append(Spacer(1, 25))

                text = f"die <strong>{name}</strong> mit dem Badge"
                Story.append(Paragraph(text, text_style))
                Story.append(Spacer(1, 20))


                text = " <strong>%s</strong> erworben hat:" % badge_name
                Story.append(Paragraph(text, text_style)) 
                Story.append(Spacer(1, 20)) 

              studyload = "%s Minuten" % competencies[i]['studyLoad']
              if competencies[i]['studyLoad'] > 120:
                  studyLoadInHours = competencies[i]['studyLoad'] / 60
                  studyload = "%s Stunden" % int(studyLoadInHours)
              competency_name = competencies[i]['name']
              competency = (competency_name[:35] + '...') if len(competency_name) > 35 else competency_name
              rounded_rect = RoundedRectFlowable(0, -10, 450, 45, 10, text=competency, strokecolor="#492E98", fillcolor="#F5F5F5", studyload= studyload, esco=competencies[i]['escoID'])    
              Story.append(rounded_rect)
              Story.append(Spacer(1, 20))   
                 
            if esco: 
                Story.append(Spacer(1, 25))
                text_style = ParagraphStyle(name='Text_Style', fontSize=12, leading=20, alignment=TA_LEFT)
                link_text = '<span><i>(E) = Kompetenz nach ESCO (European Skills, Competences, Qualifications and Occupations) <br/>' \
                    'Die Kompetenzbeschreibungen gemäß ESCO sind abrufbar über <a color="blue" href="https://esco.ec.europa.eu/de">https://esco.ec.europa.eu/de</a>.</i></span>'
                paragraph_with_link = Paragraph(link_text, text_style)
                Story.append(paragraph_with_link) 
           
    doc.build(Story, onFirstPage=AllPageSetup, onLaterPages=AllPageSetup, canvasmaker=PageNumCanvas)   

def addBadgeImage(first_page_content, badgeImage): 
    image_width = 250
    image_height = 250
    first_page_content.append(Image(badgeImage, width=image_width, height=image_height))

def add_recipient_name(first_page_content, name, issuedOn):
    first_page_content.append(Spacer(1, 50))
    recipient_style = ParagraphStyle(name='Recipient', fontSize=24, textColor='#492E98', alignment=TA_CENTER)
    
    recipient_name = f"<strong>{name}</strong>"
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
    if(len(badge_class_name) > 30):
        first_page_content.append(Spacer(1, 15))
    else:
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
    first_page_content.append(Spacer(1, 10))

def add_issuedBy(first_page_content, issued_by):
    issued_by_style = ParagraphStyle(name='Issued_By', fontSize=18, textColor='#492E98', alignment=TA_CENTER)
    text = "- Vergeben von: " + f"<strong>{issued_by}</strong> -"
    first_page_content.append(Paragraph(text, issued_by_style))
    first_page_content.append(Spacer(1, 15))

def add_issuerImage(first_page_content, issuerImage): 
    image_width = 60
    image_height = 60
    first_page_content.append(Image(issuerImage, width=image_width, height=image_height))

def get_name(badgeinstance: BadgeInstance):
    """Evaluates the name to be displayed for the recipient of the badge.
    
    This is either the name that was specified in the award process of the badge
    (which is by now mandatory) or, if none was specified, the full profile of the
    recipient. If no name was specified and the profile can't be found, a
    `BadgeUser.DoesNotExist` exception is thrown.
    """
    recipientProfile = badgeinstance.extension_items.get('extensions:recipientProfile', {})
    name = recipientProfile.get('name', None)
    if name:
        return name
    
    badgeuser = BadgeUser.objects.get(email=badgeinstance.recipient_identifier)  
    first_name = badgeuser.first_name.capitalize()
    last_name = badgeuser.last_name.capitalize()
    return f"{first_name} {last_name}"

@api_view(["GET"])
@authentication_classes([TokenAuthentication, SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def pdf(request, *args, **kwargs):
    slug = kwargs["slug"]
    try:
        badgeinstance = BadgeInstance.objects.get(entity_id=slug)

        # Get emails of all issuer owners
        issuer= Issuer.objects.get(entity_id=badgeinstance.issuer.entity_id)
        issuer_owners = issuer.staff.filter(issuerstaff__role=IssuerStaff.ROLE_OWNER)
        issuer_owners_emails = list(map(attrgetter('primary_email'), issuer_owners))

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

    add_issuedBy(first_page_content, badgeinstance.issuer.name)

    try:
        add_issuerImage(first_page_content, badgeclass.issuer.image)
    except: 
        pass    

    create_multi_page(response, first_page_content, competencies, name, badgeclass.name)

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
