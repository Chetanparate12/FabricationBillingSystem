from app import app
import sys
import logging
import os

if __name__ == "__main__":
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Use production settings when deployed
        debug_mode = os.environ.get("ENVIRONMENT") != "production"
        port = int(os.environ.get("PORT", 5000))
        
        print("Billing app starting - authentication disabled.")
        app.run(host="0.0.0.0", port=port, debug=debug_mode)
    except Exception as e:
        logging.error(f"Failed to start application: {str(e)}")
        sys.exit(1)
