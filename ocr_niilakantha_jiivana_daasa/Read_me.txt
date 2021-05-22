The package OCR Code includes three main modules, 'split_pdfs.py' , 'drive_upload.py' and 'merge_docs.py' and a module for user_input.

i) user_input.py
        - Used for user input for target folder for the rest of the modules.
        - split_pdfs.py will get the number of pages for splitting from here as well.
    
ii) split_pdfs.py
        -Google Drive does not allow large files to be uploaded to the server which would restrain the purpose of the OCR project. Splitting the pdf into small files greatly helps overcome the bottleneck.
        - This module will scan for pdf files in the target folder and split all of them placing them in neat folders, just within the target folder. 
        - The original pdf files will remain in their original folder through out the whole process (unharmed) for reference.

ii) pdf_to_jpeg.py
 - split_pdfs.py has been replaced with this file.
 - PDF files will be copied to a new folder of the name of the pdf and images extracted to the folder.
 - Images will then be converted back to pdfs of 10 pages each.

iii) drive_upload.py
        - This uploads the split pdfs from the separate folders to Google Drive, converts the files to Google Docs, and downloads the Docx version of the file into the same folder as the split pdf.

iv) merge_docs.py
        - This scans for all the Docx files in the folders and merges them neatly into the respective folders. This will bring together all the data from the original pdf into a merged.docx file.

v) user_run_all_code.py
         - Run all the code from this one file.
         - Code runs from where it stops, if interrupted in the middle.

Version Updates
OCR Code 2.0
 - Created an exe file to runs for easy user input using pyinstaller
 - Created an installable for easy install by user using Inno Setup Compiler
 - Created a gui using pysimplegui

OCR Code 1.6
 - Code includes pdf_to_jpeg.py replacing the split_pdf.py, doing the same work, releaving the user of print to pdf before uploading the file.
 - Includes an option to cut pdf pages into half.

OCR Code 1.5
 - Code runs from the cmd.
 - Run all the code from one file "user_run_all_code.py".
 - Code only runs automaticaly only for the files remaining at any level of code, if interrupted in the middle.

OCR Code 1.4
 - merge_docs.py - The final merged document file name takes the original pdf file name instead of "merged.docx"

OCR Code 1.3
    Bug fixes   
        - merge_docs.py was merging all the documents including those from other folders.
        - merge_docs.py was taking the merging the documents in the order 1,10,11,12.... which would render the merged document useless, as it was not in the order required.

OCR Code 1.2
    - split_pdfs.py and merge_docs.py included to chater for large files.
    - user_input.py included to reduce the strain of user having to input the same data in several files. (Reduces the risk of mistakes and file alterations.)

OCR Code 1.1
    - drive_upload.py

