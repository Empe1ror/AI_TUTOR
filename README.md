# Renewed AI Tutor 🎓🤖

### An AI-Powered Personalized Learning Assistant

Renewed AI Tutor is an intelligent educational assistant designed to make learning more personalized, interactive, and adaptive through Large Language Models (LLMs).

The project aims to move beyond traditional AI chatbots by developing a tutor that can understand individual learners, maintain conversational context, remember student information, and provide explanations tailored to their learning needs.

Built with Python, LangChain, NVIDIA AI and Streamlit, Renewed AI Tutor combines conversational AI with persistent student information to create a foundation for more personalized digital learning experiences.

---

## 🎯 Project Vision

The vision behind Renewed AI Tutor is to develop an AI-powered learning environment where every student receives guidance that reflects their individual learning needs.

Rather than providing generic answers, the tutor is designed to consider:

- The student's educational level and background.
- Their learning goals and interests.
- Their current subject or area of study.
- Their strengths and learning difficulties.
- Their previous interactions and learning progress.

The long-term goal is to evolve the application into an intelligent tutoring system capable of supporting personalized instruction, knowledge retrieval, assessment, and adaptive learning.

## ✨ Current Features

The current development focuses on establishing the core architecture of an intelligent tutoring system.

### 1. AI-Powered Tutoring

- Uses Large Language Models to generate educational responses.
- Provides explanations and answers to students' questions.
- Uses a dedicated tutoring prompt to guide the model's instructional behaviour.
- Designed to encourage understandable and student-oriented explanations.

### 2. Personalized Student Profiles

The system is designed to maintain information about individual learners.

Student profiles can contain information such as:

- Student identification.
- Educational level.
- Learning goals.
- Subjects of interest.
- Learning preferences.
- Strengths and weaknesses.

This information provides context for generating more relevant tutoring responses.

### 3. Conversational Memory

Renewed AI Tutor incorporates conversational memory to maintain context during learning interactions.

This allows the tutor to:

- Maintain the context of ongoing conversations.
- Refer to earlier messages within a conversation.
- Provide responses that are relevant to the current discussion.

### 4. Persistent Data Storage

MongoDB is used as the database layer for storing student profiles and conversation records.

This establishes a foundation for maintaining learner information beyond individual application sessions.

### 5. Streamlit User Interface

The project includes a Streamlit-based interface that provides an interactive environment for students to communicate with the AI tutor.

The interface is designed to make the tutoring experience accessible without requiring users to interact directly with the command line.

---

## 🧠 System Architecture

The project follows a modular architecture in which different components handle specific responsibilities.

| Component | Responsibility |
|---|---|
| `ui.py` | Streamlit user interface |
| `app.py` | Command-line application entry point |
| `llm.py` | LLM configuration and conversational chain |
| `memory.py` | Conversation history and memory management |
| `db.py` | MongoDB connection and database operations |
| `prompts.py` | System instructions and tutoring prompts |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

### How the System Works

1. A student interacts with the tutor through the Streamlit interface.
2. The application identifies the relevant student profile and conversation context.
3. The tutoring system prepares the relevant information and instructions.
4. LangChain coordinates the interaction with the configured NVIDIA-hosted language model.
5. The model generates an educational response.
6. Conversation information is maintained and persisted through the application's memory and database components.

### Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Interactive web interface |
| LangChain | LLM orchestration |
| NVIDIA AI | Language model inference |
| MongoDB | Persistent data storage |
| python-dotenv | Environment configuration |

---

## 📂 Project Structure

```text
renewed-ai-tutor/
│
├── ui.py
│   └── Streamlit application interface
│
├── app.py
│   └── Command-line application
│
├── llm.py
│   └── Language model and chain configuration
│
├── memory.py
│   └── Conversational memory management
│
├── db.py
│   └── MongoDB operations
│
├── prompts.py
│   └── AI tutor and student profile prompts
│
├── requirements.txt
│   └── Project dependencies
│
├── .env.example
│   └── Environment configuration template
│
└── README.md
    └── Project documentation
```

---

## ⚙️ Installation and Setup

Follow these steps to run the project locally.

### Prerequisites

Ensure you have the following installed:

- Python 3.10 or later (depending on dependency compatibility).
- Git.
- A MongoDB database.
- An NVIDIA API key with access to your configured model.

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
```

Navigate into the project directory:

```bash
cd renewed-ai-tutor
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment.

**Windows:**

```bash
venv\Scripts\activate
```

**Linux / macOS:**

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project's root directory using `.env.example` as a template.

Configure the required credentials:

```env
NVIDIA_API_KEY=your_nvidia_api_key

NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

MONGODB_URI=your_mongodb_connection_string
```

Replace the placeholder values with your actual credentials.

**Important:** Never commit your `.env` file or expose your API keys and database credentials publicly.

### 5. Run the Application

To launch the Streamlit interface:

```bash
streamlit run ui.py
```

The application should become accessible through your local browser.

To run the command-line version:

```bash
python app.py
```

---

## 🛣️ Development Roadmap

Renewed AI Tutor is an evolving project. Its development is organized into stages to progressively introduce more advanced intelligent tutoring capabilities.

### Phase 1 — Core AI Tutoring Foundation

- [x] Python-based application foundation.
- [x] LLM integration.
- [x] Dedicated tutoring prompts.
- [x] Conversational memory foundation.
- [x] Student profile management foundation.
- [x] MongoDB integration foundation.
- [x] Streamlit user interface.

### Phase 2 — Retrieval-Augmented Generation (RAG)

**Status: In development / planned**

The next major milestone is integrating Retrieval-Augmented Generation.

The objective is to enable students to learn from relevant educational resources instead of depending exclusively on the language model's pretrained knowledge.

Planned capabilities:

- [ ] Educational document uploads.
- [ ] Document processing and text extraction.
- [ ] Text chunking and embedding generation.
- [ ] Vector database integration.
- [ ] Semantic search and contextual retrieval.
- [ ] Retrieval-grounded responses.
- [ ] Source references and citations.

### Phase 3 — Advanced Student Memory

- [ ] Improved persistent conversational memory.
- [ ] Long-term student learning history.
- [ ] Automatic student profile updates.
- [ ] Learning progress tracking.
- [ ] Identification of knowledge gaps.
- [ ] Personalized learning recommendations.

### Phase 4 — Intelligent Assessment

- [ ] AI-generated quizzes.
- [ ] Student performance evaluation.
- [ ] Automated feedback.
- [ ] Strength and weakness analysis.
- [ ] Adaptive difficulty levels.

### Phase 5 — Agentic AI Tutor

- [ ] Intelligent learning agents.
- [ ] Multi-step learning task execution.
- [ ] Personalized learning pathways.
- [ ] Automated learning resource recommendations.
- [ ] Advanced adaptive tutoring workflows.

---

## 🔐 Security and Configuration

The application uses environment variables to manage sensitive credentials.

For responsible development:

- Keep API keys outside source code.
- Never commit `.env` files.
- Protect database connection strings.
- Apply appropriate database access restrictions.
- Validate user input before processing.

---

## 🎓 Educational Application

Renewed AI Tutor explores how Artificial Intelligence can improve teaching and learning through personalized digital instruction.

The project is particularly interested in the intersection of:

- Artificial Intelligence in Education.
- Large Language Models.
- Intelligent Tutoring Systems.
- Personalized Learning.
- Retrieval-Augmented Generation.
- Adaptive Learning Technologies.

It is being developed with the broader objective of exploring practical applications of AI in education, particularly within the evolving digital learning landscape.

---

## 🚀 Project Status

**Active Development**

Renewed AI Tutor is currently transitioning from its foundational conversational AI architecture towards a more context-aware and knowledge-grounded intelligent tutoring system.

The immediate development priority is implementing RAG while strengthening the existing student memory and personalization architecture.

## 👨‍💻 Author

**Damperor**

Aspiring AI/ML Engineer | Educational Technology Enthusiast | Graphics Designer

Building at the intersection of Artificial Intelligence, Education, and Technology.

---

*Renewed AI Tutor — Rethinking how students learn with Artificial Intelligence.*
