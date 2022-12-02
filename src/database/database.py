import sys
sys.path.append('../')
from configs import *


class Database():
    def __init__(self) -> None:
        self.db_config = self.read_db_config()
        self.conn = self.create_connection()
        self.init_db()

    def create_connection(self):
        conn = None
        db_file = self.db_config['DB_NAME']
        try:
            conn = sqlite3.connect(db_file, check_same_thread=False)
            print('Connected to database using SQLite', sqlite3.version)
        except sqlite3.Error as e:
            print(e)
        return conn

    def init_db(self):
        print('Initilizing the databse ...')
        try:
            for table in self.db_config['TABLES_LIST']:
                self.create_table(table)
            print('- Initilized !')
        except sqlite3.Error as e:
            print(e)

    def create_table(self, create_table_sql):
        try:
            cursor = self.conn.cursor()
            cursor.execute(create_table_sql)
        except sqlite3.Error as e:
            print(e)

    def read_db_config(self):
        with open(db_conf_file) as f:
            db_config = json.load(f)
        return db_config
    
    def error_log(self, error):
        error_tet = str(error)
        cursor = self.conn.cursor()
        time_now = dt.datetime.now()
        rows = [(error_tet, time_now, None)]
        cursor.executemany('insert into Errors values (?, ?, ?)', rows)
        self.conn.commit()
        print(error)

    def tweet_log(self, args):
        try:
            tweet_id = args['tweet_id']
            tweet_text = args['tweet_text']
            user_name = args['user_name']
            status = args['status']
            admin = args['admin']
            time_now = dt.datetime.now()

            cursor = self.conn.cursor()
            time_now = dt.datetime.now()
            rows = [(tweet_id, tweet_text, user_name, status, time_now, admin, None)]
            cursor.executemany('insert into Tweets values (?, ?, ?, ?, ?, ?, ?)', rows)
            self.conn.commit()
        except Exception as e:
            self.error_log(e)

    def check_tweet_existence(self, tweet_id):
        cursor = self.conn.cursor()
        cursor.execute('select * from Tweets where tweet_id = ?', (tweet_id,))
        rows = cursor.fetchall()
        if len(rows) > 0 and rows[0][3] == 'Success':
            return True
        else:
            return False