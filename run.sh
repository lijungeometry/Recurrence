#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${PYTHON:-}" ]; then
    PYTHON="$PYTHON"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v conda >/dev/null 2>&1; then
    PYTHON="$(conda run -n agent which python)"
else
    PYTHON="$(command -v python3)"
fi

resolve_default_problem_file() {
    if [ -f "$SCRIPT_DIR/problem/problem.md" ]; then
        echo "$SCRIPT_DIR/problem/problem.md"
        return
    fi
    if [ -f "$SCRIPT_DIR/problem/problem.markdown" ]; then
        echo "$SCRIPT_DIR/problem/problem.markdown"
        return
    fi

    shopt -s nullglob
    local md_candidates=("$SCRIPT_DIR"/problem/*.md "$SCRIPT_DIR"/problem/*.markdown)
    local tex_candidates=("$SCRIPT_DIR"/problem/*.tex)
    shopt -u nullglob

    if [ "${#md_candidates[@]}" -eq 1 ]; then
        echo "${md_candidates[0]}"
        return
    fi

    if [ "${#md_candidates[@]}" -gt 1 ]; then
        echo "ERROR: Multiple Markdown problem files found in $SCRIPT_DIR/problem/" >&2
        printf '  %s\n' "${md_candidates[@]}" >&2
        echo "Pass the problem file explicitly, e.g. ./run_recurrence.sh problem/name.md output_dir config.yaml" >&2
        exit 1
    fi

    if [ -f "$SCRIPT_DIR/problem/problem.tex" ]; then
        echo "$SCRIPT_DIR/problem/problem.tex"
        return
    fi

    if [ "${#tex_candidates[@]}" -eq 1 ]; then
        echo "${tex_candidates[0]}"
        return
    fi

    if [ "${#tex_candidates[@]}" -gt 1 ]; then
        echo "ERROR: Multiple TeX problem files found in $SCRIPT_DIR/problem/" >&2
        printf '  %s\n' "${tex_candidates[@]}" >&2
        echo "Pass the problem file explicitly, e.g. ./run_recurrence.sh problem/name.tex output_dir config.yaml" >&2
        exit 1
    fi

    echo "ERROR: No problem file found in $SCRIPT_DIR/problem/ (.md, .markdown, or .tex)" >&2
    exit 1
}

if [ $# -ge 1 ]; then
    PROBLEM_FILE="$1"
else
    PROBLEM_FILE="$(resolve_default_problem_file)"
fi
OUTPUT_DIR="${2:-$SCRIPT_DIR/proof_output}"
CONFIG="${3:-$SCRIPT_DIR/config.yaml}"

echo "============================================================"
echo "  Running smoke tests..."
echo "============================================================"
"$PYTHON" "$SCRIPT_DIR/code/smoke_test.py" --config "$CONFIG"
echo ""

# Copy global human_help into the output directory so the pipeline reads
# everything from proof_output.  Use cp -n to not overwrite files that
# already exist (e.g. edited by the UI before a resume).
mkdir -p "$OUTPUT_DIR/human_help"
for f in "$SCRIPT_DIR/human_help"/*; do
    [ -f "$f" ] && cp -n "$f" "$OUTPUT_DIR/human_help/" 2>/dev/null || true
done

echo "============================================================"
echo "  Recurrence Agent Pipeline"
echo "============================================================"
echo "  Problem:  $PROBLEM_FILE"
echo "  Output:   $OUTPUT_DIR"
echo "  Config:   $CONFIG"
echo ""

PIPELINE_CMD=(
    "$PYTHON" "$SCRIPT_DIR/code/pipeline.py"
    --input "$PROBLEM_FILE" \
    --output "$OUTPUT_DIR" \
    --config "$CONFIG"
)

if [ "${RECURRENCE_KEEP_AWAKE:-0}" = "1" ] && command -v caffeinate >/dev/null 2>&1; then
    echo "  Keep awake: enabled via caffeinate"
    exec caffeinate -dimsu "${PIPELINE_CMD[@]}"
fi

exec "${PIPELINE_CMD[@]}"
