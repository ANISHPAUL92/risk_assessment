# 1. Enter the project directory
cd risk_assessment

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux


# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
Add COMPANIES_HOUSE_API_KEY and BRAVE_SEARCH_API_KEY to the .env files

# 5. Start the server
python main.py

# 6. Open the UI
open http://localhost:8000

# 7. To assess a company
To assess a company, enter a company name or registration number and select a jurisdiction. 

If you have real API keys configured, Companies House will be queried live for company profile, directors, and filing history, and Brave Search will be queried live for adverse media coverage 

Without keys, only Cartoon Network Ltd returns a full demo profile — any other name returns null data and the LLM assesses using its own training knowledge only.



# 8. To run the Tests
cd risk_assessment
python -m pytest tests/ -v