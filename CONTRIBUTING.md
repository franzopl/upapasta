# Contributing to UpaPasta

Thank you for your interest in contributing to UpaPasta!

## Internationalization (i18n)

UpaPasta uses `gettext` for internationalization. English is the canonical language, and Portuguese (pt-BR) is the primary translation.

### Adding a New Language

To add support for a new language (e.g., Spanish - `es`):

1. **Initialize the language structure**:
   ```bash
   cd upapasta/locale
   make init LANG=es
   ```

2. **Translate the strings**:
   Edit `upapasta/locale/es/LC_MESSAGES/upapasta.po` using a text editor or a tool like [Poedit](https://poedit.net/).

3. **Compile the translation**:
   ```bash
   make compile
   ```

4. **Verify the translation**:
   Run UpaPasta with the new locale:
   ```bash
   UPAPASTA_LANG=es upapasta --help
   ```

### Updating Translations

If new strings are added to the code:

1. **Extract new strings**:
   ```bash
   cd upapasta/locale
   make update
   ```

2. **Translate the new entries** in the `.po` files.

3. **Recompile**:
   ```bash
   make compile
   ```

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest ruff mypy
```

## Testing

Run the test suite:
```bash
pytest tests/
```

To test with a specific locale:
```bash
UPAPASTA_LANG=pt_BR pytest tests/
```

## Credits

Translators are listed in `upapasta/locale/TRANSLATORS`.
