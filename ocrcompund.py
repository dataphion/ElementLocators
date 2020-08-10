import cv2
import sys
import base64
import pytesseract
from pytesseract import Output
import json
from PIL import Image
import requests
from io import BytesIO

url = "http://10.93.16.36"
 
class Ocr_Tesseract:

  def getText(self,word,image):
    
    try :
      # imPath = str.encode(image)
      with open("imageToSave.png", "wb") as fh:
        fh.write(base64.b64decode(image.replace("data:image/png;base64,", "")))
      
      # Define config parameters.
      # '-l eng'  for using the English language
      # '--oem 1' for using LSTM OCR Engine
      config = ('-l eng --oem 1 --psm 3')
    
      # Read image from disk
      im = cv2.imread("imageToSave.png", cv2.IMREAD_GRAYSCALE)
      (iH,iW) = im.shape[:2]
    
      # Run tesseract OCR on image
      text = pytesseract.image_to_data(im, config=config,output_type=Output.DICT)

      sentences = []
      n_boxes = len(text['level'])
      j = 0
      sentence = ""
      data = None
      for i in range(n_boxes):
          # print(i)
          if (i + 1) in range(n_boxes): 
              (next_x, next_y, next_w, next_h) = (text['left'][i+1], text['top'][i+1], text['width'][i+1], text['height'][i+1])
              (x, y, w, h) = (text['left'][i], text['top'][i], text['width'][i], text['height'][i])
              
              if (next_x - (x + w)) < (h*0.8) and next_y < (y + h) and text['text'][i+1] != "":
                  
                  sentence+=(str(text['text'][i])+ " ")
              else:
                  sentence+=(str(text['text'][i])+ " ")
                  (rect_x, rect_y, rect_w, rect_h) = (text['left'][j], text['top'][j],text['left'][i] + text['width'][i], text['top'][i] + text['height'][i])
                  # print(text['text'][j])
                  # print(j)
                  j=i+1
                  sentences.append(sentence.strip())
                  if (sentence.strip()).lower() == word.lower():          
                      print("------------------------------------------------------")
                      print("YES")
                      
                      data = {'startX':rect_x,'startY':rect_y,'endX':rect_w,'endY':rect_h,'image_width':iW,'image_height':iH}
                      print("------------------------------------------------------")
                      
                  cv2.rectangle(im, (rect_x, rect_y), (rect_w, rect_h), (0, 0, 255), 2)
                  
                  sentence = ""
              
              
      # cv2.imshow('img', im)
      # cv2.imwrite("img.png",im)
      # cv2.waitKey(0)
      cv2.destroyAllWindows()

      # Print recognized text
      # print(text)
      print("------------------------------------------------------")
      print(sentences)
      
      if data == None:
        result = {'status':"fail",'data':"Not got the text"}
      else:
        result = {'status':"success",'data':data}
      
      return result

    except Exception as exception:

      print(exception)
      return {'status':"fail"}
