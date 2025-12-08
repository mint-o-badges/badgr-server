from math import ceil
from PIL import Image
import cairosvg
import io
import os
import base64
from django.contrib.staticfiles import finders
import logging

logger = logging.getLogger(__name__)


class ImageComposer:
    DEFAULT_CANVAS_SIZE = (600, 600)
    CANVAS_SIZES = {
        "participation": DEFAULT_CANVAS_SIZE,
        "competency": DEFAULT_CANVAS_SIZE,
        "learningpath": DEFAULT_CANVAS_SIZE,
    }
    FRAME_PADDING = 0.86
    MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB
    MAX_DIMENSIONS = (512, 512)
    ALLOWED_FORMATS = {"PNG", "SVG"}

    def __init__(self, category=None):
        self.category = category
        self.CANVAS_SIZE = self.CANVAS_SIZES.get(category, self.DEFAULT_CANVAS_SIZE)

    def get_canvas_size(self, category):
        return self.CANVAS_SIZES.get(category, self.DEFAULT_CANVAS_SIZE)

    def compose_badge_from_uploaded_image(
        self, image, issuerImage, networkImage, draw_frame=True
    ):
        """
        Compose badge image with issuer logo from image upload
        """
        try:
            if not draw_frame:
                # return original image untouched
                if isinstance(image, str) and image.startswith("data:image/"):
                    return image
                else:
                    return f"data:image/png;base64,{image}"

            canvas = Image.new("RGBA", self.CANVAS_SIZE, (255, 255, 255, 0))

            ### Frame ###
            if draw_frame:
                shape_image = self._get_colored_shape_svg()
                if shape_image:
                    # Center the frame on the canvas
                    frame_x = (self.CANVAS_SIZE[0] - shape_image.width) // 2
                    frame_y = (self.CANVAS_SIZE[1] - shape_image.height) // 2
                    canvas.paste(shape_image, (frame_x, frame_y), shape_image)

            ### badge image ###
            badge_img = self._prepare_uploaded_image(image)
            if badge_img:
                x = (self.CANVAS_SIZE[0] - badge_img.width) // 2
                y = (self.CANVAS_SIZE[1] - badge_img.height) // 2
                canvas.paste(badge_img, (x, y), badge_img)

            if draw_frame:
                if issuerImage:
                    canvas = self._add_issuer_logo(canvas, self.category, issuerImage)

                if networkImage:
                    canvas = self._add_network_logo(canvas, networkImage)

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

                if header.startswith("data:image/svg"):
                    png_bytes = cairosvg.svg2png(bytestring=image_bytes)
                    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
                else:
                    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

            else:
                raise ValueError("Expected base64 string for image data")

            target_size = (
                int(((self.CANVAS_SIZE[0] * self.FRAME_PADDING) // 2)),
                int(((self.CANVAS_SIZE[0] * self.FRAME_PADDING) // 2)),
            )

            if img.width < target_size[0] or img.height < target_size[1]:
                # upscale (e.g. nounproject images are 200x200px)
                img = img.resize(target_size, Image.Resampling.LANCZOS)
            else:
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
        Scale SVG to match new canvas size
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
                    # Scale SVG to match canvas size
                    cairosvg.svg2png(
                        file_obj=f,
                        write_to=png_buf,
                        output_width=self.CANVAS_SIZE[0] * self.FRAME_PADDING,
                    )
                except IOError as e:
                    raise (f"IO error while converting svg2png {e}")
                img = Image.open(png_buf)

            return img

        except Exception as e:
            raise (f"Error processing shape SVG: {e}")

    def _add_issuer_logo(self, canvas, category, issuerImage):
        """
        Add issuer logo in square container
        """
        try:
            base_logo_height = 96  # base container height for 600px canvas
            scale_factor = self.CANVAS_SIZE[0] / 600
            logo_height = int(base_logo_height * scale_factor)
            logo_size = (logo_height, logo_height)

            if category == "competency":
                offset_ratio = 160 / 600
            elif category == "learningpath":
                offset_ratio = 135 / 600
            else:
                offset_ratio = 125 / 600

            logo_x = (
                self.CANVAS_SIZE[0]
                - logo_size[0]
                - int(self.CANVAS_SIZE[0] * offset_ratio)
            )

            # Vertical centering relative to the main frame
            shape_image = self._get_colored_shape_svg()
            frame_y = (self.CANVAS_SIZE[1] - shape_image.height) // 2

            frame_image = self._get_logo_frame_svg("square")
            if frame_image:
                frame_resized = frame_image.resize(logo_size, Image.Resampling.LANCZOS)
                canvas.paste(frame_resized, (logo_x, frame_y), frame_resized)

            PADDING_RATIO = (
                12 / 96
            )  # Figma: 8px + 4px (inside the white) padding in 96px frame
            PADDING = int(ceil(logo_size[0] * PADDING_RATIO))

            inner_size = (
                logo_size[0] - PADDING * 2,
                logo_size[1] - PADDING * 2,
            )

            logo_img = self._prepare_issuer_logo(issuerImage, inner_size)
            if logo_img:
                final_logo_x = logo_x + PADDING
                final_logo_y = frame_y + PADDING
                canvas.paste(logo_img, (final_logo_x, final_logo_y), logo_img)

            return canvas

        except Exception as e:
            logger.error(f"Error adding issuer logo: {e}")
            return canvas

    def _add_network_logo(self, canvas, networkImage):
        """
        Add network image in bottom center, flush with canvas bottom
        """
        try:
            base_canvas_size = 600
            scale_factor = self.CANVAS_SIZE[0] / base_canvas_size

            network_image_size = (
                int(224 * scale_factor),
                int(96 * scale_factor),
            )

            if self.category == "participation":
                frame_bottom_ratio = (
                    0.85  # bottom frame border at approximately 85% of canvas height
                )
                frame_bottom = int(self.CANVAS_SIZE[1] * frame_bottom_ratio)
                bottom_y = frame_bottom - (network_image_size[1] // 2)
            elif self.category == "competency":
                frame_bottom_ratio = 0.89
                frame_bottom = int(self.CANVAS_SIZE[1] * frame_bottom_ratio)
                bottom_y = frame_bottom - (network_image_size[1] // 2)
            else:
                bottom_y = self.CANVAS_SIZE[1] - network_image_size[1]

            bottom_x = (self.CANVAS_SIZE[0] - network_image_size[0]) // 2

            frame_image = self._get_logo_frame_svg("rectangle")
            if frame_image:
                frame_resized = frame_image.resize(
                    network_image_size, Image.Resampling.LANCZOS
                )
                canvas.paste(frame_resized, (bottom_x, bottom_y), frame_resized)

            border_padding = int(8 * scale_factor)

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

    def _create_network_logo_with_text(self, network_img, frame_inner_size):
        """
        Create the 'NETWORK PARTNER' + network logo composite inside the inner rectangle frame.
        """
        from PIL import Image, ImageDraw, ImageFont

        composite = Image.new("RGBA", frame_inner_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(composite)

        figma_inner_width = 208
        figma_inner_height = 80
        figma_logo_size = 72
        figma_font_size = 26
        figma_gap = 8
        logo_padding = (figma_inner_height - figma_logo_size) // 2

        text_color = (255, 255, 255, 255)  # white

        # Use the smaller scale to ensure everything fits
        scale = min(
            frame_inner_size[0] / figma_inner_width,
            frame_inner_size[1] / figma_inner_height,
        )

        logo_height = int(round(figma_logo_size * scale))
        font_size = max(
            int(round(figma_font_size * scale)), 8
        )  # Minimum 8px for readability
        gap = int(round(figma_gap * scale))

        network_img = self._trim_transparency(network_img)

        aspect = network_img.width / network_img.height
        logo_width = int(logo_height * aspect)

        network_img = network_img.resize(
            (logo_width, logo_height), Image.Resampling.LANCZOS
        )

        font_path_regular = finders.find("fonts/Rubik-Regular.ttf")
        font_path_bold = finders.find("fonts/Rubik-SemiBold.ttf")
        try:
            font = ImageFont.truetype(font_path_regular, font_size)
            font_bold = ImageFont.truetype(font_path_bold, font_size)
        except Exception:
            font = ImageFont.load_default()
            font_bold = ImageFont.load_default()

        text = "NETWORK"
        text2 = "\nPARTNER"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_height = text_bbox[3] - text_bbox[1]
        text_offset_y = (
            -text_bbox[1] * 2 + 2
        )  # Offset to align text baseline properly + line spacing

        logo_x = int(logo_padding * scale)
        logo_y = int(logo_padding * scale)

        text_x = gap + logo_width + logo_padding * 2
        text_y = (frame_inner_size[1] - text_height * 2) // 2 + text_offset_y

        draw.text((text_x, text_y), text, fill=text_color, font=font)
        draw.text((text_x, text_y), text2, fill=text_color, font=font_bold)
        composite.paste(network_img, (logo_x, logo_y), network_img)

        return composite

    def _get_logo_frame_svg(self, shape="square"):
        """Load and convert the square frame SVG"""
        if shape == "square":
            frame_path = finders.find("images/square.svg")

        elif shape == "rectangle":
            frame_path = finders.find("images/rectangle.svg")

        if not os.path.exists(frame_path):
            raise (f"SVG frame not found: {frame_path}")

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

    def _trim_transparency(self, img):
        """
        Crop transparent whitespace from around an RGBA image.
        Keeps the non-transparent content tight within its bounds.
        """
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        bbox = img.getbbox()
        if bbox:
            return img.crop(bbox)
        return img
