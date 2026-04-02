# Company Risk Assessment

A system that gathers and structures information about companies to risk-assess them as payment beneficiaries, built for Tunic Pay.

## Quick Start

```bash
# 1. Clone and enter the project
cd risk-assessment

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
# Optionally add COMPANIES_HOUSE_API_KEY and BRAVE_SEARCH_API_KEY
# (system works with mock data if those are absent)

# 4. Run the server
python main.py
# or: uvicorn main:app --reload --port 8000

# 5. Open the UI
open http://localhost:8000
```
