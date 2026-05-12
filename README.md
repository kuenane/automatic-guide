# UK 49s Lottery Results & Prediction Analyzer

A web application for fetching UK 49s lottery results and running predictive analysis on draw outcomes.

## Features

- Fetch recent results from multiple UK 49s draw types (Brunchtime, Lunchtime, Drivetime, Teatime)
- Run advanced number prediction analysis based on mathematical combinations
- Web-based interface with real-time status
- RESTful API for integration

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Run the application:
   ```bash
   python app.py
   ```

   Open http://localhost:5000 in your browser.

## Configuration

Use environment variables:
- `DEBUG`: Enable debug mode (default: False)
- `PORT`: Server port (default: 5000)
- `CACHE_TYPE`: Caching backend (default: SimpleCache)
- `CACHE_DEFAULT_TIMEOUT`: Cache timeout in seconds (default: 300)

## Docker

Build and run with Docker:
```bash
docker build -t uk49s-app .
docker run -p 5000:5000 uk49s-app
```

## API Endpoints

- `GET /api/health`: Health check
- `GET /api/results?draw=all|lunch&num=10`: Fetch results
- `POST /api/analyse`: Run analysis on numbers

## Testing

Run tests:
```bash
pytest
```

## Analysis Algorithm

The prediction system generates candidate sets based on:
- Concatenation and addition combinations (S1)
- Neighbour shifts (S2)
- Date-based neighbourhoods (S3)
- TSE digit extraction (S4)
- x1-x3 combinations (S5)

Groups numbers by colour and ending digit for pattern analysis.
