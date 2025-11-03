import os
import subprocess
import time
import secrets
from flask import Flask, request, render_template_string

# Directory where notes and the Git repository will live
REPO_DIR = "notes_repo"
NOTE_FILENAME = "my_first_note.md"

NOTE_PATH = os.path.join(REPO_DIR, NOTE_FILENAME)

app = Flask(__name__)


def setup_repo():
    # to initialize the repository and git if they don't exist.
    if not os.path.exists(REPO_DIR):
        os.makedirs(REPO_DIR)
        print(f"Created directory: {REPO_DIR}")

    git_init_path = os.path.join(REPO_DIR, ".git")
    if not os.path.exists(git_init_path):
        try:
            # Initialize Git repository
            subprocess.run(
                ["git", "init"],
                cwd=REPO_DIR,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"Initialized Git repository in {REPO_DIR}")
        except subprocess.CalledProcessError as e:
            print(f"Error initializing Git: {e}")
            return False
        except FileNotFoundError:
            print(
                "Error: Git command not found. Please ensure Git is installed and in your system PATH."
            )
            return False

    # Ensure the note file exists so the app doesn't crash on the first load
    if not os.path.exists(NOTE_PATH):
        with open(NOTE_PATH, "w", encoding="utf-8") as f:
            f.write(
                "# Welcome to your Version-Controlled Notebook!\n\nStart typing here. Changes will be automatically committed to Git."
            )
        # Commit the initial file
        run_git_commit("Initial setup of the notebook file.")

    return True


def run_git_commit(message):
    """Executes git add and git commit commands."""
    try:
        # Step 1: Stage all changes
        subprocess.run(
            ["git", "add", "."],
            cwd=REPO_DIR,
            check=True,
            capture_output=True,
            text=True,
        )

        # Step 2: Commit staged changes
        # Use --allow-empty-message and --no-verify for simpler use case
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_DIR,
            check=False,  # Don't raise error on no changes (common during autosave)
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            if "nothing to commit" in result.stdout:
                return f"No changes detected (Autosave attempted at {time.strftime('%H:%M:%S')})."
            return f"Change committed successfully! ({message})"
        else:
            return f"Git Commit Failed: {result.stderr.strip()}"

    except subprocess.CalledProcessError as e:
        return f"System error during Git operation: {e.stderr}"
    except FileNotFoundError:
        return "System error: Git executable not found."


# Run setup once when the application starts
if not setup_repo():
    print("Application failed to set up the Git repository. Exiting.")
    exit(1)


@app.route("/", methods=["GET"])
def index():
    try:
        with open(NOTE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        content = f"Error loading file: {e}"

    return render_template_string(HTML_TEMPLATE, note_content=content)


@app.route("/save", methods=["POST"])
def save_and_commit():
    # to handle the AJAX save request, write the file, and commit the change.
    new_content = request.form.get("content", "")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"Autosave: {timestamp}"

    # 1. Write the new content to the file
    try:
        with open(NOTE_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return {"status": "error", "message": f"File write failed: {e}"}

    # 2. Run Git add and commit
    commit_status = run_git_commit(commit_message)

    return {"status": "success", "message": commit_status}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Git Notebook - {{ NOTE_FILENAME }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* Use Inter font */
        body { font-family: 'Inter', sans-serif; }
        /* Style the textarea for a modern look */
        #editor {
            resize: none;
            height: calc(100vh - 120px); /* Full height minus header/status */
            font-size: 1rem;
            line-height: 1.5;
            tab-size: 4;
            transition: all 0.3s;
        }
        #editor:focus {
            outline: none;
            box-shadow: 0 0 0 4px rgba(66, 153, 225, 0.5); /* Blue focus ring */
        }
    </style>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        'primary-blue': '#4c51bf',
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-gray-100 p-4">

    <div class="max-w-4xl mx-auto">
        <header class="mb-4 flex justify-between items-center p-3 bg-white shadow-md rounded-lg">
            <h1 class="text-xl font-bold text-gray-800">Git Auto-Commit Notebook</h1>
            <p class="text-sm font-medium text-primary-blue bg-blue-100 px-3 py-1 rounded-full">File: {{ NOTE_FILENAME }}</p>
        </header>

        <textarea id="editor" name="editor"
                class="w-full p-4 border border-gray-300 rounded-lg shadow-inner focus:border-primary-blue"
                placeholder="Start writing your notes here...">{{ note_content }}</textarea>

        <div id="status-message" class="mt-3 p-3 text-sm rounded-lg bg-yellow-100 text-yellow-800 shadow-md transition-opacity duration-300">
            Waiting for input...
        </div>

    </div>

    <script>
        const editor = document.getElementById('editor');
        const statusMessage = document.getElementById('status-message');
        let saveTimer = null;
        const SAVE_DELAY_MS = 2000; // 2 seconds delay after typing stops

        // --- Core Save/Commit Logic ---
        async function saveContent() {
            statusMessage.textContent = 'Saving and committing changes...';
            statusMessage.className = 'mt-3 p-3 text-sm rounded-lg bg-blue-100 text-primary-blue shadow-md';

            const content = editor.value;

            try {
                const formData = new FormData();
                formData.append('content', content);

                // Send the content to the Flask backend
                const response = await fetch('/save', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.status === 'success') {
                    statusMessage.textContent = 'Saved! ' + result.message;
                    statusMessage.className = 'mt-3 p-3 text-sm rounded-lg bg-green-100 text-green-800 shadow-md';
                } else {
                    statusMessage.textContent = 'Save Error: ' + result.message;
                    statusMessage.className = 'mt-3 p-3 text-sm rounded-lg bg-red-100 text-red-800 shadow-md';
                }

            } catch (error) {
                statusMessage.textContent = 'Network Error: Could not connect to server.';
                statusMessage.className = 'mt-3 p-3 text-sm rounded-lg bg-red-100 text-red-800 shadow-md';
                console.error('Fetch error:', error);
            }
        }

        // --- Debouncing Logic (The 'Autosave' Mechanism) ---
        // This is key to requirement 2: "As soon as you stop writing..."
        editor.addEventListener('keyup', () => {
            // Clear the previous timer (the user is still typing)
            if (saveTimer) {
                clearTimeout(saveTimer);
            }

            statusMessage.textContent = 'Typing... Waiting to auto-commit.';
            statusMessage.className = 'mt-3 p-3 text-sm rounded-lg bg-yellow-100 text-yellow-800 shadow-md';


            // Set a new timer. If the user doesn't press another key before the delay, saveContent runs.
            saveTimer = setTimeout(saveContent, SAVE_DELAY_MS);
        });

        // Initial status message
        window.onload = () => {
            statusMessage.textContent = 'Application loaded. Start typing in the editor.';
        };
    </script>

</body>
</html>
"""

if __name__ == "__main__":
    # to access the history of the changes by go to the 'notes_repo' directory
    # and run 'git log' in your terminal!
    print(f"\n--- Note Taker App Ready ---")
    print(f"Notes are stored in the '{REPO_DIR}' directory.")
    app.run(debug=True, use_reloader=False)
