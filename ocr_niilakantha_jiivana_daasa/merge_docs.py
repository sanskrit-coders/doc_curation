from docx import Document
import os

def combine_word_documents(files):
    merged_document = Document()

    for index, file in enumerate(files):
        sub_doc = Document(file)

        if index < len(files)-1:
            sub_doc.add_page_break()

        for element in sub_doc.element.body:
            merged_document.element.body.append(element)

    path = os.path.dirname(files[0])

    merged_doc_name = (path + '\\' + os.path.basename(path) + ' - merged' + '.docx')
    merged_document.save(merged_doc_name)
    return merged_doc_name
