from google import genai

from curation_utils import creds

client = None

def get_client(api_key_path, cred_path="/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/tokens.toml"):
  global client
  if client is None:
    creds.get_toml_value(path=cred_path, key=api_key_path)
    client = genai.Client(api_key=api_key_path)
  return client


def process_file(file_path, prompt, api_key_path="gemini.vv"):
  client = get_client(api_key_path=api_key_path)
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
