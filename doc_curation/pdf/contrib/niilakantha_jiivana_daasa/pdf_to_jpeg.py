from __future__ import print_function
import shutil
import fitz
import os.path
from os.path import isfile,join
from os import listdir
import os
import PySimpleGUI as sg
# sg.Print = sg.Print

all_pdfs = [] 
pdf_folders = []
files = []
img_list = []

class PDF_to_JPEG:
    def __init__(self,path_list):
        self.path_list = path_list

    def pdf_jpeg(self, file_path, img_fol):
        self.pdf_file_obj = fitz.open(file_path)
        sg.Print(f"The total number of pages in the pdf document is {self.pdf_file_obj.page_count}")
        self.number_of_pages = self.pdf_file_obj.page_count
        number_of_pages = self.number_of_pages
        pdf_file_obj = self.pdf_file_obj
        
        sg.Print("Splitting pdf to images...")
        i = 0
        for page in range(number_of_pages):
            page = pdf_file_obj.loadPage(page)  # number of page
            zoom = 2.0  # zoom brings clarity to the pdf photos
            mat = fitz.Matrix(zoom, zoom)  # zoom factor 2 in each dimension
            pix = page.get_pixmap(matrix=mat)  # use 'mat' instead of the identity matrix
            # pix = page.getPixmap() # outputs low-quality photos
            output = join(img_fol,os.path.basename(file_path)) + ' -Part-' + str(f"{i+1:05}") + '.png'
            # output = join(os.path.dirname(file_path) + os.path.basename(file_path)) + ' -Part-' + str(f"{i+1:05}") + '.jpeg'
            pix.writePNG(output)
            i = i + 1

    def jpeg_pdf(self, file_path, img_fol, pages_per_file):
        sg.Print("Preparing split pdfs...")
        for img in listdir(img_fol):
            if isfile(join(img_fol, img)):
                if img.endswith(".png"):
                    img_list.append(join(img_fol, img))

        number_of_pages = self.number_of_pages
        if number_of_pages % pages_per_file == 0:
            number_of_output = number_of_pages/pages_per_file
        else:
            number_of_output = (number_of_pages/pages_per_file) + 1

        self.number_of_output = int(number_of_output)
        number_of_output = self.number_of_output

        a = 0
        p = 1

        for _ in range(number_of_output):
            doc = fitz.open()
            for f in img_list:
                img = fitz.open(f)  # open pic as document
                rect = img[0].rect  # pic dimension
                pdfbytes = img.convert_to_pdf()  # make a PDF stream
                img.close()  # no longer needed
                imgPDF = fitz.open("pdf", pdfbytes)  # open stream as PDF
                page = doc.new_page(width = rect.width,  # new page with ...
                                height = rect.height)  # pic dimension
                page.show_pdf_page(rect, imgPDF, 0)  # image fills the page
                os.remove(join(img_fol,f))
                a = a + 1
                if a % pages_per_file == 0:
                    del img_list[:pages_per_file]
                    break
                
            doc.save(join(img_fol,os.path.basename(file_path)) + ' -Part- ' + str(f"{p:04}") + '.pdf')
            p = p + 1
        del img_list[:]
        self.pdf_file_obj.close()
        os.remove(file_path)

    def split_pages_half(self, file_path, img_fol):  
        sg.Print("Splitting the pdf pages into half...")

        src = fitz.open(file_path)
        doc = fitz.open()  # empty output PDF

        for spage in src:  # for each page in input
            r = spage.rect  # input page rectangle
            d = fitz.Rect(spage.CropBoxPosition,  # CropBox displacement if not
                        spage.CropBoxPosition)  # starting at (0, 0)
            #--------------------------------------------------------------------------
            # example: cut input page into 2 parts horizontally
            #--------------------------------------------------------------------------
            tmp = (r.tl + r.tr) / 2 # mid-point at the top
            bmp = (r.bl + r.br) / 2 # mid-point at the bottom
            r1 = fitz.Rect(r.tl, bmp)   
            r2 = fitz.Rect(tmp, r.br)
            
            rect_list = [r1 , r2]  # put them into a list

            for rx in rect_list:  # run thru rect list
                rx += d  # add the CropBox displacement
                page = doc.new_page(-1,  # new output page with rx dimensions
                                width = rx.width,
                                height = rx.height)
                page.show_pdf_page(
                        page.rect,  # fill all new page with the image
                        src,  # input document
                        spage.number,  # input page number
                        clip = rx,  # which part to use of input page
                    )
        src.close()
        os.remove(file_path)
        doc.save(join(img_fol, os.path.basename(src.name)),
                garbage=3,  # eliminate duplicate objects
                deflate=True,  # compress stuff where possible
        )

    def run_pdf_to_jpeg(self, folder_path, pages_per_file, half_pages):
        for pdf in listdir(folder_path):
            if isfile(join(folder_path, pdf)):
                if pdf.endswith(".pdf"):
                    all_pdfs.append(pdf)
                    
                    for folder in self.path_list:
                        if folder not in pdf_folders:
                            pdf_folders.append(folder)

                    for f_path in pdf_folders:
                        for f in listdir(f_path):
                            if isfile(join(f_path, f)):
                                if f.endswith(".pdf"):
                                    if (folder + f) not in files:
                                        files.append(f_path + f)

                    for fil in files:
                        original_pdf = os.path.basename(fil)
                        split_pdf = os.path.basename(fil)
                        split_pdf = split_pdf[:len(split_pdf) - 20]
                        split_pdf = str(split_pdf + ".pdf")
                        
                        original_path = os.path.dirname(fil)
                        original_path = original_path + "\\"

                        for fi in listdir(original_path):
                            if fi.endswith(".pdf"):
                                if pdf == split_pdf or pdf == original_pdf:
                                    if pdf in all_pdfs:
                                        sg.Print ("%s has already been split"%os.path.basename(pdf))
                                        all_pdfs.remove(pdf)

                    for i in all_pdfs:
                        if i == pdf:
                            # self.progress_metre(item_file = i, list_of_files = all_pdfs)
                            size = len(pdf)
                            directory = pdf[:size - 4]
                            parent_dir = folder_path
                            path = os.path.join(parent_dir, directory) 
                            os.mkdir(path)
                            sg.Print("Directory '% s' created" % directory) 

                            shutil.copy(join(folder_path,pdf),join(parent_dir,directory,pdf))
                            file_path = join(parent_dir,directory,pdf)


                            self.img_fol = path
                            img_fol = self.img_fol
                            
                            if half_pages == "yes":
                                sg.Print ("PDF pages will be split into half vertically")
                                self.split_pages_half(file_path, img_fol)
                                self.pdf_jpeg(file_path, img_fol)
                                self.jpeg_pdf(file_path, img_fol, pages_per_file)
                            else:
                                self.pdf_jpeg(file_path, img_fol)
                                self.jpeg_pdf(file_path, img_fol, pages_per_file)

    
    def progress_metre(item_file, list_of_files):
        sg.theme('DarkAmber')
        num_of_files = len(list_of_files)
        # for i in range(num_of_files):
        sg.OneLineProgressMeter('Splitting %s'% item_file, item_file + 1 ,num_of_files,'key')

# ocr_folder_path = 'C:\\Users\\Dell\\Desktop\\test'
# # file_path = 'C:\\Users\\Dell\\Desktop\\test\\1.pdf'
# # img_fol = 'C:\\Users\\Dell\\Desktop\\test\\testfiles\\'
# half_pages = "no"
# pages_per_file = 10


# def sub_dir_paths(file_path, file_type):
#    paths = []
#    for root, dirs, files in os.walk(file_path):
#       if root != file_path:
#          for file in files:
#             if file.lower().endswith(file_type.lower()):
#                paths.append(root + "\\")
#    return(paths)

# path_list = sub_dir_paths(ocr_folder_path,'pdf')

# jpeg = PDF_to_JPEG(path_list)
# jpeg.run_pdf_to_jpeg(ocr_folder_path, pages_per_file, half_pages)