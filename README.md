# Getting started

## Prerequisites

- Download and install [Node.js LTS version](https://nodejs.org/en/download/) (version >=21)
- Docker and Docker Compose
- Python with virtual environment support

## Installation & Setup

### 1. Clone Repository and Install Dependencies

```bash
git clone https://gitlab/ai/AI_HUB/starter-kit/node-template.git
cd node-template
npm install
```

### 2. Start Docker Services

```bash
docker-compose up
```

### 3. Setup Python Environment

Activate your virtual environment and install Python requirements:

```bash
# Activate virtual environment (example for venv)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 4. Start MCP Service

Run the MCP (Model Context Protocol) service:

```bash
python mcp_server_document.py
```

### 5. Run the Application

Start the main application:

```bash
npx tsx src/main.ts
```


## Swagger UI

Access the API documentation at: https://localhost:3000/docs

## Development Workflow

1. Ensure Docker services are running (`docker-compose up`)
2. Activate Python virtual environment
3. Start MCP service
4. Run the application with `npx tsx src/main.ts` or `npm run dev`
5. Access Swagger documentation for API testing