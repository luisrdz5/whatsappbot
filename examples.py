import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import boto3
import io
from PIL import Image
import psycopg2
import argparse
import datetime
import uuid

# Cargar variables de entorno desde el archivo .env
load_dotenv()


uuid_log= str(uuid.uuid4())
# Obtener credenciales de la cuenta de servicio desde las variables de entorno
creds = service_account.Credentials.from_service_account_info({
    "type": os.environ["TYPE"],
    "project_id": os.environ["PROJECT_ID"],
    "private_key_id": os.environ["PRIVATE_KEY_ID"],
    "private_key": os.environ["PRIVATE_KEY"].replace('\\n', '\n'),
    "client_email": os.environ["CLIENT_EMAIL"],
    "client_id": os.environ["CLIENT_ID"],
    "auth_uri": os.environ["AUTH_URI"],
    "token_uri": os.environ["TOKEN_URI"],
    "auth_provider_x509_cert_url": os.environ["AUTH_PROVIDER_X509_CERT_URL"],
    "client_x509_cert_url": os.environ["CLIENT_X509_CERT_URL"]
})


folder_id = os.environ["FOLDER_ID"]
bucket_name = os.environ["BUCKET_NAME"]
s3_client = boto3.client('s3')
models_catalog_str= [
    {
        "name": "BASE PARA BOCINA",
        "model": "BasesBocina",
        "tabla":"basesBocina",
        "google_id": ""
    },
    {
        "name": "EPICENTROS",
        "model": "Epicentros",
        "tabla":"Epicentros",
        "google_id": ""
    },
    {
        "name": "SEGURIDAD",
        "model": "BasesBocina",
        "tabla":"basesBocina",
        "google_id": ""
    },
    {
        "name": "AMPLIFICADORES",
        "model": "Amplificadores",
        "tabla":"Amplificadores",
        "google_id": ""
    },
    {
        "name": "AUTOESTEREOS",
        "model": "Estereos",
        "tabla":"Estereos",
        "google_id": ""
    },
    {
        "name": "BOCINAS",
        "model": "Bocinas",
        "tabla":"Bocinas",
        "google_id": ""
    },
    {
        "name": "TWEETERS",
        "model": "Tweeters",
        "tabla":"Tweeters",
        "google_id": ""
    },
    {
        "name": "FRENTES",
        "model": "Bases",
        "tabla":"Bases",
        "google_id": ""
    }                       
]


models_catalog = models_catalog_str

# Crear una instancia de la API de Google Drive
service = build("drive", "v3", credentials=creds)


# Establecer la conexión con la base de datos
conn = psycopg2.connect(
    host= os.environ["DB_HOST"],
    database= os.environ["DB_NAME"],
    user= os.environ["DB_USER"],
    password= os.environ["DB_PASSWORD"]
)


def list_files_in_folder(folder_id, archivos, parent="", product="" ):
    """Lista todos los archivos y carpetas en la carpeta especificada en Google Drive"""
    archivosinternos=0
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="nextPageToken, files(parents,name, id, mimeType)").execute()
    items = results.get("files", [])
    parents = []
    for item in items:
        validate_model(item["name"], item["id"])
   
    for item in items:
        if item["mimeType"] == "application/vnd.google-apps.folder":
            print(f'Entrando a carpeta una carpeta con ID: {item["name"]}')
            archivos= archivos + list_files_in_folder(item["id"], archivos, item['parents'][0], item["name"])
        else:
            file_id = item['id']
            file_name = item['name']
            file_name = file_name.replace('_Ig.', '_lg.')
            #validamos la estructura 
            try:
                # Obtener el contenido del archivo y convertir a png
                file_content = service.files().get_media(fileId=file_id).execute()
                img = Image.open(io.BytesIO(file_content))
                png_content = io.BytesIO()
                img.save(png_content, format='png', optimize=True)
                png_content.seek(0)
                # Cargar el archivo png en S3
                s3_file_key = f'{bucket_name}/{file_name.split(".")[0]}.png'  # Cambiar la extensión del archivo a png
                s3_client.upload_fileobj(png_content, bucket_name, s3_file_key, ExtraArgs={'ACL': 'public-read'}) 
                url=f'https://{bucket_name}.s3.amazonaws.com/{s3_file_key}'
                archivos += 1
                print(f'Archivo {item["name"]} subido a S3.')
                # Obtengo el id de la carpeta padre
                model= get_model(parent)
                print(f'Descargando el archivo: {file_name}')
                size = file_name.split("_")[2].split(".")[0]
                sku = file_name.split("_")[0]
                id_image = file_name.split("_")[1].split(".")[0]
                data = {
                    'type':s3_file_key.split(".")[1],
                    'fileName':file_name,
                    'url':url,
                    'product':model[1],
                    'sku': sku,
                    'size': size,
                    'model': model[0],
                    'tabla': model[2],
                    'id_image': id_image,
                }
                verify_data(data)
            except (Exception) as error:
                log = f' el archivo : {file_name} genero el error: {error} '
                write_log(log)
    return archivosinternos

'''


* Se debe hacer catalogo de tamaños
** Plus
Crear imagenes tamaño md y small
'''

def validate_model(modelName, modelId):
    for i in range(len(models_catalog)):
        if models_catalog[i]['name'] == modelName:
            models_catalog[i]['google_id'] = modelId
            break

def get_model(parentid):
    print(f'parentid es: {parentid} ')
    for i in range(len(models_catalog)):
        valor=models_catalog[i]['google_id']
        if models_catalog[i]['google_id'] == parentid:
            #return models_catalog[i]['model']
            data = [models_catalog[i]['model'], models_catalog[i]['name'], models_catalog[i]['tabla']]
            return data
            break

def verify_data(data):
    print(f'validando sku : {data["sku"]}')  
    tabla = data["tabla"]
    cadena = f'select sku from "{tabla}" where sku=\'{data["sku"]}\';' 
    try:
        # busco el sku en el modelo 
        cur = conn.cursor()
        cur.execute(cadena) 
        sku = cur.fetchone()   
        if(sku):
            id_foto = save_files_into_db(data)
            print(f' id_foto encontrado : {id_foto}')
            cadena = f'UPDATE "{tabla}" SET "fotosId"={id_foto}  where sku=\'{data["sku"]}\';' 
            cur.execute(cadena)
        else:
            log = f' sku NO encontrado : {data["sku"]} en el producto: {data["product"]} en la tabla: {tabla} '
            write_log(log)
        #cur.execute('INSERT INTO "DetalleFotos" ( type, "fileName", url, product, sku, size, model, created_at) VALUES (%s, %s ,%s, %s ,%s, %s, %s , NOW());', (data["type"], data["fileName"], data["url"], data["product"], data["sku"], data["size"] ,data["model"]))
        conn.commit()  
        cur.close()       
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)

def save_files_into_db(data):
    """Lista todos los archivos y carpetas en la carpeta especificada en Google Drive"""
    try:
        # inserto en tabla CatalogoFotos y DetalleFotos
        cur = conn.cursor()
        cur.execute('INSERT INTO "CatalogoFotos" (sku, model, created_at) VALUES (%s, %s , NOW()) RETURNING id ;', (data["sku"], data["model"]))    
        # Obtener el ID del registro insertado
        id_insertado = cur.fetchone()[0]
        cur.execute('INSERT INTO "DetalleFotos" ( type, "fileName", url, product, sku, size, model, "idCatalogoFotos", created_at) VALUES (%s, %s ,%s, %s ,%s, %s, %s, %s , NOW());', (data["type"], data["fileName"], data["url"], data["product"], data["sku"], data["size"] ,data["model"], id_insertado))
        conn.commit()  
        cur.close()  
        return id_insertado     
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    

def write_log(cadena):
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nombre_archivo = 'logs/log_' + fecha[:10] + uuid_log + '.txt'  
    # crea la carpeta si no existe
    os.makedirs(os.path.dirname(nombre_archivo), exist_ok=True) 
    with open(nombre_archivo, 'a') as archivo:
        archivo.write(fecha + ': ' + cadena + '\n')

def truncate_tables():
    print("Truncando tablas CatalogoFotos y DetalleFotos ")
    cur = conn.cursor()
    try:
        cur.execute('TRUNCATE TABLE "CatalogoFotos"')
        conn.commit()
        cur.execute('TRUNCATE TABLE "DetalleFotos"')
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)

def main():
    # Definir los argumentos que puede recibir el script
    parser = argparse.ArgumentParser(description='Este script Toma imagenes cargadas en una carpeta de google drive y las sube a s3 ')
    parser.add_argument('action', type=str, choices=['new', 'add'], help='Acción a realizar')
    args = parser.parse_args()
    archivos = 0
    if args.action == 'new':
        print('Se van a truncar las tablas de fotos y se cargaran todas nuevamente .... ')
        truncate_tables()
        archivos = list_files_in_folder(folder_id,  archivos )

    if args.action == 'new':
        print('Se van a agregar las nuevas fotos a las tablas .... ')
        archivos = list_files_in_folder(folder_id,  archivos )
    print(f'Se pocesaron: {archivos} archivos')

if __name__ == "__main__":
    main()
