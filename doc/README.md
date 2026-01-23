# Documentation localization

This documentation uses Sphinx gettext catalogs. We keep doc translations in
`doc/locale/` so they stay separate from the app UI translations in `src/`.

## Generate and update translations

Install `sphinx-intl` once, then use it for all PO management:

```bash
pip install sphinx-intl

cd doc
make gettext
sphinx-intl update -p locale -l <lang>
```

This writes POT files into `doc/locale/` and creates/updates
`doc/locale/<lang>/LC_MESSAGES/*.po`. Replace `<lang>` with a Sphinx language
code (e.g. `es`, `fr`, `pt_BR`).

Translator note: do not translate Sphinx substitution tokens like
`|icon_echo|`. Keep the `|...|` text unchanged in `msgid`/`msgstr`.

## Manual PO creation (if you are not using sphinx-intl)

```bash
cd doc
make gettext
mkdir -p locale/<lang>/LC_MESSAGES
cp locale/*.pot locale/<lang>/LC_MESSAGES/
for f in locale/<lang>/LC_MESSAGES/*.pot; do mv "$f" "${f%.pot}.po"; done
```

## Build localized docs

```bash
cd doc
make html SPHINXOPTS="-D language=<lang>"
```

Sphinx will load PO files from `doc/locale/` via `locale_dirs` in `doc/conf.py`.
