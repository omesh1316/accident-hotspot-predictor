# Deploying Roadwatch to Vercel

The Vercel version uses the static dashboard in `public/` and the Python serverless API in `api/index.py`. The original Streamlit app and Docker setup remain in place for local or container hosting.

## Deploy from GitHub

1. Push this repository to GitHub. Keep `data/Road.csv`, `models/accident_model.pkl`, and `models/feature_columns.pkl` in the repository; the Vercel function needs all three.
2. In Vercel, choose **Add New Project** and import the GitHub repository.
3. Leave the root directory set to the repository root. Vercel detects the Python function from `api/index.py` and serves the files in `public/` as static assets.
4. Deploy. No environment variables are required.

The dashboard calls the Python function for filtered chart data and predictions. Map tiles and chart/icon/font libraries load from public CDNs, so those browser resources require an internet connection.

## Local Vercel preview

Install the packages in `requirements.txt`, then install the Vercel CLI and run `vercel dev` from the repository root. Open the local URL printed by the CLI. The model files and CSV must be present in their repository paths.