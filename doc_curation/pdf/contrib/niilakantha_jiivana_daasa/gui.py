import PySimpleGUI as sg

# Very basic form.  Return values as a list
window = sg.FlexForm('OCR Unicode')  # begin with a blank form

layout = [
          [sg.Text('Please enter the folder path')],
          [sg.Text('Folder Path', size=(15, 1))], 
          [sg.InputText()],
          [sg.Checkbox('Split pdf_pages into half')],
          [sg.Submit(), sg.Cancel()]
         ]

button, values = sg.Window(window, layout).Read()
# print(values[0], values[1])
ocr_folder_path = values[0]
half_split = values[1]
if half_split == True:
    half_split = 'yes'
else:
    half_split = 'no'

print(ocr_folder_path)
print(half_split)

# window = sg.Window("OCR Unicode",layout)

# events, values = window.read()
window.close()

# ocr_folder_path = values[0]
# sg.popup('You entered', values[0])

# print(values[0])