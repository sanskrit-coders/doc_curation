from __future__ import print_function
# for drive_upload.py
import pickle
import io
from os import listdir
from os.path import isfile, join
import socket
from googleapiclient.discovery import BODY_PARAMETER_DEFAULT_VALUE, build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import *
import pathlib

# for pdf_to_jpeg.py
# from __future__ import print_function
import shutil
import fitz
import os.path
from os.path import isfile,join
from os import listdir
import os

# for split_pdf.py (incase it would be used)
import PyPDF2
from os import listdir
import os
from os.path import isfile, join
import shutil

# for merge_docs
from docx import Document

# for run_code.py
from os.path import isfile,join
import os
from os import listdir
import shutil
import split_pdfs
import drive_upload
import merge_docs
import pdf_to_jpeg

# for user_input.py
import os
from run_code import CodeRunner
import argparse

# for setup.py
from distutils.core import setup # Need this to handle modules
import py2exe

setup(
    options = {'py2exe': {'bundle_files': 1, 'compressed': True}},
    console = [{'script': 'C:\\Users\\Dell\\Downloads\\Ocr Code Portable\\Ocr Code 1.5_portable\\ocr_code_1.6\\user_input.py'}],
    zipfile = None,
)