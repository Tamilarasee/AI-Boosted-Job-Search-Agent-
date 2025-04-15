# AI-Powered Personalized Job Search Agent

This project is an AI-driven application designed to help users find relevant job opportunities based on their resume and preferences. It leverages Large Language Models (LLMs) and vector search to provide personalized job recommendations, analysis, and insights.

## Key Features

*   **Resume Analysis:** Extracts key skills and suggests relevant job titles from uploaded resumes.
*   **Personalized Job Search:** Fetches job listings from external APIs and filters them based on user criteria (roles, skills, location, preferences).
*   **Semantic Relevance Ranking:** Uses LLM-generated embeddings and Pinecone vector search to find jobs that semantically match the user's profile and optimized search queries.
*   **AI-Powered Analysis:** Provides job-fit scores, identifies skill gaps between the user's profile and job requirements, and offers tailored resume suggestions for top matches.
*   **Consolidated Skill Insights:** Aggregates common skill gaps across multiple job searches to highlight key development areas.
*   **Interactive Dashboard:** A Streamlit-based UI for user interaction, managing profiles, viewing job results, and insights.

## Tech Stack

*   **Backend:** Python, FastAPI (Asynchronous)
*   **Frontend:** Streamlit
*   **AI/ML:**
    *   OpenAI API (for LLM tasks like query generation, analysis, embeddings)
    *   Pinecone (Vector Database for semantic search)
*   **Database:** Supabase (PostgreSQL for user data, job details, search history)
*   **External Data:** RapidAPI (Example for initial job fetching)
*   **Containerization:** Docker

## Getting Started (Overview)

1.  **Prerequisites:** Python 3.8+, Docker, Supabase account, Pinecone account, OpenAI API Key, RapidAPI Key.
2.  **Configuration:** Set up environment variables (`.env`) with your API keys and database credentials.
3.  **Backend:** Run the FastAPI backend server (potentially using `uvicorn`).
4.  **Frontend:** Launch the Streamlit application (`streamlit run app/app.py`).


## Usage (Overview)

1.  Register/Login via the Streamlit interface.
2.  Upload your resume for analysis.
3.  Define job preferences (roles, skills, location, etc.). Voice input is also supported.
4.  Initiate a job search.
5.  Review matched jobs, AI analysis, and skill gap insights.
