from flask import Flask, redirect, request, url_for, render_template, session, flash
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from flask_session import Session
from datetime import datetime
from posthog import Posthog
from enum import Enum
from dotenv import load_dotenv
import json
import os
import markdown
import requests

from helpers.mongo import get_mongo_client, get_mongo_collection
mongo_db = os.environ['MONGO_DB']
mongo_collection = os.environ['MONGO_COLLECTION']


app = Flask(__name__)
load_dotenv()
app.secret_key = os.environ['SHARED_SUPER_SECRET_KEY']
app.config['DISCORD_CLIENT_ID'] = os.environ['DISCORD_CLIENT_ID']
app.config['DISCORD_CLIENT_SECRET'] = os.environ['DISCORD_CLIENT_SECRET']
app.config['DISCORD_REDIRECT_URI'] = os.environ['DISCORD_REDIRECT_URI']
discord = DiscordOAuth2Session(app)
discord_scope = ['identify', 'guilds']
posthog = Posthog(os.environ['POSTHOG_TOKEN'], host=os.environ['POSTHOG_URL'])

# MongoDB connection settings
admin_token = os.environ['ADMIN_TOKEN']

# Configure MongoDB for session storage
app.config["SESSION_TYPE"] = "mongodb"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True  # Sign the session ID cookie to prevent tampering


# Set up the MongoDB client and session store
client = get_mongo_client()
app.config["SESSION_MONGODB"] = client
app.config["SESSION_MONGODB_DB"] = mongo_db  # Database name
app.config["SESSION_MONGODB_COLLECT"] = "sessions"  # Collection name

# Initialize the session extension
Session(app)

class Auth(Enum):
    No=0
    Approved=1
    Denied=2


def check_auth():
    if not discord.authorized or 'oauth_token' not in session:
        posthog.capture(0, 'check_auth', {'Auth':'No'})
        return redirect(url_for("login"))
    user = discord.fetch_user()
    collection = get_mongo_collection("GA")
    query={}
    query['user_id'] = user.id
    allowed_user = list(collection.find(query))

    if allowed_user is not None:
        posthog.capture(user.id, 'check_auth', {'Auth':'Approved'})
        return Auth.Approved
    posthog.capture(user.id, 'check_auth', {'Auth':'Denied'})
    return Auth.Denied


@app.errorhandler(Unauthorized)
def redirect_unauthorized(_):
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
    token = request.headers.get('token')
    if token != admin_token:
        return ('', 401)

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
    user = discord.fetch_user()
    channel_id = request.args.get('channel_id')
    if (channel_id is None):
        return redirect(url_for('list_channels'))
    posthog.capture(user.id, 'prihlaska', {'channel_id':channel_id})
    query = {}
    query['channel_id'] = int(channel_id)
    # Fetch the messages from MongoDB
    collection = get_mongo_collection(mongo_collection)
    messages = list(collection.find(query))
    for message in messages:
        message['formatted_timestamp'] = datetime.fromisoformat(message['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        message['own'] = user.id == int(message['author_id'])
        message['lines'] = markdown.markdown(message['message']).split('\n')

    # Render the conversation template and pass the messages as a variable
    theme = session.get('theme', 'dark')
    return render_template('conversation.html', messages=messages, user_id=user.id, theme=theme)

@app.route('/toggle_theme')
def toggle_theme():
    if 'theme' not in session or session['theme'] == 'dark':
        session['theme'] = 'light'
    else:
        session['theme'] = 'dark'
    return redirect(request.referrer or url_for('list_channels'))

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

    theme = session.get('theme', 'dark')
    return render_template('channel_list.html', channel_info=channel_info, theme=theme)


if __name__ == '__main__':

    app.run()
