"""No-Docker SQLite sandbox only. PostgreSQL and its permissions are verified in CI."""
import os
from .config import Settings
from .database import Database
from .main import create_app

database = Database('sqlite://')
database.prepare_sqlite_demo()
app = create_app(Settings(database_url='sqlite://',api_key=os.environ['API_KEY']), database)
