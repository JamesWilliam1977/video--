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
make html SPHINXOPTS="-D language=<lang> -D ga4_measurement_id=G-XXXX"
```

Sphinx will load PO files from `doc/locale/` via `locale_dirs` in `doc/conf.py`.

## Create language translations for openshot.org website

```bash
  cd doc
  make html SPHINXOPTS="-D ga4_measurement_id=G-W2VHM9Y8QH"

 # languages from locale folders
  langs=$(find locale -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

  mkdir -p _build/html
  for lang in $langs; do
    rm -rf "_build/html/$lang"
    sphinx-build -b html -D language="$lang" -D ga4_measurement_id=G-W2VHM9Y8QH . "_build/html/$lang"

    # rewrite asset URLs to point to parent shared dirs
    find "_build/html/$lang" -name "*.html" -print0 | xargs -0 perl -pi -e '
      s!(?<=["'\''])_static/!../_static/!g;
      s!(?<=["'\''])_images/!../_images/!g;
      s!(?<=["'\''])_sources/!../_sources/!g;
      s!(?<=["'\''])_downloads/!../_downloads/!g;
    '

    # remove per-lang asset dirs
    rm -rf "_build/html/$lang/_static" \
           "_build/html/$lang/_images" \
           "_build/html/$lang/_sources" \
           "_build/html/$lang/_downloads" \
           "_build/html/$lang/.doctrees"
  done
```

## Create PDF translations for openshot.org website

```bash
  # languages from locale folders
  langs=$(find locale -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

  # broken: "hi"
  # fixed but needs RTL: "fa"
  # list of language codes to skip for PDF (these all have issues)
  skip_langs=("ar" "hi" "ja" "ko" )

  # Build PDFs (skip list) and copy into html folders
  for lang in $langs; do
    if [[ " ${skip_langs[*]} " == *" $lang "* ]]; then
      echo "Skipping PDF for $lang"
      continue
    fi
    builddir="_build/pdf/$lang"
    make latexpdf SPHINXOPTS="-D language=$lang" BUILDDIR="$builddir"
    cp -f "$builddir/latex/OpenShotVideoEditor.pdf" "_build/html/$lang/OpenShotVideoEditor.pdf"
  done
```
