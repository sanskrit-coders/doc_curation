from os.path import isfile,join
import os
from os import listdir
import shutil
import split_pdfs
import drive_upload
import merge_docs
import pdf_to_jpeg
import PySimpleGUI as sg
import time

file_paths = []
folder_paths = []
pdf_folders = []
all_doc_folders = []
doc_folders = []
files = []
files_in_merged_docs = []
copy_merged_docs = []

class CodeRunner():
   def __init__(self,input_file_type,output_file_type):	
      self.input_file_type = input_file_type
      self.output_file_type = output_file_type

   def rundownload(self,ocr_folder_path, pages_per_file, input_file_type, get_paths, half_pages):
      
      self.path_list = get_paths(ocr_folder_path, input_file_type)
      jpeg = pdf_to_jpeg.PDF_to_JPEG(self.path_list)
      jpeg.run_pdf_to_jpeg(ocr_folder_path, pages_per_file, half_pages)
      # s = split_pdfs.Ssplit(path_list)
      # s.run_split_pdfs(ocr_folder_path, pages_per_file)
      self.path_list = get_paths(ocr_folder_path,input_file_type)
      path_list = self.path_list
      
      
      for folder in path_list:
         if folder not in pdf_folders:
            pdf_folders.append(folder)

      for f_path in pdf_folders:
         for f in listdir(f_path):
            if isfile(join(f_path, f)):
               if f.endswith(".pdf"):
                  file_paths.append(f_path + f)
                  folder_paths.append(f_path)

                  for fil in file_paths:
                     ocr_doc = os.path.basename(fil)
                     ocr_doc = str(ocr_doc+".docx")

                     for fol in pdf_folders:
                        for fi in listdir(fol):
                           if fi.endswith(".docx"):
                              if ocr_doc == fi:
                                 sg.Print('%s already downloaded' %f)
                                 file_paths.remove(f_path + f)
                                 folder_paths.remove(f_path)
      
      if file_paths != []:
         drive = drive_upload.GDrive(self.input_file_type,self.output_file_type)
      
         for file_name,path_name in zip(file_paths, folder_paths):
            drive.convert(str(file_name),str(path_name))
            # self.progress_metre(file_name)

      for folder in path_list:
         if folder not in all_doc_folders:
            all_doc_folders.append(folder)
            doc_folders.append(folder)

            for fol in doc_folders:
               for fi in listdir(fol):
                  if isfile(join(fol,fi)):
                     if fi.endswith(" - merged.docx"):
                        if (fol in doc_folders):
                           sg.Print('%s has already been merged'% os.path.dirname(fol))
                           doc_folders.remove(fol)

      merged_docs_folder = os.path.join(ocr_folder_path, "Merged Docs")
      if not os.path.isdir(join(ocr_folder_path, "Merged Docs")):
         os.mkdir(merged_docs_folder)

      
      for folder_path in doc_folders:
         for f in listdir(folder_path):
            if isfile(join(folder_path, f)):
                  if f.endswith(".docx"):
                     files.append(folder_path + f)
         merge_docs.combine_word_documents(files)
         sg.Print(os.path.basename(os.path.dirname(join(folder_path,f))) + ".pdf merged")
         files.clear()

      
      for k in listdir(merged_docs_folder):
         files_in_merged_docs.append(k)

      
      for i in all_doc_folders:
         for n in listdir(i):
            if isfile(join(i,n)):
               if n.endswith(" - merged.docx"):
                  copy_merged_docs.append(join(i,n))
      
      sg.Print("Cleaning up the files...")
      drive = drive_upload.GDrive(self.input_file_type, self.output_file_type)
      for item in copy_merged_docs:
         if os.path.basename(item) not in files_in_merged_docs:
            shutil.copy(item, merged_docs_folder)

      sg.Print("OCR has been done for all the pdfs and docx files copied to 'Merged Docs' folder")

      for item in copy_merged_docs:
         drive.upload_merged_doc(str(os.path.basename(item)),str(item))
         # drive_upload.GDrive(self.input_file_type, self.output_file_type).upload_merged_doc(str(os.path.basename(item)),str(item))

      sg.Print("The program will now shut down automatically")

      for i in all_doc_folders:
         shutil.rmtree(i)

      sg.Print("Shut Down")
      time.sleep(5)

