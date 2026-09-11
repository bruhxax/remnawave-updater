# Contributing

1. Fork the repository and create a feature branch.
2. Keep the CLI usable in both Russian and English; add new user-facing strings to `remnawave_updater/i18n.py`.
3. Do not store VPS passwords or weaken SSH key verification.
4. Keep update commands aligned with the official Remnawave documentation.
5. Run `python -m unittest discover -s tests -p 'test_*.py' -v` and `python -m compileall -q remnawave_updater` before opening a pull request.
