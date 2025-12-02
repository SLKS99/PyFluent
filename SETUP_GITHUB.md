# Setting Up PyFluent on GitHub

This guide will help you push PyFluent to a new GitHub repository.

## Steps

### 1. Create a New Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `PyFluent`
3. Description: "Python library for controlling Tecan Fluent liquid handling robots"
4. Choose **Public** or **Private**
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

### 2. Update Repository URLs

Before pushing, update these files with your GitHub username:

1. **README.md** - Replace `YOUR_USERNAME` with your GitHub username:
   - Line 179: `git clone https://github.com/YOUR_USERNAME/PyFluent.git`
   - Line 263: `https://github.com/YOUR_USERNAME/PyFluent/issues`

2. **setup.py** - Replace `YOUR_USERNAME` with your GitHub username:
   - Line 27: `url="https://github.com/YOUR_USERNAME/PyFluent"`

### 3. Push to GitHub

```bash
# Make sure you're in the PyFluent directory
cd PyFluent

# Add the remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/PyFluent.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

### 4. Set Up Repository Settings

1. Go to your repository on GitHub
2. Click **Settings** → **General**
3. Scroll to **Features**:
   - ✅ Enable **Issues**
   - ✅ Enable **Discussions** (optional)
   - ✅ Enable **Wiki** (optional)

4. Go to **Settings** → **Pages** (optional):
   - Source: `main` branch, `/docs` folder
   - This will host your documentation

5. Go to **Settings** → **Actions** → **General**:
   - Enable **Workflow permissions**: Read and write permissions

### 5. Add Repository Topics

Go to your repository and click the gear icon next to **About**, then add topics:
- `python`
- `tecan`
- `liquid-handling`
- `laboratory-automation`
- `pylabrobot`
- `robotics`
- `biotechnology`

### 6. Create a Release (Optional)

1. Go to **Releases** → **Create a new release**
2. Tag: `v0.1.0`
3. Title: `v0.1.0 - Initial Release`
4. Description:
   ```markdown
   ## Initial Release

   - Direct .NET API integration with Tecan VisionX
   - Full PyLabRobot compatibility
   - Worklist generation and conversion
   - Multi-channel pipetting support
   - Comprehensive documentation
   ```

### 7. Verify Everything

Check that:
- ✅ README displays correctly
- ✅ All files are present
- ✅ No __pycache__ files are included
- ✅ License file is present
- ✅ Documentation links work
- ✅ Examples are included

## Repository Structure

Your repository should have this structure:

```
PyFluent/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── python-package.yml
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   └── worklists.md
├── examples/
│   ├── simple_pyfluent_usage.py
│   ├── simple_csv_runner.py
│   └── pylabrobot_to_worklist.py
├── pyfluent/
│   ├── backends/
│   │   ├── fluent_visionx.py
│   │   ├── xml_commands.py
│   │   └── errors.py
│   ├── deck.py
│   ├── method_manager.py
│   ├── protocol.py
│   ├── worklist.py
│   ├── worklist_converter.py
│   └── ...
├── tests/
├── worklists/
├── .gitignore
├── .gitattributes
├── LICENSE
├── README.md
├── CONTRIBUTING.md
├── requirements.txt
└── setup.py
```

## Next Steps

After pushing:

1. **Add a description** to your repository
2. **Add topics** for discoverability
3. **Enable GitHub Pages** for documentation (optional)
4. **Create issues** for known limitations or future features
5. **Add collaborators** if working with a team

## Troubleshooting

### "Repository not found"
- Check that the repository name matches exactly
- Verify you have push access
- Make sure you're using the correct username

### "Authentication failed"
- Use a Personal Access Token instead of password
- Or use SSH: `git remote set-url origin git@github.com:YOUR_USERNAME/PyFluent.git`

### Files not showing up
- Make sure files are committed: `git status`
- Check .gitignore isn't excluding important files
- Verify you're in the correct directory
