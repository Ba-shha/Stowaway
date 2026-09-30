from pathlib import Path
from stegano import lsb
from stegano.lsb import generators

#revealed_message = lsb.reveal("./Edited_Images/edited1.png", generators.eratosthenes())

#print(f"Revealed Message: {revealed_message}")

def norm_reveal():
    file = Path(input("Enter the file path of image to be decrypted: "))
    revealed_message = lsb.reveal(file,generators.eratosthenes())
    return revealed_message