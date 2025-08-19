# Install JUST!
# https://github.com/casey/just

# Setup: Install NX CLI, Node.js dependencies, and Python dependencies
i:
    just install

install:
    if ! command -v nx > /dev/null; then npm install -g nx; fi
    @echo "Installing Node.js dependencies..."
    npm install

# Build the application
build:
    @echo "Running build for NX workspace..."
    nx run-many -t build 

# Serve the application
serve:
    @echo "Starting the application..."
    nx run-many --target=serve --parallel=6

# Serve all applications and gateway
serve-mcp:
    @echo "Starting all applications (app and mcp)..."
    nx run-many --target=serve --projects=@mcp/rag-mcp,@mcp/summarization-mcp,@mcp/translation-mcp --parallel=5    

serve-gw:
    @echo "Starting gateway application..."
    nx run gateway:serve

# Create Docker images
docker-build:
    @echo "Creating Docker images..."
    nx run-many --target=docker-build

# Run docker-compose
compose-up:
    @echo "Starting docker-compose..."
    docker-compose up -d

compose-down:
    @echo "Stopping docker-compose..."
    docker-compose down

# Initialize a new Node.js application
init-node app-type app-name:
    @if [ "{{app-type}}" != "mcp" ] && [ "{{app-type}}" != "app" ] && [ "{{app-type}}" != "lib" ]; then \
        echo "Error: app-type must be either 'mcp', 'app', or 'lib'."; \
        exit 1; \
    fi
    @if [ "{{app-type}}" = "mcp" ]; then \
        echo "Initializing a new Node.js application named {{app-name}} as MCP..."; \
        nx generate @nx/node:app --name={{app-name}} mcps/{{app-name}}; \
    else \
        echo "Initializing a new Node.js application named {{app-name}}..."; \
        nx generate @nx/node:{{app-type}} --name={{app-name}} {{app-type}}s/{{app-name}}; \
    fi

# Initialize a new Python application
init-py app-type app-name:
    @if [ "{{app-type}}" != "mcp" ] && [ "{{app-type}}" != "app" ] && [ "{{app-type}}" != "lib" ]; then \
        echo "Error: app-type must be either 'mcp' or 'app'."; \
        exit 1; \
    fi
    @echo "Initializing a new Python application named {{app-name}}..."
    nx generate @nxlv/python:uv-project {{app-name}}
    mv {{app-name}} {{app-type}}s
    uv venv {{app-type}}s/{{app-name}}/.venv