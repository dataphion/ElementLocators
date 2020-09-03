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

host = "http://localhost:1337"
flow = host+"/flows/"
flowsteps = host+"/flowsteps/"
graphql = host+"/graphql"
Dbregistration = host+"/Dbregistrations/"
environment = host+"/environments/"

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
            print("mqdata----->", mqdata)
            response = requests.get(flow+str(mqdata["testcaseid"]))
            response = json.loads(response.content)
            graph_json=response["graph_json"]
            node_json = graph_json[mqdata["id"]]
            properties = node_json["properties"]
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
            


            # ----------- Previous working code ------------

            # from kafka.consumer import KafkaConsumer
            # from kafka import TopicPartition
            # from time import sleep
            # # print(properties)
            # host = data['ip']+":"+data['port']
            # topic_name = properties['KafkaTopicName']
            
            # # GET LAST OFFSET
            # consumer = KafkaConsumer(topic_name, bootstrap_servers=host)
            # partitions=  [TopicPartition(topic_name, p) for p in consumer.partitions_for_topic(topic_name)]
            # last_offset_per_partition = consumer.end_offsets(partitions)
            # str_partition = str(last_offset_per_partition)
            # offset_value = int(str_partition.split(":")[1].split("}")[0])

            # last_offset_value = offset_value
            # latest_offset_value = 0

            # # POLLING & WAITING TIME TO CONSUME MESSAGE
            # max_time = properties['KafkaWaitingTime'] * 60
            # t = datetime.datetime.now()
            # split_time= str(t).split(" ")
            # date_split = split_time[0].split("-")
            # time_split = split_time[1].split(":")
            # a = datetime.datetime(int(date_split[0]),int(date_split[1]),int(date_split[2]),int(time_split[0]),int(time_split[1]),int(float(time_split[2])))
            # waiting_time = a + datetime.timedelta(0,max_time) # days, seconds, then other fields.

            # received_msg = ""
            # maxi_time = a.time()

            # print("get new msg for consumer -------->")
            # from confluent_kafka import Consumer, KafkaError
            # settings = {
            #     'bootstrap.servers': host,
            #     'group.id': 'mygroup',
            #     'client.id': 'client-1',
            #     'enable.auto.commit': True,
            #     'session.timeout.ms': 6000,
            #     'default.topic.config': {'auto.offset.reset': 'smallest'}
            # }

            # c = Consumer(settings)
            # c.subscribe([topic_name])
            # message_received = False
            # while maxi_time < waiting_time.time():
            #     sleep(properties['PollingInterval'])
            #     tm = datetime.datetime.now()
            #     split_time1= str(tm).split(" ")
            #     date_split1 = split_time1[0].split("-")
            #     time_split1 = split_time1[1].split(":")
            #     a1 = datetime.datetime(int(date_split1[0]),int(date_split1[1]),int(date_split1[2]),int(time_split1[0]),int(time_split1[1]),int(float(time_split1[2])))
            #     maxi_time = a1.time()
            #     # print("maxi_time updated", maxi_time)
            #     msg = c.poll(properties['PollingInterval'])
            #     if msg is None:
            #         continue
            #     elif not msg.error():
            #         if msg.offset() == last_offset_value:
            #             latest_offset_value = msg.offset()
            #             print('Received message: {0}'.format(msg.value()))
            #             received_msg = msg.value().decode("utf-8")
            #             message_received = True
            #             # VALIDATE RESPONSE
            #             if properties['kafkaValidation'] == "response":
            #                 print("validate response", type(properties['ExpectedKafkaReponse']))
            #                 if received_msg.startswith("{"):
            #                     received_msg = json.loads(received_msg)
            #                 if type(received_msg) == type(properties['ExpectedKafkaReponse']):
            #                     for key in properties['ExpectedKafkaReponse'].keys(): 
            #                         if not key in received_msg:
            #                             print("validation failed")
            #                             message_received = False
            #                 else:
            #                     message_received = False
            #             else:
            #                 print("index validation")
            #                 if latest_offset_value == last_offset_value:
            #                     message_received = True
            #                 else:
            #                     message_received = False
            #             break
            #     elif msg.error().code() == KafkaError._PARTITION_EOF:
            #         if msg.offset() == last_offset_value:
            #             print('End of partition reached {0}/{1}'
            #                 .format(msg.topic(), msg.partition()))
            #             break
            #     else:
            #         if msg.offset() == last_offset_value:
            #             print('Error occured: {0}'.format(msg.error().str()))
            #             break
            
            # if message_received:
            #     return {'status':True,'response':{"status":f"Consume from {topic_name}", "message": received_msg }}
            # else:
            #     return {'status':False,'response':{"status":f"Consume from {topic_name}", "message": "" }}
                
        except Exception as identifier:
            print("--------error>", identifier)
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
        print("Data --> ")
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
