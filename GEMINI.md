# GEMINI.md - Project Context: UpaPasta

## Project Overview
**UpaPasta** is a sophisticated Python-based CLI tool designed to automate the complete workflow of uploading files and directories to the Usenet. It serves as a high-level orchestrator for several high-performance binary utilities, managing the entire lifecycle of a Usenet post from metadata generation to post-upload cleanup.

### Key Technologies
- **Language:** Python 3.8+ (Core logic and orchestration)
- **Primary Dependencies (Binaries):**
  - `rar`: For multi-part archive creation (RAR5).
  - `nyuu`: For NNTP/Usenet uploading and NZB generation.
  - `parpar` (preferred) or `par2`: For Reed-Solomon error correction (PAR2) generation.
  - `ffmpeg` / `ffprobe`: For extracting video metadata.
  - `mediainfo`: For detailed technical NFO generation.
- **Configuration:** Environment variables managed via `~/.config/upapasta/.env`.

### Architecture & Workflow
The project follows a modular, procedural architecture where `main.py` acts as the `UpaPastaOrchestrator`. The workflow is strictly defined as follows:
1.  **Metadata (NFO):** Generates technical descriptions (`nfo.py`).
2.  **Archiving (RAR):** Packs content into volumes, optionally with encryption (`makerar.py`).
3.  **Parity (PAR2):** Calculates optimal slice sizes and generates redundancy files (`makepar.py`).
4.  **Obfuscation:** Atomic renaming of files for privacy before parity generation.
5.  **Upload:** Invokes `nyuu` to send articles to NNTP servers and generate the NZB (`upfolder.py`).
6.  **Finalization:** Injects passwords into the NZB and fixes XML subjects for path retention (`nzb.py`).
7.  **Resource Management:** Dynamically scales threads and memory usage based on available system resources and payload size (`resources.py`).

---

## Building and Running

### Development Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e .
```

### Key Commands
- **Run Application:** `upapasta /path/to/folder_or_file`
- **Configuration Setup:** Run `upapasta` for the first time to trigger the interactive setup.
- **Testing:** `pytest` (Tests are located in the `tests/` directory).
- **Cleanup (Manual):** `upapasta /path/to/input --skip-upload` (or use internal cleanup logic).

---

## Development Conventions

### General Principles
- **Subprocess-First:** Most heavy lifting is delegated to external binaries. Always use `managed_popen` from `upapasta._process` (never bare `subprocess.Popen`) so that child processes are always terminated on `KeyboardInterrupt` or exceptions.
- **Statelessness:** The tool avoids maintaining a local database for state, relying on the presence of physical files (`.rar`, `.par2`) to determine progress or required actions.
- **Dynamic Optimization:** Hardcoded limits should be avoided. Use `resources.py` to calculate optimal thread counts and memory limits based on the host machine.
- **Security:** Never log NNTP passwords. Use `secrets` for random password generation when obfuscating.

### Coding Style
- **Type Hinting:** Use type hints for all function signatures. Use `from __future__ import annotations` for compatibility with older Python versions (3.8+).
- **Logging:** Use the `upapasta` named logger. Avoid `print()` for debugging; use `logger.debug()` instead.
- **Error Handling:** Differentiate between transient errors (eligible for retry) and fatal errors (input missing, binary missing).

### Testing Practices
- **Mocking:** Tests should mock subprocess calls to avoid requiring `rar` or `nyuu` binaries in CI environments.
- **Data-Driven:** Use `tests/test_data/` for representative input structures.

---

## Project Status & Roadmap (Internal Context)
- **Current Version:** 0.9.0 (Beta)
- **Critical Focus:** Improving terminal output parsing robustness (progress bars via regex are fragile against tool version changes).
- **Upcoming Features:** `--resume` mode, webhook notifications (Discord/Telegram), TMDb metadata integration, and upload history tracking.
