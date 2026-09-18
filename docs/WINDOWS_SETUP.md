# Helix on Windows: first local run and initial GitHub upload

This guide targets **Windows with Python 3.13**. The application remains foundation 0.1.0; this distribution adds Windows helpers, not new AI capabilities. No GPU or cloud subscription is required to test the demo.

## Status and visibility

The GitHub connector reported `saiidz/helix` as **public and empty** during setup. No files have been uploaded by this package. For the proposed commercial/private development plan, change the repository to private before the first push: repository **Settings > General > Danger Zone > Change repository visibility > Make private**. This is your choice; the scripts do not change GitHub settings.

## Prerequisites

Install Python 3.13 for Windows and Git for Windows (or GitHub Desktop) from their official distributors. An existing installation is sufficient. The launchers do not install either product automatically. Avoid installing into a protected system directory; use a user-owned directory such as `%USERPROFILE%\source\helix`.

Official references:
- Python Windows installers: https://www.python.org/downloads/windows/
- Python virtual environments: https://docs.python.org/3.13/library/venv.html
- Git for Windows: https://git-scm.com/downloads/win
- Repository visibility: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility
- Add local code to GitHub: https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- Hardware query: https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/get-ciminstance

## First checkout

In PowerShell, one command at a time:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\source" | Out-Null
Set-Location "$env:USERPROFILE\source"
git clone https://github.com/saiidz/helix.git
Set-Location helix
```

A warning about cloning an empty repository is expected on the first checkout. Once private, authenticate using Git's supported browser/credential-manager flow. Do not paste passwords or access tokens into chat, source files, or the remote URL. If the destination already exists, inspect it instead of deleting it or cloning over it.

Extract `Helix_Windows_Starter.zip`. Copy the **contents of its inner `helix` folder** into the checkout. The checkout root must contain `README.md`, `requirements.txt`, `SETUP_WINDOWS.cmd`, and the Python package directory `helix\`. It must not have an extra wrapper folder around the whole project. Preserve the checkout's `.git` directory.

## Run locally

Double-click `SETUP_WINDOWS.cmd`. It creates/reuses `.venv`, requires Python 3.13, installs the pinned requirements and test dependencies, checks the dependency environment, and runs the test suite. Every failed command stops setup rather than reporting success. Installing dependencies requires internet access. This setup does not download model weights, change execution policies, buy services, upload data, or modify GitHub.

Then double-click `START_HELIX.cmd`. Leave that terminal open. Open `http://127.0.0.1:8765` in your browser, paste the generated local access key, and choose **Check connection & costs**. Keep the key private. Use `Ctrl+C` to stop the server.

The demo is intentionally deterministic. It is **not yet a learned AI model**. It does not access email/calendar, browse the internet, execute code, train models, or act as a live personal assistant. Those features remain roadmap work. Do not expose this single-owner prototype to your network or through a public tunnel.

The scripts call `.venv\Scripts\python.exe` directly; you do not need to activate a PowerShell script or relax execution policies. Python documents that explicit activation is optional.

## First commit and upload

After reviewing the copied source, confirming the desired repository visibility, and passing setup, run from the checkout:

```powershell
git status --short
git add .
git diff --cached --stat
git diff --cached --name-only
```

Review the list before committing. Do not commit `.venv`, `.helix`, `.env`, `config/local.json`, model weights, credentials, or private data. `.gitignore` helps prevent common mistakes but is not a secret scanner and does not protect previously tracked files. If the list contains an unexpected file, stop before the commit.

Then:

```powershell
git commit -m "Initialize Helix local foundation and Windows setup"
git branch -M main
git push -u origin main
```

This is the **first commit** workflow for the currently empty repository. If someone adds commits before you push, fetch and review that history; do not force-push. If Git asks for a commit identity, configure a repository-local name and your chosen verified or GitHub no-reply email, or use GitHub Desktop. No identity is configured automatically by these scripts.

## Determine the first real model

Double-click `CHECK_PC.cmd`. It uses read-only Windows queries to print CPU, installed RAM, Windows version, display-adapter names and fixed-disk space. If available, `nvidia-smi` also prints the NVIDIA GPU's dedicated memory. It does not save or send a report. When NVIDIA tooling is unavailable, the script does not infer VRAM from unreliable display-adapter counters; check Task Manager's GPU panel instead.

Use the actual hardware, available SSD space, model license and measured latency to choose one real local checkpoint. One checkpoint may initially serve all three role profiles; this is not equivalent to three separately trained specialists. No model has yet been selected for this PC.

## Validation and remaining gates

The Python tests were rerun in the Linux build environment for this distribution. The `.cmd` launchers and actual Windows installation have **not** been executed on a Windows host here. Windows test output, browser operation and hardware details are the next validation evidence. Consult `evidence/windows-preparation.txt` for actual preparation results.

No GitHub push, cloud provisioning, model download, paid inference or deployment was performed by this preparation.
