#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    if ! command_exists node; then
        print_error "Node.js is not installed. Please install Node.js 18+ first."
        exit 1
    fi

    if ! command_exists npm; then
        print_error "npm is not installed. Please install npm first."
        exit 1
    fi

    print_success "All prerequisites are installed"
}

# Setup environment
setup_environment() {
    print_status "Setting up environment..."

    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            print_warning "Created .env file from .env.example"
            print_warning "Please edit .env file with your Azure OpenAI credentials before proceeding"
            echo ""
            echo "Required environment variables:"
            echo "- AZURE_OPENAI_API_KEY"
            echo "- AZURE_OPENAI_ENDPOINT"
            echo ""
            read -p "Press Enter after you've configured the .env file..."
        else
            print_error ".env.example file not found"
            exit 1
        fi
    else
        print_success ".env file already exists"
    fi

    # Validate required environment variables
    source .env
    if [ -z "$AZURE_OPENAI_API_KEY" ] || [ -z "$AZURE_OPENAI_ENDPOINT" ]; then
        print_error "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in .env file"
        exit 1
    fi

    print_success "Environment configuration validated"
}

# Install dependencies
install_dependencies() {
    print_status "Installing Node.js dependencies..."
    npm install
    print_success "Dependencies installed"
}

# Build TypeScript application
build_application() {
    print_status "Building TypeScript application..."
    npm run build
    print_success "Application built successfully"
}

# Start infrastructure services
start_infrastructure() {
    print_status "Starting infrastructure services (MongoDB, Qdrant)..."
    docker-compose up -d mongodb qdrant

    print_status "Waiting for services to be ready..."
    sleep 30

    # Check if services are healthy
    if docker-compose ps | grep -q "mongodb.*healthy" && docker-compose ps | grep -q "qdrant.*healthy"; then
        print_success "Infrastructure services are running"
    else
        print_warning "Infrastructure services may still be starting. Check with: docker-compose ps"
    fi
}

# Start MCP services
start_mcp_services() {
    print_status "Starting Python MCP services..."

    # Check if Python MCP services exist
    if [ -d "./python-mcp-services" ]; then
        docker-compose up -d document-service
        print_status "Waiting for MCP services to be ready..."
        sleep 30
        print_success "MCP services started"
    else
        print_warning "Python MCP services directory not found"
        print_warning "Starting TypeScript application only"
        print_warning "Make sure Python MCP services are running separately on ports 8001, 8002, 8003"
    fi
}

# Start TypeScript application
start_application() {
    print_status "Starting TypeScript/Fastify application..."

    if [ "$1" = "docker" ]; then
        docker-compose up -d fastify-app
        print_success "Fastify application started in Docker"
    else
        print_status "Starting in development mode..."
        npm run dev &
        APP_PID=$!
        print_success "Fastify application started (PID: $APP_PID)"

        # Save PID for later cleanup
        echo $APP_PID > .app.pid
    fi
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."

    if [ -f .app.pid ]; then
        APP_PID=$(cat .app.pid)
        if kill -0 $APP_PID 2>/dev/null; then
            kill $APP_PID
            print_success "Stopped application (PID: $APP_PID)"
        fi
        rm -f .app.pid
    fi
}

# Stop all services
stop_services() {
    print_status "Stopping all services..."
    docker-compose down
    cleanup
    print_success "All services stopped"
}

# Show logs
show_logs() {
    if [ "$1" = "fastify" ]; then
        docker-compose logs -f fastify-app
    elif [ "$1" = "mcp" ]; then
        docker-compose logs -f document-service rag-service docdb-service
    else
        docker-compose logs -f
    fi
}

# Main deployment function
deploy() {
    local mode=${1:-development}

    print_status "Starting deployment in $mode mode..."

    check_prerequisites
    setup_environment
    install_dependencies
    build_application
    start_infrastructure

    if [ "$mode" = "production" ] || [ "$mode" = "docker" ]; then
        start_mcp_services
        start_application docker
    else
        print_warning "In development mode, make sure Python MCP services are running"
        start_application development
    fi

    health_check
}

# Trap signals for cleanup
trap cleanup SIGINT SIGTERM

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        deploy ${2:-development}
        ;;
    "stop")
        stop_services
        ;;
    "logs")
        show_logs $2
        ;;
    "health")
        curl -s http://localhost:3000/health | jq '.' || curl -s http://localhost:3000/health
        ;;
    "restart")
        stop_services
        sleep 5
        deploy ${2:-development}
        ;;
    *)
        echo "Usage: $0 {deploy|stop|logs|health|restart} [mode]"
        echo ""
        echo "Commands:"
        echo "  deploy [development|production|docker] - Deploy the application"
        echo "  stop                                   - Stop all services"
        echo "  logs [fastify|mcp|all]                - Show service logs"
        echo "  health                                - Check application health"
        echo "  restart [development|production]      - Restart the application"
        echo ""
        echo "Examples:"
        echo "  $0 deploy development    # Start in development mode"
        echo "  $0 deploy production     # Start in production mode with Docker"
        echo "  $0 logs fastify         # Show Fastify application logs"
        echo "  $0 stop                 # Stop all services"
        exit 1
        ;;
esac