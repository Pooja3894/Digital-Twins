Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau

[LICENSE](https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE)

## Getting Started

### Requirements

#### Required Software

* [Node.JS / npm](https://nodejs.org) (**N**ode **P**ackage **M**anager)

#### Required Credentials

* [Cesium access token](https://cesium.com/ion/tokens) (API token to retrieve map data from Cesium)

### Running the visualisation server in development mode:
1. Set up environment variables:
   1. ```bash
      # Copy the environment variable template
      cp .env.production .env.local
      ```
   1. Edit `.env.local` and fill in each value. The geoserver host and port should be accessible from the browser.
1. Install dependencies:
   ```bash
   npm ci
   ```
1. Serve application:
   ```bash
   npm run serve
   ```
1. Access website: [localhost:8080](https://localhost:8080)
