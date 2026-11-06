#!/bin/sh
# Bütün testler (gerçek yazıcıya, ayarlara ve önbelleğe dokunmaz). Kullanım: ./test.sh [-v]
cd "$(dirname "$0")" && exec .venv/bin/python -W error::DeprecationWarning:yazdir -m unittest discover -s tests -t . "$@" 2>&1 \
  | grep -v "propagateSizeHints"
