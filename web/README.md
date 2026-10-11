# BharatSearch Web

Static frontend for the BharatSearch API.

Serve the repository root with `python -m http.server 8080`, open `http://localhost:8080/web/`, then use the ⚙ settings button to set the API URL to `http://127.0.0.1:8000`.

The UI intentionally does not pretend to have global search results: results are returned only from the project's own crawled index.
