# Mobile Portability Guide

This document outlines strategies for porting the TesseraiDB Robot Simulation to iOS and Android devices.

## Current Architecture

The browser simulation uses:
- **Vite + TypeScript** - Standard web tooling
- **Oxigraph WASM** - In-browser SPARQL reasoning via WebAssembly
- **Canvas 2D** - Rendering layer
- **Vanilla TypeScript** - No framework dependencies

### Current Limitations for Mobile
- Fixed 320px side panel assumes desktop width
- No touch event handlers (click only)
- Canvas dimensions not responsive
- No offline support (requires network for initial WASM load)
- Not installable as app

---

## Option 1: Progressive Web App (PWA)

**Recommended first step. Effort: 1-2 days.**

PWA allows the existing web app to behave like a native app on mobile devices while reusing 100% of the existing codebase.

### Required Changes

#### 1. Add Web App Manifest

Create `public/manifest.json`:
```json
{
  "name": "TesseraiDB Robot Simulation",
  "short_name": "RoboSim",
  "description": "Ontology-driven robot simulation powered by TesseraiDB",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#4ecdc4",
  "orientation": "any",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-maskable-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ]
}
```

Link in `index.html`:
```html
<link rel="manifest" href="/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="/icons/icon-192.png">
```

#### 2. Add Service Worker for Offline Support

Create `public/sw.js`:
```javascript
const CACHE_NAME = 'robosim-v1';
const ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  // WASM files (critical for offline)
  '/node_modules/oxigraph/web_bg.wasm',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});
```

Register in `main.ts`:
```typescript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}
```

#### 3. Make CSS Responsive

Add to `index.html` styles:
```css
/* Mobile-first responsive layout */
@media (max-width: 768px) {
  .container {
    flex-direction: column;
    gap: 10px;
  }

  .side-panel {
    width: 100%;
    order: 2; /* Move below canvas on mobile */
  }

  canvas {
    width: 100% !important;
    height: auto !important;
    max-height: 50vh;
  }

  .ontology-panel {
    max-height: 40vh;
  }

  /* Bottom sheet style for controls */
  .panel {
    border-radius: 16px 16px 0 0;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    max-height: 45vh;
    overflow-y: auto;
  }
}

/* Touch-friendly buttons */
@media (pointer: coarse) {
  button {
    min-height: 44px; /* Apple HIG touch target */
    min-width: 44px;
  }

  .tab-btn {
    padding: 12px 16px;
  }
}
```

#### 4. Add Touch Event Handlers

Update `main.ts`:
```typescript
function setupEventHandlers(): void {
  const startBtn = document.getElementById("startBtn")!;
  const pauseBtn = document.getElementById("pauseBtn")!;
  const resetBtn = document.getElementById("resetBtn")!;

  // Support both click and touch
  const addTapHandler = (el: HTMLElement, handler: () => void) => {
    el.addEventListener('click', handler);
    el.addEventListener('touchend', (e) => {
      e.preventDefault(); // Prevent double-firing
      handler();
    });
  };

  addTapHandler(startBtn, () => { /* ... */ });
  addTapHandler(pauseBtn, () => { /* ... */ });
  addTapHandler(resetBtn, () => { /* ... */ });
}
```

#### 5. Dynamic Canvas Sizing

Update `renderer.ts`:
```typescript
export class Renderer {
  private resizeObserver: ResizeObserver;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d")!;

    // Responsive canvas sizing
    this.resizeObserver = new ResizeObserver(() => this.handleResize());
    this.resizeObserver.observe(canvas.parentElement!);
    this.handleResize();
  }

  private handleResize(): void {
    const container = this.canvas.parentElement!;
    const maxWidth = Math.min(container.clientWidth - 40, 800);
    const aspectRatio = this.worldHeight / this.worldWidth;

    this.canvas.width = maxWidth;
    this.canvas.height = maxWidth * aspectRatio;
    this.cellSize = maxWidth / this.worldWidth;
  }
}
```

### PWA Testing

```bash
# Build for production
npm run build

# Test with a local HTTPS server (required for service workers)
npx serve dist --ssl

# Or use Lighthouse in Chrome DevTools to audit PWA compliance
```

---

## Option 2: Capacitor Native Wrapper

**For App Store distribution. Effort: 3-5 days.**

Capacitor wraps the web app in a native container, providing access to native APIs while reusing the web codebase.

### Setup

```bash
# Install Capacitor
npm install @capacitor/core @capacitor/cli

# Initialize
npx cap init "Robot Simulation" com.tesserai.robotsim --web-dir=dist

# Add platforms
npx cap add ios
npx cap add android
```

### Configuration

Edit `capacitor.config.ts`:
```typescript
import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.tesserai.robotsim',
  appName: 'Robot Simulation',
  webDir: 'dist',
  server: {
    androidScheme: 'https'
  },
  ios: {
    contentInset: 'always',
    allowsLinkPreview: false
  },
  android: {
    allowMixedContent: true
  }
};

export default config;
```

### Build & Deploy

```bash
# Build web assets
npm run build

# Sync to native projects
npx cap sync

# Open in Xcode (iOS)
npx cap open ios

# Open in Android Studio
npx cap open android
```

### Native Enhancements (Optional)

```bash
# Haptic feedback
npm install @capacitor/haptics

# Splash screen
npm install @capacitor/splash-screen

# Status bar control
npm install @capacitor/status-bar
```

Usage:
```typescript
import { Haptics, ImpactStyle } from '@capacitor/haptics';

// Haptic feedback on object collection
function onObjectCollected(): void {
  Haptics.impact({ style: ImpactStyle.Light });
}
```

---

## Option 3: Native Rust Bindings

**For maximum performance and native UI. Effort: 2-4 weeks.**

This approach compiles Oxigraph directly to native iOS/Android libraries, bypassing WASM entirely.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Swift UI / Jetpack Compose               │
├─────────────────────────────────────────────────────────────┤
│                    Swift / Kotlin Bindings                  │
├─────────────────────────────────────────────────────────────┤
│                         C FFI Layer                         │
├─────────────────────────────────────────────────────────────┤
│                   Oxigraph (Rust Library)                   │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Add Mobile Targets

```bash
# iOS targets
rustup target add aarch64-apple-ios          # iOS devices (ARM64)
rustup target add aarch64-apple-ios-sim      # iOS Simulator (M1/M2 Mac)
rustup target add x86_64-apple-ios           # iOS Simulator (Intel Mac)

# Android targets
rustup target add aarch64-linux-android      # Android ARM64
rustup target add armv7-linux-androideabi    # Android ARMv7 (older devices)
rustup target add x86_64-linux-android       # Android emulator
rustup target add i686-linux-android         # Android x86 (rare)
```

### Step 2: Create FFI Wrapper Crate

Create `oxigraph-mobile/Cargo.toml`:
```toml
[package]
name = "oxigraph-mobile"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["staticlib", "cdylib"]

[dependencies]
oxigraph = "0.4"

[build-dependencies]
cbindgen = "0.26"
```

Create `oxigraph-mobile/src/lib.rs`:
```rust
use oxigraph::io::RdfFormat;
use oxigraph::model::*;
use oxigraph::sparql::QueryResults;
use oxigraph::store::Store;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::ptr;

/// Opaque handle to an Oxigraph store
pub struct OxigraphStore {
    store: Store,
}

/// Create a new in-memory store
/// Returns null on failure
#[no_mangle]
pub extern "C" fn oxigraph_store_new() -> *mut OxigraphStore {
    match Store::new() {
        Ok(store) => Box::into_raw(Box::new(OxigraphStore { store })),
        Err(_) => ptr::null_mut(),
    }
}

/// Load Turtle data into the store
/// Returns 0 on success, -1 on failure
#[no_mangle]
pub extern "C" fn oxigraph_load_turtle(
    store: *mut OxigraphStore,
    turtle_data: *const c_char,
) -> i32 {
    if store.is_null() || turtle_data.is_null() {
        return -1;
    }

    let store = unsafe { &mut *store };
    let turtle = unsafe {
        match CStr::from_ptr(turtle_data).to_str() {
            Ok(s) => s,
            Err(_) => return -1,
        }
    };

    match store.store.load_from_reader(RdfFormat::Turtle, turtle.as_bytes()) {
        Ok(_) => 0,
        Err(_) => -1,
    }
}

/// Execute a SPARQL query
/// Returns JSON string (caller must free with oxigraph_string_free)
/// Returns null on failure
#[no_mangle]
pub extern "C" fn oxigraph_query(
    store: *mut OxigraphStore,
    sparql: *const c_char,
) -> *mut c_char {
    if store.is_null() || sparql.is_null() {
        return ptr::null_mut();
    }

    let store = unsafe { &*store };
    let query = unsafe {
        match CStr::from_ptr(sparql).to_str() {
            Ok(s) => s,
            Err(_) => return ptr::null_mut(),
        }
    };

    match store.store.query(query) {
        Ok(results) => {
            let json = match results {
                QueryResults::Solutions(solutions) => {
                    let rows: Vec<_> = solutions
                        .filter_map(|s| s.ok())
                        .map(|solution| {
                            solution
                                .iter()
                                .map(|(var, term)| {
                                    format!("\"{}\": \"{}\"", var.as_str(), term)
                                })
                                .collect::<Vec<_>>()
                                .join(", ")
                        })
                        .map(|row| format!("{{{}}}", row))
                        .collect();
                    format!("[{}]", rows.join(", "))
                }
                QueryResults::Boolean(b) => format!("{{\"result\": {}}}", b),
                QueryResults::Graph(_) => "[]".to_string(),
            };

            match CString::new(json) {
                Ok(s) => s.into_raw(),
                Err(_) => ptr::null_mut(),
            }
        }
        Err(e) => {
            let error_json = format!("{{\"error\": \"{}\"}}", e);
            CString::new(error_json).map(|s| s.into_raw()).unwrap_or(ptr::null_mut())
        }
    }
}

/// Insert a triple into the store
#[no_mangle]
pub extern "C" fn oxigraph_insert(
    store: *mut OxigraphStore,
    subject: *const c_char,
    predicate: *const c_char,
    object: *const c_char,
) -> i32 {
    if store.is_null() || subject.is_null() || predicate.is_null() || object.is_null() {
        return -1;
    }

    let store = unsafe { &mut *store };

    let s = unsafe { CStr::from_ptr(subject).to_str().unwrap_or("") };
    let p = unsafe { CStr::from_ptr(predicate).to_str().unwrap_or("") };
    let o = unsafe { CStr::from_ptr(object).to_str().unwrap_or("") };

    let subject = match NamedNode::new(s) {
        Ok(n) => n,
        Err(_) => return -1,
    };
    let predicate = match NamedNode::new(p) {
        Ok(n) => n,
        Err(_) => return -1,
    };

    // Try as IRI first, then as literal
    let object: Term = NamedNode::new(o)
        .map(Term::from)
        .unwrap_or_else(|_| Literal::new_simple_literal(o).into());

    match store.store.insert(&Quad::new(
        subject,
        predicate,
        object,
        GraphName::DefaultGraph,
    )) {
        Ok(_) => 0,
        Err(_) => -1,
    }
}

/// Free a store instance
#[no_mangle]
pub extern "C" fn oxigraph_store_free(store: *mut OxigraphStore) {
    if !store.is_null() {
        unsafe { drop(Box::from_raw(store)) };
    }
}

/// Free a string returned by oxigraph functions
#[no_mangle]
pub extern "C" fn oxigraph_string_free(s: *mut c_char) {
    if !s.is_null() {
        unsafe { drop(CString::from_raw(s)) };
    }
}
```

### Step 3: Generate C Header

Create `oxigraph-mobile/build.rs`:
```rust
use std::env;
use std::path::PathBuf;

fn main() {
    let crate_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let out_path = PathBuf::from(&crate_dir).join("include");

    std::fs::create_dir_all(&out_path).unwrap();

    cbindgen::Builder::new()
        .with_crate(crate_dir)
        .with_language(cbindgen::Language::C)
        .generate()
        .expect("Unable to generate C bindings")
        .write_to_file(out_path.join("oxigraph.h"));
}
```

Generated `include/oxigraph.h`:
```c
#ifndef OXIGRAPH_H
#define OXIGRAPH_H

#include <stdint.h>

typedef struct OxigraphStore OxigraphStore;

OxigraphStore* oxigraph_store_new(void);

int32_t oxigraph_load_turtle(OxigraphStore* store, const char* turtle_data);

char* oxigraph_query(OxigraphStore* store, const char* sparql);

int32_t oxigraph_insert(
    OxigraphStore* store,
    const char* subject,
    const char* predicate,
    const char* object
);

void oxigraph_store_free(OxigraphStore* store);

void oxigraph_string_free(char* s);

#endif /* OXIGRAPH_H */
```

### Step 4: Build for iOS

Create `build-ios.sh`:
```bash
#!/bin/bash
set -e

cd oxigraph-mobile

# Build for all iOS targets
cargo build --target aarch64-apple-ios --release
cargo build --target aarch64-apple-ios-sim --release
cargo build --target x86_64-apple-ios --release

# Create universal simulator library
mkdir -p target/universal-sim
lipo -create \
    target/aarch64-apple-ios-sim/release/liboxigraph_mobile.a \
    target/x86_64-apple-ios/release/liboxigraph_mobile.a \
    -output target/universal-sim/liboxigraph_mobile.a

# Create XCFramework
xcodebuild -create-xcframework \
    -library target/aarch64-apple-ios/release/liboxigraph_mobile.a \
    -headers include/ \
    -library target/universal-sim/liboxigraph_mobile.a \
    -headers include/ \
    -output OxigraphMobile.xcframework

echo "Created OxigraphMobile.xcframework"
```

### Step 5: Swift Wrapper

Create `Sources/OxigraphMobile/Oxigraph.swift`:
```swift
import Foundation

public class OxigraphStore {
    private var handle: OpaquePointer?

    public init?() {
        handle = oxigraph_store_new()
        if handle == nil {
            return nil
        }
    }

    deinit {
        if let h = handle {
            oxigraph_store_free(h)
        }
    }

    public func loadTurtle(_ turtle: String) -> Bool {
        guard let h = handle else { return false }
        return oxigraph_load_turtle(h, turtle) == 0
    }

    public func query(_ sparql: String) -> [[String: String]]? {
        guard let h = handle else { return nil }
        guard let resultPtr = oxigraph_query(h, sparql) else { return nil }

        defer { oxigraph_string_free(resultPtr) }

        let json = String(cString: resultPtr)
        guard let data = json.data(using: .utf8) else { return nil }

        return try? JSONDecoder().decode([[String: String]].self, from: data)
    }

    public func insert(subject: String, predicate: String, object: String) -> Bool {
        guard let h = handle else { return false }
        return oxigraph_insert(h, subject, predicate, object) == 0
    }
}
```

### Step 6: Build for Android

Install Android NDK and `cargo-ndk`:
```bash
# Install cargo-ndk
cargo install cargo-ndk

# Set NDK path (adjust to your installation)
export ANDROID_NDK_HOME=$HOME/Library/Android/sdk/ndk/25.2.9519653
```

Create `build-android.sh`:
```bash
#!/bin/bash
set -e

cd oxigraph-mobile

# Build for all Android targets
cargo ndk \
    -t arm64-v8a \
    -t armeabi-v7a \
    -t x86_64 \
    -o ../android/app/src/main/jniLibs \
    build --release

echo "Built Android libraries to android/app/src/main/jniLibs/"
```

### Step 7: Kotlin/JNI Wrapper

Create `android/app/src/main/java/com/tesserai/oxigraph/OxigraphStore.kt`:
```kotlin
package com.tesserai.oxigraph

import org.json.JSONArray

class OxigraphStore : AutoCloseable {
    private var handle: Long = 0

    init {
        System.loadLibrary("oxigraph_mobile")
        handle = nativeCreate()
        if (handle == 0L) {
            throw RuntimeException("Failed to create Oxigraph store")
        }
    }

    fun loadTurtle(turtle: String): Boolean {
        return nativeLoadTurtle(handle, turtle) == 0
    }

    fun query(sparql: String): List<Map<String, String>> {
        val json = nativeQuery(handle, sparql) ?: return emptyList()

        val results = mutableListOf<Map<String, String>>()
        val array = JSONArray(json)

        for (i in 0 until array.length()) {
            val obj = array.getJSONObject(i)
            val map = mutableMapOf<String, String>()
            obj.keys().forEach { key ->
                map[key] = obj.getString(key)
            }
            results.add(map)
        }

        return results
    }

    fun insert(subject: String, predicate: String, obj: String): Boolean {
        return nativeInsert(handle, subject, predicate, obj) == 0
    }

    override fun close() {
        if (handle != 0L) {
            nativeFree(handle)
            handle = 0
        }
    }

    private external fun nativeCreate(): Long
    private external fun nativeLoadTurtle(handle: Long, turtle: String): Int
    private external fun nativeQuery(handle: Long, sparql: String): String?
    private external fun nativeInsert(handle: Long, s: String, p: String, o: String): Int
    private external fun nativeFree(handle: Long)
}
```

### Alternative: Use UniFFI (Recommended)

Mozilla's UniFFI generates bindings automatically from a UDL (Universal Definition Language) file.

Create `oxigraph-mobile/src/oxigraph.udl`:
```
namespace oxigraph {
    // Empty namespace, all in interface
};

interface OxigraphStore {
    constructor();

    [Throws=OxigraphError]
    void load_turtle(string turtle);

    [Throws=OxigraphError]
    string query(string sparql);

    [Throws=OxigraphError]
    void insert(string subject, string predicate, string object_value);
};

[Error]
enum OxigraphError {
    "ParseError",
    "QueryError",
    "StoreError",
};
```

UniFFI generates Swift, Kotlin, Python, and Ruby bindings automatically.

---

## Comparison Matrix

| Aspect | PWA | Capacitor | Native Rust |
|--------|-----|-----------|-------------|
| **Effort** | 1-2 days | 3-5 days | 2-4 weeks |
| **Code Reuse** | 100% | 100% | UI: 0%, Logic: 100% |
| **Performance** | Good (WASM) | Good (WASM) | Best (Native) |
| **App Store** | No | Yes | Yes |
| **Offline** | Yes (SW) | Yes | Yes |
| **Native APIs** | Limited | Full | Full |
| **Update Process** | Instant | Instant | App Store review |
| **Binary Size** | ~5MB WASM | ~10MB | ~3MB per arch |

---

## Recommended Approach

### Phase 1: PWA (Immediate)
Make the web app responsive and installable. This provides mobile access with minimal effort and no app store friction.

### Phase 2: Capacitor (If needed)
If users need:
- Push notifications
- Background sync
- App Store presence
- Native look and feel

Wrap the PWA in Capacitor - it's additive, not a rewrite.

### Phase 3: Native Rust (Future)
Consider only if:
- Performance benchmarks show WASM is a bottleneck
- Need to support very large ontologies (100K+ triples)
- Building a commercial product requiring native UI

---

## Resources

- [Vite PWA Plugin](https://vite-pwa-org.netlify.app/) - Simplifies PWA setup
- [Capacitor Documentation](https://capacitorjs.com/docs)
- [cargo-ndk](https://github.com/aspect-rs/cargo-ndk) - Android NDK builds
- [UniFFI](https://mozilla.github.io/uniffi-rs/) - Cross-platform bindings
- [cbindgen](https://github.com/mozilla/cbindgen) - C header generation
- [Apple Human Interface Guidelines - Touch Targets](https://developer.apple.com/design/human-interface-guidelines/inputs/pointing-devices)
