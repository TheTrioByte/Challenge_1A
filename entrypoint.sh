#!/bin/bash
# Process all PDFs in input dir
mkdir -p /app/output
for pdf in /app/input/*.pdf; do
    if [ -f "$pdf" ]; then
        name=$(basename "$pdf" .pdf)
        output="/app/output/${name}.json"
        python extract_outline.py "$pdf" "$output"
    fi
done
