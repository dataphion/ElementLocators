import cv2
import sys
import pytesseract
from pytesseract import Output
import base64
import math
import requests, json
import shutil
 
if __name__ == '__main__':
 
    # if len(sys.argv) < 1:
    #     print('Usage: python test.py image.jpg texttofind' )
    #     sys.exit(1)
    
    url = "http://10.93.16.36:1337"
    payload = { 'query':"query{  objectrepositories(where:{id:\"5d25e66c19061c1965d9f656\"}){  description,  pixel_ratio,x_cord,  y_cord,height,width,    base_image{      url    }  }}"}
    response = requests.post(url+"/graphql",data=payload)
    # print(response.content)
    jresponse = json.loads(response.content)
    # print(jresponse)
    
    for  jsonresponse in jresponse["data"]["objectrepositories"]:

        if jsonresponse["x_cord"] is not None:

            jsonresponse['x_cord'] = jsonresponse['x_cord'] * float(jsonresponse['pixel_ratio'])
            jsonresponse['y_cord'] = jsonresponse['y_cord'] * float(jsonresponse['pixel_ratio'])
            jsonresponse['width'] = jsonresponse['width'] * float(jsonresponse['pixel_ratio'])
            jsonresponse['height'] = jsonresponse['height'] * float(jsonresponse['pixel_ratio'])
            print(jsonresponse["x_cord"])
            (startX,startY) = ( jsonresponse["x_cord"] , jsonresponse["y_cord"]) 
            (endX,endY) = ( jsonresponse["x_cord"] + jsonresponse["width"], jsonresponse["y_cord"] + jsonresponse["height"]) 
            print(str(startX)+" "+str(startY))

            
            base_image_url = jsonresponse["base_image"]["url"]
            print(base_image_url)
            response = requests.get(url+base_image_url, stream=True)
            with open('page.png', 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)                
            page = cv2.imread("page.png")
            # Read image path from command line
            # imPath = sys.argv[1]

            # (startX,startY) = ( float("728")*1.125 , float("86") *1.125)
            # (endX,endY) = ( float("719")*1.125 + float("54")*1.125,float("591") *1.125+ float("29")*1.125)
            # print(str(startX)+" "+str(startY))
            #   word = sys.argv[2]
            
            # Read image from disk
            # im = cv2.imread(imPath, cv2.IMREAD_GRAYSCALE)

            # Define config parameters.
            # '-l eng'  for using the English language
            # '--oem 1' for using LSTM OCR Engine
            config = ('-l eng --oem 1 --psm 3')
            # Run tesseract OCR on image
            text = pytesseract.image_to_data(page, config=config,output_type=Output.DICT)

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
                        
                        if sentence != "":
                            print("------------------------------------------------------")
                            print(sentence)
                            print(topdistance,leftdistance)
                            print("------------------------------------------------------")
                        # print(minval)

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
                print("Nothing")
            else:
                print("------------------------------------------------------")
                print(word)
                print("------------------------------------------------------")
                print(jsonresponse["description"])
                print("------------------------------------------------------")
