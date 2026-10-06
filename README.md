# PKHosting: Domain Name Idea Generator


Source: ZR-26-00740 · Built for the TechAbout employee Growth task
"PKHosting: Domain Name Idea Generator".


A Streamlit app that turns keywords into domain name ideas:


- Enter keywords → get prefix/suffix combos (`gethost`, `cloudhub`),
  keyword mashups (`hostcloud`), optional hyphens and numbers
- Pick TLDs: `.com`, `.pk`, `.net`, `.io`, `.org`, `.co`, `.dev`, `.app`,
  `.tech`, `.store`, `.online`, `.site`
- Filter by name length; every idea tagged with how it was made
- Heuristic "taken-risk" labels (rough guesses from length/TLD/style —
  **not** availability checks)
- Best-effort DNS resolution check (clearly labeled): a resolving domain is
  very likely taken; a non-resolving domain may still be registered.
  Always confirm real availability with a domain registrar.
- Download results as CSV


## Run locally


```bash
cd pkhosting-domain-generator
pip install -r requirements.txt
streamlit run app.py
```


Then open the URL Streamlit prints (usually http://localhost:8501).


## Deploy on Streamlit Community Cloud


1. Push this folder to a GitHub repository.
2. Go to https://share.streamlit.io → **New app**.
3. Select the repo, branch, and `app.py` as the main file.
4. Click **Deploy**. No secrets or API keys are needed.


---
## Built for BlogReach
SEO outreach for this project via [BlogReach](https://blogreach.com) — the guest-posting marketplace.
---
