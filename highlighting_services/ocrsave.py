import cv2
import sys
import base64
import pytesseract
from pytesseract import Output
import json
import math
import shutil
import requests
import os

host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337"
class OCR:

    def setText(self,jcoord):

        try :
            ### get coordinates
            (startX,startY) = ( int(jcoord["x_cord"]) , int(jcoord["y_cord"]) )
            (endX,endY) = ( int(jcoord["x_cord"]) + int(jcoord["width"]), int(jcoord["y_cord"]) + int(jcoord["height"]) )
            print(str(startX)+" "+str(startY))

            ### get image
            base_image_url = jcoord["base_image"]["url"]
            print(base_image_url)
            response = requests.get(host+base_image_url, stream=True)
            with open('OcrImage.png', 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            # Read image from disk
            im = cv2.imread("OcrImage.png", cv2.IMREAD_GRAYSCALE)
            (iH,iW) = im.shape[:2]
            
            # Define config parameters.
            # '-l eng'  for using the English language
            # '--oem 1' for using LSTM OCR Engine
            config = ('-l eng --oem 1 --psm 3')
            # Run tesseract OCR on image
            text = pytesseract.image_to_data(im, config=config,output_type=Output.DICT)

            sentences = []
            n_boxes = len(text['level'])
            j = 0
            sentence = ""
            word = ""
            found = None
            for i in range(n_boxes):
                # print(i)
                if (i + 1) in range(n_boxes): 
                    (next_x, next_y, next_w, next_h) = (text['left'][i+1], text['top'][i+1], text['width'][i+1], text['height'][i+1])
                    (x, y, w, h) = (text['left'][i], text['top'][i], text['width'][i], text['height'][i])
                    
                    if (next_x - (x + w)) < (h*0.75) and next_y < (y + h) and text['text'][i+1] != "":
                        
                        sentence+=(str(text['text'][i])+ " ")
                    else:
                        sentence+=(str(text['text'][i])+ " ")
                        (senstartX, senstartY, senendX, senendY) = (text['left'][j], text['top'][j],text['left'][i] + text['width'][i], text['top'][i] + text['height'][i])
                        (sencentX,sencentY) = ((senstartX + senendX)/2,(senstartY + senendY)/2)
                        # print(text['text'][j])
                        # print(j)
                        j=i+1
                        sentence = sentence.strip()
                        sentences.append(sentence)

                        # distance = math.sqrt( ((senstartX-int(startX))**2)+((senstartY-int(startY))**2))
                        # rightdistance = math.sqrt( ((senendX-int(endX))**2)+((senendY-int(endY))**2))
                        topdistance = math.sqrt( ((senstartX-startX)**2)+((senendY-startY)**2))
                        leftdistance = math.sqrt( ((senstartX-endX)**2)+((senstartY-startY)**2))
                        distance = min(topdistance,leftdistance)

                        if found is None or (distance < found and sentence != "" and  int(senstartX) in range(0,int(startX)+10) and int(senstartY) in range(0,int(startY)+10)):
                            found = distance
                            word = sentence
                        
                        sentence = ""
                    
                    
            # cv2.imshow('img', im)
            # cv2.imwrite("img.png",im)
            # cv2.waitKey(0)
            cv2.destroyAllWindows()

            # Print recognized text
            # print(text)
            print("------------------------------------------------------")
            print(sentences)
            
            if word == "":
                result = {'status':"fail",'data':"Not got the text"}
            else:
                result = {'status':"success",'word':word}
            
            return result

        except Exception as exception:

            print(exception)
            return {'status':"fail"}

