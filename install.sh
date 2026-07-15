#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CODEX_HOME=${CODEX_HOME:-"$HOME/.codex"}
SKILL_TARGET="$CODEX_HOME/skills/codex-auto-model-router"
LEGACY_SKILL_TARGET="$CODEX_HOME/skills/codex-model-router"
AGENT_TARGET="$CODEX_HOME/agents"

mkdir -p "$SKILL_TARGET/agents" "$SKILL_TARGET/references" "$SKILL_TARGET/scripts" "$AGENT_TARGET"

cp "$ROOT/SKILL.md" "$SKILL_TARGET/SKILL.md"
cp "$ROOT/agents/openai.yaml" "$SKILL_TARGET/agents/openai.yaml"
cp "$ROOT/references/"*.md "$SKILL_TARGET/references/"
cp "$ROOT/scripts/"*.py "$SKILL_TARGET/scripts/"
cp "$ROOT/codex-agents/"*.toml "$AGENT_TARGET/"

chmod +x "$SKILL_TARGET/scripts/"*.py

# Remove only this project's legacy installation so Codex does not show both names.
if [ -d "$LEGACY_SKILL_TARGET" ]; then
  rm -rf "$LEGACY_SKILL_TARGET"
fi
for legacy_name in \
  project-model-router.toml project-model-router-low.toml project-model-router-high.toml project-model-router-xhigh.toml \
  project-model-router-terra.toml project-model-router-terra-low.toml project-model-router-terra-high.toml project-model-router-terra-xhigh.toml \
  project-model-router-luna.toml project-model-router-luna-low.toml project-model-router-luna-high.toml project-model-router-luna-xhigh.toml \
  project-model-executor.toml project-model-executor-low.toml project-model-executor-high.toml project-model-executor-xhigh.toml \
  project-model-executor-terra.toml project-model-executor-terra-low.toml project-model-executor-terra-high.toml project-model-executor-terra-xhigh.toml \
  project-model-executor-luna.toml project-model-executor-luna-low.toml project-model-executor-luna-high.toml project-model-executor-luna-xhigh.toml
do
  legacy_agent="$AGENT_TARGET/$legacy_name"
  if [ -f "$legacy_agent" ]; then
    rm -f "$legacy_agent"
  fi
done

printf '%s\n' "Installed codex-auto-model-router into $CODEX_HOME"
printf '%s\n' "Removed legacy codex-model-router skill and project-model agent presets when present."
printf '%s\n' "Restart Codex to refresh skills and custom agents."
