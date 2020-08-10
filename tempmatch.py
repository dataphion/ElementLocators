# USAGE
# python match.py --template cod_logo.png --images images

# import the necessary packages
import numpy as np
import argparse
import imutils
import glob
import cv2
import json
import math
import base64

# construct the argument parser and parse the arguments
# multiple images
class TemplateMatch1:

	def matchtheimage(self,templatebyte,imagebyte,basebyte,jtextcoord):

		# try :		
			# print(text_coord)
			# jtextcoord = json.loads(text_coord)
			print(jtextcoord)
			(centtextocrX,centtextocrY) = ((jtextcoord["endX"]+jtextcoord["startX"])/2,(jtextcoord["endY"]+jtextcoord["startY"])/2)
			print(str(centtextocrX)+" "+str(centtextocrY))
            
			# templatePath = str.encode(templatebyte)
			with open("template.png", "wb") as templateimg :
				templateimg.write(base64.b64decode(templatebyte.replace("data:image/png;base64,","")))

			# imagePath = str.encode(imagebyte)
			with open("image.png", "wb") as imageimg :
				imageimg.write(base64.b64decode(imagebyte.replace("data:image/png;base64,","")))

			with open("base.png", "wb") as baseimg :
				baseimg.write(base64.b64decode(basebyte.replace("data:image/png;base64,","")))


			template = cv2.imread("template.png")
			template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
			template = cv2.Canny(template, 50, 200)
			(tH, tW) = template.shape[:2]

			#cv2.imshow("Template", template)

			# loop over the images to find the template in
			# for imagePath in glob.glob(args["images"] + "/*.png"):
			# load the image, convert it to grayscale, and initialize the
			# bookkeeping variable to keep track of the matched region

			
			successresult = None
			(resstartX,resstartY) = (0,0)
			(resendX,resendY) = (0,0)
			(iH,iW) = (0,0)

			images = ["base.png","image.png"]
			found = None
			tempthreshold = 85

			for img in images:

			    image = cv2.imread(img)
			    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
			    threshold = 90
                
			    while threshold > 45 :

			        print("------------------------")
			        print(threshold,tempthreshold)
			        print("------------------------")
			        for scale in np.linspace(0.2, 1.0, 20)[::-1]:
			            # resize the image according to the scale, and keep track
			            # of the ratio of the resizing
			            resized = imutils.resize(gray, width = int(gray.shape[1] * scale))
			            r = gray.shape[1] / float(resized.shape[1])

			            # if the resized image is smaller than the template, then break
			            # from the loop
			            if resized.shape[0] < tH or resized.shape[1] < tW:
			                break

			            # detect edges in the resized, grayscale image and apply template
			            # matching to find the template in the image
			            edged = cv2.Canny(resized, 50, 200)

			            clone = np.dstack([edged, edged, edged])
			            res = cv2.matchTemplate(edged,template,cv2.cv2.TM_CCOEFF_NORMED)
			            loc = np.where( res >= (threshold/100))
			            
			            for pt in zip(*loc[::-1]):
			                
			                (startX, startY) = (int(pt[0] * r), int(pt[1] * r))
			                (endX, endY) = (int((pt[0] + tW) * r), int((pt[1] + tH) * r))
									        
			                (centtempX,centtempY) = ((endX+startX)/2,(endY+startY)/2)

			                distance = math.sqrt( ((centtempX-centtextocrX)**2)+((centtempY-centtextocrY)**2) )
							
			                if found is None or tempthreshold < threshold:
			                    found = distance
			                    tempthreshold = threshold
			                    (resstartX,resstartY) = (startX, startY)
			                    (resendX,resendY) = (endX, endY)
			                    (iH,iW) = image.shape[:2]

			                elif tempthreshold == threshold and found > distance:
			                	print(found,distance)
			                	found = distance
			                	tempthreshold = threshold
			                	(resstartX,resstartY) = (startX, startY)
			                	(resendX,resendY) = (endX, endY)
			                	(iH,iW) = image.shape[:2]
			        
			        threshold = threshold - 5


			    print(str(resstartX) + "   "+ str(resendX))	
			    if resstartX != 0 and resendX !=0:
			        successresult = {'startX':resstartX,'startY':resstartY,'endX':resendX,'endY':resendY}
			        cv2.rectangle(image, (resstartX, resstartY), (resendX, resendY), (0,0,255), 2)
			        # cv2.imshow("Image", image)
			        # cv2.imwrite("template_in_image_nearest.png",image)
			        # cv2.waitKey(0)
			        cv2.destroyAllWindows()
            
			if successresult != None :
			    result = {'status':"success",'data':successresult,'scale':{'x':iW,'y':iH}}
			else:
			    result = {'status':"fail",'data':"Not found"}
                
			print(result)

			return result
		
		# except Exception as exception :

			# print(exception)
			# return {'status':"fail"}