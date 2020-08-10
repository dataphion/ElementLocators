import pika
import threading
import json
import requests
import base64
import os
import time
from base64 import decodestring
from highlightelement import HighlightElement
from ocrsave import OCR
import os

host = "http://localhost:1337"
obj_resp = "/objectrepositories/"
images = "/opt/images"
class Consumer():
    def __init__(self, host,port, api_host):
        self._host = host
        self._port = port
        self._api_host = api_host
        self._h = HighlightElement()
        self._ocrsave = OCR()

    # Not necessarily a method.
    def callback_func(self, channel, method, properties, body):
        
        #data = json.loads(json.loads(body))
        data = json.loads(body)
        data = json.loads(data)
        print("Data --> ")
        print(data)
        i=0
        while i in range(10):
            #Query record from Strapi
            time.sleep(3)
            print(str(data["id"]))
            url = self._api_host+obj_resp+str(data['id'])
            print(url)
            resp = requests.get(url)
            resp = resp.json()
            jsondata = {}
            if 'x_cord' in resp and resp['x_cord'] != None and resp['base_image'] != None:

                resp['x_cord'] = resp['x_cord'] * float(resp['pixel_ratio'])
                resp['y_cord'] = resp['y_cord'] * float(resp['pixel_ratio'])
                resp['width'] = resp['width'] * float(resp['pixel_ratio'])
                resp['height'] = resp['height'] * float(resp['pixel_ratio'])
                
                directory = images+"/"+str(data['id'])
                if not os.path.exists(directory):
                    os.makedirs(directory)
                    
                highresp = self._h.highlightelement(resp, encoded=False, path=directory)

                #Move these files to image static path folder.
                #Folder name will be ID of tblstep
                if highresp["status"] == "success":
                    #jsondata.update({'thumbnail': "data:image/png;base64,"+highresp['thumbnail'],'element_snapshot': "data:image/png;base64,"+highresp['element_snapshot'], 'highlighted_snapshot':"data:image/png;base64,"+highresp['highlighted_snapshot']})
                    jsondata.update({'thumbnail_url':"/p_images/"+str(data['id'])+"/thumbnail.png",
                                    'element_snapshot': "/p_images/"+str(data['id'])+"/croppedimage.png",
                                    'highlighted_image_url':"/p_images/"+str(data['id'])+"/highlightedimage.png",
                                    'page_url':"/p_images/"+str(data['id'])+"/page.png"})
                    print("Highlight Element Done")
                else :
                    print("Something Failed")
                
                ocrdata = self._ocrsave.setText(resp)
                if ocrdata["status"] == "success":
                    jsondata.update({'text':ocrdata["word"]})
                    print("OCR Done")
                else :
                    print("Something Failed")
                
                if len(jsondata) > 0:
                    j = 0
                    while j < 10:
                        try:
                            response = requests.put(url,json=jsondata)
                            print(response)
                            break
                        except Exception as identifier:
                            print(identifier)
                            j +=1
                
                break

            else :
                print("No Co-ordinates found")
                i+=1

    def run(self):
        credentials = pika.PlainCredentials("guest", "guest")

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))

        channel = connection.channel()

        channel.queue_declare(queue='highlight_queue')

        channel.basic_consume(queue='highlight_queue',
                      auto_ack=True,
                      on_message_callback=self.callback_func)

        channel.start_consuming()


if __name__ == "__main__":

    RMQ_HOST = os.environ.get('RMQ_HOST') if os.environ.get('RMQ_HOST') else "localhost" 
    RMQ_PORT = int(os.environ.get('RMQ_PORT')) if os.environ.get('RMQ_PORT') else 5672 
    HOST = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337" 

    print(HOST,RMQ_HOST,RMQ_PORT)
    consumer = Consumer(host = RMQ_HOST,port = RMQ_PORT,api_host = HOST)
    consumer.run()
