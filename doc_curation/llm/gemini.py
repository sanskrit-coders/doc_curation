from google import genai

client = genai.Client()

def process_file(file_path, prompt):
  uploaded = client.files.upload(
    file=file_path
  )

  response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents=[
      uploaded,
      prompt
    ]
  )
  
  return response
