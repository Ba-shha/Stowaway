from stegano import lsb
from stegano.lsb import generators

revealed_message = lsb.reveal("Edited_Images/edited1.png", generators.eratosthenes())

print(f"Revealed Message: {revealed_message}")
