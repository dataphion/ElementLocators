from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from flask_restful import Resource, Api, reqparse
import json
import pika
import requests
import re
import os

app = Flask(__name__)
api = Api(app)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

RMQ_HOST = ""
RMQ_PORT = ""
host = "http://localhost:1337"
flow = host+"/flows/"
flowsteps = host+"/flowsteps/"
tsexecution = host+"/testsessionexecutions/"
tcexecution = host+"/testcaseexecutions/"
testcase = host+"/testcases/"
testsuite = host+"/testsuites/"
endpointpack = host+"/endpointpacks/"
graphql = host+"/graphql"
jobs = host+"/jobs/"


class TestRunner(Resource):

    def sendresponse(self, data):
        try:

            queue_name = "testdecider" if 'testsuiteid' in data else "decider"
            print("queue name ------------->", queue_name)
            #insert jobs
            json_payload = {"status": "started"}
            jobs_result = requests.post(url=jobs, json=json_payload).json()
            print("job created --", jobs_result)
            data["job_id"] = jobs_result["id"]

            credentials = pika.PlainCredentials("guest", "guest")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT,
                                            credentials=credentials))
            channel = connection.channel()

            channel.queue_declare(queue=queue_name)

            print("job created with job ------------>", data)
            channel.basic_publish(
                exchange='', routing_key=queue_name, body=json.dumps(data))
            
            channel.close()
            return {'message': "Test started", "job_id": jobs_result["id"]}
        except Exception as identifier:
            print(identifier)
            return {'message': "Test couldnt be started"}

    def post(self):

        print("Received")
        parser = reqparse.RequestParser()
        parser.add_argument('testsessionid')
        parser.add_argument('testcaseid')
        parser.add_argument('environment_id')
        parser.add_argument('testsuiteid')
        parser.add_argument('browser')
        args = parser.parse_args()
        print(args)
        if args["testsuiteid"]:
            print("Inside Testsuiteid")
            print("----------------------------------\n")
            data = {'testsuiteid': args["testsuiteid"],
                    'environment_id': args["environment_id"],
                    'browser': args["browser"]}
            data = self.sendresponse(data)
        else:
            print("Inside Testsessionid")
            print("----------------------------------\n")
            data = {'testsessionid': args["testsessionid"],
                    'testcaseid': args["testcaseid"],
                    'environment_id': args["environment_id"]}
            data = self.sendresponse(data)

        return data, 201


api.add_resource(TestRunner, '/api/Runtest')

if __name__ == '__main__':
    RMQ_HOST = os.environ.get('RMQ_HOST') if os.environ.get(
        'RMQ_HOST') else "localhost"
    RMQ_PORT = int(os.environ.get('RMQ_PORT')
                   ) if os.environ.get('RMQ_PORT') else 5672

    host = os.environ.get('HOST') if os.environ.get(
        'HOST') else "http://localhost:1337"

    flow = host+"/flows/"
    flowsteps = host+"/flowsteps/"
    tsexecution = host+"/testsessionexecutions/"
    tcexecution = host+"/testcaseexecutions/"
    testcase = host+"/testcases/"
    testsuite = host+"/testsuites/"
    endpointpack = host+"/endpointpacks/"
    graphql = host+"/graphql"
    jobs = host+"/jobs/"

    app.run(host='0.0.0.0', port='9501', debug=True)
