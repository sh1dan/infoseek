# 🚀 Git Setup Instructions

## Initial Setup for https://github.com/sh1dan/infoseek

## ⚠️ Prerequisites

### Install Git (if not installed)

If you see the error `git : The term 'git' is not recognized`, you need to install Git first:

**Option 1: Download Git for Windows**
1. Go to https://git-scm.com/download/win
2. Download and run the installer
3. Use default settings (recommended)
4. Restart your terminal/VS Code after installation

**Option 2: Install via Winget (Windows Package Manager)**
```powershell
winget install --id Git.Git -e --source winget
```

**Option 3: Install via Chocolatey**
```powershell
choco install git
```

**Verify Installation:**
```powershell
git --version
```

### Step 1: Initialize Git (if not already initialized)

```bash
git init
```

### Step 2: Add Remote Repository

```bash
git remote add origin https://github.com/sh1dan/infoseek.git
```

### Step 3: Check Current Status

```bash
git status
```

### Step 4: Add All Files

```bash
git add .
```

### Step 5: Create Initial Commit

```bash
git commit -m "feat: Initial commit - InfoSeek news search application

- Add Django REST API backend with Celery tasks
- Add React frontend with premium dark mode UI
- Implement article search with customizable count
- Add automatic PDF generation
- Add Docker containerization
- Add comprehensive documentation"
```

### Step 6: Push to GitHub

```bash
git branch -M main
git push -u origin main
```

## If Repository Already Has Content

If you need to force push (⚠️ use with caution):

```bash
git push -u origin main --force
```

## Verify Push

After pushing, verify at: https://github.com/sh1dan/infoseek

## Troubleshooting

### If you get authentication error:

```bash
# Use GitHub CLI or Personal Access Token
# Or configure Git credentials:
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### If remote already exists:

```bash
# Remove existing remote
git remote remove origin

# Add correct remote
git remote add origin https://github.com/sh1dan/infoseek.git
```

