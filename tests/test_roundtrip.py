# Lock, hide, extract, unlock

# Lock, add repair data, hide, damage, extract, unlock
from PIL import Image

from stowaway.pipeline import receive, send
from stowaway.storm import damage_image

IMAGE = Image.new("RGB", (400, 400), (20, 30, 60))


def test_roundtrip():
    assert receive(send(IMAGE, "HELLO", "pw"), "pw") == ("ok", "HELLO")


def test_wrong_password():
    assert receive(send(IMAGE, "HELLO", "pw"), "nope")[0] == "tampered"


def test_repair_survives_a_storm():
    stego = send(IMAGE, "HELLO", "pw")
    damaged, flipped = damage_image(stego, 0.0005, seed=1)
    assert flipped > 0 and receive(damaged, "pw") == ("ok", "HELLO")