from django.apps import AppConfig
import requests
import logging

logger = logging.getLogger(__name__)

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    model_name = "gemma:2b"

    def ready(self):
        self.check_ollama_connection()

    def check_ollama_connection(self):
        try:
            # First, check if the Ollama server is running
            health_response = requests.get("http://localhost:11434", timeout=10)
            health_response.raise_for_status()  # Raise error for non-2xx status codes
            logger.info("Ollama server is running.")

            # Check for models available in Ollama
            response = requests.get("http://localhost:11434/api/tags", timeout=10)
            response.raise_for_status()
            
            # Get the list of available models
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            
            logger.info(f"Connected to Ollama. Available models: {model_names}")
            
            if self.model_name not in model_names:
                logger.warning(f"Model '{self.model_name}' not found in Ollama server!")
            else:
                logger.info(f"Model '{self.model_name}' is available on the server.")
        
        except requests.Timeout:
            logger.error("The request to Ollama server timed out. Please try again later.")
        except requests.RequestException as e:
            logger.error(f"Failed to connect to Ollama: {e}")
