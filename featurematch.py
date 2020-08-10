 #!/usr/bin/env python

'''
Feature-based image matching

'''
# Python 2/3 compatibility
from __future__ import print_function

import numpy as np
import cv2 as cv
import sys
import base64
from scipy.spatial import KDTree
from common import anorm, getsize
from PIL import Image, ImageEnhance
import requests
from io import BytesIO
import os

FLANN_INDEX_KDTREE = 1  # bug: flann enums are missing
FLANN_INDEX_LSH    = 6

url = os.environ.get('IMAGE_HOST') if os.environ.get('IMAGE_HOST') else "https://aitester.dataphion.com"

class FeatureMatch:

    def featurematch(self,templatebyte,imagebyte):

        # try:

            # with open("template.png", "wb") as templateimg:
            #     templateimg.write(base64.b64decode(templatebyte.replace("data:image/png;base64,", "")))

            with open("image.png", "wb") as imageimg:
                imageimg.write(base64.b64decode(imagebyte.replace("data:image/png;base64,", "")))
            
            response = requests.get(url+templatebyte)
            template = Image.open(BytesIO(response.content))
            contrast_enhancer = ImageEnhance.Contrast(template)
            pil_enhanced_image = contrast_enhancer.enhance(2)
            enhanced_image = np.asarray(pil_enhanced_image)
            r, g, b = cv.split(enhanced_image)
            enhanced_image = cv.merge([b, g, r])
            img1 = cv.cvtColor(enhanced_image,cv.IMREAD_GRAYSCALE)
            # cv.imshow("img1",img1)

            # img1 = cv.imread("template.png",cv.IMREAD_GRAYSCALE)
            img2 = cv.imread("image.png", cv.IMREAD_GRAYSCALE)
            (iH,iW) = img2.shape[:2]

            detector = cv.xfeatures2d.SIFT_create()
            norm = cv.NORM_L2
            flann_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)

            matcher = cv.FlannBasedMatcher(flann_params, {})

            if img1 is None:
                print('Failed to load img1:', img1)
                sys.exit(1)

            if img2 is None:
                print('Failed to load img2:', img2)
                sys.exit(1)

            if detector is None:
                print('unknown feature:')
                sys.exit(1)

            kp1, desc1 = detector.detectAndCompute(img1, None)
            kp2, desc2 = detector.detectAndCompute(img2, None)
            print('img1 - %d features, img2 - %d features' % (len(kp1), len(kp2)))
            
            print('matching...')
            raw_matches = matcher.knnMatch(desc1, trainDescriptors = desc2, k = 2) #2

            p1, p2, kp_pairs = self.filter_matches(kp1, kp2, raw_matches)

            if len(p1) >= 10:

                H, status = cv.findHomography(p1, p2, cv.RANSAC, 5.0)
                print('%d / %d  inliers/matched' % (np.sum(status), len(status)))
                if len(status) > 10:

                    min_x,min_y,max_x,max_y,iH,iW = self.explore_match("image", img1, img2, kp_pairs, status, H)

                    if min_x != 0 and max_x != 0:
                        # cv.waitKey(0)
                        cv.destroyAllWindows()
                        return {"status":"success","data":[{"startX":int(min_x) , "startY":int(min_y),"endX":int(max_x),"endY":int(max_y)}],'scale':{"x":iW,"y":iH}}
                    else:
                        return {"status":"fail"}
                else:
                    print('only %d matched' % len(p1))
                    return {"status":"fail"}
            else:
                H, status = None, None
                print('%d matches found, not enough for homography estimation' % len(p1))

                return {"status":"fail"}
        
        # except Exception as exception:
            
        #     print(exception)
        #     return {"status":"fail"}
        
    def filter_matches(self,kp1, kp2, matches, ratio = 0.75):
        mkp1, mkp2 = [], []
        for m in matches:
            if len(m) == 2 and m[0].distance < m[1].distance * ratio:
                m = m[0]
                mkp1.append( kp1[m.queryIdx] )
                mkp2.append( kp2[m.trainIdx] )
        p1 = np.float32([kp.pt for kp in mkp1])
        p2 = np.float32([kp.pt for kp in mkp2])
        kp_pairs = zip(mkp1, mkp2)
        return p1, p2, list(kp_pairs)

    def explore_match(self,win, img1, img2, kp_pairs, status = None, H = None):
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        vis = np.zeros((max(h1, h2), w1+w2), np.uint8)
        # vis[:h1, :w1] = img1
        # vis[:h2, w1:w1+w2] = img2
        
        vis[:h1, :w1] = img1[:h1,:w1,0] if img1.ndim > 2 else img1
        vis[:h2, w1:w1+w2] = img2[:h2,:w2,0] if img2.ndim > 2 else img2
        vis = cv.cvtColor(vis, cv.COLOR_GRAY2BGR)

        if H is not None:
            corners = np.float32([[0, 0], [w1, 0], [w1, h1], [0, h1]])
            corners = np.int32( cv.perspectiveTransform(corners.reshape(1, -1, 2), H).reshape(-1, 2) + (w1, 0) )
            cv.polylines(vis, [corners], True, (255, 255, 255))

        if status is None:
            status = np.ones(len(kp_pairs), np.bool_)
        p1, p2 = [], []  # python 2 / python 3 change of zip unpacking
        for kpp in kp_pairs:
            p1.append(np.int32(kpp[0].pt))
            p2.append(np.int32(np.array(kpp[1].pt) + [w1, 0]))

        green = (0, 255, 0)
        red = (0, 0, 255)
        kp_color = (51, 103, 236)
        for (x1, y1), (x2, y2), inlier in zip(p1, p2, status):
            if inlier:
                col = green
                cv.circle(vis, (x1, y1), 2, col, -1)
                cv.circle(vis, (x2, y2), 2, col, -1)
            else:
                col = red
                r = 2
                thickness = 3
                cv.line(vis, (x1-r, y1-r), (x1+r, y1+r), col, thickness)
                cv.line(vis, (x1-r, y1+r), (x1+r, y1-r), col, thickness)
                cv.line(vis, (x2-r, y2-r), (x2+r, y2+r), col, thickness)
                cv.line(vis, (x2-r, y2+r), (x2+r, y2-r), col, thickness)
        vis0 = vis.copy()
        (iH,iW) = vis.shape[:2]
        
        (min_x,min_y) = (None,None)
        (max_x,max_y) = (None,None)
        points = []
        nppoint = []
        for (x1, y1), (x2, y2), inlier in zip(p1, p2, status):
            if inlier:
                cv.line(vis, (x1, y1), (x2, y2), green)

                # point = {'x':str(x2),'y':str(y2)}
                # points.append(point)
                # nppoint.append((x2,y2))
                print(x2,y2)
                if min_x == None :
                    (min_x,min_y) = (x2,y2)
                elif max_x == None:
                    (max_x,max_y) = (x2,y2)                                        
                elif (min_x,min_y) > (x2,y2):
                    (min_x,min_y) = (x2,y2)
                else :
                    (max_x,max_y) = (x2,y2) 
        
        # nppoints = np.array(nppoint)
        # T = KDTree(nppoints)
        # idx = T.query_pairs(nppoints,r=2)
        # print(idx)

        if min_x != None:
            (centX,centY) = ((max_x+min_x)/2,(max_y+min_y)/2)
            print(str(centX) + " " + str(centY) )
            # cv.imshow("vis0",vis0)
            # cv.imshow(win, vis)

            return (min_x,min_y,max_x,max_y,iH,iW)
        else :
            return (0,0,0,0,iH,iW)
        
        def onmouse(event, x, y, flags, param):
            cur_vis = vis
            if flags & cv.EVENT_FLAG_LBUTTON:
                cur_vis = vis0.copy()
                r = 8
                m = (anorm(np.array(p1) - (x, y)) < r) | (anorm(np.array(p2) - (x, y)) < r)
                idxs = np.where(m)[0]

                kp1s, kp2s = [], []
                for i in idxs:
                    (x1, y1), (x2, y2) = p1[i], p2[i]
                    col = (red, green)[status[i][0]]
                    cv.line(cur_vis, (x1, y1), (x2, y2), col)
                    kp1, kp2 = kp_pairs[i]
                    kp1s.append(kp1)
                    kp2s.append(kp2)
                cur_vis = cv.drawKeypoints(cur_vis, kp1s, None, flags=4, color=kp_color)
                cur_vis[:,w1:] = cv.drawKeypoints(cur_vis[:,w1:], kp2s, None, flags=4, color=kp_color)

            # cv.imshow(win, cur_vis)
        cv.setMouseCallback(win, onmouse)
        return vis

    

