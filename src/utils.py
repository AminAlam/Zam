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

def set_state(conn, args):
    chat_id = args['chat_id']
    state = args['state']
    cursor = conn.cursor()
    # check if the chat_id already exists
    cursor.execute('select * from States where chat_id=?', (chat_id,))
    states = cursor.fetchall()

    if len(states)==0:
        # create a new state
        rows = [(chat_id, state, None)]
        cursor.executemany('insert into States values (?, ?, ?)', rows)
        conn.commit()

    else:
        # update the state
        cursor.execute('update States set state=? where chat_id=?', (state, chat_id))
        conn.commit()

def check_state(conn, args):
    chat_id = args['chat_id']
    cursor = conn.cursor()
    cursor.execute('select * from States where chat_id=?', (chat_id,))
    states = cursor.fetchall()

    if len(states)==0:
        return None
    else:
        return states[0][1]