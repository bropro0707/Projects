# The Recommender 🎬

Wassup mate, give the answer of 5 simple questions and engine will recommend you the movies or tv shows that you will actually like. Not just any nut personalized for you.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Overview

**The Recommender** is a full-stack web application that helps users discover movies and TV shows based on their current mood and viewing preferences. Instead of endless scrolling, simply select how you want to feel—make me laugh, make me cry, keep me on edge—and get personalized recommendations powered by machine learning.

### Key Features

✨ **Mood-Based Discovery** – Choose from 7 different emotional states to get tailored recommendations  
🔍 **Smart Search** – Multi-field search with intelligent scoring across titles, genres, cast, and keywords  
❤️ **Favorites Management** – Save and track your favorite movies and shows  
⚙️ **Personalization** – Customize recommendations based on runtime, rating, and content preferences  
📊 **Advanced Filtering** – Filter by genres, runtime, rating, and content flags  
🎨 **Modern UI** – Beautiful, responsive design built with Bootstrap 5  
🚀 **RESTful API** – Clean API endpoints for easy integration

## Tech Stack

### Backend
- **Framework:** Flask with CORS support
- **Database:** MySQL with pooling
- **ML:** scikit-learn for recommendation scoring
- **Data Processing:** pandas
- **Environment:** python-dotenv for configuration

### Frontend
- **HTML5 / CSS3** with responsive design
- **JavaScript (Vanilla)** for interactivity
- **Bootstrap 5** for UI components
- **Bootstrap Icons** for visual elements

## Here is the structure

```
the-recommender/
├── client/                          # Frontend application
│   ├── index.html                  # Homepage with mood selector
│   ├── detail.html                 # Individual title details
│   ├── personalize.html            # Personalization/filtering page
│   ├── config.js                   # Frontend configuration
│   └── assets/
│       ├── css/
│       │   └── style.css           # Styling
│       └── js/
│           ├── app.js              # Main app logic
│           ├── index.js            # Homepage logic
│           ├── detail.js           # Detail page logic
│           └── personalize.js      # Personalization logic
│
└── server/                          # Backend application
    ├── run.py                       # Entry point
    ├── requirements.txt             # Python dependencies
    ├── .env.example                 # Environment variables template
    ├── app/
    │   ├── __init__.py             # App factory
    │   ├── db.py                   # Database connection pooling
    │   ├── routes.py               # API endpoints
    │   ├── search.py               # Search functionality & scoring
    │   └── personalize.py          # Mood-based recommendation logic
    └── scripts/
        ├── ingest.py               # Database population
        ├── build_recommendations.py # ML recommendation engine
        ├── backfill_details.py      # Content detail enrichment
        ├── backfill_content_flags.py # Content classification
        └── migrations/
            ├── 001_add_title_columns.sql
            └── 002_add_content_flags.sql
```

## Installation

### Prerequisites
- Python 3.8 or higher
- MySQL 5.7 or higher (or MariaDB)
- Node.js (optional, for frontend development)

### Backend Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/the-recommender.git
   cd the-recommender/server
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your MySQL credentials:
   ```env
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_password
   MYSQL_DATABASE=movie_recommender
   ```

5. **Initialize the database:**
   ```bash
   mysql -u root -p movie_recommender < app/migrations/001_add_title_columns.sql
   mysql -u root -p movie_recommender < app/migrations/002_add_content_flags.sql
   ```

6. **Populate the database:**
   ```bash
   python scripts/ingest.py
   python scripts/build_recommendations.py
   ```

7. **Run the server:**
   ```bash
   python run.py
   ```
   The API will be available at `http://localhost:5000`

### Frontend Setup

1. **Navigate to the client directory:**
   ```bash
   cd ../client
   ```

2. **Configure the API endpoint** in `config.js`:
   ```javascript
   const API_URL = 'http://localhost:5000/api';
   ```

3. **Serve the frontend:**
   - Using Python: `python -m http.server 8000`
   - Using Node.js: `npx http-server`
   - Open `http://localhost:8000` in your browser

## API Endpoints

### `/api/config` (GET)
Returns static configuration for the quiz (moods, runtime options, hard-no's).

**Response:**
```json
{
  "moods": {
    "laugh": {"label": "Make me laugh", "icon": "bi-emoji-laughing"},
    ...
  },
  "runtime_options": {...},
  "hard_no": [...]
}
```

### `/api/favorites` (GET)
Retrieve user's favorited titles.

### `/api/search?q={query}` (GET)
Search for titles by name, cast, or keywords with intelligent scoring.

### `/api/recommendations` (POST)
Get personalized recommendations based on mood and preferences.

**Request Body:**
```json
{
  "mood": "laugh",
  "runtime_min": 60,
  "runtime_max": 120,
  "genres": ["Comedy"],
  "hard_no": []
}
```

## Mood Categories

The recommendation engine supports 7 mood categories, each mapped to specific genres:

- 😂 **Laugh** – Comedy, Animation, Family
- 😢 **Cry** – Drama, Romance
- 😨 **Tense** – Thriller, Crime, Mystery, Horror
- 🧠 **Intellectual** – Documentary, History, Sci-Fi, Mystery, War & Politics
- 🤗 **Comforted** – Family, Animation, Romance, Fantasy, Comedy
- 💔 **Devastated** – Drama, Romance, War
- 🚀 **Escape** – Action, Adventure, Fantasy, Sci-Fi, Animation, Comedy

## Database Schema

The application uses a relational database with tables for:
- **titles** – Movies and TV shows metadata
- **genres** – Genre classifications
- **credits** – Cast and crew information
- **keywords** – Content tags and keywords
- **content_flags** – Content ratings and warnings
- **recommendations** – Pre-computed ML-based recommendations

See `server/app/migrations/` for the full schema.

## Development

### Adding New Moods
Edit `server/app/personalize.py` and add:
1. Mood key to `MOOD_LABELS`
2. Icon to `MOOD_ICONS`
3. Genre mapping to `MOOD_GENRES`

### Updating Search Scoring
Adjust weights in `server/app/search.py` under the `SEARCH_*` constants.

### Building ML Models
Run the recommendation builder:
```bash
python server/scripts/build_recommendations.py
```

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.


## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Styled with [Bootstrap 5](https://getbootstrap.com/)
- Icons from [Bootstrap Icons](https://icons.getbootstrap.com/)
- ML powered by [scikit-learn](https://scikit-learn.org/)

## Support

For questions, issues, or suggestions just message me mate

---

**Happy recommending! 🎬✨**
