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

        # TiDB Cloud (and most managed MySQL hosts) require an encrypted
        # connection. Set MYSQL_SSL=true in production; local dev against
        # plain MySQL is untouched since this defaults to off.
        if os.getenv('MYSQL_SSL', 'false').lower() == 'true':
            import certifi
            # Uses a trusted public CA bundle by default. Only set
            # MYSQL_SSL_CA if your host gives you a specific cert file.
            _config['ssl_ca'] = os.getenv('MYSQL_SSL_CA', certifi.where())
            _config['ssl_verify_cert'] = True
        else:
            # Local MySQL needs this auth plugin; TiDB doesn't use it.
            _config['auth_plugin'] = 'mysql_native_password'
    return _config


def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **_load_config())
    return _pool


def get_db():
    return get_pool().get_connection()