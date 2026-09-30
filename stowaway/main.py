from pathlib import Path
from reveal import reveal
from normal_reveal import norm_reveal
from cryptocumrepair import cryptocumrepair
from storm import storm
from hide import hide

userwant = int(input("What do you want to do?"))
# 1 - encrypt | 2 - decrypt(repair) | 3 - damage | 4 - review damage | 5 - decrypt(no repair)

if userwant == 1:
    text = input("Text to encrypt: ")
    encrypted_text = cryptocumrepair("e",text)
    file_path = Path(input("Enter the image's file path:"))
    hide(input=file_path,message=encrypted_text,output="edited1.png")
elif userwant == 2:
    hidden_str = reveal()
    decrypted_str = cryptocumrepair("d",hidden_str)
    print(decrypted_str)
elif userwant == 3:
    storm()
elif userwant == 4:
    og_str = reveal()
    print(f"the orginal encrypted string is {og_str}")
    damage_str = reveal()
    print(f"the damaged encrypted string is {damage_str}")
elif userwant == 5:
    try:
        hidden_str = norm_reveal()
        decrypted_str = cryptocumrepair("d",hidden_str)
        print(decrypted_str)
    except IndexError:
        print('CANNOT EXTRACT TEXT!!')
else:
    print("INVALID INPUT!!")



