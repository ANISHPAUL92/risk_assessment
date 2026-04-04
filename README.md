# 1. Enter the project directory
cd risk_assessment

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows

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

If you have real API keys configured, Companies House will be queried live. 

Without keys, only Cartoon Network Ltd returns a full demo profile — any other name returns null data and the LLM assesses using its own training knowledge only.


As you type a company name, a disambiguation dropdown appears showing up to 5 matching companies from Companies House (debounced at 400ms — waits until you stop typing before searching).
Select the correct match to pre-fill both the name and registration number, then click Assess Risk to run the full pipeline.


If no dropdown appears, either no matches were found or no Companies House key is configured — you can still proceed with whatever you've typed.


# 8. To run the Tests
cd risk_assessment
python python main  