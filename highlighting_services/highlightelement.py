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
import shutil
import requests
import os

host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337"

# construct the argument parser and parse the arguments
class HighlightElement:
    
    def highlightelement(self, jdata, encoded=True, path=None):

        try:

            ####get image 
            base_image_url = jdata["base_image"]["url"]
            print(base_image_url)
            response = requests.get(host+base_image_url, stream=True)
            with open('page.png', 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)                
            page = cv2.imread("page.png")

            ##get coordinates            
            print(type(jdata["height"]))
            (height,width) = (int(jdata["height"]),int(jdata["width"]))
            (resstartX, resstartY) = ( int(jdata["x_cord"]) , int(jdata["y_cord"]) )
            (resendX, resendY) = ( int(jdata["x_cord"]) + int(width) , int(jdata["y_cord"]) + int(height) )
            print(resstartX, resstartY, resendX, resendY)

            ### cropped image
            crop_img = page[resstartY:resstartY+height,resstartX:resstartX+width]
            cv2.imwrite("croppedimage.png",crop_img)
            with open("croppedimage.png", "rb") as image_file:
                encoded_croppedimage = base64.b64encode(image_file.read())
            

            ### highlight image
            cv2.rectangle(page, (resstartX, resstartY), (resendX, resendY), (0,0,255), 2)
            
            cv2.imwrite("highlightedimage.png",page)
            with open("highlightedimage.png", "rb") as image_file:
                encoded_highlightimage = base64.b64encode(image_file.read()) 
            

            ### thumbnail image
            thumbnail = self.resizeAndPad(page,(150,200),255)
            cv2.imwrite("thumbnail.png",thumbnail)            
            with open("thumbnail.png", "rb") as thumb_image_file:
                encoded_thumbnailimage = base64.b64encode(thumb_image_file.read())
            #cv2.waitKey(0)

            ### save image locally
            if encoded == False:
                
                with open("thumbnail.png", "rb") as image_file:
                    thumbnail = image_file.read()
                with open("page.png", "rb") as image_file:
                    page = image_file.read()
                with open("highlightedimage.png", "rb") as image_file:
                    highlighted = image_file.read()
                with open("croppedimage.png", "rb") as image_file:
                    cropped = image_file.read()
                if path:
                    #Write files to the path..
                    from shutil import copyfile
                    copyfile("page.png", path+"/page.png")
                    copyfile("thumbnail.png", path+"/thumbnail.png")
                    copyfile("highlightedimage.png", path+"/highlightedimage.png")
                    copyfile("croppedimage.png", path+"/croppedimage.png")

                return {"status":"success"}
                # ,"thumbnail":thumbnail,
                #             "highlighted_snapshot":highlighted,
                #             "element_snapshot":cropped,
                #             'page': page}
            
            else :
            ### response
                highlightimgbase64 = str(encoded_highlightimage).split("\'")            
                croppedimgbase64 = str(encoded_croppedimage).split("\'")
                thumbnailimgbase64 = str(encoded_thumbnailimage).split("\'")

                if highlightimgbase64 != "" and croppedimgbase64 != "" and thumbnailimgbase64 != "":
                    return {"status":"success","thumbnail":str(thumbnailimgbase64[1]),"highlighted_snapshot":str(highlightimgbase64[1]),"element_snapshot":str(croppedimgbase64[1])}
            
        except Exception as exception:
            
            print(exception)
            return{"status":"fail"}
    
    def resizeAndPad(self,img, size, padColor=0):
        h, w = img.shape[:2]
        sh, sw = size

        # interpolation method
        if h > sh or w > sw: # shrinking image
            interp = cv2.INTER_AREA
        else: # stretching image
            interp = cv2.INTER_CUBIC

        # aspect ratio of image
        aspect = w/h  # if on Python 2, you might need to cast as a float: float(w)/h

        # compute scaling and pad sizing
        if aspect > 1: # horizontal image
            new_w = sw
            new_h = np.round(new_w/aspect).astype(int)
            pad_vert = (sh-new_h)/2
            pad_top, pad_bot = np.floor(pad_vert).astype(int), np.ceil(pad_vert).astype(int)
            pad_left, pad_right = 0, 0
        elif aspect < 1: # vertical image
            new_h = sh
            new_w = np.round(new_h*aspect).astype(int)
            pad_horz = (sw-new_w)/2
            pad_left, pad_right = np.floor(pad_horz).astype(int), np.ceil(pad_horz).astype(int)
            pad_top, pad_bot = 0, 0
        else: # square image
            new_h, new_w = sh, sw
            pad_left, pad_right, pad_top, pad_bot = 0, 0, 0, 0

        # set pad color
        if len(img.shape) is 3 and not isinstance(padColor, (list, tuple, np.ndarray)): # color image but only one color provided
            padColor = [padColor]*3

        # scale and pad
        scaled_img = cv2.resize(img, (new_w, new_h), interpolation=interp)
        scaled_img = cv2.copyMakeBorder(scaled_img, pad_top, pad_bot, pad_left, pad_right, borderType=cv2.BORDER_CONSTANT, value=padColor)

        return scaled_img

