from flask import Flask
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    CORS(app)

    from .routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Optionally serve the client/ folder too, so a single host can run everything.
    # The client works standalone against the API, so this is purely a convenience.
    client_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'client',
    )
    if os.path.isdir(client_dir):
        from flask import send_from_directory

        @app.route('/', defaults={'path': 'index.html'})
        @app.route('/<path:path>')
        def serve_client(path):
            full = os.path.join(client_dir, path)
            if os.path.isfile(full):
                return send_from_directory(client_dir, path)
            return send_from_directory(client_dir, 'index.html')

    return app