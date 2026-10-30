# Renewed AI Tutor — Streamlit UI

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Create `.env` in this directory:

```env
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
MONGODB_URI=your_mongodb_connection_string
```

4. Start the app: `streamlit run ui.py`

The UI uses the existing LangChain tutor chain and MongoDB persistence. Use a consistent Student ID to reopen the same long-term learner profile. Do not share the ID if it is being used as a private identifier; add authentication before deploying to multiple users.
