import sqlite3

DATABASE = 'lan_monitoring.db'

def check_schema():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    
    # Get the list of tables from the SQLite master table
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    
    for table in tables:
        table_name = table[0]
        print(f"Table: {table_name}")
        
        # Get the schema of the current table using PRAGMA
        cur.execute(f"PRAGMA table_info('{table_name}')")
        columns = cur.fetchall()
        for col in columns:
            # Each 'col' is a tuple containing column information:
            # (cid, name, type, notnull, dflt_value, pk)
            print(f"   Column: {col[1]}, Type: {col[2]}, NotNull: {bool(col[3])}, Default: {col[4]}, PK: {bool(col[5])}")
        print()
    
    conn.close()

if __name__ == '__main__':
    check_schema()
