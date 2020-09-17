import requests
import json
import pika
import re
import time
import sys
import socketio
import datetime
import os
import threading 
from threading import *
from api_executor import Api_Executor
from condition_executor import Condition_Executor
from api_executor import Api_Executor
from source_executor import Source_Executor

RMQ_HOST = "localhost"
RMQ_PORT = "5672"
socket_host = "http://127.0.0.1:1337"
host = "http://localhost:1337"
flow = host+"/flows/"
flowsteps = host+"/flowsteps/"
tsexecution = host+"/testsessionexecutions/"
tcexecution = host+"/testcaseexecutions/"
testcase = host+"/testcases/"
graphql = host+"/graphql"
sio = None
nodes = {}
api_executor = Api_Executor()
condition_executor = Condition_Executor()
source_executor = Source_Executor()

class Decider:

    def start(self,sdata):

        testsession_result = requests.get(url=tsexecution+str(sdata["testsessionid"])).json()
        if testsession_result["testsuite"]["suite_name"] == "default":
            json_payload = {
                'total_test':int(testsession_result["total_test"]) +1
            }
            testsessionexecution_result = requests.put(url=tsexecution+str(sdata["testsessionid"]),json=json_payload).json()


        testsessionid = sdata["testsessionid"]
        testcaseid = sdata["testcaseid"]
        environmentid = sdata["environment_id"]
        browser = sdata["browser"] if "browser" in sdata else "chrome"
        ### testcaseexecution entry
        json_payload={
            'status':"started",
            'type':"api",
            'start_time':str(datetime.datetime.now()),
            'testcase':{
                'id':testcaseid
            },
            'testsessionexecution':{
                'id':str(testsessionid)
            }
        }
        testcaseexecution_result = requests.post(url=tcexecution,json=json_payload).json()

        ### get flow details
        testcase_result = requests.get(url=testcase+str(testcaseid),json=json_payload).json()
        print(testcase_result)
        ###get graph details
        print(flow+str(testcase_result["flow"]["id"]))
        response = requests.get(flow+str(testcase_result["flow"]["id"])).json()
        graph_json=response["graph_json"]
        
        tree = self.bfs_decode_graph(graph_json)   
        print(tree)
        print("------------------------")
        
        root = graph_json["root"]
        data = {'id':testcase_result["flow"]["id"],'graph_json':graph_json,
                'testcaseexecution':testcaseexecution_result["id"],
                'testsessionexecution':testsessionid,'node_id':root,
                'environment_id':environmentid,'browser':browser}
        self.run(data)

    def run(self,data,node_response= None,index=1):
            
            id = data['id']
            graph_json = data['graph_json']
            testcaseexecution = data['testcaseexecution']
            testsessionexecution = data['testsessionexecution']
            node_id = data['node_id']
            environment_id = data['environment_id']
            browser = data['browser']
            ### check node response details 
            if node_response:

                ### IF it's TRUE
                if node_response["status"]:
                    time.sleep(1)
                    if node_response["type"] == "iterator":
                        print("yes")

                        for i in range(1,node_response["length"]+1):
                            socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                                        'testsessionexecutionid':testsessionexecution,"index":i,
                                        'type':node_response["type"],'status':"successfull"}
                            self.pushtosocketio(socketdata)

                        node_id = self.getchildren(graph_json,node_id)[0] if self.getchildren(graph_json,node_id) else None

                        if node_response["executionmode"] == "Sequencial Execution":
                            pass
                        elif node_response["executionmode"] == "Parallel Execution":
                            for iteration in range(1,node_response["length"]):
                                print(iteration)
                                self.run(id,graph_json,testcaseexecution,testsessionexecution,node_id,index=iteration)
                            index=node_response["length"]
                        
                    elif node_response["type"] == "conditions":
                        socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                                        'testsessionexecutionid':testsessionexecution,"index":index,
                                        'type':node_response["type"],'status':"successfull",
                                        "condition_satisfied":node_response["condition_satisfied"]}
                        self.pushtosocketio(socketdata)
                        if node_response["condition_satisfied"]:
                            node_id = str(node_response["result_node"])
                        else:
                            node_id = None

                    elif node_response["type"] == "assertion":
                        socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                                        'testsessionexecutionid':testsessionexecution,"index":index,
                                        'type':node_response["type"],'status':"successfull",
                                        "condition_satisfied":node_response["condition_satisfied"]}
                        self.pushtosocketio(socketdata)
                        if node_response["condition_satisfied"]:
                            node_id = self.getchildren(graph_json,node_id)[0] if self.getchildren(graph_json,node_id) else None
                        else:
                            node_id = None                              
                    
                    else:
                        socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                                    'testsessionexecutionid':testsessionexecution,'type':node_response["type"],
                                    'status':"successfull","index":index}
                        self.pushtosocketio(socketdata)
                        node_id = self.getchildren(graph_json,node_id)[0] if self.getchildren(graph_json,node_id) else None
                
                ### IF it's FALSE
                else:
                    socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                                'testsessionexecutionid':testsessionexecution,
                                'type':node_response["type"],'status':"fail","index":index}
                    self.pushtosocketio(socketdata)
                    node_id = None
                    # json_payload = {
                    #         'status':"failed"
                    #     }
                    # testcaseexecution1 = requests.put(url=tcexecution+testcaseexecution,json=json_payload).json()
            
            print(node_id)
            
            ### check if remaining in the POOL
            if node_id == None:

                flag = False
                responsepayload = {'query':"query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{type:\"iterator\", index:\"INDEX\"}){ id,pending, node_id }}}"}
                responsepayload['query'] = responsepayload['query'].replace("INDEX",str(index))
                responsepayload['query'] = responsepayload['query'].replace("ID",str(testcaseexecution))
                response = requests.post(url=graphql,data=responsepayload).json()
                response_jsons = response["data"]["testcaseexecutions"][0]["flowsteps"]
                if len(response_jsons) != 0:
                    responsepayload = {'pending':0}
                    response = requests.put(url=flowsteps+response_jsons[0]["id"],data=responsepayload).json()
                
                responsepayload = {'query':"query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{type:\"iterator\"}){ id,pending,index, node_id }}}"}
                responsepayload['query'] = responsepayload['query'].replace("ID",str(testcaseexecution))
                response = requests.post(url=graphql,data=responsepayload).json()
                response_jsons = response["data"]["testcaseexecutions"][0]["flowsteps"]

                if len(response_jsons) != 0:
                    for response_json in response_jsons:
                        print(response_json)
                        if response_json["pending"] == 1:
                            if graph_json[response_json["node_id"]]["properties"]["ExecutionMode"] == "Sequencial Execution":
                                node_id = self.getchildren(graph_json,response_json["node_id"])[0] if self.getchildren(graph_json,response_json["node_id"]) else None
                                print(index)
                                index = response_json["index"]
                            flag = False
                            break
                        else:
                            flag = True
                else:
                    flag = True
                
                if flag:
                    

                    print("-------------came to completion--------------")
                    ### get testsessionexecution data
                    testsessionexecution1 = requests.get(url=tsexecution+str(testsessionexecution)).json()
                    
                    ### get testcaseexecution data
                    responsepayload = {'query':"""{
                        testcaseexecution(id:"TESTCASEEXECUTIONID"){
                            flowsteps(where:{status:"fail"}){
                            status
                            }
                        }
                        }"""}
                    responsepayload['query'] = responsepayload['query'].replace("TESTCASEEXECUTIONID",str(testcaseexecution))
                    response = requests.post(url=graphql,data=responsepayload).json()
                    print(response)
                    response_jsons = response["data"]["testcaseexecution"]["flowsteps"]

                    ### setup report data
                    if len(response_jsons) > 0:
                        tce_json_payload = {
                            'status':"failed",
                            'end_time':str(datetime.datetime.now())
                        }
                        tse_json_payload = {
                            'total_fail':int(testsessionexecution1["total_fail"]) +1,
                            'end_time':str(datetime.datetime.now())
                        }

                        socketdata = {'testcaseexecutionid':testcaseexecution,'testsessionexecutionid':testsessionexecution,
                                        'status':"failed"}
                    else:
                        tce_json_payload = {
                            'status':"completed",
                            'end_time':str(datetime.datetime.now())
                        }
                        tse_json_payload = {
                            'total_pass':int(testsessionexecution1["total_pass"]) +1,
                            'end_time':str(datetime.datetime.now())
                        }
                        socketdata = {'testcaseexecutionid':testcaseexecution,'testsessionexecutionid':testsessionexecution,
                                        'status':"completed"}


                    ### push to socket saying testcaseexecution result
                    self.pushtosocketio(socketdata)

                    ### store the testcaseexecution status result 
                    testcaseexecution1 = requests.put(url=tcexecution+str(testcaseexecution),json=tce_json_payload).json()
                    print(testcaseexecution1)
                    
                    
                    ### send reponse if testsuite is not default 
                    ### i.e it is not only testcase run its a testsuite runner
                    if not testsessionexecution1["testsuite"]["suite_name"] == "default":

                        ### store the testsessionexecution status result 
                        testsessionexecution_result = requests.put(url=tsexecution+str(testsessionexecution),json=tse_json_payload).json()
                        
                        json_payload = {
                            'testsessionid':testsessionexecution,
                            'environment_id':environment_id,
                            'browser':browser                        }
                        self.sendresponse(json_payload)

                    print("test completed")

                if node_id == None:
                    print("done")       
                    return
            print(node_id)

            Type = graph_json[node_id]["properties"]["Type"]

            if Type == "api":
                data = {"id":node_id,"testcaseid":id,"testcaseexecutionid":testcaseexecution,
                            'testsessionexecutionid':testsessionexecution,"index":index,
                            'environment_id':environment_id,"browser":browser}  
                # self.pushtoqueue('api_executor',data)
                d = threading.Thread(name='a'+str(testcaseexecution), target=api_executor.run, args=[data])
                d.start()
                socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                                'testsessionexecutionid':testsessionexecution,'type':"api",
                                        'status':"started","index":index}
                self.pushtosocketio(socketdata)
            
            elif Type == "source":
                data = {"id":node_id,"testcaseid":id,"testcaseexecutionid":testcaseexecution,
                            'testsessionexecutionid':testsessionexecution,"index":index,
                            'environment_id':environment_id,"browser":browser}  
                # self.pushtoqueue('source_executor',data)
                d = threading.Thread(name='s'+str(testcaseexecution), target=source_executor.run, args=[data])
                d.start()
                socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                                'testsessionexecutionid':testsessionexecution,'type':"source",
                                        'status':"started","index":index}
                self.pushtosocketio(socketdata)

            elif Type == "controls":
                
                data = {"id":node_id,"testcaseid":id,"testcaseexecutionid":testcaseexecution,
                            'testsessionexecutionid':testsessionexecution,"index":index,
                            'environment_id':environment_id,"browser":browser}       
                # self.pushtoqueue('condition_executor',data)
                d = threading.Thread(name='c'+str(testcaseexecution), target=condition_executor.run, args=[data])
                d.start()
                socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                            'testsessionexecutionid':testsessionexecution,
                            'type':graph_json[node_id]["properties"]["Method"],
                            'status':"started","index":index}
                self.pushtosocketio(socketdata)
            elif Type == "testcase":
                data = {"id": node_id, "testcaseid": graph_json[node_id]["properties"]["UiTestcase"], "testcaseexecutionid": testcaseexecution,
                            'testsessionid':testsessionexecution,"index":index,
                            'environment_id':environment_id,"browser":browser,"node_id":node_id,"api_testcase_id":id}   
                     
                requests.post(url=testcase+"run",json=data)
                socketdata = {'id':node_id,'testcaseexecutionid':testcaseexecution,
                            'testsessionexecutionid':testsessionexecution,
                            'type':graph_json[node_id]["properties"]["Method"],
                            'status':"started","index":index}
                self.pushtosocketio(socketdata)
                # break    

    def dfs_decode_graph(self,graph_json):
        
        tree_id = []
        root = graph_json["root"]
        def dfs_walk(node):
            tree_id.append(node)
            for succ in graph_json[node]["children"]:
                if not succ in tree_id:
                    dfs_walk(succ)

        dfs_walk(root)
        return tree_id

    def bfs_decode_graph(self,graph_json):
        
        tree_id = []
        queue = []
        root = graph_json["root"]
        # root = "4"
        queue.append(root)
        while queue:
            s = queue.pop(0)
            tree_id.append(s)
            for succ in graph_json[s]["children"]:
                queue.append(succ)

        return tree_id

    def getchildren(self,graph_json,root):
        tree_id = []
        for succ in graph_json[root]["children"]:
            tree_id.append(succ)
        return tree_id

    def pushtoqueue(self,queue_name,json_data):
        try:
            connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=RMQ_HOST,port=RMQ_PORT))
            channel = connection.channel()

            channel.queue_declare(queue=queue_name)
            channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(json_data))
            connection.close()
            return True
        except Exception as identifier:
            return False
    
    def pushtosocketio(self,data):
        global sio
        sio.emit('api_execution', data)

    def sendresponse(self, data):

        try:
            queue_name = "testdecider"
            connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=RMQ_HOST,port=RMQ_PORT))
            channel = connection.channel()

            channel.queue_declare(queue=queue_name)

            print(data)
            channel.basic_publish(
                exchange='', routing_key=queue_name, body=json.dumps(data))

            channel.close()
        except Exception as identifier:
            print(identifier)

class Consumer():

    def __init__(self, host,port):
        self._host = host
        self._port = port
        self._decider = Decider()

    def callback_func(self, channel, method, properties, body):
        
        # print("{} received '{}'".format(self.name, body))
        try:
            data = json.loads(body)
            print("Data --> ")
            print(data)

            if 'testsessionid' in data:
                print("started")
                self._decider.start(data)
                print("----------------------------------------------------")
            else:
                print("received")
                print(data)
                response = requests.get(flow+str(data["testcaseid"])).json()
                graph_json=response["graph_json"]
                resdata = {'id':data["testcaseid"],'graph_json':graph_json,
                        'testcaseexecution':data["testcaseexecutionid"],
                        'testsessionexecution':data["testsessionexecutionid"],
                        'node_id':data["id"],'environment_id':data['environment_id'],'browser':data['browser']}
                self._decider.run(resdata,data,data["index"])
                print("----------------------------------------------------")
        except Exception as identifier:
            print(identifier)
            
    def run(self):

        self.startsioserver()

        credentials = pika.PlainCredentials("guest", "guest")

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))

        channel = connection.channel()

        channel.queue_declare(queue='decider')

        channel.basic_consume(queue='decider',
                      auto_ack=True,
                      on_message_callback=self.callback_func)

        channel.start_consuming()
    
    def startsioserver(self):
        global sio
        # create a Socket.IO CLient
        sio = socketio.Client()
        sio.connect(socket_host)

if __name__ == "__main__":

    RMQ_HOST = os.environ.get('RMQ_HOST') if os.environ.get('RMQ_HOST') else "localhost" 
    RMQ_PORT = int(os.environ.get('RMQ_PORT')) if os.environ.get('RMQ_PORT') else 5672 
    socket_host = os.environ.get('SOCKET_HOST') if os.environ.get('SOCKET_HOST') else "http://127.0.0.1:1337"
    host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337"


    flow = host+"/flows/"
    flowsteps = host+"/flowsteps/"
    tsexecution = host+"/testsessionexecutions/"
    tcexecution = host+"/testcaseexecutions/"
    testcase = host+"/testcases/"
    graphql = host+"/graphql"

    print(RMQ_HOST,RMQ_PORT,socket_host)
    consumer = Consumer(host = RMQ_HOST,port = RMQ_PORT)
    consumer.run()
    
