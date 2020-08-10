import requests
import json
import pika
import re
import time
import sys
import socketio
import datetime
import os
from api_executor import Api_Executor
from condition_executor import Condition_Executor

RMQ_HOST = ""
RMQ_PORT = ""
host = "http://localhost:1337"
flow = host+"/flows/"
flowsteps = host+"/flowsteps/"
tsexecution = host+"/testsessionexecutions/"
tcexecution = host+"/testcaseexecutions/"
testcase = host+"/testcases/"
graphql = host+"/graphql"
jobs = host+"/jobs/"
sio = None
nodes = {}


class TestDecider:

    def start(self, data):

        testsuiteid = data["testsuiteid"]
        try:

            responsepayload = {
                'query': "query{  testsuites(where:{id:\"ID\"}){  sequence }}"}
            responsepayload['query'] = responsepayload['query'].replace(
                "ID", testsuiteid)
            # print(responsepayload)
            response = requests.post(url=graphql, data=responsepayload).json()
            testcaseids = response["data"]["testsuites"][0]["sequence"]

            # testsessionexecution entry
            json_payload = {
                'start_time': str(datetime.datetime.now()),
                'total_test': len(testcaseids),
                'pending': len(testcaseids)-1,
                'total_fail': 0,
                'total_pass': 0,
                'testsuite': {
                    'id': str(testsuiteid)
                },
                'jobs': data["job_id"]
            }
            testsessionexecution_result = requests.post(
                url=tsexecution, json=json_payload).json()

            testcase_d = requests.get(testcase+testcaseids[0]).json()
            IF_API = True if testcase_d["type"] == "api" else False

            # send to decider queue
            json_data = {
                'testsessionid': testsessionexecution_result["id"],
                'testcaseid': testcaseids[0],
                'environment_id':data['environment_id'],
                'browser':data["browser"]
            }
            self.pushtodeciderqueue(json_data, IF_API)

        except Exception as identifier:
            print(identifier)

    def nextrun(self, data):
        data = json.loads(data) if type(data) == "object" else data
        print(data)
        print(type(data))

        testsessionid = data["testsessionid"]
        testsessionexecution = requests.get(
            url=tsexecution+str(testsessionid)).json()
        testcaseids = testsessionexecution["testsuite"]["sequence"]
        if int(testsessionexecution["pending"]) > 0:
            num = int(testsessionexecution["total_test"]) - \
                int(testsessionexecution["pending"])

            # send to decider queue
            json_data = {
                'testsessionid': testsessionid,
                'testcaseid': testcaseids[num],
                'environment_id':data['environment_id'],
                'browser':data["browser"]
            }

            testcase_d = requests.get(testcase+str(testcaseids[num])).json()
            IF_API = True if testcase_d["type"] == "api" else False

            self.pushtodeciderqueue(json_data, IF_API)

            json_data = {
                'pending': int(testsessionexecution["pending"])-1,
            }
            testsessionexecution = requests.put(
                url=tsexecution+str(testsessionid), json=json_data).json()
            #update jobs
            updatejobs = requests.put(url=jobs+str(testsessionexecution["jobs"]["id"]), json=json_data).json()
        else:
            json_payload = {
                'end_time': str(datetime.datetime.now())
            }
            testsessionexecution = requests.put(
                url=tsexecution+str(testsessionid), json=json_payload).json()
            #update
            print(testsessionexecution["jobs"])
            updatejobs = requests.put(url=jobs+str(testsessionexecution["jobs"]["id"]), json={"status": "completed"}).json()
            self.pushtosocketio(testsessionexecution,"send_email")

    def pushtosocketio(self, data,quename="api_execution"):
        global sio
        sio.emit(quename, data)

    def startsioserver(self):
        global sio
        # create a Socket.IO CLient
        sio = socketio.Client()
        sio.connect(host)

    def waitforresponse(self, testcaseid):

        wait = True
        while wait:
            credentials = pika.PlainCredentials("guest", "guest")

            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, credentials=credentials))

            channel = connection.channel()

            channel.queue_declare(queue=testcaseid)

            method_frame, header_frame, body = channel.basic_get(
                queue=testcaseid)

            if not method_frame or method_frame.NAME == 'Basic.GetEmpty':
                wait = True
            else:
                channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                print(body)
                connection.close()
                break

        # body = json.loads(body)
        return body

    def pushtodeciderqueue(self, json_data, IF_API):
        # try:
        if IF_API:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT))
            channel = connection.channel()

            channel.queue_declare(queue='decider')
            channel.basic_publish(
                exchange='', routing_key='decider', body=json.dumps(json_data))
            connection.close()

        else:
            testrunresp = requests.post(url = testcase+"run",json = json_data)
            print(testrunresp)
        # except Exception as identifier:
        #     return False


class Consumer():

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._decider = TestDecider()

    def callback_func(self, channel, method, properties, body):

        # print("{} received '{}'".format(self.name, body))
#        try:
            data = json.loads(body)
            print("Data --> ")
            print(data)

            global sio
            if not sio:
                self._decider.startsioserver()
            if "TYPE" in data and data['TYPE'] == 'NESTED_UI':
                # send to decider queue
                json_data = {
                    'testsessionid': data['testsessionid'],
                    'testcaseid': data['testcaseid'],
                    'environment_id':data['environment_id'],
                    'browser':data['browser']
                }
                self._decider.pushtodeciderqueue(json_data,False)

            if "testsuiteid" in data:
                print("started")
                self._decider.start(data)
                print("----------------------------------------------------")
            else:
                print("received")
                self._decider.nextrun(data)
                print("----------------------------------------------------")

#        except Exception as identifier:
#            print(identifier)

    def run(self):
        credentials = pika.PlainCredentials("guest", "guest")

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host, port=self._port,
                                      credentials=credentials))

        channel = connection.channel()

        channel.queue_declare(queue='testdecider')

        channel.basic_consume(queue='testdecider',
                              auto_ack=True,
                              on_message_callback=self.callback_func)

        channel.start_consuming()


if __name__ == "__main__":

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
    graphql = host+"/graphql"
    jobs = host+"/jobs/"

    print(RMQ_HOST, RMQ_PORT)
    consumer = Consumer(host=RMQ_HOST, port=RMQ_PORT)
    consumer.run()
