"""Hide text inside an image and read it back (least significant bit, via stegano)."""

import io

from PIL import Image
from stegano import lsb
from stegano.lsb import generators

COLON = 58  # the header is "<length>:<text>", and 58 is the code for ":"


def _as_png(image: Image.Image) -> io.BytesIO:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def hide(image: Image.Image, text: str) -> Image.Image:
    """Return a copy of the image with the text hidden in it."""
    return lsb.hide(_as_png(image), text, generators.eratosthenes()).convert("RGB")


def reveal(image: Image.Image) -> str:
    """Read the hidden text. Raises ValueError if the length header is damaged."""
    img = image.convert("RGB")
    pixels, width = img.load(), img.width
    out, bits, count, total = bytearray(), 0, 0, None

    for n in generators.eratosthenes():
        if n >= width * img.height:
            break
        for channel in pixels[n % width, n // width]:
            bits = (bits << 1) | (channel & 1)
            count += 1
            if count == 8:
                out.append(bits)
                bits = count = 0
        if total is None and COLON in out:
            head = bytes(out[:out.index(COLON)])
            if not head.isdigit():
                raise ValueError("Header damaged")
            total = len(head) + 1 + int(head)
        if total is not None and len(out) >= total:
            break

    if total is None:
        raise ValueError("No header found")
    return bytes(out[:total]).partition(b":")[2].decode("latin-1")