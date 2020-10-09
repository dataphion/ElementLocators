import pika
import threading
import json
import os
import requests
import time
import re
import operator
import socketio
from multiprocessing import Pool
from api_executor import Api_Executor
from ast import literal_eval

host = "http://localhost:1337"
flow = host+"/flows/"
flowsteps = host+"/flowsteps/"
graphql = host+"/graphql"
sio = None
class Condition_Executor:
    def __init__(self):

        global host, flow, flowsteps, graphql, tcases
        RMQ_HOST = os.environ.get('RMQ_HOST') if os.environ.get('RMQ_HOST') else "localhost" 
        RMQ_PORT = int(os.environ.get('RMQ_PORT')) if os.environ.get('RMQ_PORT') else 5672 
        host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337" 

        flow = host+"/flows/"
        flowsteps = host+"/flowsteps/"
        graphql = host+"/graphql"
        tcases = host+"/testcases/"

        self.producer = Producer(host = RMQ_HOST,port = RMQ_PORT)
        print("intialized condition executor") 

    # Not necessarily a method.
    def run(self, data):
        node_response = self.testcondition(data)
        
        self.producer.publish(node_response)
        # print(response) 
        
    def get_operator_fn(self,op):
        # print("yes")
        return {
            "Equal to" : operator.eq,
            "Not equal to" : operator.ne,
            "Less than" : operator.lt,
            "Less than Equal to" : operator.le,
            "Greater than" : operator.gt,
            "Greater than Equal to" : operator.ge,
            }[op] 

    def testcondition(self,mqdata):
        try:
            
            response = requests.get(flow+str(mqdata["testcaseid"]))
            response = json.loads(response.content)
            graph_json=response["graph_json"]
            node_json = graph_json[mqdata["id"]]
            properties = node_json["properties"]
            title = properties["Title"]
            method = properties["Method"]
            print(method)
            if "parent" in node_json and len(node_json["parent"]) > 0:
                parent = node_json["parent"][0]
            if "children" in node_json and len(node_json["children"]) > 0:
                children = node_json["children"][0]
                children_node = graph_json[children]
            
            parent_response_node = {}
            ### search for {{parent.}}            
            if re.search("\{\{parent\.(.*?)\}\}",str(properties)) :
                ### get parent data
                parent_response_node = self.getparentdata(mqdata, parent)
                if parent_response_node == None:
                    return {'status': False ,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':'api','testcaseexecutionid':mqdata["testcaseexecutionid"],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"],
                        'message':"No parent data found"}

                # if isinstance(parent_response_node[0]["response"], list):                
                #     parent_response_node = parent_response_node[0]["response"][0] if len(parent_response_node[0]["response"])>0 else None
                # else:
                #     parent_response_node = parent_response_node[0]["response"]

                xs = re.findall("\{\{parent\.(.*?)\}\}",str(properties))
                for x in xs:
                    if "." in x:
                        parent_value = parent_response_node
                        splitstring = str(x).split(".")
                        # print(splitstring)
                        for string in splitstring:
                            if re.search("\[(.*?)\]",string):
                                # print(string)
                                no = re.findall("\[(.*?)\]",str(string))
                                # print(no)
                                splstr = string.split('[')
                                parent_value = parent_value[splstr[0]][int(no[0])]
                            else:
                                parent_value = parent_value[string]
                    else:
                        print(x)
                        parent_value = parent_response_node[x]
                    
                    temp = "\{\{parent\."+x+"\}\}"
                    temp = temp.replace('[','\[')
                    temp = temp.replace(']', '\]')

                    replace_value = str(parent_value) if not isinstance(
                        parent_value, str) else parent_value

                    properties = re.sub(temp, replace_value, str(properties))

                    if not isinstance(parent_value, str):
                        print("yes")
                        properties = re.sub("}'", "}", str(properties))
                        properties = re.sub(": '\{", ": {", str(properties))
                        properties = re.sub("]'", "]", str(properties))
                        properties = re.sub(": '\[", ": [", str(properties))
                
                properties = literal_eval(properties)

            ### search for {{}}            
            if re.search("\{\{(.*?)\}\}",str(properties)) :

                xs = re.findall("\{\{(.*?)\}\}",str(properties))
                for x in xs:
                    xsplit = str(x).split('.', 1)
                    node_output = self.getparentdata(mqdata,xsplit[0],FromNode=True)
                    if node_output == None:
                        return {'status': False ,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                            'type':'api','testcaseexecutionid':mqdata["testcaseexecutionid"],
                            'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"],
                            'message':"No parent data found"}

                    # if isinstance(node_output[0]["response"], list):                
                    #     node_output = node_output[0]["response"][0] if len(node_output[0]["response"])>0 else None
                    # else:
                    #     node_output = node_output[0]["response"]
                    if "." in xsplit[1]:
                        parent_value = node_output
                        splitstring = str(xsplit[1]).split(".")
                        for string in splitstring:
                            if re.search("\[(.*?)\]",string):
                                no = re.findall("\[(.*?)\]",str(string))
                                splstr = string.split('[')
                                parent_value = parent_value[splstr[0]][int(no[0])]
                            else:
                                parent_value = parent_value[string]
                    else:
                        parent_value = node_output[xsplit[1]]
                    temp = "\{\{"+x+"\}\}"
                    temp = temp.replace('[','\[')
                    temp = temp.replace(']','\]')

                    replace_value = str(parent_value) if not isinstance(parent_value, str) else parent_value

                    properties = re.sub(temp, replace_value, str(properties))

                    if not isinstance(parent_value, str):
                        print("yes")
                        properties = re.sub("}'", "}", str(properties))
                        properties = re.sub(": '\{", ": {", str(properties))
                        properties = re.sub("]'", "]", str(properties))
                        properties = re.sub(": '\[", ": [", str(properties))

                properties = literal_eval(properties)

            if method == "iterator":
                ExecutionMode = properties["ExecutionMode"]
                parent_outputs = self.getparentdata(mqdata, parent)["response"]
                # print(ExecutionMode)
                
                index = 1
                for parent_output in parent_outputs:
                    json_response={
                        'name': title,
                        'status':'pass',
                        'node_id':mqdata["id"],
                        'type':'iterator',    
                        'index':index,
                        'pending':1,   
                        'response':parent_output,
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response).json()
                    index += 1

                return {'status':True,'type':method,'length':len(parent_outputs),
                        'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],'executionmode':ExecutionMode,
                        'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }

            elif method == "conditions":

                Conditions = properties["ConditionsAdd"]
                Num_Condition = len(Conditions)
                outputs = []
                # print(properties["ConditionsParse"])
                for Condition in properties["ConditionsParse"]:
                    outcomes = {'status':None,'data':[]}
                    
                    self.check_condition(Condition,mqdata,outcomes)

                    if outcomes["status"] == 200:
                        outcomes["result_node"]= Condition["selected_condition_id"]

                    outputs.append(outcomes)

                json_response={
                    'name':title,
                    'node_id':mqdata["id"],
                    'status':'fail',
                    'index':mqdata["index"],
                    'type':'conditions',
                    'response':parent_response_node,
                    'conditions_result':outputs,                    
                    'testcaseexecution':{
                        'id':mqdata["testcaseexecutionid"]
                    }
                }

                result = {'status':False,'condition_satisfied':False,'type':method,
                            'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                            'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],'browser':mqdata['browser'],
                            'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }
                for output in outputs:
                    if output["status"] == 200:
                        result['status'] = True
                        result['condition_satisfied'] = True
                        result['result_node']=output["result_node"]
                        json_response['status'] = 'pass'
                        break
                
                dbresponse = requests.post(url=flowsteps,json=json_response).json()
                return result

            elif method == "assertion":

                Assertion = properties["AssertionParse"]
                outputs = []
                outcomes = {'status':None,'data':[]}
                self.check_condition(Assertion[0],mqdata,outcomes)

                outputs.append(outcomes)
                
                print(type(mqdata["testcaseexecutionid"]) )
                json_response={
                    'name':title,
                    'status':'pass',
                    'node_id':mqdata["id"],
                    'index':mqdata["index"],
                    'type':'assertion',
                    'response':parent_response_node,
                    'conditions_result':outputs,                    
                    'testcaseexecution':{
                        'id':mqdata["testcaseexecutionid"]
                    }
                }

                result = {'status':True,'condition_satisfied':True,'type':method,
                            'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                            'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                            'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }
                for output in outputs:
                    if output["status"] == 500:
                        result['status'] = False
                        result['condition_satisfied'] = False
                        json_response['status'] = 'fail'
                        break

                dbresponse = requests.post(url=flowsteps,json=json_response).json()
                
                return result
            
            elif method == "variable":

                response = {}
                Variables = properties["VariableAdd"]
                for Variable in Variables:
                    if Variable["Type"] == "Object":
                        response[Variable["VariableName"]] = json.loads(Variable["Value"])
                    else:
                        response[Variable["VariableName"]] = Variable["Value"]
                print(response)

                json_response = {
                    'name': title,
                    'status':'pass',
                    'node_id': mqdata["id"],
                    'index': mqdata["index"],
                    'type': 'variable',
                    'response': response,
                    'testcaseexecution': {
                        'id': mqdata["testcaseexecutionid"]
                    }
                }
                dbresponse = requests.post(url=flowsteps, json=json_response).json()

                return {'status': True, 'type': method, 'index': mqdata["index"],
                          'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                          'testcaseexecutionid': mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                          'testsessionexecutionid': mqdata["testsessionexecutionid"]}

        except Exception as identifier:
            print(identifier)
            json_response={
                'name':title,
                'status':'fail',
                'node_id':mqdata["id"],
                'index':mqdata["index"],
                'type':method,
                'testcaseexecution':{
                    'id':mqdata["testcaseexecutionid"]
                }
            }
            dbresponse = requests.post(url=flowsteps,json=json_response).json()
            return {'status':False,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],'type':method,
                        'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }
    
    def check_condition(self,Condition,mqdata,outcomes,Condition_type=None):

        LHS = Condition["operand_1"]
        RHS = Condition["operand_2"]
        Operator = Condition["operator"]
        print("{0} {1} {2}".format(LHS,Operator,RHS))
        print(self.get_operator_fn(Operator)(LHS,RHS))
        
        outcome = "{0} {1} {2}".format(LHS,Operator,RHS)
        if Condition_type:
            if Condition_type == "and":
                if self.get_operator_fn(Operator)(LHS,RHS):

                    payload = {'status_code':200,'result':"Matched",'input':outcome,
                                'condition_type':Condition_type}
                    outcomes["status"] = 200
                    outcomes["data"].append(payload)

                    if len(Condition["nested"]) > 0:
                        self.check_condition(Condition["nested"][0],mqdata,outcomes,Condition["type"])

                else:
                    payload = {'status_code':500,'result':"Not Matched",'input':outcome,
                            'condition_type':Condition_type}
                    outcomes["status"] = 500
                    outcomes["data"].append(payload)
            elif Condition_type == "or":
                if outcomes["status"] == 200:

                    print("previous data is True")
                    if self.get_operator_fn(Operator)(LHS,RHS):
                        payload = {'status_code':200,'result':"Matched",'input':outcome,
                                    'condition_type':Condition_type}
                    else:
                        payload = {'status_code':500,'result':"Not Matched",
                            'input':outcome,'condition_type':Condition_type}
                    outcomes["status"] = 200
                    outcomes["data"].append(payload)
                else:
                    print("previous data is False")

                    if self.get_operator_fn(Operator)(LHS,RHS):
                        payload = {'status_code':200,'result':"Matched",'input':outcome,
                                    'condition_type':Condition_type}
                        
                        outcomes["status"] = 200
                        outcomes["data"].append(payload)
                    else:
                        payload = {'status_code':500,'result':"Not Matched",
                            'input':outcome,'condition_type':Condition_type}
                            
                        outcomes["status"] = 500
                        outcomes["data"].append(payload)
                if len(Condition["nested"]) > 0:
                    self.check_condition(Condition["nested"][0],mqdata,outcomes,Condition["type"])
        else:
            if self.get_operator_fn(Operator)(LHS,RHS):
                payload = {'status_code':200,'result':"Matched",'input':outcome,
                            'condition_type':Condition_type}
                outcomes["status"] = 200
                outcomes["data"].append(payload)
            else:
                payload = {'status_code':500,'result':"Not Matched",'input':outcome}
                outcomes["status"] = 500
                outcomes["data"].append(payload)
                
            Conditions_type = Condition["type"] if not Condition["type"] == None else None
            if Conditions_type:
                if Condition["type"] == "and":
                    if outcomes["status"] == 200:
                        self.check_condition(Condition["nested"][0],mqdata,outcomes,Condition["type"])
                else:
                    self.check_condition(Condition["nested"][0],mqdata,outcomes,Condition["type"])
    
    def getparentdata(self, mqdata, parent,FromNode=False):
        if FromNode:
            responsepayload = {'query':"query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{name:\"NAME\"}){ response request }}}"}
            responsepayload['query'] = responsepayload['query'].replace("NAME",parent)
            responsepayload['query'] = responsepayload['query'].replace("ID",str(mqdata["testcaseexecutionid"]))
            print(responsepayload)
            response = requests.post(url=graphql,data=responsepayload).json()
            # print(response)
            parent_response_node = response["data"]["testcaseexecutions"][0]["flowsteps"][0]
        else:
            responsepayload = {'query':"query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{node_id:\"NODEID\", index: IND}){ response request }}}"}
            responsepayload['query'] = responsepayload['query'].replace("IND",str(mqdata["index"]))
            responsepayload['query'] = responsepayload['query'].replace("NODEID",parent)
            responsepayload['query'] = responsepayload['query'].replace("ID",str(mqdata["testcaseexecutionid"]))
            # print(responsepayload)
            response = requests.post(url=graphql,data=responsepayload).json()
            # print(response)
            parent_response_node = response["data"]["testcaseexecutions"][0]["flowsteps"][0]
        
        return parent_response_node

        
class Producer():    
    def __init__(self, host,port):
        self._host = host
        self._port = port
    
    def publish(self, data):

        queue_name = "decider"

        credentials = pika.PlainCredentials("guest", "guest")
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))
        channel = connection.channel()

        channel.queue_declare(queue=queue_name)

        channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(data))

        channel.close()
        connection.close()
class Consumer():
    def __init__(self, host,port):
        self._host = host
        self._port = port
        self._condition_executor = Condition_Executor()

    # Not necessarily a method.
    def callback_func(self, channel, method, properties, body):
        
        # print("{} received '{}'".format(self.name, body))
        data = json.loads(body)
        print("condition Data --> ")
        print(data)

        node_response = self._condition_executor.testcondition(data)
        # print(node_response)
        self.sendresponse(node_response)
        # print(response)    

    def run(self):
        credentials = pika.PlainCredentials("guest", "guest")

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))

        channel = connection.channel()

        channel.queue_declare(queue='condition_executor')

        channel.basic_consume(queue='condition_executor',
                      auto_ack=True,
                      on_message_callback=self.callback_func)

        channel.start_consuming()
    
    def sendresponse(self,data,ToDecider=True):
        
        queue_name = "decider" if ToDecider else "condition_response"

        credentials = pika.PlainCredentials("guest", "guest")
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))
        channel = connection.channel()

        channel.queue_declare(queue=queue_name)

        print(data)
        channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(data))

        channel.close()
   
if __name__ == "__main__":

    RMQ_HOST = os.environ.get('RMQ_HOST') if os.environ.get('RMQ_HOST') else "localhost" 
    RMQ_PORT = int(os.environ.get('RMQ_PORT')) if os.environ.get('RMQ_PORT') else 5672 
    host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337"
    
    flow = host+"/flows/"
    flowsteps = host+"/flowsteps/"
    graphql = host+"/graphql"

    print(RMQ_HOST,RMQ_PORT)
    consumer = Consumer(host = RMQ_HOST,port = RMQ_PORT)
    consumer.run()
