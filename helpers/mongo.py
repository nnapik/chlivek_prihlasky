import os
from pymongo import MongoClient

mongo_host = os.environ['MONGO_HOST']
mongo_port = os.environ['MONGO_PORT']
mongo_auth = os.environ['MONGO_AUTH_DB']
mongo_db = os.environ['MONGO_DB']
mongo_collection = os.environ['MONGO_COLLECTION']
mongo_username = os.environ['MONGO_USER']
mongo_password = os.environ['MONGO_PASS']

def get_mongo_client():
    return MongoClient(
        host=mongo_host,
        port=int(mongo_port),
        username=mongo_username,
        password=mongo_password,
        authSource=mongo_auth,
        authMechanism='SCRAM-SHA-256'
    )

def get_mongo_collection(collection):
    # Fetch the messages from MongoDB
    db = get_mongo_client()[mongo_db]
    return db[collection]
