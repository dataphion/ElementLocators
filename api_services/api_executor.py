import pika
import threading
import json
import os
import requests
import time
import re
import sys
import socketio
import jsonschema
from requests.exceptions import HTTPError
from requests.auth import HTTPBasicAuth
from ast import literal_eval

host = "http://localhost:1337"
flow = host+"/flows/"
flowsteps = host+"/flowsteps/"
graphql = host+"/graphql"
tcases = host+"/testcases/"
sio = None
class Api_Executor:
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
        print("intialized api executor") 

    def run(self, data):
        
        node_response = {'status': False,'message':"No Data"}
        if data:
            node_response = self.testapi(data)
        
        self.producer.publish(node_response)
        
    def testapi(self,mqdata):

      try:

            print(str(mqdata["testcaseid"]))
            print(mqdata["id"])
            print(flow)
            response = requests.get(flow+str(mqdata["testcaseid"]))
            response = json.loads(response.content)
            graph_json=response["graph_json"]
            node_json = graph_json[mqdata["id"]]
            properties = node_json["properties"]
            if "parent" in node_json and len(node_json["parent"]) > 0:
                parent = node_json["parent"][0]
            if "children" in node_json and len(node_json["children"]) > 0:
                children = node_json["children"][0]
                children_node = graph_json[children]
            Iterator = True if 'parent_data' in mqdata else False
            title = properties["Title"]
            print("api titles ---->", title)
            print("api properties --->", properties)
            
            ### search for {{parent.}}            
            if re.search("\{\{parent\.(.*?)\}\}",json.dumps(properties)) :
                isString = False
                output = self.getparentdata(mqdata, parent)
                if output == None:
                    return {'status': False ,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':'api','testcaseexecutionid':mqdata["testcaseexecutionid"],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"],
                        'message':"No parent data found"} 
                properties = json.dumps(properties)
                xs = re.findall("\{\{parent\.(.*?)\}\}",json.dumps(properties))
                for x in xs:
                    if "." in x:
                        parent_value = output
                        splitstring = str(x).split(".")
                        for string in splitstring:
                            if string == "toString":
                                isString = True
                                break
                            if re.search("\[(.*?)\]",string):
                                no = re.findall("\[(.*?)\]",str(string))
                                splstr = string.split('[')
                                parent_value = parent_value[splstr[0]][int(no[0])]
                            else:
                                parent_value = parent_value[string]
                    else:
                        parent_value = output[x]

                    if isString:
                        temp = "\{\{parent\."+x+"\}\}"
                    else:
                        temp = "\"\{\{parent\."+x+"\}\}\""
                    temp = temp.replace('[','\[')
                    temp = temp.replace(']', '\]')
                    
                    if isinstance(parent_value, str):      
                        parent_value = parent_value.replace('/','\/')
                        parent_value = parent_value.replace('"','\\"')                  
                        # regex = re.compile('[@_!"#+$%^&*()<>?/\}{\-\[\]~:;,=.]')
                        # if not (regex.search(parent_value) == None): 
                        #     tes = re.findall(regex,parent_value)
                        #     print(list(set(tes)))
                        #     for spec in list(set(tes)):
                        #         print("spec------>",spec)
                        #         parent_value = parent_value.replace(spec,'\\'+spec)
                    if not isinstance(parent_value, str):
                        replace_value = json.dumps(parent_value)
                    else:
                        if isString:
                            replace_value = parent_value
                        else:
                            replace_value = "\""+parent_value+ "\""

                    # print(properties)

                    # print("-----------")
                    # print(temp)
                    # print(replace_value)
                    # print("-----------")
                    # print(json.dumps(properties))
                    # print("-----------")
                    properties = re.sub(temp, replace_value, properties)
                    print(properties)

                properties = json.loads(properties)
                isString = False
            
            ### search for {{}}            
            if re.search("\{\{(.*?)\}\}",json.dumps(properties)) :
                isString = False
                xs = re.findall("\{\{(.*?)\}\}",json.dumps(properties))
                properties = json.dumps(properties)
                for x in xs:
                    xsplit = str(x).split('.', 1)
                    node_output = self.getparentdata(mqdata,xsplit[0],FromNode=True)
                    if node_output == None:
                        return {'status': False ,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                            'type':'api','testcaseexecutionid':mqdata["testcaseexecutionid"],
                            'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"],
                            'message':"No parent data found"}
                    if "." in xsplit[1]:
                        parent_value = node_output
                        splitstring = str(xsplit[1]).split(".")
                        for string in splitstring:
                            if string == "toString":
                                isString = True
                                break
                            if re.search("\[(.*?)\]",string):
                                no = re.findall("\[(.*?)\]",str(string))
                                splstr = string.split('[')
                                parent_value = parent_value[splstr[0]][int(no[0])]
                            else:
                                parent_value = parent_value[string]
                    else:
                        parent_value = node_output[xsplit[1]]
                    
                    temp = "\"\{\{"+x+"\}\}\""
                    temp = temp.replace('[','\[')
                    temp = temp.replace(']', '\]')

                    
                    if isinstance(parent_value, str):                        
                        parent_value = parent_value.replace('/','\/')
                        parent_value = parent_value.replace('"','\\"')
                        # regex = re.compile('[@_!"#+$%^&*()<>?/\}{\-\[\]~:;,=.]')
                        # if not (regex.search(parent_value) == None): 
                        #     tes = re.findall(regex,parent_value)
                        #     print(list(set(tes)))
                        #     for spec in list(set(tes)):
                        #         print("spec------>",spec)
                        #         parent_value = parent_value.replace(spec,'\\'+spec)
                    if not isinstance(parent_value, str):
                        replace_value = json.dumps(parent_value)
                    else:
                        replace_value = "\""+parent_value+ "\""
                        
                    # print(properties)
                    # print("-----------")
                    # print(temp)
                    # print(replace_value)
                    # print("-----------")
                    properties = re.sub(temp, replace_value, properties)
                    # print(properties)

                properties = json.loads(properties)
                isString = False
            
            ### get host
            print("properties ------------>", properties)
            print(properties["EndpointPackId"])
            response
            request_dict ={}
            if properties["Method"] == "graphql":
                graphql_query = "query" + properties["graphqlQuery"]
                graphql_URL = properties["GraphqlUrl"]
                graphql_headers = properties["HeadersAdd"]
                print("execute graphql", graphql_query)
                response = requests.post(graphql_URL, json={'query': graphql_query}, headers=graphql_headers)
                response.raise_for_status()

            else:    
                responsepayload = {'query':"query {  endpointpacks(where: { id: \"ENDPACKID\"}) { host_url }}"}
                responsepayload['query'] = responsepayload['query'].replace("ENDPACKID",str(properties["EndpointPackId"]).strip())
                # print(responsepayload)
                response_json = requests.post(url=graphql,data=responsepayload).json()
                host_url = response_json["data"]["endpointpacks"][0]["host_url"]

                # testcase = requests.get(url=tcases+response["testcase"]["id"]).json()
                # print(testcase["application"]["name"])
                # host1 = testcase["application"]["url"]

                method = properties["Method"]
                Uri = host_url+properties["Uri"]

                # if "custom_api" in properties:
                #     Uri = properties["Uri"]


                BodyType = properties["BodySelectedMenu"]
                pathparams = properties["PathParametersAdd"] if properties["PathParametersAdd"] else ""
                params = properties["QueryParametersAdd"] if properties["QueryParametersAdd"] else []
                headers = properties["HeadersAdd"] if properties["HeadersAdd"] else []

                if headers:
                    for key,value in headers.items():
                        if isinstance(value,dict):
                            headers[key] = json.dumps(value)
                        elif not isinstance(value,str):
                            headers[key] = json.dumps(value)
                AuthorizationUser = properties["AuthorizationUsername"] if properties["AuthorizationUsername"] else None          
                AuthorizationPass = properties["AuthorizationPassword"] if properties["AuthorizationPassword"] else None           
                
                ### replace parthparam
                if pathparams:
                    for key,value in pathparams.items():
                        replstr = "{"+str(key)+"}"
                        print(replstr)
                        Uri = Uri.replace(replstr,str(value))
                        print(Uri)

                request_dict = {
                    'method': method,
                    'url':Uri,
                    'params': params,
                    'headers': headers
                }

                print("request payloads api ------------------>", request_dict)

                data = properties["AceEditorValue"] if properties["AceEditorValue"] else []
                jsondata = {}
                if BodyType == "FormData":
                    data = properties["BodyFormDataAdd"]
                    request_dict['data'] = json.loads(data)
                elif BodyType == "JSON":
                    jsondata= data
                    data = []
                    request_dict['json'] = data
                    request_dict['data'] = []
                else:
                    request_dict['data'] = data

                auth=()
                if AuthorizationUser:
                    auth =(AuthorizationUser, AuthorizationPass)
                    request_dict['authorizationuser']=AuthorizationUser
                    request_dict['authorizationpass']=AuthorizationPass

                if jsondata:
                    response = requests.request(method=method,url=Uri,headers=headers,params=params,
                                data=data,json=jsondata,auth=auth)
                else:
                    response = requests.request(method=method,url=Uri,headers=headers,params=params,
                                data=data,auth=auth)

                print("response ----->", response)
                response.raise_for_status()

      except HTTPError as http_err:
          print(f'HTTP error occurred: {http_err}')  # Python 3.6
          json_response={
              'name': title,
              'status':'fail',
              'url':response.request.url,
              'status_code':response.status_code,
              'node_id':mqdata["id"],
              'type':'api',
              'request':request_dict,
              'response':response.text,
              'index':mqdata["index"],
              'testcaseexecution':{
                  'id':mqdata["testcaseexecutionid"]
              }
          }

          dbresponse = requests.post(url=flowsteps,json=json_response)
          return {'status':False,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
              'type':'api','testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
              'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"]}
              
      except Exception as identifier:
          print(identifier)
          json_response={
              'name': title,
              'status':'fail',
              'status_code':0,
              'node_id':mqdata["id"],
              'type':'api',
              'index':mqdata["index"],
              'testcaseexecution':{
                  'id':mqdata["testcaseexecutionid"]
              }
          }

          dbresponse = requests.post(url=flowsteps,json=json_response)
          return {'status':False,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
              'type':'api','testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
              'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"]}
      
      else:

            print("api status ->",response.status_code)
            ### export to database
            # print(request_dict)
            resp_data = ""
            try:
                resp_data = response.json()
            except Exception as identifier:
                print("Unable to convert response to json")
                # print(response.text)
                resp_data = response.text

            ### validate api response
            validation = True
            if "custom_api" not in properties:
                validation = self.validateresponse(properties, resp_data,response.status_code)

            json_response={
                'name': title,
                'status':"pass",
                'url':response.request.url,
                'status_code':response.status_code,
                'node_id':mqdata["id"],
                'type':'api',
                'request':request_dict,
                'response':resp_data,
                'index':mqdata["index"],
                'testcaseexecution':{
                    'id':mqdata["testcaseexecutionid"]
                }
            }

            dec_response = {'status':True,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                'type':'api','testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"]}
            if not validation:
                json_response['status'] = "fail"
                dec_response['status'] = False
            print("flowsteps dataaaaaa ---------->", json_response)
            dbresponse = requests.post(url=flowsteps,json=json_response)
            # print(dbresponse['data'])
            print("cms response")
            # print(dbresponse.text)
            print("------------")
            print("Executed")   
            return dec_response

    def getparentdata(self, mqdata, parent,FromNode=False):
        if FromNode:
            responsepayload = {'query':"query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{name:\"NAME\", index: IND}){ response request }}}"}
            responsepayload['query'] = responsepayload['query'].replace("IND",str(mqdata["index"]))
            responsepayload['query'] = responsepayload['query'].replace("NAME",parent)
            responsepayload['query'] = responsepayload['query'].replace("ID",str(mqdata["testcaseexecutionid"]))
            print(responsepayload)
            response = requests.post(url=graphql,data=responsepayload).json()
            # print(response)
            parent_response_node = response["data"]["testcaseexecutions"][0]["flowsteps"]
        else:
            responsepayload = {'query':"query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{node_id:\"NODEID\", index: IND}){ response request }}}"}
            responsepayload['query'] = responsepayload['query'].replace("IND",str(mqdata["index"]))
            responsepayload['query'] = responsepayload['query'].replace("NODEID",parent)
            responsepayload['query'] = responsepayload['query'].replace("ID",str(mqdata["testcaseexecutionid"]))
            print(responsepayload)
            response = requests.post(url=graphql,data=responsepayload).json()
            # print(response)
            parent_response_node = response["data"]["testcaseexecutions"][0]["flowsteps"]
        print(len(parent_response_node))
        output = parent_response_node[0]
        # if isinstance(parent_response_node[0], list):                
        #     output = parent_response_node[0] if len(parent_response_node[0])>0 else None
        # else:
        #     output = parent_response_node[0]["response"]
        return output
    
    def validateresponse(self, properties,response,status_code):
        try:
            responsepayload = {'query':"query {  endpointpacks(where: { id: \"ENDPACKID\"}) {  endpoints(where: { endpoint: \"ENDPOINT\", method: \"METH\" }) { id responses endpointrefs{  id ref_name structure }}}}"}
            responsepayload['query'] = responsepayload['query'].replace("ENDPACKID",str(properties["EndpointPackId"]).strip())
            responsepayload['query'] = responsepayload['query'].replace("ENDPOINT",properties["Uri"])
            responsepayload['query'] = responsepayload['query'].replace("METH",properties["Method"])
            # print(responsepayload)
            response_json = requests.post(url=graphql,data=responsepayload).json()
            endpoints = response_json["data"]["endpointpacks"][0]["endpoints"][0]
            endpointrefs = response_json["data"]["endpointpacks"][0]["endpoints"][0]["endpointrefs"]
            schema = endpoints["responses"][str(status_code)]

            print(re.search("\$ref",json.dumps(schema)))

            # print("response")
            # print(response)
            # print("schema")
            # print(schema)

            if re.search("\$ref",json.dumps(schema)):
                if "$ref" in schema:
                    for endpointref in endpointrefs:
                        if endpointref["ref_name"] == schema["$ref"]:
                            schema = endpointref["structure"]
                elif "$ref" in schema["items"]:
                    for endpointref in endpointrefs:
                        if endpointref["ref_name"] == schema["items"]["$ref"]:
                            # print(len(endpointref["structure"]))
                            schema["items"] = endpointref["structure"]
                            break
            # print(schema)
            if schema:
                schema = re.sub("json","object",json.dumps(schema))
                schema = json.loads(schema)

                jsonschema.validate(instance=response, schema=schema)
            
            print("Validation done")
            return True
        except Exception as identifier:
            print(identifier)
            print("Validation Error")
            return True
 
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
        self._apiexecutor = Api_Executor()

    # Not necessarily a method.
    def callback_func(self, channel, method, properties, body):
    
        # print("{} received '{}'".format(self.name, body))
        data = json.loads(body)
        print("api executor Data ----> ")
        print(data)

        if data:
            node_response = self._apiexecutor.testapi(data)
            self.sendresponse(node_response)
        else:
            node_response = {'status': False,'message':"No Data"}
            self.sendresponse(node_response)

        # print(response)
 
    def sendresponse(self,data,ToDecider=True):
        
        queue_name = "decider" if ToDecider else "condition_response"

        credentials = pika.PlainCredentials("guest", "guest")
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))
        channel = connection.channel()

        channel.queue_declare(queue=queue_name)

        channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(data))

        channel.close()
        
    def run(self):
        credentials = pika.PlainCredentials("guest", "guest")

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))

        channel = connection.channel()

        channel.queue_declare(queue='api_executor')

        channel.basic_consume(queue='api_executor',
                      auto_ack=True,
                      on_message_callback=self.callback_func)

        channel.start_consuming()

if __name__ == "__main__":

    RMQ_HOST = os.environ.get('RMQ_HOST') if os.environ.get('RMQ_HOST') else "localhost" 
    RMQ_PORT = int(os.environ.get('RMQ_PORT')) if os.environ.get('RMQ_PORT') else 5672 
    host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337" 

    flow = host+"/flows/"
    flowsteps = host+"/flowsteps/"
    graphql = host+"/graphql"
    tcases = host+"/testcases/"

    print(RMQ_HOST,RMQ_PORT,host)
    consumer = Consumer(host = RMQ_HOST,port = RMQ_PORT)
    consumer.run()
