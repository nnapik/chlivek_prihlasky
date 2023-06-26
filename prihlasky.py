from flask import Flask, redirect, request, session, url_for, render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from pymongo import MongoClient
from datetime import datetime
from enum import Enum
import json, secrets, os

app = Flask(__name__)

app.secret_key = secrets.token_hex(16)
app.config['DISCORD_CLIENT_ID'] = os.environ['DISCORD_CLIENT_ID']
app.config['DISCORD_CLIENT_SECRET'] = os.environ['DISCORD_CLIENT_SECRET']
app.config['DISCORD_REDIRECT_URI'] = os.environ['DISCORD_REDIRECT_URI']
discord = DiscordOAuth2Session(app)
discord_scope = ['identify', 'guilds']

# MongoDB connection settings
mongo_host = os.environ['MONGO_HOST']
mongo_port = os.environ['MONGO_PORT']
mongo_auth = os.environ['MONGO_AUTH_DB']
mongo_db = os.environ['MONGO_DB']
mongo_collection = os.environ['MONGO_COLLECTION']
mongo_username = os.environ['MONGO_USER']
mongo_password = os.environ['MONGO_PASS']

class Auth(Enum):
    No=0
    Approved=1
    Denied=2

def check_auth():
    if not discord.authorized:
        return Auth.No
    user = discord.fetch_user()
    collection = get_mongo_collection("GA")
    query={}
    query['user_id'] = user.id
    allowed_user = list(collection.find(query))

    if allowed_user is not None:
        return Auth.Approved
    return Auth.Denied

def get_mongo_collection(collection):
    # Fetch the messages from MongoDB
    client = MongoClient(
        host=mongo_host,
        port=int(mongo_port),
        username=mongo_username,
        password=mongo_password,
        authSource=mongo_auth,
        authMechanism='SCRAM-SHA-256'
    )
    db = client[mongo_db]
    return db[collection]

@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))

@app.route('/login')
def login():
    return discord.create_session(scope=discord_scope, prompt=False)

@app.route('/callback')
def callback():
    discord.callback()
    return redirect(url_for('list_channels'))

@app.route('/upload', methods=['POST'])
def add_conversation():
    # Get the uploaded JSON file
    file = request.get_data()
    # Read the JSON data from the file
    data = json.loads(file)

    # Insert the data into MongoDB
    collection = get_mongo_collection(mongo_collection)
    for message in data:
        message_id = message['id']
        collection.update_one(
            {'id': message_id},
            {'$set': message},
            upsert=True
        )
    return ('', 204)

@app.route('/prihlaska')
@requires_authorization
def display_conversation():
    match (check_auth()):
        case Auth.No:
            return redirect(url_for('login'))
        case Auth.Denied:
            return ("Auth Denied", 403)
    channel_id = request.args.get('channel_id')
    query = {}
    query['channel_id'] = int(channel_id)
    # Fetch the messages from MongoDB
    collection = get_mongo_collection(mongo_collection)
    messages = list(collection.find(query))
    for message in messages:
        message['formatted_timestamp'] = datetime.fromisoformat(message['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        message['lines'] = message['message'].split('\n')

    # Render the conversation template and pass the messages as a variable
    return render_template('conversation.html', messages=messages)

@app.route('/', methods=['GET'])
@requires_authorization
def list_channels():
    match (check_auth()):
        case Auth.No:
            return redirect(url_for('login'))
        case Auth.Denied:
            return ("Auth Denied", 403)
    # Fetch the distinct channel_ids from MongoDB
    collection = get_mongo_collection(mongo_collection)
    channel_info = collection.aggregate([
        {
            '$group': {
                '_id': {'channel_id': '$channel_id', 'channel': '$channel'}
            }
        },
        {
            '$sort': {
                '_id.channel': 1
            }
        }
    ])

    return render_template('channel_list.html', channel_info=channel_info)


if __name__ == '__main__':
    app.run()

