import os
import sys
from app import app

# Ensure we're working from the correct directory
if __name__ == "__main__":
    # Add the project directory to sys.path to ensure imports work correctly
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    app.run(debug=True)