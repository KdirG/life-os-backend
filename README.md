# Personal AI Life OS and Automation Assistant

This project provides a personal Life OS infrastructure consisting of a FastAPI backend running on a cloud server, a mobile-first Progressive Web App (PWA) client interface, a markdown database synced via GitHub with Obsidian, and a local automation agent running on your computer.

## Project Architecture

1. **Backend (FastAPI):** Hosts the API services, coordinates communication between modules, handles speech-to-text processing, and integrates with the Google Gemini API to parse natural language inputs.
2. **Frontend (PWA):** A responsive, light-themed web interface built with standard HTML5 and JavaScript. It features an offline-first Service Worker, registers Native Web Push subscriptions, and can be installed directly onto mobile devices.
3. **Database (Obsidian & GitHub):** All logs, goals, habits, curriculum study paths, and sport plans are stored as markdown files (.md) in your private GitHub repository, allowing complete local data ownership and seamless editing via Obsidian.
4. **PC Node (Automation Client):** A lightweight Python script running on your local machine that listens for remote commands (e.g., download torrents, fetch media using yt-dlp, trigger Steam installations) and executes them locally.

---

## Features and Modules

### 1. Dietary and Macro Logging
- Supports voice or text entry (e.g., "I ate 200g chicken breast and 100g rice").
- Utilizes the Google Gemini model to compute nutrition metrics, write structured calorie/protein data logs, and automatically update Yemek_Log.md.

### 2. Habit Tracker
- Interactive checkboxes that track daily streaks.
- Synchronizes habit completions with Aliskanliklar.md.

### 3. Study and Curriculum Planner
- Track study topics, syllabus modules, and course progress percentages.
- Organize subjects with collapsible accordion interfaces.
- Synchronizes with Mufredat.md.

### 4. Weekly Workout Plan
- Create daily training schedules, browse exercises, and track workouts.
- Pulls exercise descriptions, target muscles, and equipment data from the yuhonas/free-exercise-db database.
- Displays preloaded start-and-end pose alternating animations.
- Launches one-click YouTube tutorial video searches for any exercise.
- Synchronizes with Spor.md.

### 5. Nutrition & Calorie Targets
- Configure weekly calorie and protein intake limits.
- Automatically synchronizes targets across multiple browsers and devices using Hedefler.md as a cloud database.

### 6. Remote PC Automation
- Remotely queue downloads and PC automation tasks from the mobile assistant interface.
- Executes torrent downloads (via libtorrent) and video fetching (via yt-dlp) directly on your local computer.

### 7. Multi-User Integration
- Allows multiple users to use the same FastAPI backend independently.
- Configurable GitHub Personal Access Token (PAT), username, and repository name settings inside the client interface, passing parameters via custom request headers to route actions to the user's personal vault.

---

## Installation Steps

### 1. GitHub Vault Setup
- Create a private GitHub repository (e.g., MyLifeOSVault).
- Create empty markdown files named Yemek_Log.md, Hedefler.md, Aliskanliklar.md, Mufredat.md, and Spor.md, then commit them.

### 2. Backend Setup
1. Clone this repository to your server or local machine.
2. Rename .env.example to .env and fill in the parameters:
   - **GEMINI_API_KEY:** Get a free API key from Google AI Studio.
   - **GITHUB_TOKEN:** Generate a Personal Access Token (Classic) with repository scopes.
   - **GITHUB_REPO_OWNER / NAME:** Your GitHub username and vault repository name.
   - **VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY:** Generated VAPID keys for PyWebPush.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the backend:
   ```bash
   uvicorn main:app --reload
   ```

### 3. Frontend Setup
1. Configure index.html to point to your FastAPI backend URL.
2. Deploy the frontend files (index.html, manifest.json, sw.js) to Vercel, Netlify, or GitHub Pages.
3. Open the deployed page on a mobile browser, select "Add to Home Screen" to install it as a PWA, and grant notification permissions when prompted.

### 4. PC Node Setup
1. Ensure Python is installed on your local computer.
2. Install dependencies:
   ```bash
   pip install requests libtorrent yt-dlp
   ```
3. Set the BACKEND_URL in pc_node.py to match your backend.
4. Run the node:
   ```bash
   python pc_node.py
   ```
