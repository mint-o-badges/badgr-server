from collections import OrderedDict

from entity.serializers import DetailSerializerV2
from issuer.models import BadgeClass


# only for apispec for now

class BadgeClassSerializerV3(DetailSerializerV2):

   class Meta(DetailSerializerV2.Meta):
      model = BadgeClass
      apispec_definition = ('BadgeClass', {
         'properties': OrderedDict([
               ('entityId', {
                  'type': "string",
                  'format': "string",
                  'description': "Unique identifier for this BadgeClass",
                  'readOnly': True,
               }),
               ('entityType', {
                  'type': "string",
                  'format': "string",
                  'description': "\"BadgeClass\"",
                  'readOnly': True,
               }),
               ('openBadgeId', {
                  'type': "string",
                  'format': "url",
                  'description': "URL of the OpenBadge compliant json",
                  'readOnly': True,
               }),
               ('createdAt', {
                  'type': 'string',
                  'format': 'ISO8601 timestamp',
                  'description': "Timestamp when the BadgeClass was created",
                  'readOnly': True,
               }),
               ('createdBy', {
                  'type': 'string',
                  'format': 'entityId',
                  'description': "BadgeUser who created this BadgeClass",
                  'readOnly': True,
               }),

               ('issuer', {
                  'type': 'string',
                  'format': 'entityId',
                  'description': "entityId of the Issuer who owns the BadgeClass",
                  'required': False,
               }),

               ('name', {
                  'type': "string",
                  'format': "string",
                  'description': "Name of the BadgeClass",
                  'required': True,
               }),
               ('description', {
                  'type': "string",
                  'format': "string",
                  'description': "Short description of the BadgeClass",
                  'required': True,
               }),
               ('image', {
                  'type': "string",
                  'format': "data:image/png;base64",
                  'description': "Base64 encoded string of an image that represents the BadgeClass.",
                  'required': False,
               }),
               ('criteriaUrl', {
                  'type': "string",
                  'format': "url",
                  'description': ("External URL that describes in a human-readable "
                     "format the criteria for the BadgeClass"),
                  'required': False,
               }),
               ('criteriaNarrative', {
                  'type': "string",
                  'format': "markdown",
                  'description': "Markdown formatted description of the criteria",
                  'required': False,
               }),
               ('tags', {
                  'type': "array",
                  'items': {
                     'type': "string",
                     'format': "string"
                  },
                  'description': "List of tags that describe the BadgeClass",
                  'required': False,
               }),
               ('alignments', {
                  'type': "array",
                  'items': {
                     '$ref': '#/definitions/BadgeClassAlignment'
                  },
                  'description': "List of objects describing objectives or educational standards",
                  'required': False,
               }),
               ('expires', {
                  '$ref': "#/definitions/BadgeClassExpiration",
                  'description': "Expiration period for Assertions awarded from this BadgeClass",
                  'required': False,
               }),
         ])
      })