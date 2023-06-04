import os
from dotenv import load_dotenv
import openai

# Cargar variables de entorno desde el archivo .env
load_dotenv()


# Indica el API Key
openai.api_key =  os.environ["OPENAI_KEY"]
# Uso de ChapGPT en Python
model_engine = "text-davinci-003"



def main():
    prompt = "la suma de 5 mas 5"
    completion = openai.Completion.create(engine=model_engine,
                                        prompt=prompt,
                                        max_tokens=1024,
                                        n=1,
                                        stop=None,
                                        temperature=0.7)
    respuesta=""
    for choice in completion.choices:
        respuesta=respuesta+choice.text
        print(f"Response: %s" % choice.text)

if __name__ == "__main__":
    main()
