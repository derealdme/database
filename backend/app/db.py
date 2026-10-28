import os
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient

@contextmanager
def sql():
    with psycopg.connect(os.getenv('DATABASE_URL','postgresql://quant:quant@localhost:5432/quant'),row_factory=dict_row,prepare_threshold=None) as conn:
        yield conn

_client = None
def mongo():
    global _client
    if _client is None:
        _client=MongoClient(os.getenv('MONGO_URL','mongodb://localhost:27017'),serverSelectionTimeoutMS=3000)
    return _client['quant']

def init_mongo():
    db=mongo()
    if 'news' not in db.list_collection_names():
        db.create_collection('news',validator={'$jsonSchema':{'bsonType':'object','required':['ticker','title','date','sentiment'],'properties':{'ticker':{'bsonType':'string'},'title':{'bsonType':'string'},'date':{'bsonType':'date'},'sentiment':{'bsonType':'double','minimum':-1,'maximum':1}}}})
    db.news.create_index([('ticker',1),('date',-1)])
    db.news.create_index([('date',-1)])
    db.notes.create_index([('ticker',1),('updated_at',-1)])
