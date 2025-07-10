#!/usr/bin/env node

import { spawn } from 'child_process';

interface ServiceConfig {
    name: string;
    port: number;
    script: string;
}

const SERVICES: Record<string, ServiceConfig> = {
    rag: {
        name: 'RAG Server',
        port: 8002,
        script: 'dev:rag'
    },
    summarization: {
        name: 'Summarization Server',
        port: 8003,
        script: 'dev:summarization'
    }
};

type ServiceName = keyof typeof SERVICES;

function showHelp(): void {
    console.log(`
MCP Servers Management Script

Usage: npx tsx manage.ts <command> [service]

Commands:
  start <service>    Start a specific service (rag, summarization)
  start all         Start all services
  stop              Stop all running services
  status            Show status of all services
  help              Show this help message

Services:
  rag              RAG Server (port 8002)
  summarization    Summarization Server (port 8003)
  all              All services

Examples:
  npx tsx manage.ts start rag
  npx tsx manage.ts start all
  npx tsx manage.ts status
`);
}

function isValidService(serviceName: string): serviceName is ServiceName {
    return serviceName in SERVICES;
}

function startService(serviceName: string): void {
    if (!isValidService(serviceName)) {
        console.error(`Unknown service: ${serviceName}`);
        console.error(`Available services: ${Object.keys(SERVICES).join(', ')}`);
        return;
    }

    const service = SERVICES[serviceName];
    console.log(`Starting ${service.name} on port ${service.port}...`);

    const child = spawn('npm', ['run', service.script], {
        stdio: 'inherit',
        shell: true
    });

    child.on('error', (error) => {
        console.error(`Failed to start ${service.name}:`, error);
    });

    child.on('close', (code) => {
        if (code !== 0) {
            console.error(`${service.name} exited with code ${code}`);
        }
    });
}

function startAllServices(): void {
    console.log('Starting all MCP services...');

    const child = spawn('npm', ['run', 'dev:all'], {
        stdio: 'inherit',
        shell: true
    });

    child.on('error', (error) => {
        console.error('Failed to start services:', error);
    });

    child.on('close', (code) => {
        if (code !== 0) {
            console.error(`Services exited with code ${code}`);
        }
    });
}

function checkStatus(): void {
    console.log('Checking MCP services status...');

    Object.entries(SERVICES).forEach(([key, service]) => {
        console.log(`${service.name}: Check http://localhost:${service.port}/health`);
    });

    console.log('\nTo check if services are actually running:');
    Object.entries(SERVICES).forEach(([key, service]) => {
        console.log(`curl http://localhost:${service.port}/health`);
    });
}

function stopServices(): void {
    console.log('Stopping MCP services...');
    console.log('Use Ctrl+C in the terminal where services are running, or:');

    Object.entries(SERVICES).forEach(([key, service]) => {
        console.log(`pkill -f "${service.script}"`);
    });
}

// Parse command line arguments
const [,, command, service] = process.argv;

switch (command) {
    case 'start':
        if (service === 'all') {
            startAllServices();
        } else if (service && isValidService(service)) {
            startService(service);
        } else {
            console.error('Please specify a valid service or "all"');
            console.error(`Available services: ${Object.keys(SERVICES).join(', ')}`);
            showHelp();
        }
        break;

    case 'stop':
        stopServices();
        break;

    case 'status':
        checkStatus();
        break;

    case 'help':
    case undefined:
        showHelp();
        break;

    default:
        console.error(`Unknown command: ${command}`);
        showHelp();
}