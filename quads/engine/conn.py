import os
import sqlite3


def get_conn():
    gread_grand_dir = (os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_file = os.path.join(gread_grand_dir, 'data/poker.db')
    conn = sqlite3.connect(db_file)
    return conn
    