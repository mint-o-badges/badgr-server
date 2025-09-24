from PIL import Image
import cairosvg
import io
import os
import base64
from django.contrib.staticfiles import finders
import logging

logger = logging.getLogger(__name__)


class ImageComposer:
    CANVAS_SIZES = {
        "participation": (400, 400),
        "competency": (412, 412),
        "learningpath": (416, 416),
    }

    EXPANDED_CANVAS_SIZES = {
        "participation": (600, 600),
        "competency": (612, 612),
        "learningpath": (616, 616),
    }

    DEFAULT_CANVAS_SIZE = (400, 400)
    DEFAULT_EXPANDED_CANVAS_SIZE = (600, 600)

    MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB
    MAX_DIMENSIONS = (512, 512)
    ALLOWED_FORMATS = {"PNG", "SVG"}

    def __init__(self, category=None):
        self.category = category
        self.CANVAS_SIZE = self.CANVAS_SIZES.get(category, self.DEFAULT_CANVAS_SIZE)
        self.EXPANDED_CANVAS_SIZE = self.EXPANDED_CANVAS_SIZES.get(
            category, self.DEFAULT_EXPANDED_CANVAS_SIZE
        )

    def get_canvas_size(self, category):
        return self.CANVAS_SIZES.get(category, self.DEFAULT_CANVAS_SIZE)

    def get_expanded_canvas_size(self, category):
        return self.EXPANDED_CANVAS_SIZES.get(
            category, self.DEFAULT_EXPANDED_CANVAS_SIZE
        )

    def compose_badge_from_uploaded_image(self, image, issuerImage, networkImage):
        """
        Compose badge image with issuer logo from image upload
        """
        try:
            canvas = Image.new("RGBA", self.EXPANDED_CANVAS_SIZE, (255, 255, 255, 0))

            ### Frame ###
            shape_image = self._get_colored_shape_svg()
            if shape_image:
                frame_x = (self.EXPANDED_CANVAS_SIZE[0] - self.CANVAS_SIZE[0]) // 2
                frame_y = (self.EXPANDED_CANVAS_SIZE[1] - self.CANVAS_SIZE[1]) // 2
                canvas.paste(shape_image, (frame_x, frame_y), shape_image)

            ### badge image ###
            badge_img = self._prepare_uploaded_image(image)
            if badge_img:
                x = (self.EXPANDED_CANVAS_SIZE[0] - badge_img.width) // 2
                y = (self.EXPANDED_CANVAS_SIZE[1] - badge_img.height) // 2
                canvas.paste(badge_img, (x, y), badge_img)

            if issuerImage:
                canvas = self._add_issuer_logo(canvas, self.category, issuerImage)

            if networkImage:
                canvas = self._add_network_logo(canvas, self.category, networkImage)

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
                    image_bytes = base64.b64decode(image_data)

                img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            else:
                raise ValueError("Expected base64 string for image data")

            target_size = (self.CANVAS_SIZE[0] // 2, self.CANVAS_SIZE[1] // 2)

            img.thumbnail(target_size, Image.Resampling.LANCZOS)

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
                raise FileNotFoundError(f"SVG file not found: {svg_path}")

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
        Add issuer logo with frame - adjusted for expanded canvas
        """
        try:
            offset_x = (self.EXPANDED_CANVAS_SIZE[0] - self.CANVAS_SIZE[0]) // 2
            offset_y = (self.EXPANDED_CANVAS_SIZE[1] - self.CANVAS_SIZE[1]) // 2

            x_width = 55 if category == "participation" else 70
            original_logo_x = self.CANVAS_SIZE[0] - self.CANVAS_SIZE[0] // 4 - x_width
            original_logo_y = 10 if category == "learningpath" else 0

            logo_x = original_logo_x + offset_x
            logo_y = original_logo_y + offset_y

            logo_size = (self.CANVAS_SIZE[0] // 5, self.CANVAS_SIZE[1] // 5)

            frame_image = self._get_logo_frame_svg()
            if frame_image:
                frame_resized = frame_image.resize(logo_size, Image.Resampling.LANCZOS)
                canvas.paste(frame_resized, (logo_x, logo_y), frame_resized)

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
            logger.error(f"Error adding issuer logo: {e}")
            return canvas

    def _add_network_logo(self, canvas, category, networkImage):
        """
        Add network image in bottom center, overlapping with the SVG frame border
        Adjusted for expanded canvas
        """
        try:
            offset_x = (self.EXPANDED_CANVAS_SIZE[0] - self.CANVAS_SIZE[0]) // 2
            offset_y = (self.EXPANDED_CANVAS_SIZE[1] - self.CANVAS_SIZE[1]) // 2

            network_image_size = (self.CANVAS_SIZE[0] // 3, self.CANVAS_SIZE[1] // 4)

            border_positions = {
                "participation": 387,  # Based on SVG path
                "competency": 388,
                "learningpath": 389,
            }

            original_border_y = border_positions.get(category, 387)

            original_bottom_x = (self.CANVAS_SIZE[0] - network_image_size[0]) // 2
            original_bottom_y = original_border_y - (network_image_size[1] // 2)

            bottom_x = original_bottom_x + offset_x
            bottom_y = original_bottom_y + offset_y

            frame_image = self._get_logo_frame_svg()
            if frame_image:
                frame_resized = frame_image.resize(
                    network_image_size, Image.Resampling.LANCZOS
                )
                canvas.paste(frame_resized, (bottom_x, bottom_y), frame_resized)

            border_padding = 6
            inner_size = (
                network_image_size[0] - border_padding * 2,
                network_image_size[1] - border_padding * 2,
            )
            bottom_img = self._prepare_issuer_logo(networkImage, inner_size)

            if bottom_img:
                composite_img = self._create_network_logo_with_text(
                    bottom_img, inner_size
                )

                final_bottom_x = bottom_x + border_padding
                final_bottom_y = bottom_y + border_padding
                canvas.paste(
                    composite_img, (final_bottom_x, final_bottom_y), composite_img
                )

            return canvas

        except Exception as e:
            logger.error(f"Error adding network image: {e}")
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
            logger.error(f"Error loading logo frame: {e}")
            raise e

    def _prepare_issuer_logo(self, logo_field, target_size):
        """Prepare issuer logo with support for SVG and PNG formats"""
        try:
            if not hasattr(logo_field, "name"):
                raise Exception("Logo field missing name attribute")

            file_extension = logo_field.name.lower().split(".")[-1]

            if file_extension == "svg":
                return self._prepare_svg_logo(logo_field, target_size)
            elif file_extension in ["png", "jpg", "jpeg"]:
                return self._prepare_raster_logo(logo_field, target_size)
            else:
                logger.error(f"Unsupported logo format: {file_extension}")
                raise Exception("Logo format not supported")

        except Exception as e:
            logger.error(f"Error preparing issuer logo: {e}")
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
                raise Exception("Logo dimensions exceed limits")

            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            result = Image.new("RGBA", target_size, (0, 0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            result.paste(img, (x, y), img)

            return result

        except Exception as e:
            logger.error(f"Error preparing raster logo: {e}")
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
            logger.error(f"Error preparing SVG logo: {e}")
            raise e

    def _create_network_logo_with_text(self, network_img, frame_inner_size):
        """
        Create a composite image with "Part of" text to the left of the network logo
        """
        try:
            from PIL import ImageFont, ImageDraw
            import os

            composite = Image.new("RGBA", frame_inner_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(composite)

            font_size = 14
            font_path_rubik_bold = os.path.join(
                os.path.dirname(__file__), "static", "fonts", "Rubik-Bold.ttf"
            )

            try:
                font = ImageFont.truetype(font_path_rubik_bold, font_size)
            except Exception as e:
                logger.error(f"Error loading rubik font {e}")
                font = ImageFont.load_default()

            text = "Teil von"
            text_color = (0, 0, 0, 255)

            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            text_margin = 8
            container_padding = 8

            max_logo_width = frame_inner_size[0] * 0.4
            max_logo_height = frame_inner_size[1] * 0.6

            logo_scale_x = max_logo_width / network_img.width
            logo_scale_y = max_logo_height / network_img.height
            scale_factor = min(logo_scale_x, logo_scale_y, 0.5)

            new_logo_size = (
                int(network_img.width * scale_factor),
                int(network_img.height * scale_factor),
            )
            network_img = network_img.resize(new_logo_size, Image.Resampling.LANCZOS)

            available_width = frame_inner_size[0] - (container_padding * 2)
            content_width = text_width + text_margin + network_img.width

            if content_width <= available_width:
                start_x = container_padding + (available_width - content_width) // 2
            else:
                start_x = container_padding

            text_x = start_x
            text_y = (frame_inner_size[1] - text_height) // 2

            draw.text((text_x, text_y), text, fill=text_color, font=font)

            logo_x = text_x + text_width + text_margin
            logo_y = (frame_inner_size[1] - network_img.height) // 2

            composite.paste(network_img, (logo_x, logo_y), network_img)

            return composite

        except Exception as e:
            logger.error(f"Error creating network logo with text: {e}")
            # Return original logo
            return network_img
