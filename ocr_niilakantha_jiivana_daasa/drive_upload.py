from __future__ import print_function
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
import PySimpleGUI as sg

# If modifying these scopes, delete the file token.pickle.
class GDrive():
	def __init__(self,input_file_type,output_file_type):	
		self.input_file_type = input_file_type
		self.output_file_type = output_file_type
		sg.Print("Authenticating...")
		self.SCOPES = ['https://www.googleapis.com/auth/drive']
		creds = None
		# The file token.pickle stores the user's access and refresh tokens, and is
		# created automatically when the authorization flow completes for the first time
		if os.path.exists('token.pickle'):
			with open('token.pickle', 'rb') as token:
				creds = pickle.load(token)
		if not creds or not creds.valid:
			if creds and creds.expired and creds.refresh_token:
				creds.refresh(Request())
			else:
				flow = InstalledAppFlow.from_client_secrets_file(
					join(pathlib.Path(__file__).parent.absolute() , 'client_secrets.json'), self.SCOPES)
				creds = flow.run_local_server(port=8080)
			with open(join(pathlib.Path(__file__).parent.absolute() ,'token.pickle'), 'wb') as token:
				pickle.dump(creds, token)
		socket.setdefaulttimeout(300)
		self.service = build('drive', 'v3', credentials=creds)
		# sg.Print("Authentication Complete")
		
	def upload(self, fileName, filePath):
		sg.Print("Uploading...")
		file_metadata = {'name': fileName, 'mimeType': 'application/vnd.google-apps.document'}
		if self.input_file_type == 'jpeg':
			media = MediaFileUpload(filePath, mimetype='image/jpeg')
		elif self.input_file_type == 'png':
			media = MediaFileUpload(filePath, mimetype='image/png')
		else:
			media = MediaFileUpload(filePath, mimetype='application/pdf')
		file1 = self.service.files().create(body=file_metadata,
											media_body=media,
											fields='id').execute()
		socket.setdefaulttimeout(300)
		sg.Print('%s Uploaded ' % file_metadata['name'])
		return file1.get('id')

	def upload_merged_doc(self, fileName, filePath):
		file_metadata = {'name': fileName, 'mimeType': 'application/vnd.google-apps.document'}
		media = MediaFileUpload(filePath, mimetype='application/msword')
		self.service.files().create(body=file_metadata,
											media_body=media,
											fields='id').execute()
		sg.Print('%s Uploaded ' % file_metadata['name'])

	def download(self, file_id):
		# sg.Print("Downloading...")
		if self.output_file_type == "docx":
			request = self.service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
		else:
			request = self.service.files().export_media(fileId=file_id, mimeType='text/plain')
		fh = io.BytesIO()
		downloader = MediaIoBaseDownload(fh, request)
		done = False
		while done is False:
			status, done = downloader.next_chunk()
		sg.Print("Download Complete...")
		return fh

	def writeFile(self, byteObject, fileName, outputPath):
		if self.output_file_type == "docx":
			with open(outputPath + fileName + u".docx", "wb") as outfile:
				outfile.write(byteObject.getbuffer())
		else:
			with open(outputPath + fileName + u".txt", "wb") as outfile:
				outfile.write(byteObject.getbuffer())
		# sg.Print("Completed")
	
	def convert(self, filePath, outputPath):
		fileName = os.path.basename(filePath)
		fileId = self.upload(fileName,filePath)
		self.writeFile(self.download(fileId), fileName, outputPath)

# if __name__ == '__main__':
# 	file_name = "C:\\Users\\Dell\\Desktop\\test\\test\\1.pdf"
# 	path_name = "C:\\Users\\Dell\\Desktop\\test\\test\\"
# 	drive = GDrive('pdf',"docx")
# 	drive.convert(str(file_name),str(path_name))
