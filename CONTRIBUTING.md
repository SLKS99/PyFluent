# Contributing to PyFluent

Thank you for your interest in contributing to PyFluent! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/PyFluent.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Install in development mode: `pip install -e ".[dev]"`

## Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/PyFluent.git
cd PyFluent

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## Code Style

- Follow PEP 8 style guidelines
- Use type hints where possible
- Add docstrings to all public functions and classes
- Keep lines under 100 characters when possible

## Testing

- Write tests for new features
- Ensure all tests pass: `pytest tests/`
- Test with real hardware when possible (use simulation mode for CI)

## Submitting Changes

1. Make sure your code follows the style guidelines
2. Write or update tests as needed
3. Update documentation if needed
4. Commit your changes: `git commit -m "Add feature: description"`
5. Push to your fork: `git push origin feature/your-feature-name`
6. Create a Pull Request on GitHub

## Pull Request Process

1. Update README.md if needed
2. Update documentation in `docs/` if needed
3. Add tests for new functionality
4. Ensure all tests pass
5. Request review from maintainers

## Reporting Issues

When reporting issues, please include:
- Python version
- PyFluent version
- Tecan VisionX/FluentControl version
- Operating system
- Error messages and tracebacks
- Steps to reproduce

## Questions?

Feel free to open an issue for questions or discussions!

