#!/bin/bash
# Run this script to activate the virtual environment and run the Llama PyPI Scraper
source llama_pypi_env/bin/activate
python3 llama_pypi_scraper.py "$@"
