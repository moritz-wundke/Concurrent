#!/bin/bash
# How not to incluse root package?

cd concurrent;
sphinx-apidoc -f -l -P -o ../docs/ .
cd ..
cd docs; make html
