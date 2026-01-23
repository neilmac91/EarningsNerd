import sqlite3
import sys
import os

# Add backend to path so we can import app
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.database import engine
from sqlalchemy import inspect

try:
    inspector = inspect(engine)
    if not inspector.has_table("contact_submissions"):
        print("Table 'contact_submissions' DOES NOT EXIST.")
    else:
        print("Table 'contact_submissions' EXISTS.")
        columns = inspector.get_columns("contact_submissions")
        print("Columns:")
        for col in columns:
            print(f"- {col['name']} ({col['type']}) nullable={col['nullable']}")
except Exception as e:
    print(f"Error inspecting DB: {e}")
