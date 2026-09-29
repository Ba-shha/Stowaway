from stegano import lsb
from stegano.lsb import generators

revealed_message = lsb.reveal("Edited_Images/damaged_image.png", generators.eratosthenes())

print(f"Revealed Message: {revealed_message}")
