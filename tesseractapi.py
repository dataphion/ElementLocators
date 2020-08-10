from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from flask_restful import Resource, Api, reqparse
from json import dumps
from ocrcompund import Ocr_Tesseract
from tempmatchnearest import TemplateMatch
from tempmatch import TemplateMatch1
from templatematch import TemplateMatchFind
from featurematch import FeatureMatch

from google.cloud import vision
from google.cloud.vision import types
from enum import Enum

import io
import json
import base64
import requests
import os

app = Flask(__name__)
api = Api(app)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
host = "http://10.93.16.36:1337/graphql"
getAttributeFile = os.environ.get('GET_ATTR_FILE') if os.environ.get('GET_ATTR_FILE') else  os.getcwd() + "\\getAttribute.txt"

def convertToBinaryData(filename):
    print("convert binary image", filename)
    with open(filename, 'rb') as file:
        binaryData = base64.b64encode(file.read())
    return binaryData

def get_document_bounds(image_file):
    """Returns document bounds given an image."""
    client = vision.ImageAnnotatorClient()

    bounds = []

    with io.open(image_file, 'rb') as image_file:
        content = image_file.read()

    image = types.Image(content=content)

    response = client.text_detection(image=image)
    # print(response)
    # {'x1':,'x2':,'y1':,'y2':}
    texts = []
    for text in response.text_annotations:
        d = {'text':str(text.description), 'box':{'x1':text.bounding_poly.vertices[0].x, 
                                        'x2':text.bounding_poly.vertices[2].x,
                                        'y1':text.bounding_poly.vertices[0].y,
                                        'y2':text.bounding_poly.vertices[2].y}}
        texts.append(d)
    return texts

class Template_Match(Resource):
    def post(self):
        self._templatematch = TemplateMatchFind()
        self._featurematch = FeatureMatch()
        self._ocrtext = Ocr_Tesseract()
        self._templatematchnearest = TemplateMatch()

        parser = reqparse.RequestParser()
        parser.add_argument("id")
        parser.add_argument("image")

        args = parser.parse_args()

        # try:
            # print()
        if args["id"] == None or args["image"] == None :
            return {"status":"fail","message":"Arguments error"} ,201
        else :
            print(type(args["image"]))
            print(args["id"])
            print(host)
            payload = {'query':"query{  objectrepositories(where: {id:\""+args["id"]+"\"}){id,element_snapshot,text}}"}
            response = requests.post(host+"/graphql",data=payload)
            print(response.content)
            resp = json.loads(response.content)
            resp = resp["data"]["objectrepositories"][0]
            print(resp['text'])

            failed = True
            if resp['text'] != "":
                ocrdata = self._ocrtext.getText(resp["text"],args["image"])
                print(ocrdata)

                if ocrdata["status"] == "success":

                    failed = False
                    template_result = self._templatematchnearest.matchtheimage(resp["element_snapshot"],args["image"],ocrdata["data"])
                    
                    if template_result["status"] == "success":
                        return template_result,201
                    else :
                        failed = True
            
            if resp['text'] == "" or failed:

                templatedata = self._templatematch.matchtheimage(resp["element_snapshot"],args["image"])
                return templatedata, 201
                
                if templatedata["status"] == "fail":
                    feature_result = self._featurematch.featurematch(resp["element_snapshot"],args["image"])
                    return feature_result, 201
                else :
                    return templatedata, 201
        
        # except Exception as identifier:
        #     print(identifier)
        #     return {'error':identifier}, 201
        
class PageOCR(Resource):
    def post(self):
        data = request.json
        scale = 1
        if 'scale' in data:
            scale = data['scale']

        """
        1. image_data &
        2. Pixelratio - Scale
        """
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        content_data = base64.b64decode(data['data'])
        image = vision.types.Image(content=content_data)
        response = client.document_text_detection(image=image)
        data = {}
        for page in response.full_text_annotation.pages:
            for block in page.blocks:

                for paragraph in block.paragraphs:
                    box = paragraph.bounding_box
                    word_text = ""
                    for word in paragraph.words:
                        word_text += ' '+''.join([symbol.text for symbol in word.symbols])
                    x1 = int(box.vertices[0].x/scale)
                    x2 = int(box.vertices[2].x/scale)
                    y1 = int(box.vertices[0].y/scale)
                    y2 = int(box.vertices[2].y/scale)
                    # x1 = int(box.vertices[0].x)
                    # x2 = int(box.vertices[2].x)
                    # y1 = int(box.vertices[0].y)
                    # y2 = int(box.vertices[2].y)
                    word_text = word_text.lower()
                    """if word_text in data:
                        # Check if the first element is Tuple or int.
                        print("%s already exists. Hence adding"%(word_text))
                        if not isinstance(data[word_text][0], list):
                            print("Before update")
                            print(data[word_text])
                            tmp = data[word_text]
                            data[word_text] = [tmp, [x1, y1, x2, y2]]
                        else:
                            data[word_text].append([x1, y1, x2, y2])
                        print("Data after update")
                        print(data[word_text])
                    else:
                        data[word_text] = [x1, y1, x2, y2]"""
                    data[word_text] = [x1, y1, x2, y2]
                    
        return jsonify({"data":data})

class ScanOCR(Resource):
    def post(self):
        data = request.json
        image = "/opt/data/image/img1.jpg"
        from PIL import Image
        data = get_document_bounds(image)
        width, height = Image.open(image).size
        return jsonify({"response":data, "width":width, "height": height})

class PDFToImage(Resource):
    def post(self):
        try:
            import os
            import pdf2image

            mydir = "/opt/data"
            # filelist = [ f for f in os.listdir(mydir) if f.endswith(".jpg") ]
            # for f in filelist:
            #     os.remove(os.path.join(mydir, f))

            if 'file' not in request.files:
                return "No file found"
            PDF_file = "/opt/data/pdf/test.pdf"

            file = request.files['file']
            file.save(PDF_file)
            print(PDF_file)
            pages = pdf2image.convert_from_path(PDF_file, 500)
            image_counter = 1
            print("all pages", pages)
            images = [] 
            # Remove all jpg files from folder..
            os.popen('rm -f /opt/data/image/*.jpg')

            for page in pages:
                print("pages", page)
                filename = "img"+str(image_counter)+".jpg"
                page.save(os.path.join(mydir+"/image/", filename), 'JPEG')
                empPicture = convertToBinaryData(mydir+"/image/" + filename)
                # print(filename, "--->", empPicture)
                img = {"img_data": empPicture}
                images.append(img)
                image_counter += 1
            return jsonify(images)

        except Exception as e:
            print("exception", e)
            res = jsonify({"status":"unsuccessful"})
            return res

class Find_Element(Resource):
    def get(self):

        with open(getAttributeFile,"r") as f:
            sttrr = f.read().strip().replace('\n', '')
        # print(sttrr)
        data = {"data" :sttrr}
        return data , 201

api.add_resource(Template_Match, '/vision/api/TemplateMatch')
api.add_resource(PageOCR, '/vision/api/PageOCR')
api.add_resource(ScanOCR, '/vision/api/ScanOCR')
api.add_resource(PDFToImage, '/vision/api/PDFToImage')
api.add_resource(Find_Element, '/vision/api/find_element')

if __name__ == '__main__':

    host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337"
    app.run(host='0.0.0.0',port='9502')
