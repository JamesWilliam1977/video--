# Documentation localization

This documentation uses Sphinx gettext catalogs. We keep doc translations in
`doc/locale/` so they stay separate from the app UI translations in `src/`.

## Generate POT files

From the repository root:

```bash
make -C doc gettext
```

This writes POT files into `doc/locale/` (e.g. `doc/locale/getting_started.pot`).

## Create PO files for a language

Create a language catalog directory and copy POTs into it as PO files:

```bash
mkdir -p doc/locale/<lang>/LC_MESSAGES
cp doc/locale/*.pot doc/locale/<lang>/LC_MESSAGES/
for f in doc/locale/<lang>/LC_MESSAGES/*.pot; do mv "$f" "${f%.pot}.po"; done
```

Replace `<lang>` with a Sphinx language code (e.g. `es`, `fr`, `pt_BR`).

## Use sphinx-intl (optional)

If you install `sphinx-intl`, it can manage PO files for you:

```bash
pip install sphinx-intl

cd doc
make gettext
sphinx-intl update -p locale -l <lang>
```

This creates/updates `doc/locale/<lang>/LC_MESSAGES/*.po` based on the POT
files.

## Build localized docs

```bash
cd doc
make html SPHINXOPTS="-D language=<lang>"
```

Sphinx will load PO files from `doc/locale/` via `locale_dirs` in `doc/conf.py`.
