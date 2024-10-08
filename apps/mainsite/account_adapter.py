from io import BytesIO
import logging
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse
import os

from allauth.account.adapter import DefaultAccountAdapter, get_adapter
from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
from allauth.account.utils import user_pk_to_url_str
from allauth.exceptions import ImmediateHttpResponse
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.urls import resolve, Resolver404, reverse
from django.utils.safestring import mark_safe

from issuer.models import BadgeClass, BadgeInstance
from badgeuser.authcode import authcode_for_accesstoken
from badgeuser.models import BadgeUser, CachedEmailAddress
import badgrlog
from badgrsocialauth.utils import set_session_badgr_app
from mainsite.models import BadgrApp, EmailBlacklist, AccessTokenProxy
from mainsite.utils import get_name, OriginSetting, set_url_query_params
from backpack.views import add_recipient_name, add_title, add_description, add_narrative, addBadgeImage, add_issuedBy, RoundedRectFlowable, AllPageSetup, PageNumCanvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT

logger = badgrlog.BadgrLogger()

class BadgrAccountAdapter(DefaultAccountAdapter):

    def generate_pdf_content(self, slug):
        if slug is None:
            raise ValueError("Missing slug parameter")
        
        try:
            badgeinstance = BadgeInstance.objects.get(entity_id=slug)
        except BadgeInstance.DoesNotExist:
            raise ValueError("BadgeInstance not found")
        try:
            badgeclass = BadgeClass.objects.get(
                entity_id=badgeinstance.badgeclass.entity_id
            )
        except BadgeClass.DoesNotExist:
            raise ValueError("BadgeClass not found")

        name = None
        try:
            name = get_name(badgeinstance)
        except BadgeUser.DoesNotExist:
            logger = logging.getLogger(__name__)
            logger.warning("Could not find badgeuser")
        
        first_page_content = []
        add_recipient_name(first_page_content, name, badgeinstance.issued_on) 

        competencies = badgeclass.json["extensions:CompetencyExtension"]


        addBadgeImage(first_page_content, badgeclass.image)

        add_title(first_page_content, badgeclass.name)  

        add_description(first_page_content, badgeclass.description)

        add_narrative(first_page_content, badgeinstance.narrative)

        add_issuedBy(first_page_content, badgeinstance.issuer.name, badgeclass.issuer.image)    
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
    
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
                Story.append(Spacer(1, 35))

                title_style = ParagraphStyle(name='Title', fontSize=20, textColor='#492E98', alignment=TA_LEFT)
                text_style = ParagraphStyle(name='Text', fontSize=18, leading=20, textColor='#323232', alignment=TA_LEFT)



                Story.append(Paragraph("<strong>Kompetenzen</strong>", title_style))
                Story.append(Spacer(1, 15))


                if name:
                     text = f"die <strong>{name}</strong> mit dem Badge <strong>{badgeclass.name}</strong> erworben hat:"
                else: 
                    text = f"die <strong>%s</strong> mit dem Badge <strong>{badgeclass.name}</strong> erworben hat:" % badgeinstance.recipient_identifier    
                Story.append(Paragraph(text, text_style))
                Story.append(Spacer(1, 20))


                text_style = ParagraphStyle(name='Text', fontSize=18, leading=20, textColor='#323232', alignment=TA_LEFT)
      

                for i in range(num_competencies):
                    if i != 0 and i % competenciesPerPage == 0: 
                        Story.append(PageBreak())
                        Story.append(Spacer(1, 35))
                        Story.append(Paragraph("<strong>Kompetenzen</strong>", title_style))
                        Story.append(Spacer(1, 15))

                        if name:
                            text = f"die <strong>%s</strong> mit dem Badge <strong>{badgeclass.name}</strong> erworben hat:" % (name)
                        else: 
                            text = f"die <strong>%s</strong> mit dem Badge <strong>{badgeclass.name}</strong> erworben hat:" % badgeinstance.recipient_identifier    
                        Story.append(Paragraph(text, text_style))
                        Story.append(Spacer(1, 20))

                    studyload = "%s min" % competencies[i]['studyLoad']
                    if competencies[i]['studyLoad'] > 120:
                        studyload = "%s h" % int(competencies[i]['studyLoad'] / 60 )
                    competency_name = competencies[i]['name']
                    competency = competency_name
                    rounded_rect = RoundedRectFlowable(0, -1, 450, 45, 10, text=competency, strokecolor="#492E98", fillcolor="#F5F5F5", studyload = studyload, esco = competencies[i]['escoID'])

                    Story.append(rounded_rect)    
                    Story.append(Spacer(1, 10))   
                    
                if esco: 
                    Story.append(Spacer(1, 10))
                    text_style = ParagraphStyle(name='Text_Style', fontSize=12, leading=15.6, alignment=TA_LEFT, leftIndent=-35, rightIndent=-35)
                    link_text = '<span><i>(E) = Kompetenz nach ESCO (European Skills, Competences, Qualifications and Occupations) <br/>' \
                    'Die Kompetenzbeschreibungen gemäß ESCO sind abrufbar über <a color="blue" href="https://esco.ec.europa.eu/de">https://esco.ec.europa.eu/de</a>.</i></span>'
                    paragraph_with_link = Paragraph(link_text, text_style)
                    Story.append(paragraph_with_link) 
            
        doc.build(Story, onFirstPage=AllPageSetup, onLaterPages=AllPageSetup, canvasmaker=PageNumCanvas) 
        
        pdf_content = buffer.getvalue()
        
        buffer.close()
        
        return pdf_content

    EMAIL_FROM_STRING = ''

    def send_mail(self, template_prefix, email, context):
        context['STATIC_URL'] = getattr(settings, 'STATIC_URL')
        context['HTTP_ORIGIN'] = getattr(settings, 'HTTP_ORIGIN')
        context['PRIVACY_POLICY_URL'] = getattr(settings, 'PRIVACY_POLICY_URL', None)
        context['TERMS_OF_SERVICE_URL'] = getattr(settings, 'TERMS_OF_SERVICE_URL', None)
        context['GDPR_INFO_URL'] = getattr(settings, 'GDPR_INFO_URL', None)
        context['OPERATOR_STREET_ADDRESS'] = getattr(settings, 'OPERATOR_STREET_ADDRESS', None)
        context['OPERATOR_NAME'] = getattr(settings, 'OPERATOR_NAME', None)
        context['OPERATOR_URL'] = getattr(settings, 'OPERATOR_URL', None)

        if context.get('unsubscribe_url', None) is None:
            try:
                badgrapp_pk = context['badgr_app'].pk
            except (KeyError, AttributeError):
                badgrapp_pk = None
            context['unsubscribe_url'] = getattr(settings, 'HTTP_ORIGIN') + EmailBlacklist.generate_email_signature(
                email, badgrapp_pk)

        self.EMAIL_FROM_STRING = self.set_email_string(context)
        
        if template_prefix == 'issuer/email/notify_account_holder':
            context['mbr_block'] = True


        msg = self.render_mail(template_prefix, email, context)
        # badge_id is equal to the badge instance slug
        if template_prefix == 'issuer/email/notify_account_holder' or template_prefix == 'issuer/email/notify_earner':
            pdf_document = context['pdf_document']
            badge_name = f"{context['badge_name']}.badge"
            img_path = os.path.join(settings.MEDIA_ROOT, "uploads", "badges", "assertion-{}.png".format(context.get('badge_id', None)))
            with open(img_path, 'rb') as f:
                badge_img = f.read()
            msg.attach(badge_name + '.png', badge_img, "badge_image/png")
            msg.attach(badge_name + '.pdf', pdf_document,'badge_certificate/pdf')
        logger.event(badgrlog.EmailRendered(msg))
        msg.send()

    def set_email_string(self, context):
        # site_name should not contain commas.
        # email sender name
        from_elements = [context.get('site_name', 'Open Educational Badges').replace(',', '')]

        # DEFAULT_FROM_EMAIL must not already have < > in it.
        default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        if not default_from:
            raise NotImplementedError("DEFAULT_FROM_EMAIL setting must be defined.")
        elif '<' in default_from:
            return default_from
        else:
            from_elements.append("<{}>".format(default_from))

        return " ".join(from_elements)

    def get_from_email(self):
        return self.EMAIL_FROM_STRING

    def is_open_for_signup(self, request):
        return getattr(settings, 'OPEN_FOR_SIGNUP', True)

    def get_email_confirmation_redirect_url(self, request, badgr_app=None):
        """
        The URL to return to after successful e-mail confirmation.
        """
        if badgr_app is None:
            badgr_app = BadgrApp.objects.get_current(request)
            if not badgr_app:
                logger = logging.getLogger(self.__class__.__name__)
                logger.warning("Could not determine authorized badgr app")
                return super(BadgrAccountAdapter, self).get_email_confirmation_redirect_url(request)

        try:
            resolver_match = resolve(request.path)
            confirmation = EmailConfirmationHMAC.from_key(resolver_match.kwargs.get('confirm_id'))
            # publish changes to cache
            email_address = CachedEmailAddress.objects.get(pk=confirmation.email_address.pk)
            email_address.publish()

            query_params = {
                'email': email_address.email.encode('utf8')
            }
            # Pass source and signup along to UI
            source = request.query_params.get('source', None)
            if source:
                query_params['source'] = source

            signup = request.query_params.get('signup', None)
            if signup:
                query_params['signup'] = 'true'
                return set_url_query_params(badgr_app.get_path('/auth/welcome'), **query_params)
            else:
                return set_url_query_params(urllib.parse.urljoin(
                    badgr_app.email_confirmation_redirect.rstrip('/') + '/',
                    urllib.parse.quote(email_address.user.first_name.encode('utf8'))
                ), **query_params)

        except Resolver404 as xxx_todo_changeme:
            EmailConfirmation.DoesNotExist = xxx_todo_changeme
            return badgr_app.email_confirmation_redirect

    def get_email_confirmation_url(self, request, emailconfirmation, signup=False):
        url_name = "v1_api_user_email_confirm"
        temp_key = default_token_generator.make_token(emailconfirmation.email_address.user)
        token = "{uidb36}-{key}".format(uidb36=user_pk_to_url_str(emailconfirmation.email_address.user),
                                        key=temp_key)
        activate_url = OriginSetting.HTTP + reverse(url_name, kwargs={'confirm_id': emailconfirmation.key})
        badgrapp = BadgrApp.objects.get_current(request=request)
        tokenized_activate_url = "{url}?token={token}&a={badgrapp}".format(
            url=activate_url,
            token=token,
            badgrapp=badgrapp.id
        )

        # Add source and signup query params to the confimation url
        if request:
            source = None
            if hasattr(request, 'data'):
                source = request.data.get('source', None)
            elif hasattr(request, 'session'):
                source = request.session.get('source', None)

            if source:
                tokenized_activate_url = set_url_query_params(tokenized_activate_url, source=source)

            if signup:
                tokenized_activate_url = set_url_query_params(tokenized_activate_url, signup="true")

        return tokenized_activate_url

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        current_site = get_current_site(request)
        activate_url = self.get_email_confirmation_url(
            request,
            emailconfirmation,
            signup)
        badgr_app = BadgrApp.objects.get_current(request, raise_exception=False)
        ctx = {
            "user": emailconfirmation.email_address.user,
            "email": emailconfirmation.email_address,
            "activate_url": mark_safe(activate_url),
            "current_site": current_site,
            "key": emailconfirmation.key,
            "badgr_app": badgr_app,
        }
        if signup:
            email_template = 'account/email/email_confirmation_signup'
        else:
            email_template = 'account/email/email_confirmation'
        get_adapter().send_mail(email_template,
                                emailconfirmation.email_address.email,
                                ctx)

    def get_login_redirect_url(self, request):
        """
        If successfully logged in, redirect to the front-end, including an authToken query parameter.
        """
        if request.user.is_authenticated:
            badgr_app = BadgrApp.objects.get_current(self.request)

            if badgr_app is not None:
                accesstoken = AccessTokenProxy.objects.generate_new_token_for_user(
                    request.user,
                    application=badgr_app.oauth_application if badgr_app.oauth_application_id else None,
                    scope='rw:backpack rw:profile rw:issuer')

                if badgr_app.use_auth_code_exchange:
                    authcode = authcode_for_accesstoken(accesstoken)
                    params = dict(authCode=authcode)
                else:
                    params = dict(authToken=accesstoken.token)

                return set_url_query_params(badgr_app.ui_login_redirect, **params)
        else:
            return '/'

    def login(self, request, user):
        """
        Guard against unverified users and preserve badgr_app session data
        across Django login() boundary.
        """
        badgr_app = BadgrApp.objects.get_current(request)

        if not user.verified and badgr_app.ui_login_redirect != badgr_app.ui_signup_success_redirect:
            # The usual case if a user gets here without a verified recipient
            # identifier is a new sign-up with an unverified email. If that's
            # the case, we just sent them a confirmation.
            # This is for UI clients that do not have the ability to function without a verified user identifier
            raise ImmediateHttpResponse(
                self.respond_email_verification_sent(request, user))

        ret = super(BadgrAccountAdapter, self).login(request, user)
        set_session_badgr_app(request, badgr_app)
        return ret

    def logout(self, request):
        badgrapp_pk = request.session.get('badgr_app_pk')
        super(BadgrAccountAdapter, self).logout(request)
        if badgrapp_pk:
            request.session['badgr_app_pk'] = badgrapp_pk
