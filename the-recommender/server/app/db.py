import os
from mysql.connector import pooling

_config = None
_pool = None


def _load_config():
    global _config
    if _config is None:
        _config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DATABASE', 'movie_recommender'),
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
        }
    return _config


def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **_load_config())
    return _pool


def get_db():
    return get_pool().get_connection()