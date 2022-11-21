from flask import Flask, flash, request, redirect, url_for 
import flask
from flask.helpers import send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename 
from dotenv import load_dotenv
import os, io
import time
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes, VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials
import sys
import requests, uuid, json

ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg']) 

app = Flask(__name__)
cors = CORS(app)
load_dotenv()
subscription_key = os.getenv('COG_SERVICE_KEY')
location = os.getenv('COG_SERVICE_REGION')

def get_text(image, computervision_client):

    # Call API with image and raw response (allows you to get the operation location)
    read_response = computervision_client.read_in_stream(image, raw=True)
    # Get the operation location (URL with ID as last appendage)
    read_operation_location = read_response.headers["Operation-Location"]
    # Take the ID off and use to get results
    operation_id = read_operation_location.split("/")[-1]

    image.close()

    #t1 = time.time()
    # Call the "GET" API and wait for it to retrieve the results 
    i=0
    while True:
        i+=1
        read_result = computervision_client.get_read_result(operation_id)
        if read_result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)
    #t2 = time.time()
    #print("time taken: ", t2-t1)

    # Print the detected text, line by line
    if read_result.status == OperationStatusCodes.succeeded:
        text = ""
        for text_result in read_result.analyze_result.read_results:
            for line in text_result.lines:
                text += line.text
    return text

def detect_language(text, subscription_key, location, constructed_url):
    params = {
            "api-version": "3.0"
        }
    headers = {
    "Ocp-Apim-Subscription-Key": subscription_key,
    "Ocp-Apim-Subscription-Region": location,
    "Content-type": "application/json"
    }
    body = [{
        "text": text
    }]
    # Send the request and get response
    request = requests.post(constructed_url, params=params, headers=headers, json=body)
    response = request.json()
    language = response[0]["language"]
    return language

def translate(text, source_language, target_language, subscription_key, location, constructed_url):
    params = {
        'api-version': '3.0',
        'from': source_language,
        'to': target_language
    }

    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Ocp-Apim-Subscription-Region': location,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }


    body = [{
        'text': text
    }]

    request = requests.post(constructed_url, params=params, headers=headers, json=body)
    response = request.json()

    translation = response[0]["translations"][0]["text"]
    return translation

def allowed_file(filename): 
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 


@app.route("/", methods=["GET"])
def check_server():
    return flask.Response("Flask server is working!", headers={"Content-Type":"text/html"})

@app.route("/translate", methods=["POST"])
def my_translator():
    image_path = ""
    # check if the post request has the file part 
    if 'file' not in request.files: 
        print("file not in request")
        return flask.Response("Request does not contain image file.", headers={"Content-Type":"text/html"})
    
    file = request.files['file'] 
    target_language  = request.form.get("target_lang")
    #default is english
    if target_language == "":
        target_language = "en"

    if file and allowed_file(file.filename): 
        #read image file as bytes into file_like object
        image = io.BytesIO(file.read())

        #Authenticate Computer Vision client
        endpoint = "https://livetext.cognitiveservices.azure.com/"
        trans_endpoint = "https://api.cognitive.microsofttranslator.com"
        computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))
        detect_constructed_url = trans_endpoint + '/detect'
        trans_constructed_url = trans_endpoint + '/translate'
        
        text = get_text(image, computervision_client)
        source_language = detect_language(text, subscription_key, location, detect_constructed_url)
        translated_text = translate(text, source_language, target_language, subscription_key, location, trans_constructed_url)

        return flask.Response(translated_text, headers={"Content-Type":"text/html"})


if __name__ == "__main__":
    app.run("0.0.0.0", debug=True, threaded=True)

 
 
