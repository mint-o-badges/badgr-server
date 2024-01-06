import base64
import binascii
import mimetypes
import urllib.parse
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import ugettext as _
from rest_framework.fields import FileField, SkipField

from mainsite.validators import ValidImageValidator


class Base64FileField(FileField):

    # mimetypes.guess_extension() may return different values for same mimetype, but we need one extension for one mime
    _MIME_MAPPING = {
        'image/jpeg': '.jpg',
        'audio/wav': '.wav',
        'image/svg+xml': '.svg'
    }
    _ERROR_MESSAGE = _('Base64 string is incorrect')

    def to_internal_value(self, data):
        if isinstance(data, UploadedFile):
            return super(Base64FileField, self).to_internal_value(data)

        try:
            mime, encoded_data = data.replace('data:', '', 1).split(';base64,')
            extension = self._MIME_MAPPING[mime] if mime in list(
                self._MIME_MAPPING.keys()) else mimetypes.guess_extension(mime)
            if extension is None:
                raise ValidationError('Invalid MIME type')
            ret = ContentFile(base64.b64decode(encoded_data), name='{name}{extension}'.format(name=str(uuid.uuid4()),
                                                                                              extension=extension))
            return ret
        except (ValueError, binascii.Error):
            return super(Base64FileField, self).to_internal_value(data)


class ValidImageField(Base64FileField):
    default_validators = [ValidImageValidator()]

    def __init__(self, skip_http=True, allow_empty_file=False, use_url=True, allow_null=True, **kwargs):
        self.skip_http = skip_http
        self.use_public = kwargs.pop('use_public', False)

        super(ValidImageField, self).__init__(
            allow_empty_file=allow_empty_file, use_url=use_url, allow_null=allow_null, **kwargs
        )

    def to_internal_value(self, data):
        # Skip http/https urls to avoid overwriting valid data when, for example, a client GETs and subsequently PUTs an
        # entity containing an image URL.
        if self.skip_http and not isinstance(data, UploadedFile) and urllib.parse.urlparse(data).scheme in ('http', 'https'):
            raise SkipField()

        self.source_attrs = ['image']  # Kind of a dirty hack, because this is failing to stick if set on init.
        return super(ValidImageField, self).to_internal_value(data)

    def to_representation(self, value):
        if self.use_public:
            try:
                if getattr(value, 'instance', None):
                    return value.instance.image_url(public=True)  # sometimes value is a FileField despite source="*"
                return value.image_url(public=True)
            except AttributeError:
                pass
        try:
            return super(ValidImageField, self).to_representation(value.image)
        except AttributeError:
            return super(ValidImageField, self).to_representation(value)
