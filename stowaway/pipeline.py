"""Connects the stages: lock (crypto), add repair data (repair), hide (hide)."""

import base64
import math

from PIL import Image

from stowaway.crypto import lock, unlock
from stowaway.hide import hide, reveal
from stowaway.repair import protect, repair

NSYM = 100     # repair bytes per block
BLOCK = 255    # Reed-Solomon block size: 155 data bytes plus NSYM repair bytes
B64 = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def capacity(image: Image.Image) -> int:
    """Longest message, in bytes, that fits in the image after encryption and repair data."""
    pixels = image.width * image.height
    chars = int(pixels / math.log(pixels)) * 3 // 8 - 10    # 3 bits per prime pixel, minus header
    packed = chars * 3 // 4                                  # base64 undoes 4/3 growth
    data = packed // BLOCK * (BLOCK - NSYM) + max(0, packed % BLOCK - NSYM)
    return max(0, (data - 16) * 3 // 4 - 57 - 16)            # salt, Fernet overhead, padding


def send(image: Image.Image, message: str, password: str) -> Image.Image:
    """Lock the message, add repair data, hide it. Returns the image carrying the message."""
    salt, token = lock(message, password)
    packed = base64.urlsafe_b64encode(protect(salt + token, NSYM)).decode("ascii").rstrip("=")
    return hide(image, packed)


def receive(image: Image.Image, password: str, use_repair: bool = True, tamper: bool = False):
    """Read the message back. Returns (status, text) with status ok, damaged or tampered."""
    try:
        text = "".join(c if c in B64 else "A" for c in reveal(image))
        protected = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except ValueError:
        return "damaged", ""

    if use_repair:
        try:
            data = repair(protected, NSYM)
        except ValueError:
            return "damaged", ""
    else:  # skip repair: cut the repair bytes off each block and trust the rest
        data = b"".join(protected[i:i + BLOCK][:-NSYM] for i in range(0, len(protected), BLOCK))

    if tamper:  # staged attack for the demo: change one byte after repair
        data = data[:20] + bytes([data[20] ^ 0xFF]) + data[21:]

    try:
        return "ok", unlock(data[16:], password, data[:16])
    except ValueError:
        return ("tampered" if use_repair else "damaged"), ""