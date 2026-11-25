"""Focused integration exercises for databases and brokers in the OpsBridge domain."""
import json,os,uuid
from datetime import datetime,timezone
from typing import Any
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel,Field

app=FastAPI(title="OpsBridge Integration Lab",version="1.0.0")
class Record(BaseModel): key:str=Field(min_length=1,max_length=180); data:dict[str,Any]
def tenant_or_fail(value:str|None):
 if not value or len(value)>100:raise HTTPException(400,"A tenant context is required.")
 return value
def base_record(tenant:str,record:Record):return {"_id":f"{tenant}:{record.key}","tenantId":tenant,"key":record.key,"data":record.data,"updatedAt":datetime.now(timezone.utc).isoformat()}
@app.get('/health')
def health():return {"status":"ok","service":"integration-lab","profile":"educational-connectors"}

@app.post('/v1/adapters/mongodb/upsert')
def mongo_upsert(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  from pymongo import MongoClient
  client=MongoClient(os.getenv('MONGODB_URL','mongodb://localhost:27017/opsbridge'),serverSelectionTimeoutMS=2500);client.opsbridge.records.update_one({'_id':f'{tenant}:{record.key}'},{'$set':base_record(tenant,record)},upsert=True);return {'adapter':'mongodb','key':record.key,'stored':True}
 except Exception as exc:raise HTTPException(503,'MongoDB adapter unavailable or write failed.') from exc

@app.post('/v1/adapters/mysql/upsert')
def mysql_upsert(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  import pymysql
  url=os.getenv('MYSQL_URL','mysql+pymysql://opsbridge:opsbridge@localhost:3306/opsbridge').replace('mysql+pymysql://','');auth,hostdb=url.split('@',1);user,password=auth.split(':',1);hostdb,db=hostdb.rsplit('/',1);host,port=(hostdb.rsplit(':',1)+['3306'])[:2]
  connection=pymysql.connect(host=host,port=int(port),user=user,password=password,database=db,connect_timeout=3,autocommit=True)
  with connection.cursor() as cur:
   cur.execute('CREATE TABLE IF NOT EXISTS integration_records (tenant_id VARCHAR(100) NOT NULL, record_key VARCHAR(180) NOT NULL, payload JSON NOT NULL, updated_at VARCHAR(40) NOT NULL, PRIMARY KEY(tenant_id, record_key))')
   cur.execute('INSERT INTO integration_records(tenant_id,record_key,payload,updated_at) VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE payload=VALUES(payload),updated_at=VALUES(updated_at)',(tenant,record.key,json.dumps(record.data),datetime.now(timezone.utc).isoformat()))
  connection.close();return {'adapter':'mysql','key':record.key,'stored':True}
 except Exception as exc:raise HTTPException(503,'MySQL adapter unavailable or write failed.') from exc

@app.post('/v1/adapters/dynamodb/upsert')
def dynamodb_upsert(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  import boto3
  endpoint=os.getenv('DYNAMODB_ENDPOINT');client=boto3.client('dynamodb',region_name=os.getenv('AWS_REGION','ap-south-1'),endpoint_url=endpoint,aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID','local'),aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY','local'))
  table_name=os.getenv('DYNAMODB_TABLE','opsbridge-records');tables=client.list_tables().get('TableNames',[])
  if table_name not in tables:client.create_table(TableName=table_name,KeySchema=[{'AttributeName':'pk','KeyType':'HASH'}],AttributeDefinitions=[{'AttributeName':'pk','AttributeType':'S'}],BillingMode='PAY_PER_REQUEST');client.get_waiter('table_exists').wait(TableName=table_name)
  client.put_item(TableName=table_name,Item={'pk':{'S':f'{tenant}:{record.key}'},'tenantId':{'S':tenant},'data':{'S':json.dumps(record.data)},'updatedAt':{'S':datetime.now(timezone.utc).isoformat()}});return {'adapter':'dynamodb','key':record.key,'stored':True}
 except Exception as exc:raise HTTPException(503,'DynamoDB adapter unavailable or write failed.') from exc

@app.post('/v1/adapters/elasticsearch/upsert')
def elastic_upsert(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  from elasticsearch import Elasticsearch
  es=Elasticsearch(os.getenv('ELASTICSEARCH_URL','http://localhost:9200'));es.index(index='opsbridge-records',id=f'{tenant}:{record.key}',document=base_record(tenant,record));return {'adapter':'elasticsearch','key':record.key,'stored':True}
 except Exception as exc:raise HTTPException(503,'Elasticsearch adapter unavailable or write failed.') from exc

@app.post('/v1/adapters/{graph}/upsert')
def graph_upsert(graph:str,record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 if graph not in {'neo4j','memgraph'}:raise HTTPException(404,'Unknown graph adapter.')
 try:
  from neo4j import GraphDatabase
  uri=os.getenv('NEO4J_URI' if graph=='neo4j' else 'MEMGRAPH_URI',f'bolt://localhost:{7687 if graph=="neo4j" else 7688}');auth=(os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD','local-only-password')) if graph=='neo4j' else None
  driver=GraphDatabase.driver(uri,auth=auth);driver.execute_query('MERGE (r:OpsRecord {tenantId:$tenant, key:$key}) SET r.payload=$payload, r.updatedAt=$updatedAt',tenant=tenant,key=record.key,payload=json.dumps(record.data),updatedAt=datetime.now(timezone.utc).isoformat());driver.close();return {'adapter':graph,'key':record.key,'stored':True}
 except Exception as exc:raise HTTPException(503,f'{graph} adapter unavailable or write failed.') from exc

@app.post('/v1/adapters/oracle/upsert')
def oracle_upsert(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  import oracledb
  conn=oracledb.connect(user=os.getenv('ORACLE_USER','system'),password=os.getenv('ORACLE_PASSWORD','local-only-password'),dsn=os.getenv('ORACLE_DSN','localhost:1521/FREEPDB1'))
  with conn.cursor() as cur:
   try:cur.execute('CREATE TABLE OPSBRIDGE_RECORDS (TENANT_ID VARCHAR2(100), RECORD_KEY VARCHAR2(180), PAYLOAD CLOB, UPDATED_AT VARCHAR2(40), CONSTRAINT OPSBRIDGE_REC_PK PRIMARY KEY(TENANT_ID,RECORD_KEY))')
   except oracledb.DatabaseError:pass
   cur.execute('MERGE INTO OPSBRIDGE_RECORDS dst USING (SELECT :tenant tenant_id,:key record_key,:payload payload,:updated updated_at FROM dual) src ON (dst.TENANT_ID=src.tenant_id AND dst.RECORD_KEY=src.record_key) WHEN MATCHED THEN UPDATE SET dst.PAYLOAD=src.payload,dst.UPDATED_AT=src.updated_at WHEN NOT MATCHED THEN INSERT(TENANT_ID,RECORD_KEY,PAYLOAD,UPDATED_AT) VALUES(src.tenant_id,src.record_key,src.payload,src.updated_at)',tenant=tenant,key=record.key,payload=json.dumps(record.data),updated=datetime.now(timezone.utc).isoformat())
  conn.commit();conn.close();return {'adapter':'oracle','key':record.key,'stored':True}
 except Exception as exc:raise HTTPException(503,'Oracle adapter unavailable or write failed.') from exc

@app.post('/v1/adapters/redis/upsert')
def redis_upsert(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  import redis
  client=redis.Redis.from_url(os.getenv('REDIS_URL','redis://localhost:6379/2'),decode_responses=True,socket_connect_timeout=2);key=f'opsbridge:{tenant}:record:{record.key}';client.set(key,json.dumps(record.data),ex=86400);return {'adapter':'redis','key':record.key,'ttlSeconds':86400,'stored':True}
 except Exception as exc:raise HTTPException(503,'Redis adapter unavailable or write failed.') from exc

@app.post('/v1/adapters/kafka/publish')
def kafka_publish(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  from confluent_kafka import Producer
  p=Producer({'bootstrap.servers':os.getenv('KAFKA_BOOTSTRAP_SERVERS','localhost:9092'),'enable.idempotence':True,'acks':'all'});p.produce('opsbridge.lab.v1',key=f'{tenant}:{record.key}',value=json.dumps(base_record(tenant,record)));remaining=p.flush(10)
  if remaining:raise RuntimeError('Kafka delivery timed out')
  return {'adapter':'kafka','key':record.key,'published':True}
 except Exception as exc:raise HTTPException(503,'Kafka adapter unavailable or publish failed.') from exc

@app.post('/v1/adapters/rabbitmq/publish')
def rabbit_publish(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  import pika
  connection=pika.BlockingConnection(pika.URLParameters(os.getenv('RABBITMQ_URL','amqp://opsbridge:opsbridge@localhost:5672/')));channel=connection.channel();channel.queue_declare(queue='opsbridge.lab',durable=True);channel.confirm_delivery();channel.basic_publish(exchange='',routing_key='opsbridge.lab',body=json.dumps(base_record(tenant,record)),properties=pika.BasicProperties(content_type='application/json',delivery_mode=2,headers={'tenantId':tenant}));connection.close();return {'adapter':'rabbitmq','key':record.key,'published':True}
 except Exception as exc:raise HTTPException(503,'RabbitMQ adapter unavailable or publish failed.') from exc

@app.post('/v1/adapters/nats/publish')
async def nats_publish(record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 try:
  import nats
  client=await nats.connect(os.getenv('NATS_URL','nats://localhost:4222'));await client.publish('opsbridge.lab.v1',json.dumps(base_record(tenant,record)).encode());await client.flush(timeout=3);await client.close();return {'adapter':'nats','key':record.key,'published':True}
 except Exception as exc:raise HTTPException(503,'NATS adapter unavailable or publish failed.') from exc

@app.post('/v1/adapters/{service}/notify')
def aws_notify(service:str,record:Record,x_tenant_id:str|None=Header(default=None)):
 tenant=tenant_or_fail(x_tenant_id)
 if service not in {'sqs','sns'}:raise HTTPException(404,'Unknown notification adapter.')
 try:
  import boto3
  client=boto3.client(service,region_name=os.getenv('AWS_REGION','ap-south-1'),endpoint_url=os.getenv('AWS_ENDPOINT_URL') or None);body=json.dumps(base_record(tenant,record))
  if service=='sqs':
   queue=os.getenv('SQS_QUEUE_URL');
   if not queue:raise ValueError('SQS_QUEUE_URL is required.')
   result=client.send_message(QueueUrl=queue,MessageBody=body,MessageAttributes={'tenantId':{'DataType':'String','StringValue':tenant}});return {'adapter':'sqs','messageId':result['MessageId']}
  topic=os.getenv('SNS_TOPIC_ARN')
  if not topic:raise ValueError('SNS_TOPIC_ARN is required.')
  result=client.publish(TopicArn=topic,Message=body,MessageAttributes={'tenantId':{'DataType':'String','StringValue':tenant}});return {'adapter':'sns','messageId':result['MessageId']}
 except Exception as exc:raise HTTPException(503,f'{service.upper()} adapter unavailable or not configured.') from exc
