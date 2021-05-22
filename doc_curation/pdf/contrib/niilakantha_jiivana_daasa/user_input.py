# Don't forget to save this file after editing

# ocr_folder_path = "C:\\Users\\Dell\\Desktop\\test\\" # input with double forward slashes in middle and end


# for pdf_to_jpeg.py;
# pip install PyMuPDF #install
# half_pages = False

# for split_pdf.py;
# pip install PyPDF2 #install
pages_per_file = 10 #input number of pages in each pdf after split

# for drive_upload.py;
# pip install google-api-python-client #install
# pip install google_auth_oauthlib
input_file_type = "pdf" #input = "pdf","jpeg","png"
output_file_type = "docx" #input = "docx","txt"
# search_subfolders_only = "yes" #input = "yes", "no"

# for merge_docs.py;
# pip install python-docx #install

import os
from os import path
from run_code import CodeRunner
# import argparse
import PySimpleGUI as sg
import subprocess
import sys
# from PySimpleGUI.PySimpleGUI import Window

# parser = argparse.ArgumentParser(description= 'OCR pdf files')
# parser.add_argument('-i', '--folder', help='input folder path', required= True)
# parser.add_argument('-o', '--split_pages', help='<True> to split_pages (default: False)', required=False)

# # parse input arguments
# args = parser.parse_args()
# # sg.Print(args.folder(args.split_pages))


def run_command(cmd, timeout=None, window=None):
    """ run shell command
    @param cmd: command to execute
    @param timeout: timeout for command execution
    @param window: the PySimpleGUI window that the output is going to (needed to do refresh on)
    @return: (return code from command, command output)
    """
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = ''
    for line in p.stdout:
        line = line.decode(errors='replace' if (sys.version_info) < (3, 5) else 'backslashreplace').rstrip()
        output += line
        sg.Print(line)
      #   window.Refresh() if window else None      # yes, a 1-line if, so shoot me

    retval = p.wait(timeout)
    return (retval, output)

# Very basic form.  Return values as a list
sg.theme('DarkAmber')
layout = [
         [sg.Text('Please enter the folder path')],
         [sg.Text('Folder Path', size=(15, 1))], 
         [sg.InputText(key = '-FOLDER INPUT-')],
         # [sg.Output(size = (60,15))],
         # [sg.InputText()],
         [sg.Checkbox('Split pdf_pages into half', default=False, key='-IN-')],
         [sg.Button('Run')]
         ]

window = sg.Window('OCR Unicode',layout)  # begin with a blank form

while True: # Event Loop
   event, values = window.Read()
   if event == 'Run':
      run_command(cmd=values, window = window)
      break
   # elif event == 'Exit': #in (None,'Exit'):
   #    break
   # elif event == None:
   #    break
   else:
      break

window.Close()
   # if len(args) == 1: # collect arguments from GUI
ocr_folder_path = values['-FOLDER INPUT-']
ocr_folder_path = ocr_folder_path.replace('//','\\')
ocr_folder_path = str(ocr_folder_path + '\\')
half_pages = values['-IN-']
if half_pages == True:
   half_pages = 'yes'
else:
   half_pages = 'no'

# else: # collect arguements from sys.argv
#    ocr_folder_path = args.folder
#    ocr_folder_path = ocr_folder_path.replace('//','\\')
#    ocr_folder_path = str(ocr_folder_path + '\\')
#    half_pages = args.split_pages

def sub_dir_paths(file_path, file_type):
   paths = []
   for root, dirs, files in os.walk(file_path):
      if root != file_path:
         for file in files:
            if file.lower().endswith(file_type.lower()):
               paths.append(root + "\\")
   return(paths)

path_list = sub_dir_paths
run = CodeRunner(input_file_type,output_file_type)
run.rundownload(ocr_folder_path,pages_per_file,input_file_type, path_list,half_pages)