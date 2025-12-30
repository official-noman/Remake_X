# Remake_X: AI-Powered Product Management & Upcycling Platform

**Remake_X** is a full-stack web application built with the **Django** framework that combines traditional product lifecycle management with a modern, sustainability-focused **upcycling** workflow.

A key differentiator of this project is its integration with a **local conversational AI chatbot** powered by **Ollama**, enabling **privacy-preserving, offline LLM interactions** entirely on your own machine.

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Technical Stack](#-technical-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#-prerequisites)
  - [Installation](#-installation)
  - [Running the Application](#-running-the-application)
- [Usage Guide](#-usage-guide)
  - [Product Management](#product-management)
  - [Upcycling Workflow](#upcycling-workflow)
  - [AI Chatbot](#ai-chatbot)
- [Configuration & Customization](#-configuration--customization)
- [Future Enhancements](#-future-enhancements)
- [Why Ollama & SQLite?](#-why-ollama--sqlite)
- [Author](#-author)

---

## 🧭 Overview

Remake_X is designed as a **practical demonstration of AI-assisted product management** with a strong emphasis on **sustainability**:

- Manage products end-to-end (create, categorize, update, archive).
- Propose and track **upcycling ideas** for existing products instead of discarding them.
- Leverage a **local LLM** to:
  - Suggest upcycling ideas,
  - Draft product descriptions,
  - Assist in decision-making within the platform.

This makes it suitable both as a **portfolio project** and a starting point for **AI-enabled internal tools**.

---

## 🚀 Key Features

### 1. AI-Enhanced Product Management

- **Local AI Chatbot Integration** using the **Ollama API**.
- Interact with models like **Llama 3** or **Mistral** completely **offline**.
- Use the chatbot to:
  - Generate product descriptions,
  - Suggest upcycling strategies,
  - Provide assistant-like help within the UI.

### 2. Upcycling Module

- Dedicated `upcycle` app/module to:
  - Attach upcycling ideas to existing products,
  - Track status (e.g., *Proposed*, *In-Progress*, *Completed*),
  - Promote re-use and repurposing instead of disposal.
- Clean separation of concerns between **core product management** and **upcycling workflows**.

### 3. Product Catalog & CRUD Operations

- Full **CRUD** for products:
  - Create, update, delete products.
  - Organize with categories/tags.
  - Attach images or other media.
- Searchable / filterable listing (depending on implementation of template logic).

### 4. Modern, Responsive Frontend

- UI built with **Django Templates**, **CSS**, and **JavaScript**.
- Responsive layout suitable for both desktop and mobile screens.
- Clear separation of layout vs. business logic via `templates/` and `static/`.

### 5. Asset & Media Management

- **Static files** (CSS/JS) handled via Django’s static files framework.
- **Media files** (e.g., product images) served from a dedicated `media/` directory.
- Easy to swap/extend with a CDN or cloud storage in the future.

---

## 🏗 System Architecture

At a high level, Remake_X follows a clean, layered architecture with a local AI engine:

```mermaid
flowchart LR
    user[User Browser] --> ui[Remake_X Web UI<br/>(Django Templates)]
    ui --> views[Django Views / Controllers]
    views --> db[(SQLite Database)]
    views --> ai[Local AI Engine<br/>(Ollama)]
    ai --> views

    style user fill:#f0f8ff,stroke:#4a90e2,stroke-width:1px
    style ui fill:#ffffff,stroke:#4a90e2,stroke-width:1px
    style views fill:#f5f5f5,stroke:#999,stroke-width:1px
    style db fill:#f9f2d0,stroke:#c49b0b,stroke-width:1px
    style ai fill:#e8f8f5,stroke:#1abc9c,stroke-width:1px
```

**Flow:**

1. The user interacts with the **web UI** (Django templates).
2. **Django views** handle HTTP requests, perform validation, query the database, and optionally call the **Ollama API**.
3. **SQLite** persists all product and upcycling data.
4. The **Ollama service** (running locally) handles LLM inference and returns results to Django for rendering.

---

## 🛠 Technical Stack

| Layer         | Technologies                                   |
|--------------|-------------------------------------------------|
| Backend      | **Python 3.x**, **Django**                      |
| AI Engine    | **Ollama** (Local LLM – e.g., Llama 3, Mistral) |
| Database     | **SQLite3** (Django default)                    |
| Frontend     | Django Templates, **HTML5**, **CSS3**, **JavaScript** |
| Integration  | Python `requests` for **Ollama API** calls      |
| Assets       | Django static files framework (`static/`, `media/`) |

---

## 📂 Project Structure

High-level layout of the repository:

```text
Remake_X/
├─ manage.py
├─ requirements.txt
├─ myapp/              # Core application logic & AI/chatbot integration
├─ upcycle/            # Upcycling-specific models, views, and workflows
├─ products/           # Product catalog, models, and related views
├─ templates/          # All HTML templates for frontend rendering
├─ static/             # CSS, JavaScript, images, and other static assets
└─ media/              # User-uploaded content (e.g., product images)
```

- **`myapp/`**  
  Core application wiring, including AI chatbot endpoints and shared utilities.

- **`upcycle/`**  
  Holds logic for sustainability and repurposing features (`models.py`, `views.py`, `forms.py` etc.).

- **`products/`**  
  Encapsulates product data structures, business logic, and catalog presentation.

---

## 🚀 Getting Started

### ✅ Prerequisites

Before you start, ensure you have:

- **Python 3.x** installed  
- **pip** (Python package manager)  
- **Ollama** installed and running locally (default: `http://localhost:11434`)  
- (Optional) A virtual environment tool such as `venv` or `virtualenv`

### 1️⃣ Install Ollama & Pull a Model

1. Download and install Ollama from: [https://ollama.com](https://ollama.com)  
2. Pull your preferred model (example: **Llama 3**):

```bash
ollama pull llama3
```

You can verify installation with:

```bash
ollama list
```

---

### 2️⃣ Clone the Repository

```bash
git clone https://github.com/official-noman/Remake_X.git
cd Remake_X
```

---

### 3️⃣ Create & Activate a Virtual Environment

```bash
python -m venv venv
```

**On Windows:**

```bash
venv\Scripts\activate
```

**On macOS/Linux:**

```bash
source venv/bin/activate
```

---

### 4️⃣ Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### 5️⃣ Database Setup (SQLite)

Run Django migrations to create the local SQLite database schema:

```bash
python manage.py makemigrations
python manage.py migrate
```

(Optional) Create a superuser for the Django admin panel:

```bash
python manage.py createsuperuser
```

---

### 6️⃣ Run the Development Server

```bash
python manage.py runserver
```

Now open your browser and visit:

```text
http://127.0.0.1:8000/
```

> Make sure the **Ollama service** is running in the background so that AI features work correctly.

---

## 📘 Usage Guide

> Note: Exact URLs and views may vary slightly depending on your `urls.py` configuration, but the typical flows are described below.

### Product Management

- Browse the **product catalog** from the main dashboard.
- Create new products with:
  - Name, description, category,
  - Price, quantity, and status,
  - Product images (stored in `media/`).
- Edit or delete products via dedicated detail/edit pages.
- View products grouped by **category** or **upcycling status** (if implemented in UI).

### Upcycling Workflow

- Open a product’s detail page and access **“Upcycle”** actions.
- Add upcycling ideas, such as:
  - Alternative uses,
  - Refurbishing plans,
  - Bundling with other products.
- Track each idea with fields like:
  - **Status**: Proposed / In-Progress / Completed
  - **Notes**: Implementation details and outcomes.

This structure demonstrates how AI + upcycling can fit into a **real product lifecycle**.

### AI Chatbot

- Navigate to the **AI/Chatbot** page (typically something like `/chat/` or `/assistant/`).
- Converse with the local LLM to:
  - Brainstorm upcycling ideas,
  - Generate marketing copy or product descriptions,
  - Ask for recommendations on inventory optimization.
- Conversations are processed **locally via Ollama**, ensuring:
  - **No external API calls**
  - **No third-party data sharing**

---

## ⚙ Configuration & Customization

Some common customization areas:

- **Ollama Model Selection**  
  Change the default model (e.g., `llama3`, `mistral`) in the Django view or configuration that calls the Ollama API.

- **Ollama Endpoint**  
  If Ollama runs on a custom host/port, update the base URL in the module that performs:
  ```python
  import requests
  # e.g. OLLAMA_URL = "http://localhost:11434"
  ```

- **Static & Media Paths**  
  Adjust `STATIC_URL`, `STATIC_ROOT`, `MEDIA_URL`, `MEDIA_ROOT` in `settings.py` if you deploy to production.

- **Database**  
  For production, you can easily swap SQLite for **PostgreSQL** or another RDBMS by updating `DATABASES` in `settings.py`.

---

## 🧭 Future Enhancements

Planned / potential improvements:

- 🔹 Replace SQLite with **PostgreSQL/MySQL** in production.
- 🔹 Add **user authentication & authorization** (per-user products & upcycling ideas).
- 🔹 Build a more fully-featured **REST API** for external integration.
- 🔹 Persist AI chat history per product / per user.
- 🔹 Add front-end enhancements (e.g., HTMX/Alpine.js/React) for richer UX.
- 🔹 Containerize with **Docker** and add a basic **CI/CD pipeline**.

These points help demonstrate the project’s scalability and your vision for evolving it.

---

## 🤖 Why Ollama & SQLite?

**Ollama**

- Showcases how to run **LLMs locally** without external dependencies.
- Avoids recurring **API costs** and rate limits.
- Ensures all conversations remain **on-premise**, suitable for sensitive data scenarios.

**SQLite**

- Django’s default database, ideal for:
  - Rapid prototyping,
  - Local development,
  - Easy sharing with reviewers / interviewers (no extra DB setup).
- Can be seamlessly replaced with a production-grade RDBMS later.

---

## 👤 Author

**Developed by:** **Abdullah Al Noman**  
```
