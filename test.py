# import google.generativeai as genai
# genai.configure(api_key="AIzaSyA8HGldCViU0bKIdo7EtfH7D-HdkvFRKaw")

# models = genai.list_models()
# for model in models:
#     print(model.name, model.supported_generation_methods)

import google.generativeai as genai

genai.configure(api_key="AIzaSyA8HGldCViU0bKIdo7EtfH7D-HdkvFRKaw")

model = genai.GenerativeModel("gemini-1.5-flash-latest")

response = model.generate_content("Summarize: I bought a coke and chips at 7-Eleven for 3 dollars.")

print(response.text)
