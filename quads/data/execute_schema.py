import sqlite3
import os
import argparse
import sys

def run_schema(schema_path, db_path, schema_arg, db_arg) -> bool:
    """Execute schema and return success status"""
    try:
        with open(schema_path, 'r') as f:
            schema = f.read()
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.executescript(schema)
            conn.commit()
            print(f"Schema {schema_arg} applied to {db_arg}")
            return True
        except sqlite3.Error as e:
            print(f"SQLite Error: {e}")
            return False
        finally:
            conn.close()
    except FileNotFoundError:
        print(f"Could not read schema file: {schema_path}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def validate_args(schema_arg, db_arg):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(script_dir, schema_arg)
    db_path = os.path.join(script_dir, db_arg)
    schema_exists = os.path.exists(schema_path)
    db_exists = os.path.exists(db_path)
    if schema_exists and db_exists:
        user_input = input(f"Press Y to run {schema_arg} on {db_arg}\n").upper()
        if user_input == "Y":
            success = run_schema(schema_path=schema_path, db_path=db_path, 
                               schema_arg=schema_arg, db_arg=db_arg)
            if success:
                print("Schema applied successfully!")
            else:
                print("Schema application failed.")
            retry_input = input("Would you like to try another schema? (Y/N): ").upper()
            if retry_input == "Y":
                get_new_schema_input()
            else:
                print("Exiting program.")
                sys.exit(0)
        else:
            print(f"Exiting program {os.path.basename(__file__)}.")
            sys.exit(0)
    else:
        if not schema_exists:
            print(f'Schema file not found; path: {schema_path}')
        if not db_exists:
            print(f'DB file not found; path: {db_path}')
        retry_input = input("Press R to enter another schema, or any other key to exit: ").upper()
        if retry_input == "R":
            get_new_schema_input()
        else:
            print("Exiting program.")
            sys.exit(0)

def get_new_schema_input():
    """Get new schema input from user"""
    try:
        schema_name = input("Enter schema filename: ").strip()
        db_name = input("Enter database filename (or press Enter for default 'poker.db'): ").strip()
        if not db_name:
            db_name = "poker.db"    
        validate_args(schema_name, db_name)
    except KeyboardInterrupt:
        print("\nExiting program.")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Apply SQL schema to SQLite database.")
    parser.add_argument("schema", help="Filename of schema")
    parser.add_argument("--db", default="poker.db", help="DB filename")
    args = parser.parse_args()
    validate_args(args.schema, args.db)

if __name__ == "__main__":
    main()