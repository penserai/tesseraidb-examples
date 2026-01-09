# Ontology-Driven Robot Simulation (Browser Edition)

A fully portable, browser-native robot simulation powered by TesseraiDB's WASM reasoning engine. This application runs entirely in your browser with no external server dependencies.

## Features

- **Ontology-Driven Decision Making**: Robots use SPARQL queries and SWRL-style inference rules
- **In-Browser Reasoning**: TesseraiDB WASM provides full SPARQL 1.1 support directly in the browser
- **Digital Twin Architecture**: Each robot, object, and obstacle is represented as a digital twin in the knowledge graph
- **Fog of War**: World is progressively revealed as robots explore
- **Escape Mode**: Robots detect circular/stuck behavior and break free using geometric analysis
- **Pheromone Trails**: Visual traces of robot exploration paths
- **Ontology Tab**: Live view of all digital twins, SWRL rules, and TBox axioms

## Quick Start

### Prerequisites

- Node.js 18+ (for building and serving)
- npm (comes with Node.js)

### Development Mode

```bash
# Install dependencies
npm install

# Start development server with hot reload
npm run dev

# Open http://localhost:3000
```

### Production Build

```bash
# Build optimized production bundle
npm run build

# Serve the built application
npm run serve

# Open http://localhost:3000
```

### One Command Start

```bash
# Build and serve in one step
npm start
```

## Distributing to Others

The production build creates a fully portable package that anyone with Node.js can run.

### Creating a Distribution Package

```bash
# 1. Build the application
npm run build

# 2. The distributable files are:
#    - dist/          (~3.6 MB) - the compiled application
#    - serve.cjs      (~2 KB)   - zero-dependency server

# 3. Zip these for distribution
zip -r robot-simulation.zip dist/ serve.cjs
```

### Running a Distribution Package

Recipients only need Node.js installed - no npm packages required:

```bash
# Unzip the package
unzip robot-simulation.zip

# Run the server
node serve.cjs

# Open http://localhost:3000 in browser
```

#### Custom Port

```bash
node serve.cjs 8080
# Opens at http://localhost:8080
```

#### Alternative: Python Server

If Node.js is not available but Python is:

```bash
cd dist
python3 -m http.server 3000
```

## Project Structure

```
browser/
├── src/
│   ├── main.ts              # Application entry point
│   ├── types.ts             # Core type definitions
│   ├── robot.ts             # Robot class with movement logic
│   ├── known-world.ts       # Per-robot world knowledge & loop detection
│   ├── ontology-store.ts    # TesseraiDB WASM integration
│   ├── simulation-world.ts  # Main simulation loop (SENSE → REASON → ACT)
│   └── renderer.ts          # Canvas rendering with fog of war
├── index.html               # Main HTML with embedded styles
├── package.json             # Dependencies and scripts
├── tsconfig.json            # TypeScript configuration
├── vite.config.ts           # Vite bundler configuration
├── serve.cjs                # Zero-dependency production server
└── dist/                    # Production build output
    ├── index.html
    └── assets/
        ├── index-*.js       # Bundled application (~50 KB)
        └── web_bg-*.wasm    # TesseraiDB WASM engine (~3.5 MB)
```

## Architecture

### Dual Deployment Support

This browser version complements the server-based deployment:

| Deployment | Use Case | Stack |
|------------|----------|-------|
| **Browser (this)** | Portable, offline, demos | TypeScript + TesseraiDB WASM |
| **Server** | SaaS, multi-user, persistence | Python + TesseraiDB Rust |

### Simulation Cycle

Each tick follows the SENSE → REASON → ACT pattern:

1. **SENSE**: Robots discover objects/obstacles within sensor range
2. **REASON**: Query ontology, apply inference rules, determine state
3. **ACT**: Execute action (collect, explore, escape, avoid)

### Ontology Structure

**TBox (Schema)**:
- Classes: `Robot`, `WorldObject`, `Obstacle`, `CollisionState`, `ShouldVenture`, etc.
- Properties: `positionX`, `heading`, `batteryLevel`, `coverageArea`, `pathKnottiness`, etc.

**ABox (Instances)**:
- Each robot, object, and obstacle is a digital twin with real-time state

**Inference Rules** (SWRL-style):
- `LowBattery`: batteryLevel < 20 → return home
- `AtObject`: distanceToNearest < 1.0 → can collect
- `ShouldVenture`: inLoop OR smallCoverage → escape mode
- `SeverelyCircling`: coverageArea < 8 → aggressive escape

### Loop Detection

Robots detect stuck/circling behavior using geometric analysis:

- **Convex Hull Area**: Small area despite movement = circling in place
- **Path Knottiness**: High angular change = lots of turning
- **Cell Revisits**: Visiting same cells repeatedly
- **Unique Cell Ratio**: < 40% unique cells = stuck pattern

When detected, robots enter **Escape Mode** for 25 ticks, moving away from the clutter centroid.

## Configuration

Adjustable via the UI:

| Setting | Default | Description |
|---------|---------|-------------|
| Width | 40 | World width in cells |
| Height | 25 | World height in cells |
| Robots | 5 | Number of robots (max 6) |
| Objects | 15 | Collectible objects |
| Obstacles | 20 | Stone obstacles |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server with hot reload |
| `npm run build` | Create production build in `dist/` |
| `npm run serve` | Serve production build |
| `npm run preview` | Preview production build (Vite) |
| `npm start` | Build and serve in one command |

## Browser Compatibility

Requires a modern browser with WebAssembly support:
- Chrome 57+
- Firefox 52+
- Safari 11+
- Edge 16+

## License

Part of the TesseraiDB project.
