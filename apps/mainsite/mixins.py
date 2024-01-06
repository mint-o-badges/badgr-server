import io

from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from resizeimage.resizeimage import resize_contain

from defusedxml.cElementTree import parse as safe_parse

from mainsite.utils import verify_svg, scrubSvgElementTree, hash_for_image


def _decompression_bomb_check(image, max_pixels=Image.MAX_IMAGE_PIXELS):
    pixels = image.size[0] * image.size[1]
    return pixels > max_pixels


class HashUploadedImage(models.Model):
    # Adds new django field
    image_hash = models.CharField(max_length=72, blank=True, default='')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        original_hash = self.image_hash
        pending_hash = self.hash_for_image_if_open()
        changed = pending_hash is not None and pending_hash != original_hash
        if changed:
            self.image_hash = pending_hash
        result = super(HashUploadedImage, self).save(*args, **kwargs)

        if changed and self.pk:
            self.schedule_image_update_task()

        return result

    def hash_for_image_if_open(self):
        if self.image and not self.image.closed:
            return hash_for_image(self.image)
        return None

    def schedule_image_update_task(self):
        """
        Override this to perform logic if the image hash has updated during a save().
        :return: None
        """
        pass


class PngImagePreview(object):
    def save(self, *args, **kwargs):
        # Check that conversions are enabled and that an image was uploaded.
        if getattr(settings, 'SVG_HTTP_CONVERSION_ENABLED', False) and kwargs.get('force_resize'):
            # Set this to None to ensure that we make a updated preview image later in post_save.
            self.image_preview = None

        return super(PngImagePreview, self).save(*args, **kwargs)


class ResizeUploadedImage(object):

    def save(self, force_resize=False, *args, **kwargs):
        if (self.pk is None and self.image) or force_resize:
            try:
                image = Image.open(self.image)
                if _decompression_bomb_check(image):
                    raise ValidationError("Invalid image")
            except IOError:
                return super(ResizeUploadedImage, self).save(*args, **kwargs)

            if image.format == 'PNG':
                max_square = getattr(settings, 'IMAGE_FIELD_MAX_PX', 400)

                smaller_than_canvas = \
                    (image.width < max_square and image.height < max_square)

                if smaller_than_canvas:
                    max_square = (image.width
                                  if image.width > image.height
                                  else image.height)

                new_image = resize_contain(image, (max_square, max_square))

                byte_string = io.BytesIO()
                new_image.save(byte_string, 'PNG')

                self.image = InMemoryUploadedFile(byte_string, None,
                                                  self.image.name, 'image/png',
                                                  byte_string.tell(), None)

        return super(ResizeUploadedImage, self).save(*args, **kwargs)


class ScrubUploadedSvgImage(object):

    def save(self, *args, **kwargs):
        if self.image and verify_svg(self.image.file):
            self.image.file.seek(0)

            tree = safe_parse(self.image.file)
            scrubSvgElementTree(tree.getroot())

            buf = io.BytesIO()
            tree.write(buf)

            self.image = InMemoryUploadedFile(buf, 'image', self.image.name, 'image/svg+xml', buf.tell(), 'utf8')
        return super(ScrubUploadedSvgImage, self).save(*args, **kwargs)
