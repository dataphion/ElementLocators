import pika
import json
import requests


url = "http://10.93.16.36:1337/graphql"
connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='10.93.16.36'))
channel = connection.channel()

channel.queue_declare(queue='highlight_queue')

tblstepspayload = {'query':"query{  testcases(where:{name:\"dell z\"}){    testcasecomponents{      objectrepository{ id   } }}}"}
response = requests.post(url,data=tblstepspayload)
jsonresponse = json.loads(response.content)
print(jsonresponse)
i =1
for tblstepsid in jsonresponse["data"]["testcases"][0]["testcasecomponents"]:
    print(tblstepsid["objectrepository"]["id"])
    channel.basic_publish(exchange='', routing_key='highlight_queue', body=json.dumps({'id':tblstepsid["objectrepository"]["id"]}))
    print(" [x] Sent 'Hello World!'")
connection.close()

