# Project Startup Guide

This project uses **[just](https://github.com/casey/just)** as a task runner and **NX** as a monorepo tool.
It contains Node.js and Python applications, MCP services, and a gateway.

---

## Prerequisites

Before starting, ensure you have the following installed:
- **Docker & Docker Compose** - For running infrastructure services
- **Node.js** (v18 or higher) - For JavaScript/TypeScript applications
- **Python** (v3.8 or higher) - For Python applications
- **Git** - For version control

---

## Install Tools and Dependencies

### Install `just` Task Runner

Choose the installation method for your operating system:

#### **Windows**
```powershell
# Option 1: Using Chocolatey
choco install just

# Option 2: Using Scoop
scoop install just

# Option 3: Using Cargo (if Rust is installed)
cargo install just

# Option 4: Download binary directly
# Visit https://github.com/casey/just/releases
# Download the Windows binary and add to PATH
```

#### **macOS**
```bash
# Using Homebrew
brew install just

# Using MacPorts
sudo port install just
```

#### **Linux**
```bash
# Ubuntu / Debian
sudo apt install just

# Arch Linux
sudo pacman -S just

# CentOS / RHEL / Fedora
sudo dnf install just

# Or using Cargo
cargo install just
```

### Install Project Dependencies

After installing `just`, install NX CLI, Node.js, and Python dependencies:

```bash
just install
```

---

## Platform-Specific Setup Notes

### **Windows Users**
- **PowerShell**: Use PowerShell or Command Prompt for running commands
- **WSL2**: For better Docker performance, consider using WSL2 with Docker Desktop
- **Path Separators**: The project handles path differences automatically
- **Line Endings**: Ensure Git is configured to handle line endings properly:
  ```bash
  git config --global core.autocrlf true
  ```

### **macOS Users**
- **Docker Desktop**: Ensure Docker Desktop for Mac is installed and running
- **Homebrew**: Most dependencies can be installed via Homebrew

### **Linux Users**
- **Docker**: Install Docker Engine and Docker Compose
- **Permissions**: You may need to add your user to the docker group:
  ```bash
  sudo usermod -aG docker $USER
  ```

---

## Start Infrastructure with Docker Compose

To start all infrastructure services:

```bash
just compose-up
```

> This will run all services defined in `docker-compose.yml` in detached mode.

**Troubleshooting:**
- **Windows**: If you encounter permission issues, try running as Administrator
- **All Platforms**: Ensure Docker is running before executing this command

---

## Start MCP Services

To start all MCP applications at once:

```bash
just serve-mcp
```

This will start:
- `@mcp/rag-mcp`
- `@mcp/summarization-mcp`
- `@mcp/translation-mcp`

⚠ **Note:** If you plan to run `serve-mcp` manually, make sure to **stop the MCP-related services in Docker Compose first**,
because they use the same ports and will cause conflicts.

---

## Start the Gateway

Once the MCP services are up and running, you can start the gateway:

```bash
just serve-gw
```

The gateway exposes the API that communicates with the MCP applications.

⚠ **Note:** If you plan to run `serve-gw` manually, make sure to **stop the gateway service in Docker Compose first**
to avoid port conflicts.

---

## Stop Services

To stop the Docker Compose infrastructure:

```bash
just compose-down
```

---

## Development Workflow

### **Build the Project**
```bash
just build
```

### **Run All Applications in Development Mode**
```bash
just serve
```

### **View Available Commands**
```bash
just --list
```

### **Check Service Status**
```bash
# Check Docker services
docker ps

# Check specific ports (Windows)
netstat -an | findstr :3000

# Check specific ports (macOS/Linux)  
lsof -i :3000
```

---

## Troubleshooting

### Common Issues

**Port Conflicts:**
- Stop conflicting services before starting new ones
- Use `docker ps` to check running containers
- Use `just compose-down` to stop all Docker services

**Permission Issues (Windows):**
- Run PowerShell/Command Prompt as Administrator
- Check Docker Desktop is running with proper permissions

**Node.js/Python Version Issues:**
- Verify versions: `node --version` and `python --version`
- Use version managers like `nvm` (Node.js) or `pyenv` (Python)

**Docker Issues:**
- Ensure Docker Desktop is running
- Check available disk space
- Restart Docker if needed

---

## 💡 Tips

- **IDE Setup**: Consider using VS Code with recommended extensions for this monorepo
- **Environment Variables**: Copy `.env.example` to `.env` and configure as needed
- **Hot Reload**: Development servers support hot reload for faster development
- **Logs**: Use `docker logs <container_name>` to debug Docker services
- **Windows Performance**: Consider using WSL2 for better performance with Docker

---

## TODO

- [ ] Separate dependencies for Python and TypeScript packages
- [ ] Optimize Docker image size and layers
- [ ] Remove unnecessary and unused dependencies
- [ ] Add environment-specific configuration files
- [ ] Implement health checks for all services
- [ ] Add automated testing pipeline
- [ ] Refactor codebase:
    - [ ] Separate service logic
    - [ ] Create repository, service, utils, middleware, etc.
    - [ ] Structure code for maintainability and clarity
- [ ] Add Windows-specific Docker optimization
- [ ] Create development environment setup scripts
