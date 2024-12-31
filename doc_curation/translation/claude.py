import logging

import anthropic

from doc_curation import configuration

# Initialize the Claude client
client = anthropic.Anthropic(api_key=configuration['claude']["key"])


def translate_to_es_details(text):  
  # Send a basic message to Claude
  message = client.messages.create(
    model="claude-3-5-sonnet-20240620",
    max_tokens=1024,
    messages=[
      {"role": "user", "content": f"Translate the below to English and Spanish (use markdown format). Enclose the translation in tags of the form: <details><summary>English</summary>\\n\\nEN_TRANSLATION\\n</details>\\n\\n<details><summary>Español</summary>\\n\\nES_TRANSLATION\\n</details>: \n{text}"}
    ],
  )  
  # Print the response
  logging.debug(message.content)
  return message.content


if __name__ == '__main__':
  translate_to_es_details("समुद्रस्स्रोत्यानां स्रोतसि भवानां नद्यादीनाम् । 'स्रोतसो विभाषा ड्यड्ड्यौ' इति ड्यः ॥")