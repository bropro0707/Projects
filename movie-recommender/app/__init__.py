from flask import Flask
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # TODO: Initialize database connection
    # TODO: Register blueprints
    # TODO: Initialize ML models
    
    @app.route('/')
    def index():
        return 'Movie Recommender API - Under Construction'
    
    return app