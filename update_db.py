import os
import requests
import boto3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

tmpFile = 'prihlaska.tmp.json'

session = boto3.Session()
client = session.client('s3',
                        region_name=os.environ['SPACES_REGION'],
                        endpoint_url=os.environ['SPACES_URL'],
                        aws_access_key_id=os.environ['SPACES_KEY'],
                        aws_secret_access_key=os.environ['SPACES_SECRET'],
                        config=Config(s3={'addressing_style': 'virtual'}))

for obj in client.list_objects(Bucket=os.environ['SPACES_BUCKET'], Prefix=os.environ['SPACES_PREFIX'])['Contents']:
    fname = obj['Key']
    if not fname.endswith('.json'):
        continue
    print(fname)
    client.download_file(os.environ['SPACES_BUCKET'], fname, tmpFile)
    with open(tmpFile, 'rb') as f:
        data = f.read()
        response = requests.post(url=os.environ['PRIHLASKY_URL'] + '/upload',
                                 data=data,
                                 headers={
                                     'Content-Type': 'application/octet-stream',
                                     'token': os.environ['ADMIN_TOKEN']
                                     }
                                 )

        print(response)
