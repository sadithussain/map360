Architecture & Project Reference Document
Project Overview
This project is a web-based, gamified collaborative 3D mapping platform. It combines the location-tracking social dynamics of Life360, the interactive place-logging of Beli, and a user-generated version of Apple Maps' 3D cityscapes.
The core loop allows users in private groups to visit real-world locations, capture sparse visual data (3 specific photos or a 5-second video), and upload it. The system processes this media to generate a custom 3D model of the storefront or building, which is then dynamically injected into the group's shared map. Over time, the group's "world" transforms from a blank, untextured grey 3D mesh into a vibrant, fully populated 3D cityscape driven entirely by user discoveries.
Core User Workflows
The Capture: Users access the Progressive Web App (PWA) via their mobile browser, locate a point of interest, and use the device's native camera to capture specific angles or a sweeping video.
The Generation: Captured media is offloaded to the backend, where a machine learning pipeline interprets the sparse geometric data and constructs a 3D model.
The Rendering: The model is bound to real-world GPS coordinates and rendered on the client side, overwriting the default map geometry at that location.
The Social Loop: Updates are pushed to the user's selected "Groups," allowing friends to see the newly discovered and modeled location in their shared world.

The Technology Stack
1. Frontend & Hosting (The Client)
Framework: Next.js (TypeScript). This provides robust API routing and a highly component-driven structure for your UI.
Architecture: Progressive Web App (PWA). This bypasses all App Store fees and review processes while granting users the ability to "install" the app directly to their home screens with native-like features.
Media Capture: HTML5 MediaDevices API. Built directly into the browser to access the device camera for capturing the necessary storefront photos or video sweeps.
Hosting: Vercel (Hobby Tier). Next.js's native platform offers seamless GitHub integration, automated CI/CD deployments, and serverless functions for lightweight API calls at zero cost.
2. Spatial Engine & 3D Rendering (The World)
Base Map Provider: MapLibre GL JS. A fully open-source, free fork of Mapbox. This acts as the customizable canvas, allowing you to strip away standard map aesthetics and render the untextured, grey 3D building extrusions.
3D Runtime Environment: React Three Fiber (R3F). A React wrapper for Three.js that allows you to declaratively build 3D scenes. It integrates perfectly with Next.js, allowing you to overlay your web UI (like the group selection menus) on top of the 3D map canvas and dynamically inject the generated .glb files.
3. Database, Auth & Storage (The Data Layer)
Backend-as-a-Service: Supabase (Free Tier). This acts as the central hub for your data, replacing the need for a dedicated, hosted backend server.
Database: PostgreSQL. Handles all relational data (Users, Groups, Worlds, and Locations).
Geospatial Engine: PostGIS. A PostgreSQL extension critical for this app. It handles complex spatial queries, such as rendering all custom 3D models within a user's current viewport bounding box.
Authentication: Supabase Auth. Provides secure, out-of-the-box user login and session management.
Blob Storage: Supabase Storage. Provides up to 1GB of free storage to hold user-uploaded media and the final compiled 3D model assets.
4. Machine Learning Pipeline (The 3D Generation)
Scripting Language: Python. Utilized for handling the image-to-3D generation scripts (like stable-fast-3d or open-source NeRF models).
Compute Environment: Google Colab + Ngrok. Writing the generation scripts in a Colab notebook grants free access to Nvidia T4 GPUs. Ngrok exposes the notebook as a temporary public API endpoint, allowing your Vercel frontend to send image payloads directly to Colab for processing.

