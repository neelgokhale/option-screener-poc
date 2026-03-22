"""Local development entry point.

Run with: uv run main.py
Or use: uvicorn app.server:app --reload
"""

import uvicorn


def main() -> None:
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
