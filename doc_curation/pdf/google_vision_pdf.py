#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# See: https://github.com/googleapis/python-vision/blob/master/samples/snippets/detect/detect.py

import argparse
import io

from google.cloud import vision_v1

from doc_curation import pdf as doc_curation_pdf


def sample_batch_annotate_files(file_path="path/to/your/document.pdf"):
    """Perform batch file annotation."""
    client = vision_v1.ImageAnnotatorClient()

    # Supported mime_type: application/pdf, image/tiff, image/gif
    mime_type = "application/pdf"
    final_ocr_path = file_path + ".txt"
    dest_pdfs = doc_curation_pdf.split_into_small_pdfs(pdf_path=file_path,
                                                       small_pdf_pages=5, start_page=1, end_page=None)
    file_out = io.open(file_path + ".txt", "w")
    for dest_pdf in dest_pdfs:
        with io.open(dest_pdf, "rb") as f:
            content = f.read()
        input_config = {"mime_type": mime_type, "content": content}
        features = [{"type_": vision_v1.Feature.Type.DOCUMENT_TEXT_DETECTION}]

        # The service can process up to 5 pages per document file. The splitting
        # above ensures each file has not more than 5 pages
        pages = [i + 1 for i in range(5)]
        requests = [{"input_config": input_config, "features": features, "pages": pages}]

        response = client.batch_annotate_files(requests=requests)
        for image_response in response.responses[0].responses:
            file_out.write(u"{}".format(image_response.full_text_annotation.text))
    file_out.close()


def main():
    parser = argparse.ArgumentParser(description="OCR a PDF using google vision")
    parser.add_argument("--input-file", help="input pdf file to be ocred", required=True,
                        type=str)
    args = parser.parse_args()
    sample_batch_annotate_files(args.input_file)


if __name__ == '__main__':
    main()
