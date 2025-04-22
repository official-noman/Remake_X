import subprocess
from typing import Optional

def get_gemma3_response(prompt: str) -> str:
    """
    Get response from Gemma 3 model using Ollama subprocess
    
    Args:
        prompt: The input prompt to send to the model
        
    Returns:
        str: The model's response or an error message
    """
    try:
        # Check if Ollama is installed and available
        subprocess.run(["ollama", "--version"], 
                      check=True,
                      capture_output=True)
        
        # Run the model with timeout
        result = subprocess.run(
            ["ollama", "run", "gemma3", prompt],  # Changed to gemma3
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout
            check=True  # Raises CalledProcessError for non-zero returns
        )
        
        # Clean up the output
        output = result.stdout.strip()
        if not output:
            return "No response from model"
        return output
        
    except subprocess.TimeoutExpired:
        return "Error: Model response timed out after 60 seconds"
    except subprocess.CalledProcessError as e:
        if "not found" in e.stderr.lower():
            return "Error: Gemma3 model not found. Try running: 'ollama pull gemma3'"
        return f"Error: {e.stderr.strip() or 'Failed to get response'}"
    except FileNotFoundError:
        return "Error: Ollama not found. Please install Ollama first."
    except Exception as e:
        return f"Unexpected error: {str(e)}"