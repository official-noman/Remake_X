import requests
from typing import Dict, Union
from requests.exceptions import RequestException

def chat_with_ollama(prompt: str, timeout: int = 30) -> Union[str, Dict]:
    """
    Get response from Gemma3 model via Ollama's API
    
    Args:
        prompt (str): The input prompt to send to the model
        timeout (int): Timeout in seconds for the API request (default: 30)
        
    Returns:
        Union[str, Dict]: The model's response or error message. Returns raw JSON if response parsing fails.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "gemma3",  # Using gemma3 instead of gemma:3b
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 150
        }
    }
    
    try:
        # First verify Ollama is running
        health_check = requests.get("http://localhost:11434", timeout=5)
        if health_check.status_code != 200:
            return "Ollama server not responding. Please start it with 'ollama serve'"

        # Make the API request
        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )

        # Handle different status codes
        if response.status_code == 200:
            try:
                return response.json().get("response", "No response content")
            except ValueError:
                return {"error": "Invalid JSON response", "raw_response": response.text}
        
        elif response.status_code == 404:
            return "Model 'gemma3' not found. Try running: 'ollama pull gemma3'"
        
        elif response.status_code == 400:
            return f"Bad request: {response.text}"
        
        else:
            return {
                "error": f"API request failed",
                "status_code": response.status_code,
                "response": response.text
            }

    except requests.exceptions.Timeout:
        return f"Error: Request timed out after {timeout} seconds"
    
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to Ollama server. Make sure it's running."
    
    except RequestException as e:
        return f"Network error: {str(e)}"
    
    except Exception as e:
        return f"Unexpected error: {str(e)}"