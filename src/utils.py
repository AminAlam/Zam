import json 
from configs import *

from persiantools.jdatetime import JalaliDate

def read_credentials(creds_file):
    with open(creds_file) as f:
        creds = json.load(f)
    return creds

def covert_austria_time_to_iran_time(date):
    date = dt.datetime.strptime(date, '%Y-%m-%d %H:%M:%S') + dt.timedelta(hours=2, minutes=30)
    date = f"{JalaliDate(date).strftime('%Y/%m/%d')} {date.strftime('%H:%M:%S')}"
    return date