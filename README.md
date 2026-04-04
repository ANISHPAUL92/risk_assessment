# 1. Enter the project directory
cd risk_assessment

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY (see API Keys section below)

# 5. Start the server
python main.py

# 6. Open the UI
open http://localhost:8000

# 7. To run the Tests
cd risk_assessment
python python main  