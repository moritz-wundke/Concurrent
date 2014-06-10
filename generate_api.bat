@echo off
pushd "concurrent"
sphinx-apidoc -f -l -P -o ..\docs\ .
popd
pushd "docs"
start "Building documentation" make html
popd
