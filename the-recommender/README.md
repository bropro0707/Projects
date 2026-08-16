# The Recommender 🎬
Get stuck what to watch next,
Answer five quick questions about your mood and get movie or TV recommendations you'll actually want to watch — not just another "trending now" list.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)


## Overview

**The Recommender** a full-stack web app that helps you pick something to watch based on your answer. Choose how you want to feel — make me laugh, make me cry, keep me on edge — and get personalized picks from a Cinephile friend.

### Key Features

✨ **Mood-Based Discovery** – Choose from 7 emotional states to get tailored recommendations
🔍 **Smart Search** – Multi-field weighted scoring across titles, genres, cast, and keywords
❤️ **Favorites Management** – Save and track favorite movies and shows
⚙️ **Personalization** – Filter by runtime, hard-no content flags, and favorites
📊 **Advanced Filtering** – Filter by genres, runtime, rating, and content flags
🎨 **Modern UI** – Responsive design built with Bootstrap 5
🚀 **RESTful API** – Clean API endpoints for easy integration

## Tech Stack

### Backend
- **Framework:** Flask with CORS support
- **Database:** MySQL with connection pooling
- **ML:** scikit-learn for recommendation scoring
- **Data Processing:** pandas
- **Environment:** python-dotenv for configuration

### Frontend
- **HTML5 / CSS3** with responsive design
- **JavaScript (Vanilla)** for interactivity
- **Bootstrap 5** for UI components
- **Bootstrap Icons** for visual elements

## Screenshots

<img src="server/screenshots/Screenshot 2026-08-15 170818.png" alt="Homepage with search and latest releases" width="700"/>
<img src="server/screenshots/Screenshot 2026-08-15 170906.png" alt="Recommendation results" width="700"/>

## Project Structure here mate

```
the-recommender/
├── client/                          # Frontend application
│   ├── index.html                  # Home/browse page (no filtering)
│   ├── detail.html                 # Individual title details
│   ├── personalize.html            # Mood quiz page
│   ├── config.js                   # Frontend configuration
│   └── assets/
│       ├── css/
│       │   └── style.css           # Styling
│       └── js/
│           ├── app.js              # Main app logic
│           ├── index.js            # Home/browse page logic
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
        ├── schema.sql              # Base database schema
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
- A free [TMDB API key](https://www.themoviedb.org/settings/api)

### Backend Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bropro0707/projects/the-recommender.git
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
   Edit `.env` with your TMDB key and MySQL credentials:
   ```env
   TMDB_API_KEY=your_tmdb_api_key
   SECRET_KEY=generate_a_random_string_here
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_password
   MYSQL_DATABASE=movie_recommender
   ```

5. **Initialize the database:**
   ```bash
   mysql -u root -p movie_recommender < scripts/schema.sql
   mysql -u root -p movie_recommender < scripts/migrations/001_add_title_columns.sql
   mysql -u root -p movie_recommender < scripts/migrations/002_add_content_flags.sql
   ```
   `schema.sql` is the base schema (it already includes the `001`/`002` columns, so on
   a fresh install the two migrations are optional).

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

2. **Configure the API endpoint** in `config.js`. Leave it as-is if Flask is serving the client too (the default — Flask already has a route for this):
   ```javascript
   window.API_BASE = '';
   ```
   If you're hosting the frontend separately (e.g. GitHub Pages, Netlify), point it at your deployed backend instead:
   ```javascript
   window.API_BASE = 'https://your-server.example.com';
   ```

3. **Serve the frontend** (only needed if running it separately from Flask):
   - Using Python: `python -m http.server 8000`
   - Using Node.js: `npx http-server`
   - Open `http://localhost:8000` in your browser

## API Endpoints

### `/api/config` (GET)
Static config for the quiz (moods, runtime options, hard-no's).

### `/api/favorites` (GET)
Curated favorites for the quiz picker. Optional `?limit=` (default 24).

### `/api/titles` (GET)
Browse all titles, paginated. Pass `?q=` to search by title, cast, character, genre, or keyword with weighted relevance scoring.

**Query params:** `page` (default 1), `q` (optional)

### `/api/titles/{id}` (GET)
Full detail for one title, plus its 12 most similar titles (precomputed).

### `/api/personalize` (POST)
Runs the mood quiz and returns ranked results.

**Request Body:**
```json
{
  "media_type": "movie",
  "moods": ["laugh", "escape"],
  "runtime": "standard",
  "hard_no": ["horror", "subtitles"],
  "favorite_ids": "",
  "favorite_text": ""
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

See `server/scripts/schema.sql` (base schema) plus `server/scripts/migrations/` for the full schema.

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

- This product uses the TMDB API but is not endorsed or certified by TMDB.
- Built with [Flask](https://flask.palletsprojects.com/)
- Styled with [Bootstrap 5](https://getbootstrap.com/)
- Icons from [Bootstrap Icons](https://icons.getbootstrap.com/)
- ML powered by [scikit-learn](https://scikit-learn.org/)

## Support

For questions, issues, or suggestions, open an issue or reach out directly.

---

**Happy recommending! 🎬✨**