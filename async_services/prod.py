import pika
import json
import requests

connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='10.93.16.36'))
channel = connection.channel()

channel.queue_declare(queue='highlight_queue')

channel.basic_publish(exchange='', routing_key='highlight_queue', body=json.dumps({'id':"1234"}))
connection.close()

