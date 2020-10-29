import pika
import threading
import json
import os
import requests
import time
import re
import operator
from ast import literal_eval
import mysql.connector
import cx_Oracle 
from mysql.connector import Error
from pymongo import MongoClient
import datetime
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import ordered_dict_factory
import psycopg2
import paramiko
import imaplib
import email

host = "http://localhost:1337"
flow = host+"/flows/"
flowsteps = host+"/flowsteps/"
graphql = host+"/graphql"
Dbregistration = host+"/Dbregistrations/"
environment = host+"/environments/"
# getkeyfile = host

class Source_Executor:
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
        print("intialized source executor") 

    def run(self, data):
        node_response = self.testsource(data)
        self.producer.publish(node_response)

    def get_db_data(self,data):
        try:
            print("get data---------->",data)
            requestpayload = {
                'query': """{
                        environments(where:{id:"ENVIRONMENT_ID"}){
                            type
                            dbregistrations{
                            ip
                            port
                            username
                            password
                            database
                            queue_name
                            database_type
                            source_name
                            sourceregistration{
                                id
                            }
                            }
                        }
                    }"""}

            requestpayload['query'] = requestpayload['query'].replace("ENVIRONMENT_ID", str(data["environment_id"]).strip())
            print("requestpayload----------------->",requestpayload)
            response_json = requests.post(url=graphql, data=requestpayload).json()
            
            db_data = None
            for i in response_json['data']['environments'][0]['dbregistrations']:
                print("----------------------------")
                print(i)
                print("----------------------------")
                if i['sourceregistration']['id'] == str(data['source_id']):
                    db_data = i
                    break
            
            print(db_data)
            if db_data == None:
                return None
            else:
                return db_data
            
        except Exception as exce:
            print(exec)

    def testsource(self,mqdata):
        
        try:
            print("mqdata   ----->", mqdata)
            print("flow url ---->", flow+str(mqdata["testcaseid"]))
            response = requests.get(flow+str(mqdata["testcaseid"]))
            response = json.loads(response.content)
            graph_json=response["graph_json"]
            node_json = graph_json[mqdata["id"]]
            properties = node_json["properties"]
            print("properties ---->", properties)
            title = properties["Title"]
            Method = properties["Method"]
            QueryType = properties["QueryType"]
            DatabaseType = properties["DatabaseType"]
            if "parent" in node_json and len(node_json["parent"]) > 0:
                parent = node_json["parent"][0]
            if "children" in node_json and len(node_json["children"]) > 0:
                children = node_json["children"][0]
                children_node = graph_json[children]

            ### search for {{parent.}}
            if re.search("\{\{parent\.(.*?)\}\}", str(properties)):
                output = self.getparentdata(mqdata, parent)
                if output == None:
                        return {'status': False, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                                'type': 'api', 'testcaseexecutionid': mqdata["testcaseexecutionid"],
                                'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"],
                                'message': "No parent data found"}
                xs = re.findall("\{\{parent\.(.*?)\}\}", str(properties))
                for x in xs:
                    if "." in x:
                        parent_value = output
                        splitstring = str(x).split(".")
                        for string in splitstring:
                            if re.search("\[(.*?)\]", string):
                                no = re.findall("\[(.*?)\]", str(string))
                                splstr = string.split('[')
                                parent_value = parent_value[splstr[0]][int(
                                    no[0])]
                            else:
                                parent_value = parent_value[string]
                    else:
                        parent_value = output[x]
                    temp = "\{\{parent\."+x+"\}\}"
                    temp = temp.replace('[', '\[')
                    temp = temp.replace(']', '\]')

                    replace_value = str(parent_value) if not isinstance(parent_value, str) else parent_value

                    properties = re.sub(temp, replace_value, str(properties))

                    if not isinstance(parent_value, str):
                        print("yes")
                        properties = re.sub("}'", "}", str(properties))
                        properties = re.sub(": '\{", ": {", str(properties))
                        properties = re.sub("]'", "]", str(properties))
                        properties = re.sub(": '\[", ": [", str(properties))
                properties = literal_eval(properties)

            ### search for {{}}
            if re.search("\{\{(.*?)\}\}", str(properties)):
                xs = re.findall("\{\{(.*?)\}\}", str(properties))
                for x in xs:
                    xsplit = str(x).split('.', 1)
                    node_output = self.getparentdata(mqdata, xsplit[0], FromNode=True)
                    if node_output == None:
                        return {'status': False, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                                'type': 'api', 'testcaseexecutionid': mqdata["testcaseexecutionid"],
                                'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"],
                                'message': "No parent data found"}
                    if "." in xsplit[1]:
                        parent_value = node_output
                        splitstring = str(xsplit[1]).split(".")
                        for string in splitstring:
                            if re.search("\[(.*?)\]", string):
                                no = re.findall("\[(.*?)\]", str(string))
                                splstr = string.split('[')
                                parent_value = parent_value[splstr[0]][int(
                                    no[0])]
                            else:
                                parent_value = parent_value[string]
                    else:
                        parent_value = node_output[xsplit[1]]
                    temp = "\{\{"+x+"\}\}"
                    temp = temp.replace('[', '\[')
                    temp = temp.replace(']', '\]')

                    replace_value = str(parent_value) if not isinstance(parent_value, str) else parent_value

                    properties = re.sub(temp, replace_value, str(properties))

                    if not isinstance(parent_value, str):
                        print("yes")
                        properties = re.sub("}'", "}", str(properties))
                        properties = re.sub(": '\{", ": {", str(properties))
                        properties = re.sub("]'", "]", str(properties))
                        properties = re.sub(": '\[", ": [", str(properties))
                properties = literal_eval(properties)


            if DatabaseType == "mysql":
                print("database type --->", DatabaseType)
                print("data ---->", mqdata)
                ##get db data
                data = {'environment_id':mqdata['environment_id'],'source_id':properties["MysqlSourceId"]}
                data = self.get_db_data(data)

                if QueryType == "QueryTemplate":
                    Query = properties["MysqlQueryTemplate"]
                elif QueryType == "WriteQuery":
                    Query = properties["WrittenQuery"]
                # Query = Query.lower()
                query_response = self.mysqlquery(data,Query)
                if query_response["status"]:
                    json_response={
                        'name':title,
                        'status':'pass',
                        'node_id':mqdata["id"],
                        'type':DatabaseType,
                        'response': query_response["response"],
                        'source_result':str(query_response["output"]),      
                        'index':mqdata["index"],             
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response)
                    return {'status':True,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':DatabaseType,'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }
                else:
                    json_response={
                        'name':title,
                        'status':'fail',
                        'node_id':mqdata["id"],
                        'type':DatabaseType,
                        'source_result':"Error",
                        'index':mqdata["index"],              
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response).json()
                    return {'status':False,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':DatabaseType,'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }

            def mypostgresquery(self, data,Query):
                try:
                    print("test postgres query", data)
                    output = []
                    json_response = []
                    connection = psycopg2.connect(user=data["username"],
                                password=data["password"],
                                host=data["ip"],
                                port=data["port"],
                                database=data["database"])
                    if connection :
                        cursor = connection.cursor()
                        cursor.execute(Query)
                        if "select" in Query.lower():
                            rows = cursor.fetchall()
                            if rows:
                                for row in rows:
                                    output.append(row)
                                json_response = [dict((str(cursor.description[i][0]).lower(), str(value).lower()) \
                                    for i, value in enumerate(row)) for row in output]
                            else:
                                raise Exception("There are no records")
                        
                        elif "insert" in Query.lower():
                            connection.commit()
                        else:
                            connection.commit()

                        cursor.close()
                        connection.close()
                        return {'status':True,'output':output,'response':json_response}

                    else:
                        return {'status': False}
                except Exception as e:
                    print(e)
                    return {'status': False}


            if DatabaseType == "postgres":
                print("----- execute postgres queries -----")
                print(properties)
                
                data = {'environment_id':mqdata['environment_id'],'source_id':properties["CassandraSourceId"]}
                data = self.get_db_data(data)
                print("get db data ---->", data)

                if QueryType == "QueryTemplate":
                    Query = properties["CassandraQueryTemplate"]
                    print("if Query", Query)
                elif QueryType == "WriteQuery":
                    Query = properties["WrittenQuery"]
                    print("else Query", Query)

                query_response = self.mypostgresquery(data, query)
                print("---postgres query response---", query_response)
                if query_response["status"]:
                    json_response={
                        'name':title,
                        'status':'pass',
                        'node_id':mqdata["id"],
                        'type':DatabaseType,
                        'response': query_response["response"],
                        'source_result':str(query_response["output"]),      
                        'index':mqdata["index"],             
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response)
                    return {'status':True,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':DatabaseType,'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }
                else:
                    json_response={
                        'name':title,
                        'status':'fail',
                        'node_id':mqdata["id"],
                        'type':DatabaseType,
                        'source_result':"Error",
                        'index':mqdata["index"],              
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response).json()
                    return {'status':False,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':DatabaseType,'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }


            
            if DatabaseType == "oracle":
                
                ##get db data
                data = {'environment_id':mqdata['environment_id'],'source_id':properties["OracleSourceId"]}
                data = self.get_db_data(data)
                # OracleDatabase = properties["OracleDatabase"]
                # OracleSourceId = properties["OracleSourceId"]
                # source_response = requests.get(Dbregistration+OracleSourceId).json()
                if QueryType == "QueryTemplate":
                    MysqlQueryTemplate = properties["OracleQueryTemplate"]
                    Query = MysqlQueryTemplate
                elif QueryType == "WriteQuery":
                    WrittenQuery = properties["WrittenQuery"]
                    Query = WrittenQuery
                
                # Query = Query.lower()
                query_response = self.oraclequery(data,Query)
                if query_response["status"]:
                    json_response={
                        'name':title,
                        'status':'pass',
                        'node_id':mqdata["id"],
                        'type':DatabaseType,
                        'response': query_response["response"],
                        'source_result':str(query_response["output"]),      
                        'index':mqdata["index"],             
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response)
                    return {'status':True,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':DatabaseType,'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }
                else:
                    raise Exception("error")
        
            if DatabaseType == "mongo":
                print("came in mongo")
                
                ##get db data
                data = {'environment_id':mqdata['environment_id'],'source_id':properties["MongoSourceId"]}
                data = self.get_db_data(data)
                # MongoDatabase = properties["MongoDatabase"]
                # MongoSourceId = properties["MongoSourceId"]
                # source_response = requests.get(Dbregistration+OracleSourceId).json()
                if QueryType == "QueryTemplate":
                    MysqlQueryTemplate = properties["OracleQueryTemplate"]
                    Query = MysqlQueryTemplate
                elif QueryType == "WriteQuery":
                    WrittenQuery = properties["WrittenQuery"]
                    Query = WrittenQuery

                query_response = self.mongoquery(data, Query)
                if query_response["status"]:
                    json_response = {
                        'name': title,
                        'status':'pass',
                        'node_id': mqdata["id"],
                        'type': DatabaseType,
                        'response': query_response["response"],
                        'source_result': str(query_response["output"]),
                        'index': mqdata["index"],
                        'testcaseexecution': {
                            'id': mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(
                        url=flowsteps, json=json_response)
                    return {'status': True, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                            'type': DatabaseType, 'testcaseexecutionid': mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                            'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"]}
                else:
                    raise Exception("error")
            
            
            def cassandraquery(data,Query):
                
                try:
                    print("data -------------->",data)
                    print("keyspace", data["database"])
                    output = []
                    json_response = []
                    host = data["ip"]
                    if isinstance(host, str):
                        host = host.split(",")
                        print("After parse")
                    
                    clstr = None
                    auth_provider = PlainTextAuthProvider(username=data["username"], password=data["password"])
                    clstr = Cluster(contact_points=host, port=data["port"], auth_provider=auth_provider)
                    session = clstr.connect(data["database"])
                    #session.row_factory = ordered_dict_factory

                    print('Connected to Cassandra database')

                    print("Query==>", Query)

                    if "select" in Query.lower():
                        rows = session.execute(Query)

                        if rows:
                            for row in rows:
                                output.append(row)
                                print("Row=", row)   
                                                    
                            json_response = [dict((i, str(value).lower()) \
                                for i, value in enumerate(row)) for row in output]

                        else:   
                            raise Exception("There are no records")
                        
                        print("JSON===>", json_response)
                    elif "insert" in Query.lower():
                        session.execute(Query)
                        print("Inserted data")
                    else:
                        session.commit()

                    return {'status':True,'output':output,'response':json_response}

                except Exception as e:
                    print(e)
                    return {'status':False}
            
            if DatabaseType == "cassandra":
                print("database type --->", DatabaseType)
                print("data ---->", mqdata)
                ##get db data
                data = {'environment_id':mqdata['environment_id'],'source_id':properties["CassandraSourceId"]}
                data = self.get_db_data(data)
                print("get db data ---->", data)

                if QueryType == "QueryTemplate":
                    Query = properties["CassandraQueryTemplate"]
                    print("if Query", Query)
                elif QueryType == "WriteQuery":
                    Query = properties["WrittenQuery"]
                    print("else Query", Query)

                # Query = Query.lower()
                query_response = cassandraquery(data,Query)
                print("Query_response", data)
                print("After query_response", query_response)
                if query_response["status"]:
                    json_response={
                        'name':title,
                        'status':'pass',
                        'node_id':mqdata["id"],
                        'type':DatabaseType,
                        'response': query_response["response"],
                        'source_result':str(query_response["output"]),      
                        'index':mqdata["index"],             
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response)
                    return {'status':True,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':DatabaseType,'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }
                else:
                    json_response={
                        'name':title,
                        'status':'fail',
                        'node_id':mqdata["id"],
                        'type':DatabaseType,
                        'source_result':"Error",
                        'index':mqdata["index"],              
                        'testcaseexecution':{
                            'id':mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(url=flowsteps,json=json_response).json()
                    return {'status':False,'id':mqdata["id"],'testcaseid':mqdata["testcaseid"],
                        'type':DatabaseType,'testcaseexecutionid':mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid':mqdata["testsessionexecutionid"],'index':mqdata["index"] }

            def executeShellCommand(data, properties):
                try:
                    print("shell properties ---", properties)
                    print("shell data ---", data)

                    getkeyfile_host = "http://localhost:1337"
                    PEMFILEEXIST = False
                    print("pem file url", host)
                    # print("access url", graphql)
                    if 'pem_file_url' in properties:
                        if properties['pem_file_url']:
                            r = requests.get(host+properties['pem_file_url'], allow_redirects=True)
                            open('MY_AIT_KEY.pem', 'wb').write(r.content)
                            PEMFILEEXIST= True

                    k = None
                    port = 22
                    password = None
                    if PEMFILEEXIST:
                        k = paramiko.RSAKey.from_private_key_file("MY_AIT_KEY.pem")
                    if properties['SshPort']:
                        port = int(properties['SshPort'])
                    if properties['ServerPassword']:
                        password = properties['ServerPassword']
                    
                    c = paramiko.SSHClient()
                    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    # print()
                    
                    c.connect( hostname = properties['ServerIp'], port=port, username = properties['ServerUsername'], password=password, pkey = k )
                    print("connected")
                    output = {}
                    cmd = []
                    if properties['ShellCommand']:
                        cmd = properties['ShellCommand'].split(",")
                    commands = cmd
                    print("cmd---------->", cmd)
                    status = True
                    for command in commands:
                        print("Executing {}".format( command ))
                        stdin , stdout, stderr = c.exec_command(command)
                        # output
                        result = stdout.read()
                        result = str(result, 'utf-8')
                        print("results---->", result)
                        # error
                        error = stderr.read()
                        error = str(error, 'utf-8')
                        if error:
                            status = False
                            output[command] = {"result": result, "command": command, "error": error }
                        elif result:
                            status = True
                            output[command] = {"result": result, "command": command}
                        else:
                            status = False
                            output[command] = {"error": error, "command": command}
                    c.close()

                    print("output ---->", output)

                    return{'status': status, 'response': output}

                except Exception as e:
                    print("exception ----->", e)
                    return{'status': False}
            
            if DatabaseType == "shell":
                print("------inside shell executionnnnnn-----------")
                data = {'environment_id':mqdata['environment_id']}
                # data = self.get_db_data(data)
                # print("get db data ---->", data)

                shellResponse = executeShellCommand(data, properties)
                print("shell response --->", shellResponse)

                if shellResponse["status"]:
                    json_response = {
                        'name': title,
                        'status':'pass',
                        'node_id': mqdata["id"],
                        'type': "Shell Command",
                        'response': shellResponse["response"],
                        'index': mqdata["index"],
                        'testcaseexecution': {
                            'id': mqdata["testcaseexecutionid"]
                        }
                    }
                    print("json_response ------->", json_response)
                    print("--------url------", flowsteps)
                    dbresponse = requests.post(
                        url=flowsteps, json=json_response)
                    print("dbresponse ------>", dbresponse)   
                    return {'status': True, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                            'type': DatabaseType, 'testcaseexecutionid': mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                            'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"]}
                else:
                    raise Exception("error")


            if DatabaseType == "gmail_reader":
                print("came in email reader")
                print("email properties", properties)

                email_response = self.readEmails(properties)
                print("email response", email_response)
                if email_response['status']:
                    json_response = {
                        'name': title,
                        'status':'pass',
                        'node_id': mqdata["id"],
                        'type': "Shell Command",
                        'response': email_response["response"],
                        'index': mqdata["index"],
                        'testcaseexecution': {
                            'id': mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(
                        url=flowsteps, json=json_response)
                    print("dbresponse ------>", dbresponse)  
                    return {'status': True, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                            'type': DatabaseType, 'testcaseexecutionid': mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                            'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"]} 
                else:
                    raise Exception("error")

            if DatabaseType == "kafka":
                print("came in kafka")
                print("kafka type", properties)
                
                ##get db data
                data = {'environment_id':mqdata['environment_id'],'source_id':properties["KafkaSourceId"]}
                data = self.get_db_data(data)

                print("data from db", data)

                Type = properties["KafkaType"]
                if Type == "pub":
                    query_response = self.kafkapublisher(data, properties)
                elif Type == "sub":
                    query_response = self.kafkaconsumer(data, properties)
                print(query_response)
                print("--------------mqdata------------")
                print(mqdata)
                if query_response["status"]:
                    json_response = {
                        'name': title,
                        'status':'pass',
                        'node_id': mqdata["id"],
                        'type': "kafka "+Type,
                        'response': query_response["response"],
                        'index': mqdata["index"],
                        'testcaseexecution': {
                            'id': mqdata["testcaseexecutionid"]
                        }
                    }
                    print("json_response ------->", json_response)
                    print("--------url------", flowsteps)
                    dbresponse = requests.post(
                        url=flowsteps, json=json_response)
                    print("dbresponse ------>", dbresponse)   
                    return {'status': True, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                            'type': DatabaseType, 'testcaseexecutionid': mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                            'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"]}
                else:
                    raise Exception("error")
                


            if DatabaseType == "rabbitmq":
                print("came in rabbitmq")
                
                ##get db data
                data = {'environment_id':mqdata['environment_id'],'source_id':properties["RabbitmqSourceId"]}
                data = self.get_db_data(data)

                print("data from db",data)

                # RabbitmqQueueName = properties["RabbitmqQueueName"]
                # RabbitmqSourceId = properties["RabbitmqSourceId"]
                Type = properties["RabbitmqType"]
                if Type == "pub":
                    query_response = self.rabbitmqpub(data,properties)
                elif Type == "Subscribe":
                    query_response = self.rabbitmqsub(data,properties)
                print(query_response)
                if query_response["status"]:
                    json_response = {
                        'name': title,
                        'status':'pass',
                        'node_id': mqdata["id"],
                        'type': "Rabbitmq "+Type,
                        'response': query_response["response"],
                        'index': mqdata["index"],
                        'testcaseexecution': {
                            'id': mqdata["testcaseexecutionid"]
                        }
                    }
                    dbresponse = requests.post(
                        url=flowsteps, json=json_response)
                    return {'status': True, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                            'type': DatabaseType, 'testcaseexecutionid': mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                            'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"]}
                else:
                    raise Exception("error")
        
        except Exception as identifier:
            print(identifier)
            try:
                json_response = {
                    'name': title,
                    'status':'fail',
                    'node_id': mqdata["id"],
                    'type': DatabaseType,
                    'source_result': "Error",
                    'index': mqdata["index"],
                    'testcaseexecution': {
                        'id': mqdata["testcaseexecutionid"]
                    }
                }
                dbresponse = requests.post(url=flowsteps, json=json_response).json()
                return {'status': False, 'id': mqdata["id"], 'testcaseid': mqdata["testcaseid"],
                        'type': DatabaseType, 'testcaseexecutionid': mqdata["testcaseexecutionid"],'environment_id':mqdata['environment_id'],'browser':mqdata['browser'],
                        'testsessionexecutionid': mqdata["testsessionexecutionid"], 'index': mqdata["index"]}
            except Exception as e:
                return {'status': False}

    def kafkapublisher(self, data, properties):
        print("inside publisher")
        try:
            from kafka import KafkaProducer
            print("publisher property ---->", properties)
            host = data['ip']+":"+data['port']
            topic_name = properties['KafkaTopicName']
            producer = KafkaProducer(bootstrap_servers=host)
            producer.send(topic_name, bytes(str(properties["AceEditorValue"]), 'utf-8'))
            producer.flush()
            return {'status':True,'response':{"status": f"Published to {topic_name}"}}
        except Exception as identifier:
            print("error--->", identifier)
            return {'status': False}

    def kafkaconsumer(self, data, properties):

        try:
            print("propertirs ---->", properties)
            max_timeout = properties['KafkaWaitingTime']
            topic_name = properties['KafkaTopicName']
            host = data['ip']+":"+data['port']

            poll_intervel = properties['PollingInterval']
            counter = max_timeout*60/poll_intervel
            found = False
            previous_offset = properties['offsetValue']
            expected_incr = properties['ExpectedIncrement']
            cond = "GE"

            # --connect to kafka
            print("get new msg for consumer -------->")
            from confluent_kafka import Consumer, KafkaError
            settings = {
                'bootstrap.servers': host,
                'group.id': 'mygroup',
                'client.id': 'client-1',
                'enable.auto.commit': True,
                'session.timeout.ms': 6000,
                'default.topic.config': {'auto.offset.reset': 'smallest'}
            }
            c = Consumer(settings)
            c.subscribe([topic_name])
            print("counter --value", counter)
            cur_offset = 0

            while(counter > 0 and found == False ):
                msg = c.poll(properties['PollingInterval'])
                if msg is None:
                    print("--- no msg ----")
                elif not msg.error():
                    print("message from kafka --->", msg.value().decode("utf-8"))
                    cur_offset = msg.offset()+1
                
                print("current offset", cur_offset)

                if cond == "GE":
                    if cur_offset >= previous_offset + expected_incr : 
                        found = True
                else:
                    if cur_offset == previous_offset :
                        found = True
                counter = counter - 1

            if found == False:
                return {'status':False,'response':{"status":f"Consume from {topic_name}", "message": "" }}
            else:    
                return {'status':True,'response':{"status":f"Consume from {topic_name}", "message": f"found {expected_incr} new messages" }}
                
        except Exception as identifier:
            print("--------error>", identifier)
            return {'status': False}     

    def readEmails(self, properties):
        try:
            print("emails ----->", properties)
            max_timeout = properties['emailWaitingTime']
            poll_intervel = properties['PollingInterval']

            counter = max_timeout*60/poll_intervel
            last_email_count = properties['last_email_count']
            expected_incr = properties['ExpectedIncrement']


            # get email account details
            # details = requests.get(host+"/dbregistrations/"+str(properties['SelectedEmailId']), allow_redirects=True)
            # print("data---->", details.content)
            found = False
            imap_ssl_host = 'imap.gmail.com'
            imap_ssl_port = 993
            username = properties['email']
            password = properties['password']
            server = imaplib.IMAP4_SSL(imap_ssl_host, imap_ssl_port)

            server.login(username, password)

            server.select('INBOX')

            current_email_count = 0
            output = {}
            while(counter > 0 and found == False):
                status, data = server.search(None, 'UNSEEN')
                unseen_messages = data[0].split()
                print("unseen emails ----->", unseen_messages)

                # current_email_count = last_email_count + expected_incr
                if(len(unseen_messages) >= last_email_count + expected_incr):
                    expected_msg = unseen_messages[-expected_incr:]
                    print("msgssss ------->", expected_msg)
                    for num in expected_msg:
                        print("msg --->", num)
                        status, data = server.fetch(num, '(RFC822)')
                        email_msg = data[0][1]
                        raw_email_string = email_msg.decode('utf-8')
                        email_message = email.message_from_string(raw_email_string)

                        print("------------------email body-------------")
                        email_body = ""
                        for part in email_message.walk():
                            if part.get_content_type() == 'text/plain':
                                email_body = part.get_payload()
                        
                        output[num.decode("utf-8") ] = {"From": email_message['From'], "Subject": email_message['Subject'], "body": email_body}

                    found = True

                counter = counter - 1
                

            if found == False:
                return {'status':False,'response': ""}
            else:    
                return {'status':True,'response': output}
        except Exception as identifier:
            print(identifier)
            return {'status': False}  

    def rabbitmqpub(self, data,properties):

        try:
            print(properties)
            queue_name = properties["RabbitmqQueueName"]

            credentials = pika.PlainCredentials(data["username"], data["password"])
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=data["ip"],port=data["port"],
                                        credentials=credentials))
            channel = connection.channel()

            channel.queue_declare(queue=queue_name)

            channel.basic_publish(exchange='', routing_key=queue_name, body=str(properties["rmqData"]))

            channel.close()

            connection.close()

            return {'status':True,'response':f"Published to {queue_name}"}
            
        except Exception as identifier:
            print(identifier)
            return {'status':False}
    
    def rabbitmqsub(self, data,properties):

        try:
            queue_name = properties["RabbitmqQueueName"]

            credentials = pika.PlainCredentials(data["username"], data["password"])
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=data["ip"],port=data["port"],
                                        credentials=credentials))
            channel = connection.channel()

            channel.queue_declare(queue=queue_name)

            channel.basic_publish(exchange='', routing_key=queue_name, body=str(properties["AceEditorValue"]))

            channel.close()

            connection.close()
            
            return {'status':True,'response':"Published to {queue_name}"}
            
        except Exception as identifier:
            return {'status':False}
            
    def mysqlquery(self,data,Query):
        
        try:
            print("data -------------->",data)
            output = []
            json_response = []
            conn = mysql.connector.connect(host=data["ip"],port=data["port"],
                                        database=data["database"],
                                        user=data["username"],
                                        password=data["password"])
            if conn.is_connected():
                print('Connected to MySQL database')
                cursor = conn.cursor()

                cursor.execute(Query)
                print(Query)
                
                if "select" in Query.lower():

                    rows = cursor.fetchall()
                    if rows:
                        for row in rows:
                            output.append(row)
                            # print(row)   
                                                
                        json_response = [dict((str(cursor.description[i][0]).lower(), str(value).lower()) \
                                for i, value in enumerate(row)) for row in output]
                    else:
                        raise Exception("There are no records")
                    # print(json_response)
                    
                elif "insert" in Query.lower():
                    print(cursor.rowcount)
                    conn.commit()
                else:
                    conn.commit()
                
                cursor.close()
                conn.close()
                return {'status':True,'output':output,'response':json_response}
                    
            else:
                return {'status':False}

        except Exception as e:
            print(e)
            return {'status':False}
    
    def oraclequery(self,data,Query):

        try:
            output = []
            json_response = []
            dsn = cx_Oracle.makedsn(data["ip"], data["port"], service_name=data["database"])
            conn = cx_Oracle.connect(dsn=dsn, user=data["username"], password=data["password"])
            print('Connected to Oracle database')
            cursor = conn.cursor()
            
            print(Query)
            cursor.execute(Query)

            if "select" in Query.lower():
                # print("\n\nGetting Data")
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        output.append(row)
                    
                    json_response = [dict((str(cursor.description[i][0]).lower(), str(value).lower()) \
                        for i, value in enumerate(row)) for row in output]
                else:
                    raise Exception("There are no records")
                
                # print(json_response)
            elif "insert" in Query.lower():
                print(cursor.rowcount)
                conn.commit()
            else:
                conn.commit()

            cursor.close()
            conn.close()
            return {'status':True,'output':output,'response':json_response}

        except Exception as e:
            print(e)
            cursor.close()
            conn.close()
            return {'status':False}

    def mongoquery(self,data,Query):

        try:
            output = []
            json_response = []
            client = MongoClient(data["ip"], data["port"])
            db = client[data["database"]]
            db.authenticate(data["username"],data["password"])
            print('Connected to Mongo database')

            if "find" in Query.lower():
                # print("\n\nGetting Data")
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        output.append(row)
                    
                    json_response = [dict((str(cursor.description[i][0]).lower(), str(value).lower()) \
                        for i, value in enumerate(row)) for row in output]
                else:
                    raise Exception("There are no records")
                
                # print(json_response)
            elif "insert" in Query.lower():
                print(cursor.rowcount)
                conn.commit()
            else:
                conn.commit()

            cursor.close()
            conn.close()
            return {'status':True,'output':output,'response':json_response}

        except Exception as e:
            print(e)
            cursor.close()
            conn.close()
            return {'status':False}
    
    def getparentdata(self, mqdata, parent, FromNode=False):
        if FromNode:
            responsepayload = {
                'query': "query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{name:\"NAME\"}){ response request }}}"}
            responsepayload['query'] = responsepayload['query'].replace(
                "NAME", parent)
            responsepayload['query'] = responsepayload['query'].replace(
                "ID", mqdata["testcaseexecutionid"])
            print(responsepayload)
            response = requests.post(url=graphql, data=responsepayload).json()
            # print(response)
            parent_response_node = response["data"]["testcaseexecutions"][0]["flowsteps"]
        else:
            responsepayload = {
                'query': "query{  testcaseexecutions(where:{id:\"ID\"}){  flowsteps(where:{node_id:\"NODEID\", index: IND}){ response request }}}"}
            responsepayload['query'] = responsepayload['query'].replace(
                "IND", str(mqdata["index"]))
            responsepayload['query'] = responsepayload['query'].replace(
                "NODEID", parent)
            responsepayload['query'] = responsepayload['query'].replace(
                "ID", mqdata["testcaseexecutionid"])
            # print(responsepayload)
            response = requests.post(url=graphql, data=responsepayload).json()
            # print(response)
            parent_response_node = response["data"]["testcaseexecutions"][0]["flowsteps"]
        
        output = parent_response_node[0]
        return output
    
        
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
        self._source_executor = Source_Executor()

    # Not necessarily a method.
    def callback_func(self, channel, method, properties, body):
        
        # print("{} received '{}'".format(self.name, body))
        data = json.loads(body)
        print("source Data --> ")
        print(data)

        node_response = self._source_executor.testsource(data)
        self.sendresponse(node_response)
        # print(response)    

    def run(self):
        credentials = pika.PlainCredentials("guest", "guest")

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host,port=self._port,
                                      credentials=credentials))

        channel = connection.channel()

        channel.queue_declare(queue='source_executor')

        channel.basic_consume(queue='source_executor',
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

        channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(data))

        channel.close()

if __name__ == "__main__":

    RMQ_HOST = os.environ.get('RMQ_HOST') if os.environ.get('RMQ_HOST') else "localhost" 
    RMQ_PORT = int(os.environ.get('RMQ_PORT')) if os.environ.get('RMQ_PORT') else 5672 
    host = os.environ.get('HOST') if os.environ.get('HOST') else "http://localhost:1337" 

    flow = host+"/flows/"
    flowsteps = host+"/flowsteps/"
    graphql = host+"/graphql"
    Dbregistration = host+"/Dbregistrations/"

    print(RMQ_HOST,RMQ_PORT)
    consumer = Consumer(host = RMQ_HOST,port = RMQ_PORT)
    consumer.run()
