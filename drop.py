import sqlite3

DATABASE = 'lan_monitoring.db'

def drop_all_tables():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    
    # Retrieve the list of all user-defined tables in the database
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    
    for table in tables:
        table_name = table[0]
        # Skip SQLite's internal tables (e.g., sqlite_sequence)
        if table_name.startswith('sqlite_'):
            print(f"Skipping internal table: {table_name}")
            continue
        print(f"Dropping table: {table_name}")
        cur.execute(f"DROP TABLE IF EXISTS '{table_name}'")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    drop_all_tables()
