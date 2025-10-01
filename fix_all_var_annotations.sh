#!/bin/bash
# Fix all remaining var-annotated errors efficiently

# Get list of files with var-annotated errors
files=$(zuban check acb/ 2>&1 | grep "var-annotated" | cut -d: -f1 | sort | uniq)

for file in $files; do
    echo "Fixing $file..."

    # Get all var-annotated errors for this file
    vars=$(zuban check "$file" 2>&1 | grep "var-annotated" | sed 's/.*for "\(.*\)".*/\1/' | sort | uniq)

    for var in $vars; do
        echo "  - $var"

        # Determine the appropriate type based on the hint
        if zuban check "$file" 2>&1 | grep -q "$var.*Dict"; then
            type_annot="dict[str, t.Any]"
        elif zuban check "$file" 2>&1 | grep -q "$var.*List"; then
            type_annot="list[t.Any]"
        elif zuban check "$file" 2>&1 | grep -q "$var.*Set"; then
            type_annot="set[t.Any]"
        else
            type_annot="t.Any"
        fi

        # Add type annotation using sed
        # Pattern: var = value → var: type = value
        sed -i '' "s/\b${var} = /\1${var}: ${type_annot} = /" "$file"
    done
done

echo "Done! Checking results..."
zuban check acb/ 2>&1 | grep -c "var-annotated"
