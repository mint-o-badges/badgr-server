from PIL import Image
import cairosvg
import io
import os
import base64
from django.contrib.staticfiles import finders
import logging

logger = logging.getLogger(__name__)


class ImageComposer:
    # canvas sizes by svg viewbox
    CANVAS_SIZES = {
        "participation": (400, 400),
        "competency": (412, 411),
        "learningpath": (416, 416),
    }

    DEFAULT_CANVAS_SIZE = (400, 400)

    MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB
    MAX_DIMENSIONS = (512, 512)
    ALLOWED_FORMATS = {"PNG", "SVG"}

    def __init__(self, category=None):
        self.category = category
        self.CANVAS_SIZE = self.CANVAS_SIZES.get(category, self.DEFAULT_CANVAS_SIZE)

    def get_canvas_size(self, category):
        """Get canvas size for specific category"""
        return self.CANVAS_SIZES.get(category, self.DEFAULT_CANVAS_SIZE)

    def compose_badge_from_uploaded_image(self, image, issuerImage):
        """
        Compose badge image with issuer logo from image upload
        """
        try:
            canvas = Image.new("RGBA", self.CANVAS_SIZE, (255, 255, 255, 0))

            ### Frame ###

            shape_image = self._get_colored_shape_svg()
            if shape_image:
                canvas.paste(shape_image, (0, 0), shape_image)

            ### badge image ###
            badge_img = self._prepare_uploaded_image(image)
            if badge_img:
                canvas.paste(badge_img, (100, 100), badge_img)

            ### issuer logo ###
            if issuerImage:
                canvas = self._add_issuer_logo(canvas, self.category, issuerImage)

            return self._get_image_as_base64(canvas)

        except Exception as error:
            print(f"Error generating badge image from upload: {error}")
            raise error

    def _get_image_as_base64(self, canvas):
        """
        Convert PIL Image to base64
        """
        img_buffer = io.BytesIO()
        canvas.save(img_buffer, format="PNG", quality=95)
        img_buffer.seek(0)

        import base64

        img_base64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{img_base64}"

    def _prepare_uploaded_image(self, image_data):
        """
        Prepare uploaded image data (base64 string)
        """
        try:
            if isinstance(image_data, str):
                if image_data.startswith("data:image/"):
                    header, data = image_data.split(",", 1)
                    image_bytes = base64.b64decode(data)
                else:
                    # Handle base64 string without header
                    image_bytes = base64.b64decode(image_data)

                img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            else:
                raise ValueError("Expected base64 string for image data")

            target_size = (self.CANVAS_SIZE[0] // 2, self.CANVAS_SIZE[1] // 2)

            # Resize maintaining aspect ratio
            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            # Create centered image
            result = Image.new("RGBA", target_size, (0, 0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            result.paste(img, (x, y), img)

            return result

        except Exception as e:
            logger.error(f"Error preparing uploaded image: {e}")
            raise e

    def _get_colored_shape_svg(self):
        """
        Load SVG and convert to PIL Image
        """
        try:
            svg_files = {
                "participation": "participation.svg",
                "competency": "competency.svg",
                "learningpath": "learningpath.svg",
            }

            svg_filename = svg_files.get(self.category, "participation.svg")
            svg_path = finders.find(f"images/{svg_filename}")

            if not os.path.exists(svg_path):
                raise (f"SVG file not found: {svg_path}")

            with open(svg_path, "r", encoding="utf-8") as f:
                png_buf = io.BytesIO()
                f.seek(0)
                try:
                    cairosvg.svg2png(file_obj=f, write_to=png_buf)
                except IOError as e:
                    raise (f"IO error while converting svg2png {e}")
                img = Image.open(png_buf)

            return img

        except Exception as e:
            raise (f"Error processing shape SVG: {e}")

    def _add_issuer_logo(self, canvas, category, issuerImage):
        """
        Add issuer logo with frame
        """
        try:
            # Get positioning based on category
            x_width = 55 if category == "participation" else 70
            logo_x = self.CANVAS_SIZE[0] - self.CANVAS_SIZE[0] // 4 - x_width
            logo_y = 10 if category == "learningpath" else 0

            logo_size = (self.CANVAS_SIZE[0] // 5, self.CANVAS_SIZE[1] // 5)

            # Add the square frame
            frame_image = self._get_logo_frame_svg()
            if frame_image:
                # Resize frame to logo size
                frame_resized = frame_image.resize(logo_size, Image.Resampling.LANCZOS)
                canvas.paste(frame_resized, (logo_x, logo_y), frame_resized)

            # Add issuer logo
            border_padding = 12
            logo_img = self._prepare_issuer_logo(
                issuerImage,
                (logo_size[0] - border_padding * 2, logo_size[1] - border_padding * 2),
            )

            if logo_img:
                final_logo_x = logo_x + border_padding
                final_logo_y = logo_y + border_padding
                canvas.paste(logo_img, (final_logo_x, final_logo_y), logo_img)

            return canvas

        except Exception as e:
            print(f"Error adding issuer logo: {e}")
            return canvas

    def _get_logo_frame_svg(self):
        """Load and convert the square frame SVG"""

        frame_path = finders.find("images/square.svg")

        if not os.path.exists(frame_path):
            raise (f"Square frame SVG not found: {frame_path}")

        try:
            with open(frame_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
            return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

        except Exception as e:
            print(f"Error loading logo frame: {e}")
            raise e

    def _prepare_issuer_logo(self, logo_field, target_size):
        """Prepare issuer logo with support for SVG and PNG formats"""
        try:
            if not hasattr(logo_field, "name"):
                raise

            file_extension = logo_field.name.lower().split(".")[-1]

            if file_extension == "svg":
                return self._prepare_svg_logo(logo_field, target_size)
            elif file_extension in ["png", "jpg", "jpeg"]:
                return self._prepare_raster_logo(logo_field, target_size)
            else:
                logger.error(f"Unsupported logo format: {file_extension}")
                raise

        except Exception as e:
            print(f"Error preparing issuer logo: {e}")
            raise e

    def _prepare_raster_logo(self, logo_field, target_size):
        """Prepare PNG/JPEG logo with proper sizing and centering"""
        try:
            logo_field.seek(0)
            img = Image.open(logo_field).convert("RGBA")

            if (
                img.size[0] > self.MAX_DIMENSIONS[0]
                or img.size[1] > self.MAX_DIMENSIONS[1]
            ):
                logger.error(
                    f"Logo dimensions {img.size} exceed limits {self.MAX_DIMENSIONS}"
                )
                raise

            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            result = Image.new("RGBA", target_size, (0, 0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            result.paste(img, (x, y), img)

            return result

        except Exception as e:
            print(f"Error preparing raster logo: {e}")
            raise e

    def _prepare_svg_logo(self, svg_field, target_size):
        try:
            svg_field.seek(0)
            svg_content = svg_field.read()
            if isinstance(svg_content, bytes):
                svg_content = svg_content.decode("utf-8")

            png_bytes = cairosvg.svg2png(
                bytestring=svg_content.encode("utf-8"),
                output_width=target_size[0],
                output_height=target_size[1],
            )

            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

            result = Image.new("RGBA", target_size, (0, 0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            result.paste(img, (x, y), img)

            return result

        except Exception as e:
            print(f"Error preparing SVG logo: {e}")
            raise e
