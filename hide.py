from PIL import Image
from pathlib import Path #man
from stegano import lsb 
from stegano.lsb import generators

def analyze(input):
    '''
    A functions that lists the necessary attributes of the image file dealt.
    This is called when an error pops up.
    
    Open orginal file.

    type name : string
    '''

    path = Path(input)
    img = Image.open(path)
    print(f"""
    The file format is {img.format}.
    The file size is {round(path.stat().st_size/(1024**2) , 3)} MB
    The dimensions are: {img.size}. 
    Total number of pixels is {img.size[0]*img.size[1]}.
    """)
    img.show()

def hide(input,message=0,output="edited.png"):
    '''
    A function that hides text in images.

    The path of the image which is to be edited is assigned to var 'input'.
    The actual mesage to be hidden assigned to var 'message'
    The output image name is assigned to var 'output'

    type input : str
    type message : str or char
    type output : str
    '''

    try:
        in_path = Path(input)
    except FileNotFoundError:
        print("File Not Found")

    folder = Path("Edited_Images")
    folder.mkdir(exist_ok=True)
    out_path = Path("Edited_Images/"+output)

    try:
        # Hide the message inside an existing image in such a way it cannot be easily found out.
        secret_image = lsb.hide(in_path, message, generators.eratosthenes())
    except ValueError:
        print("Image is too small for text to be hiden.")
    except IndexError:
        print("Pixel index out of range")

    # Saves the newly generated image containing the hidden text.
    secret_image.save(out_path) 
    print(f"Sucess!! {out_path}")


#For test use C:/Users/Sanjay S/Documents/test2.png or test.png
hide(input="test.png",message="YOU CANNOT SEE ME!!",output="edited1.png")

''' 
To look up at orginal file to see what is wrong with it. Run:
analyze("test.png")
'''