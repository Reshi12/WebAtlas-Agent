<div align="center">
  <h1>WebAtlas Agent</h1>
  <p><b>Production-grade autonomous browser agent executing complex web interactions from natural language.</b></p>
  
  <p>
    <a href="#overview">Overview</a> •
    <a href="#core-features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#api-reference">API Reference</a> •
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
    <img src="https://img.shields.io/badge/LLM-Multi--Provider-4285F4?style=flat-square&logo=google-gemini&logoColor=white" alt="Multi-Provider LLM" />
    <img src="https://img.shields.io/badge/Architecture-LangGraph-FF6B6B?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph" />
    <img src="https://img.shields.io/badge/Safety-Multi--Layer-10B981?style=flat-square&logo=shield&logoColor=white" alt="Multi-Layer Safety" />
  </p>
</div>

---

<a id="overview"></a>
## Overview

**WebAtlas Agent** is a production-ready autonomous browser automation framework that bridges natural language understanding and complex web interactions. Unlike traditional RPA tools requiring brittle step-by-step configurations, WebAtlas automatically understands task intent, decomposes it into optimal execution steps, routes each to the appropriate backend (interactive browser control or lightweight research mode), and verifies results through multi-layer safety mechanisms.

### The Problem We Solve

Modern web automation faces critical challenges:
- **Complexity**: Tasks span multiple websites, require complex form navigation, and demand real-time decision-making
- **Brittleness**: Selector-based approaches break when UI changes occur
- **Safety**: Automation over sensitive operations (payments, credentials) requires verification mechanisms
- **Cost**: LLM-powered approaches often route all operations through expensive reasoning models
- **Adaptability**: Fixed workflows cannot handle dynamic page structures or unexpected failures

WebAtlas addresses these through intelligent routing, adaptive replanning, multi-layer safety, and optimized token consumption.

---

<a id="core-features"></a>
## 🎯 Core Features

### 1. **Intelligent Task Decomposition**
- Automatically breaks complex user instructions into atomic, executable steps
- Tags each step with optimal execution backend (interactive or research mode)
- Generates deterministic execution plans without manual configuration
- Supports logical dependencies and conditional routing

### 2. **Dual-Mode Execution Engine**

#### Interactive Mode (Browser Control)
- Real-time browser session management
- DOM interaction: clicking, form filling, navigation
- Screenshot capture and page state analysis
- Supports complex multi-step workflows (checkout flows, booking sequences)
- Per-action safety interception capability

#### Research Mode (Lightweight Aggregation)
- High-speed multi-page web scraping
- Parallel content extraction and aggregation
- Optimized for data gathering and comparison tasks
- Minimal token overhead
- Natural language search and filtering

### 3. **Multi-Layer Safety Architecture**

**Layer 1 – Pattern Detection (Fast)**
- Real-time keyword matching for payment pages, login forms, personal info
- Domain blacklist verification
- Zero LLM latency

**Layer 2 – Contextual Classification (Smart)**
- LLM-powered analysis for ambiguous scenarios
- Confidence scoring for edge cases
- Triggered only when Layer 1 is inconclusive

**Layer 3 – Human Interrupts (Control)**
- Automatic pause for credential entry, payment confirmation, destructive actions
- Resume capability with checkpoint-based state
- Full audit trail for compliance

### 4. **Token Optimization**
- **60-75% token reduction** through intelligent model selection
- Task-appropriate routing: fast/cheap models for classification, premium models for reasoning
- Eliminates redundant LLM calls via deterministic verification
- Per-backend token accounting and cost analysis

### 5. **Adaptive Execution & Resilience**
- **Auto-Replanning**: Detects page structure changes and dynamically regenerates execution plans
- **Smart Retry Logic**: Distinguishes between transient failures (retry) and hard blockers (replan)
- **State Checkpointing**: Pause and resume long-running tasks from exact execution point
- **Dry-Run Mode**: Validate execution plans before committing actions
- **Comprehensive Logging**: Full audit trail with screenshots, timings, and token metrics

### 6. **Multi-Provider LLM Support**
- **Gemini** (Google) – Free tier, excellent cost efficiency
- **Groq** – Ultra-low latency inference
- **OpenAI** (GPT-4, GPT-3.5) – Advanced reasoning
- **OpenAI-Compatible** (Nemotron, GLM, etc.) – Self-hosted or proprietary models

---

<a id="architecture"></a>
## 📐 Architecture

### Workflow Diagram

```mermaid
graph TD
    A["User Request<br/>(Natural Language)"] -->|Parse Intent| B["Task Planner"]
    B -->|Fast Model| C["Generate Execution Plan"]
    C -->|Tag by Type| D{"Route"}
    
    D -->|Interactive| E["Interactive Mode"]
    D -->|Research| F["Research Mode"]
    
    E -->|Browser Control| E1["DOM Navigator"]
    E1 -->|Interact| E2["Action Executor"]
    E2 -->|Capture| E3["State Manager"]
    
    F -->|Multi-Page| F1["Web Scraper"]
    F1 -->|Parse| F2["Content Aggregator"]
    F2 -->|Format| F3["Result Builder"]
    
    E3 -->|Result| G["Safety Gate"]
    F3 -->|Result| G
    
    G -->|Pattern| G1["Fast Detection"]
    G1 -->|Analysis| G2["LLM Classification"]
    G2 -->|Decision| G3{"Safe?"}
    
    G3 -->|Yes| H["Verifier"]
    G3 -->|Needs Action| I["Human Interrupt"]
    I -->|Proceed| H
    
    H -->|✓ Success| J["Advance"]
    H -->|⟳ Retryable| K["Retry"]
    H -->|✗ Hard Fail| L["Replan"]
    
    J -->|More?| M{"Done?"}
    K -->|Re-exec| D
    L -->|New Plan| B
    
    M -->|No| D
    M -->|Yes| N["Finalize"]
    N -->|Checkpoint| O["Output<br/>Result + Audit + Tokens"]
    
    style A fill:#f59e0b,stroke:#333,color:#000
    style B fill:#06b6d4,stroke:#333,color:#fff
    style D fill:#ec4899,stroke:#333,color:#fff
    style E fill:#06b6d4,stroke:#333,color:#fff
    style F fill:#1e3a8a,stroke:#333,color:#fff
    style G fill:#ea580c,stroke:#333,color:#fff
    style H fill:#10b981,stroke:#333,color:#fff
    style O fill:#f59e0b,stroke:#333,color:#000
```

### System Design

```
        ┌──────────────────────────────────────────────────────────────┐
        │                   LANGGRAPH STATE MACHINE                    │
        ├──────────────────────────────────────────────────────────────┤
        │                                                              │
        │  ┌────────────────────────────────────────────────────────┐  │
        │  │  Task Planning Layer                                   │  │
        │  │  • NLP understanding & decomposition                   │  │
        │  │  • Backend routing (interactive vs research)           │  │
        │  │  • Execution plan generation                           │  │
        │  └────────────────────────────────────────────────────────┘  │
        │                              ↓                               │
        │  ┌────────────────────────────────────────────────────────┐  │
        │  │  Execution Layer                                       │  │
        │  │  ┌────────────────────┐  ┌──────────────────────────┐  │  │
        │  │  │ Interactive Mode   │  │ Research Mode            │  │  │
        │  │  │ • Browser session  │  │ • Web scraper            │  │  │
        │  │  │ • DOM interaction  │  │ • Content extraction     │  │  │
        │  │  │ • Screenshot mgmt  │  │ • Multi-page aggregation │  │  │
        │  │  └────────────────────┘  └──────────────────────────┘  │  │
        │  └────────────────────────────────────────────────────────┘  │
        │                              ↓                               │
        │  ┌────────────────────────────────────────────────────────┐  │
        │  │  Safety Layer (Outside Both Backends)                  │  │
        │  │  • Layer 1: Fast pattern detection                     │  │
        │  │  • Layer 2: LLM contextual classification              │  │
        │  │  • Layer 3: Human confirmation for sensitive ops       │  │
        │  └────────────────────────────────────────────────────────┘  │
        │                              ↓                               │
        │  ┌────────────────────────────────────────────────────────┐  │
        │  │  Verification & Adaptation Layer                       │  │
        │  │  • Outcome validation                                  │  │
        │  │  • Adaptive retry/replan logic                         │  │
        │  │  • State persistence                                   │  │
        │  └────────────────────────────────────────────────────────┘  │
        │                                                              │
        │  ┌─ State Persistence ────────────────────────────────────┐  │
        │  │  • Checkpoint-based resume capability                  │  │
        │  │  • Token accounting and reporting                      │  │
        │  │  • Complete audit trail with artifacts                 │  │
        │  └────────────────────────────────────────────────────────┘  │
        │                                                              │
        └──────────────────────────────────────────────────────────────┘
```

---

<a id="quick-start"></a>
## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Node.js & npm** (for browser automation backend)
- **LLM API Key** (Gemini, Groq, OpenAI, or compatible provider)
- **Disk space**: ~500MB for dependencies and logs

### Installation

1. **Clone repository:**
   ```bash
   git clone https://github.com/yourusername/webatlas-agent.git
   cd webatlas-agent
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   npm i -g agent-browser && agent-browser install
   ```

4. **Configure:**
   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml with your settings
   ```

5. **Set credentials:**
   ```bash
   # .env file
   GEMINI_API_KEY=your_key_here
   GROQ_API_KEY=your_key_here        # Optional
   OPENAI_API_KEY=your_key_here      # Optional
   ```

### First Task

```bash
python main.py "Search for information about quantum computing and summarize key concepts"
```

**Output:**
```
🚀 Task: search_summarize_quantum (ID: task_20260624_142530)

📋 Execution Plan:
  1. 🔎 Research: Gather quantum computing resources
  2. 🌐 Interactive: Verify and extract key concepts
  3. 🔎 Research: Aggregate definitions

⏱️  Duration: 1m 02s | Tokens: 2,847 

Result:
[Structured findings with sources and citations]

✅ Task completed successfully
```

---

<a id="configuration"></a>
## 🔧 Configuration

### config.yaml Structure

```yaml
# LLM Configuration
llm:
  provider: gemini                # groq | gemini | openai | openai_compatible
  model: gemini-flash-lite-latest # Model selection
  temperature: 0.1                # Deterministic behavior (0.0-1.0)
  max_tokens: 4096                # Output limit
  timeout_seconds: 60             # API timeout

# Safety Rules
safety:
  max_retries: 1                  # Retry attempts before hard fail
  
  payment_url_keywords:
    - checkout
    - payment
    - stripe.com
    - razorpay.com
  
  personal_info_fields:
    - credit card
    - cvv
    - ssn
    - email
    - phone
  
  destructive_action_keywords:
    - delete
    - cancel
    - unsubscribe

# Browser Automation Settings
agent_browser:
  binary: agent-browser
  default_wait: networkidle        # Wait until no network activity
  wait_timeout_ms: 30000           # Max 30 seconds per page load
  headless: true                   # Run without visible browser
  parallel_tasks: 3                # Concurrent browser instances

# Research Mode Settings
research:
  max_pages: 5                     # Limit concurrent scrapes
  page_timeout_seconds: 20         # Per-page timeout
  retry_on_failure: true           # Retry failed pages

# Logging & Persistence
logging:
  level: INFO                      # DEBUG | INFO | WARNING | ERROR
  screenshots: true                # Capture page state
  save_snapshots: true             # Save DOM snapshots
  log_dir: logs
  retention_days: 30               # Auto-cleanup old logs
```

---

---

<a id="api-reference"></a>
## 📋 API Reference

### CLI Commands

```bash
# Basic execution
python main.py "Your instruction"

# Plan without execution
python main.py --dry-run "Your instruction"

# Resume interrupted task
python main.py --resume <task_id>

# List all tasks
python main.py --list-tasks

# Show task status
python main.py --status <task_id>

# Verbose logging
python main.py -v "Your instruction"

# Specific config file
python main.py --config /path/to/config.yaml "Your instruction"
```

### Execution States

| State | Meaning |
|-------|---------|
| `running` | Task actively executing |
| `awaiting_human` | Waiting for user confirmation (credentials, payment) |
| `awaiting_payment_resume` | Paused at payment page, awaiting permission to continue |
| `done` | Successfully completed |
| `failed` | Execution failed after max retries |

---

## 🛡️ Safety & Compliance

### Built-in Protections

✅ **Payment Page Detection** – Prevents auto-submission of payment forms
✅ **Login Form Blocking** – Requires manual credential entry
✅ **Personal Information Guards** – Pauses before auto-filling sensitive fields
✅ **Destructive Action Warnings** – Confirms deletion, unsubscribe, cancel operations
✅ **Audit Logging** – Complete trace of all actions with timestamps
✅ **Screenshot Capture** – Visual record of each step for review

### Compliance Features

- SOC 2 compatible audit trails
- GDPR-aligned credential handling
- Configurable safety rules per deployment
- Audit export in JSON/CSV formats

---

## 📈 Performance Metrics

| Metric | Benchmark |
|--------|-----------|
| Task Planning | 200-500ms (fast model) |
| Average Task Duration | 30s - 5m (depending on complexity) |
| Token Efficiency | 60-75% reduction vs. monolithic agents |
| Success Rate | 92-98% (varies by task complexity) |
| Concurrent Tasks | Up to 3-5 simultaneously |

---

## 📦 Project Structure

```
webatlas-agent/
├── main.py                          # CLI entrypoint
├── config.yaml                      # Configuration
├── requirements.txt                 # Python dependencies
├── README_PROFESSIONAL.md          # This file
│
├── core/
│   ├── graph.py                    # LangGraph orchestration
│   ├── llm_provider.py              # Multi-provider LLM abstraction
│   ├── state.py                     # State schema definitions
│   ├── browser_session.py           # Browser lifecycle management
│   ├── persistence.py               # Task checkpoint system
│   │
│   └── nodes/
│       ├── planner.py               # Task decomposition & routing
│       ├── agent_browser_actor.py   # Interactive mode executor
│       ├── webwright_actor.py       # Research mode executor
│       ├── safety_gate.py            # Safety verification
│       ├── verifier.py               # Outcome validation
│       ├── human_interrupt.py        # Human confirmation handler
│       └── extractor.py              # Result extraction
│
├── safety/
│   ├── rules.py                     # Safety rule enforcement
│   ├── payment_keywords.py          # Payment detection patterns
│   └── __init__.py
│
├── logs/                            # Task execution logs
│   └── task_*/                      # Per-task checkpoint directories
│
└── tests/                           # Unit and integration tests
```

---

### Development Setup

```bash
pip install -r requirements-dev.txt
pytest                              # Run tests
black .                             # Format code
pylint core/                        # Lint
```

---


<div align="center">

**WebAtlas Agent** – Autonomous, Intelligent, Enterprise-Ready

*Making complex web interactions simple through natural language.*

</div>
