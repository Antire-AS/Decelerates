#!/bin/bash
set -e

MARKETPLACE_DIR="$HOME/.claude/plugins/marketplaces/antire-marketplace"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Clone marketplace if not already present
if [ ! -d "$MARKETPLACE_DIR" ]; then
    mkdir -p "$HOME/.claude/plugins/marketplaces"
    git clone git@github.com:Antire-AS/antire-claude-plugins.git "$MARKETPLACE_DIR"
    echo "Cloned antire-marketplace"
else
    cd "$MARKETPLACE_DIR" && git pull
    echo "Updated antire-marketplace"
fi

# Enable the plugin in user settings
if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{"enabledPlugins":{"antire-standards@antire-marketplace":true}}' > "$SETTINGS_FILE"
    echo "Created settings with antire-standards enabled"
elif ! grep -q "antire-standards@antire-marketplace" "$SETTINGS_FILE"; then
    # Use a temp file to merge the enabledPlugins key
    python3 -c "
import json, sys
with open('$SETTINGS_FILE') as f:
    settings = json.load(f)
settings.setdefault('enabledPlugins', {})['antire-standards@antire-marketplace'] = True
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')
"
    echo "Enabled antire-standards in existing settings"
else
    echo "antire-standards already enabled"
fi

echo "Done. Restart Claude Code to load the plugin."
