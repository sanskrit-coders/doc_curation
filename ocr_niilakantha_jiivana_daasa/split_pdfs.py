import PyPDF2
from os import listdir
import os
from os.path import isfile, join
import shutil
import PySimpleGUI as sg
print = sg.Print

class Ssplit:
    def __init__(self,path_list):
        self.path_list = path_list
    
    def pdf_split(self, pdf, splits): 
        number_of_pages = self.number_of_pages
        pdf_reader = self.pdf_reader
        pdf_file_obj = self.pdf_file_obj
        
        start = 0
        end = splits[0] 
        
        for i in range(len(splits)+1): 
            pdfWriter = PyPDF2.PdfFileWriter() 
            
            # output pdf file name 
            outputpdf = pdf.split('.pdf')[0] + ' -Part-' + str(f"{i+1:03}") + '.pdf'

            with open(outputpdf, "wb") as f:
                for page in range(start,end): 
                    pdfWriter.addPage(pdf_reader.getPage(page))
                pdfWriter.write(f) 
    
            start = end 
            try: 
                end = splits[i+1] 
            except IndexError: 
                end = pdf_reader.numPages 
            
        pdf_file_obj.close() 

    def run_split_pdfs(self, folder_path, page_count):
        all_pdfs = [] 
        for pdf in listdir(folder_path):
            if isfile(join(folder_path, pdf)):
                if pdf.endswith(".pdf"):
                    all_pdfs.append(pdf)
                   
                    pdf_folders = []
                    for folder in self.path_list:
                        if folder not in pdf_folders:
                            pdf_folders.append(folder)

                    files = []
                    for f_path in pdf_folders:
                        for f in listdir(f_path):
                            if isfile(join(f_path, f)):
                                if f.endswith(".pdf"):
                                    files.append(f_path + f)

                    for fil in files:
                        original_pdf = os.path.basename(fil)
                        original_pdf = original_pdf[:len(original_pdf)-14]
                        original_pdf = str(original_pdf+".pdf")

                        original_path = os.path.dirname(fil)
                        original_path = original_path + "\\"

                        for fi in listdir(original_path):
                            if fi.endswith(".pdf"):
                                if original_pdf == pdf:
                                    if (pdf in all_pdfs):
                                        all_pdfs.remove(pdf)

                    for i in all_pdfs:
                        if (i == pdf):
                            self.progress_metre("Splitting PDFs",i,all_pdfs)
                            size = len(pdf)
                            directory = pdf[:size - 4]
                            parent_dir = folder_path
                            path = os.path.join(parent_dir, directory) 
                            os.mkdir(path)
                            print("Directory '% s' created" % directory) 

                            shutil.copy(join(folder_path,pdf),join(parent_dir,directory,pdf))
                            file_path = join(parent_dir,directory,pdf)
                            
                            self.pdf_file_obj = open(file_path, 'rb') 
                
                            self.pdf_reader = PyPDF2.PdfFileReader(self.pdf_file_obj) 

                            print(f"The total number of pages in the pdf document is {self.pdf_reader.numPages}")

                            self.number_of_pages = self.pdf_reader.numPages

                            number_of_pages = self.number_of_pages
                            if number_of_pages % page_count == 0:
                                number_of_output = number_of_pages/page_count
                            else:
                                number_of_output = (number_of_pages/page_count) + 1

                            number_of_output = int(number_of_output)

                            splits = [] 
                            
                            if number_of_pages >= page_count:
                                for i in range(1,number_of_output): 
                                    i = page_count * i
                                    splits.append(i)
                                Ssplit.pdf_split(self,file_path,splits)
                                os.remove(file_path)


    def progress_metre(self,title, item_file, list_of_files):
        sg.theme('DarkAmber')
        num_of_files = len(list_of_files)
        # for i in range(num_of_files):
        sg.OneLineProgressMeter(title, item_file + 1 ,num_of_files,'key')