import numpy as np
import argparse
import imutils
import glob
import cv2
import json
import base64
from PIL import Image, ImageEnhance
import requests
from io import BytesIO
import os

url = os.environ.get('IMAGE_HOST') if os.environ.get('IMAGE_HOST') else "https://aitester.dataphion.com"

# construct the argument parser and parse the arguments
class TemplateMatchFind:

	def matchtheimage(self,templatebyte,imagebyte):

		# try :

			# with open("template.png", "wb") as templateimg:
			# 	templateimg.write(base64.b64decode(templatebyte.replace("data:image/png;base64,","")))

			with open("image.png", "wb") as imageimg:
				imageimg.write(base64.b64decode(imagebyte.replace("data:image/png;base64,","")))

			# template = cv2.imread("template.png")
			print(url+templatebyte)
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

			image = cv2.imread("image.png")
			gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
			(iH,iW) = image.shape[:2]
			found = None
			(startX, startY) = (-1,-1)
			(endX, endY) = (-1,-1)

			json_data_list = []

			threshold = 0.9

			while len(json_data_list) == 0 and threshold > 0.45:

				print("------------------------")
				print(threshold)
				print("------------------------")
				# loop over the scales of the image
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


						result = {'startX':startX,'startY':startY,'endX':endX,'endY':endY}

						#print(result)
						json_data_list.append(result)
						cv2.rectangle(image, pt, (pt[0] + tW, pt[1] + tH), (0,0,255), 2)

				threshold = threshold - 0.05
				#print("------------------------")
				#print(json_data_list)
				#print("------------------------")

			if len(json_data_list) > 0:
				# cv2.imshow("Image", image)
				# cv2.imwrite("template_in_image.png",image)
				# cv2.waitKey(0)
			    result = {'status':"success",'data':json_data_list,'scale':{'x':iW,'y':iH}}
			else:
				result = {'status':"fail",'data':json_data_list}

			return result

		# except Exception as exception:

		# 	print(exception)
		# 	return {'status':"fail"}
