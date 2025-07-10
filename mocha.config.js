// mocha.config.js
module.exports = {
    require: 'ts-node/register', // Allows you to run .ts files
    extension: ['ts'], // File extensions to compile
    spec: 'tests/**/*.test.ts', // Path to test files
    timeout: 2000, // Test time threshold
    ui: 'bdd', // Mocha interface style
    colors: true, // Enable colors in the output
  };