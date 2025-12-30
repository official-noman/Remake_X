# Remake_X: AI-Powered Product Management & Upcycling Platform

**Remake_X** is a comprehensive full-stack web application built with the **Django** framework. The platform integrates traditional product management with a modern, sustainable "upcycling" workflow. A standout technical feature of this project is the integration of a local conversational AI chatbot powered by **Ollama**, enabling privacy-focused, offline Large Language Model (LLM) interactions.

## 🚀 Key Features

- **Local AI Chatbot Integration:** Implements the **Ollama API** to provide an intelligent assistant. Users can interact with models like Llama 3 or Mistral locally, ensuring data security and zero latency from external APIs.
- **Upcycling Module:** A dedicated workflow (via the `upcycle` app) focused on repurposing products and promoting sustainability.
- **Comprehensive Product Catalog:** Full CRUD functionality for managing products, including category organization and media handling.
- **Responsive Frontend:** Developed using Django Templates, CSS, and JavaScript to ensure a seamless user experience across devices.
- **Automated Asset Management:** Efficient handling of static files and user-uploaded product media.

## 🛠 Technical Stack

- **Backend:** Python 3.x, Django Framework  
- **AI Engine:** **Ollama** (Local LLM Integration)  
- **Database:** **SQLite3** (Default Django implementation for portable and efficient development)  
- **Frontend:** HTML5, CSS3, JavaScript  
- **Communication:** Python `requests` for Ollama API interaction  

## 📂 Project Architecture

- `myapp/`: Contains the core application logic and AI/Chatbot integration views.  
- `upcycle/`: Specialized module for the "Remake" and sustainability features.  
- `products/`: Manages the product database, models, and catalog display.  
- `templates/`: Centralized folder for all HTML frontend layouts.  
- `static/` & `media/`: Managed directories for CSS/JS assets and product images.  

## ⚙️ Installation & Setup Guide

Follow these steps to get the project running locally:

### 1. Prerequisite: Install Ollama

Download and install Ollama from [ollama.com](https://ollama.com). Once installed, pull your preferred model:

```bash
ollama pull llama3
```

### 2. Clone the Repository

```bash
git clone https://github.com/official-noman/Remake_X.git
cd Remake_X
```

### 3. Create a Virtual Environment

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Database Setup (SQLite)

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Run the Development Server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser to access the application.

## 🤖 Why Ollama & SQLite?

**Ollama:** Chosen to demonstrate the capability of hosting LLMs locally. This approach avoids API costs and ensures that user conversations remain private and on-premise.

**SQLite:** Utilizing Django's default SQLite database makes the project highly portable and easy to review without the need for complex database server configurations (like PostgreSQL or MySQL) during the initial evaluation phase.

---

**Developed by:** Noman
