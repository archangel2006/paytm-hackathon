"""
Generate synthetic PAN card sample images for testing.

Uses Pillow to create clearly-marked sample documents.
Each image has a watermark "SAMPLE, NOT A REAL DOCUMENT".

Run: ``python -m integrations.documents.make_samples``
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont


SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")

# Default font – Pillow will use its built-in if system fonts aren't found
def _get_font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except (OSError, IOError):
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except (OSError, IOError):
            return ImageFont.load_default()


def _draw_pan_card(
    name: str,
    pan: str,
    father_name: str = "SAMPLE FATHER",
    dob: str = "01/01/1990",
) -> Image.Image:
    """Create a synthetic PAN card image."""
    width, height = 800, 500
    img = Image.new("RGB", (width, height), color=(255, 255, 240))
    draw = ImageDraw.Draw(img)

    # Header
    header_font = _get_font(28)
    body_font = _get_font(22)
    small_font = _get_font(16)
    pan_font = _get_font(36)

    # Title bar
    draw.rectangle([(0, 0), (width, 70)], fill=(0, 51, 153))
    draw.text((20, 15), "INCOME TAX DEPARTMENT", fill="white", font=header_font)
    draw.text((20, 45), "GOVT. OF INDIA", fill="white", font=small_font)

    # PAN number
    draw.text((50, 100), f"Permanent Account Number", fill="black", font=small_font)
    draw.text((50, 130), pan, fill=(0, 51, 153), font=pan_font)

    # Name
    draw.text((50, 200), "Name", fill="gray", font=small_font)
    draw.text((50, 225), name, fill="black", font=body_font)

    # Father's name
    draw.text((50, 280), "Father's Name", fill="gray", font=small_font)
    draw.text((50, 305), father_name, fill="black", font=body_font)

    # Date of Birth
    draw.text((50, 360), "Date of Birth", fill="gray", font=small_font)
    draw.text((50, 385), dob, fill="black", font=body_font)

    # Watermark
    watermark_font = _get_font(32)
    # Draw rotated watermark
    for y_offset in range(50, height, 120):
        draw.text(
            (100, y_offset),
            "SAMPLE, NOT A REAL DOCUMENT",
            fill=(255, 0, 0, 80),
            font=watermark_font,
        )

    return img


def _make_blurry(img: Image.Image, radius: int = 8) -> Image.Image:
    """Apply Gaussian blur to make the image blurry."""
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def _make_dark(img: Image.Image, factor: float = 0.2) -> Image.Image:
    """Darken the image."""
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Brightness(img)
    return enhancer.enhance(factor)


def _make_cropped(img: Image.Image) -> Image.Image:
    """Crop the image so the PAN number is cut off."""
    w, h = img.size
    return img.crop((0, 0, w // 2, h))  # Cut off the right half


def generate_samples() -> None:
    """Generate all sample documents."""
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    # 1. Clear PAN card with correct name
    clear = _draw_pan_card(name="RAHUL SHARMA", pan="ABCDE1234F")
    clear.save(os.path.join(SAMPLES_DIR, "pan_clear.jpg"), "JPEG", quality=95)

    # 2. Blurry PAN card
    blurry = _make_blurry(clear)
    blurry.save(os.path.join(SAMPLES_DIR, "pan_blurry.jpg"), "JPEG", quality=95)

    # 3. Cropped PAN (number cut off)
    cropped = _make_cropped(clear)
    cropped.save(os.path.join(SAMPLES_DIR, "pan_cropped.jpg"), "JPEG", quality=95)

    # 4. Very dark PAN
    dark = _make_dark(clear)
    dark.save(os.path.join(SAMPLES_DIR, "pan_dark.jpg"), "JPEG", quality=95)

    # 5. Wrong name PAN
    wrong_name = _draw_pan_card(name="SOMEONE ELSE", pan="ABCDE1234F")
    wrong_name.save(os.path.join(SAMPLES_DIR, "pan_wrong_name.jpg"), "JPEG", quality=95)

    # 6. Meena blurry
    meena_clear = _draw_pan_card(name="MEENA DEVI", pan="FGHIJ5678K")
    meena_blurry = _make_blurry(meena_clear)
    meena_blurry.save(os.path.join(SAMPLES_DIR, "meena_pan_blurry.jpg"), "JPEG", quality=95)

    # 7. Meena clear
    meena_clear.save(os.path.join(SAMPLES_DIR, "meena_pan_clear.jpg"), "JPEG", quality=95)

    print(f"Generated {7} sample documents in {SAMPLES_DIR}")


if __name__ == "__main__":
    generate_samples()
