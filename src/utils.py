import json 

def read_credentials(creds_file):
    with open(creds_file) as f:
        creds = json.load(f)
    return creds