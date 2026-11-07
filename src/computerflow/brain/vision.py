import io
from dataclasses import replace
from math import ceil

from computerflow.platform.geometry import Rect


def crop_snapshot(snapshot, area):
    """Crop a normalized region and keep its mapping to physical screen coordinates."""
    from PIL import Image

    width, height = snapshot.image_size
    pixels = (
        area.left * width // 1000,
        area.top * height // 1000,
        ceil(area.right * width / 1000),
        ceil(area.bottom * height / 1000),
    )
    with Image.open(io.BytesIO(snapshot.png)) as original:
        image = original.crop(pixels)
    crop = snapshot.crop
    bounds = Rect(
        crop.left + round(pixels[0] * crop.width / width),
        crop.top + round(pixels[1] * crop.height / height),
        crop.left + round(pixels[2] * crop.width / width),
        crop.top + round(pixels[3] * crop.height / height),
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return replace(snapshot, crop=bounds, image_size=image.size, png=output.getvalue(), marks=())


def marked_png(snapshot):
    if not snapshot.marks:
        return snapshot.png
    from PIL import Image, ImageDraw

    image = Image.open(io.BytesIO(snapshot.png)).convert("RGB")
    draw = ImageDraw.Draw(image)
    sx, sy = image.width / snapshot.crop.width, image.height / snapshot.crop.height
    for index, element in snapshot.marks:
        bounds = snapshot.crop.intersect(element.rect)
        if not bounds:
            continue
        left = round((bounds.left - snapshot.crop.left) * sx)
        top = round((bounds.top - snapshot.crop.top) * sy)
        right = round((bounds.right - snapshot.crop.left) * sx) - 1
        bottom = round((bounds.bottom - snapshot.crop.top) * sy) - 1
        draw.rectangle((left, top, max(left, right), max(top, bottom)), outline="#ff9600", width=2)
        draw.rectangle((left, top, left + 20, top + 14), fill="#ff9600")
        draw.text((left + 2, top), str(index), fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
