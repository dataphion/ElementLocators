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
from PIL import Image, ImageEnhance
import requests
from io import BytesIO
import os

url = os.environ.get('IMAGE_HOST') if os.environ.get('IMAGE_HOST') else "https://aitester.dataphion.com"

# construct the argument parser and parse the arguments
class TemplateMatch:

	def matchtheimage(self,templatebyte,imagebyte,jtextcoord):

		try :		
			# print(text_coord)
			# jtextcoord = json.loads(text_coord)
			# print(jtextcoord)
			(centtextocrX,centtextocrY) = ((jtextcoord["endX"]+jtextcoord["startX"])/2,(jtextcoord["endY"]+jtextcoord["startY"])/2)
			print(str(centtextocrX)+" "+str(centtextocrY))
			
			# templatePath = str.encode(templatebyte)
			# with open("template.png", "wb") as templateimg:
			# 	templateimg.write(base64.b64decode(templatebyte.replace("data:image/png;base64,","")))

			# # imagePath = str.encode(imagebyte)
			with open("image.png", "wb") as imageimg:
				imageimg.write(base64.b64decode(imagebyte.replace("data:image/png;base64,","")))


			# template = cv2.imread("template.png")
			# template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
			response = requests.get(url+templatebyte)
			template = Image.open(BytesIO(response.content))
			contrast_enhancer = ImageEnhance.Contrast(template)
			pil_enhanced_image = contrast_enhancer.enhance(2)
			enhanced_image = np.asarray(pil_enhanced_image)
			r, g, b = cv2.split(enhanced_image)
			enhanced_image = cv2.merge([b, g, r])
			template = cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2GRAY)
			template = cv2.Canny(template, 50, 200)
			(tH, tW) = template.shape[:2]
			# cv2.imshow("Template", template)
			# cv2.waitKey()

			image = cv2.imread("image.png")
			gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
			(iH,iW) = image.shape[:2]
			# cv2.imshow("Image", gray)
			# cv2.waitKey()

			successresult = None
			failresult = []
			(resstartX,resstartY) = (0,0)
			(resendX,resendY) = (0,0)
			found = None
			threshold = 0.9
			tempthreshold = 0.85

			while threshold > 0.55 and found == None :

				print("------------------------")
				print(threshold)
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
					res = cv2.matchTemplate(edged,template,cv2.TM_CCOEFF_NORMED)
					loc = np.where( res >= threshold)
					
					for pt in zip(*loc[::-1]):
						
						(startX, startY) = (int(pt[0] * r), int(pt[1] * r))
						(endX, endY) = (int((pt[0] + tW) * r), int((pt[1] + tH) * r))
										
						(centtempX,centtempY) = ((endX+startX)/2,(endY+startY)/2)

						distance = math.sqrt( ((centtempX-centtextocrX)**2)+((centtempY-centtextocrY)**2) )

						if found is None or distance < found:
							tempthreshold = threshold
							found = distance
							(resstartX,resstartY) = (startX, startY)
							(resendX,resendY) = (endX, endY)
				
				threshold = threshold - 0.05
			
			# print(str(resstartX) + "   "+ str(resendX))	
			if resstartX != 0 and resendX !=0:
				successresult = {'startX':resstartX,'startY':resstartY,'endX':resendX,'endY':resendY}
				cv2.rectangle(image, (resstartX, resstartY), (resendX, resendY), (0,0,255), 2)
				# cv2.imshow("Image", image)
				# cv2.imwrite("template_in_image_nearest.png",image)
				# cv2.waitKey(0)
				cv2.destroyAllWindows()
				result = {'status':"success",'data':[successresult],'scale':{'x':iW,'y':iH}}

			else:
			    result = {'status':"fail",'data':"Not found"}
			
			return result
		
		except Exception as exception :

			print(exception)
			return {'status':"fail"}
