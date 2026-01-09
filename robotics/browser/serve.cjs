#!/usr/bin/env node
/**
 * Zero-dependency static file server for the WASM robot simulation.
 *
 * Usage:
 *   node serve.js [port]
 *
 * Example:
 *   node serve.js 8080
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.argv[2]) || 3000;
const DIST_DIR = path.join(__dirname, 'dist');

const MIME_TYPES = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.wasm': 'application/wasm',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

// Check if dist folder exists
if (!fs.existsSync(DIST_DIR)) {
  console.error('\x1b[31mError: dist/ folder not found.\x1b[0m');
  console.error('Run "npm run build" first to create the production build.');
  process.exit(1);
}

const server = http.createServer((req, res) => {
  let filePath = path.join(DIST_DIR, req.url === '/' ? 'index.html' : req.url);

  // Security: prevent directory traversal
  if (!filePath.startsWith(DIST_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  // Headers required for WASM streaming compilation
  const headers = {
    'Content-Type': contentType,
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
  };

  fs.readFile(filePath, (err, content) => {
    if (err) {
      if (err.code === 'ENOENT') {
        // Try index.html for SPA routing
        fs.readFile(path.join(DIST_DIR, 'index.html'), (err2, content2) => {
          if (err2) {
            res.writeHead(404);
            res.end('Not Found');
          } else {
            res.writeHead(200, { ...headers, 'Content-Type': 'text/html' });
            res.end(content2);
          }
        });
      } else {
        res.writeHead(500);
        res.end('Server Error');
      }
    } else {
      res.writeHead(200, headers);
      res.end(content);
    }
  });
});

server.listen(PORT, () => {
  console.log('\x1b[32m╔════════════════════════════════════════════════════════╗\x1b[0m');
  console.log('\x1b[32m║\x1b[0m  🤖 Ontology-Driven Robot Simulation | TesseraiDB      \x1b[32m║\x1b[0m');
  console.log('\x1b[32m╠════════════════════════════════════════════════════════╣\x1b[0m');
  console.log('\x1b[32m║\x1b[0m                                                        \x1b[32m║\x1b[0m');
  console.log(`\x1b[32m║\x1b[0m  Open in browser: \x1b[36mhttp://localhost:${PORT}/\x1b[0m              \x1b[32m║\x1b[0m`);
  console.log('\x1b[32m║\x1b[0m                                                        \x1b[32m║\x1b[0m');
  console.log('\x1b[32m║\x1b[0m  Press Ctrl+C to stop                                  \x1b[32m║\x1b[0m');
  console.log('\x1b[32m╚════════════════════════════════════════════════════════╝\x1b[0m');
});
