#!/bin/bash
# growth — one-command launcher for Mac
# Usage:
#   ./run.sh
#   ./run.sh --ui-port 21322 --api-port 21322
#   ./run.sh --ui-port 21322 --save-ports
#   GROWTH_UI_PORT=21322 GROWTH_API_PORT=21322 ./run.sh
#   ./run.sh --https                    # iPhone Safari HTTPS-Only fix
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "First run: installing dependencies..."
  python3 main.py install
fi

# Optional interactive port pick (only if --ask-ports passed)
ARGS=()
ASK=false
for arg in "$@"; do
  if [[ "$arg" == "--ask-ports" ]]; then
    ASK=true
  else
    ARGS+=("$arg")
  fi
done

if $ASK; then
  DEFAULT_UI=$(.venv/bin/python -c "import json; print(json.load(open('config.json')).get('ui_port',21322))" 2>/dev/null || echo 21322)
  DEFAULT_API=$(.venv/bin/python -c "import json; print(json.load(open('config.json')).get('api_port',21322))" 2>/dev/null || echo 21322)
  read -r -p "UI port [$DEFAULT_UI]: " UI_IN
  read -r -p "API port [$DEFAULT_API]: " API_IN
  UI_IN="${UI_IN:-$DEFAULT_UI}"
  API_IN="${API_IN:-$DEFAULT_API}"
  ARGS+=(--ui-port "$UI_IN" --api-port "$API_IN")
fi

exec .venv/bin/python main.py start "${ARGS[@]}"