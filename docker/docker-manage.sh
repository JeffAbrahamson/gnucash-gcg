#!/bin/bash

set -euo pipefail

export SSH_USER=$LOGNAME

cd "$(dirname "$0")"

# Get version from git for setuptools-scm (since .git is not in container)
# Format as PEP 440 compliant version
_git_desc=$(git -C .. describe --tags --always 2>/dev/null || echo "")
if [[ "$_git_desc" =~ ^[0-9]+\.[0-9]+ ]]; then
    # Has version tag, use as-is or convert to PEP 440
    export SETUPTOOLS_SCM_PRETEND_VERSION="$_git_desc"
else
    # No version tag, just commit hash - format as dev version
    export SETUPTOOLS_SCM_PRETEND_VERSION="0.1.dev0+g${_git_desc:-unknown}"
fi

BUILD_NOCACHE=""
while getopts "b" opt; do
    case "$opt" in
	b) BUILD_NOCACHE=1 ;;
	*) ;;
    esac
done
shift $((OPTIND - 1))

action="${1:-}"
shift || true

maybe_build_nocache() {
    local service="$1"
    if [ -n "$BUILD_NOCACHE" ]; then
	echo "Explicit build requested."
	docker compose build --no-cache "$service"
    fi
}

case "$action" in
    sh)
        # Interactive shell - shares container across multiple shells
        maybe_build_nocache dev-sh
        docker compose up -d --build dev-sh
        docker compose exec dev-sh /usr/local/bin/entrypoint.sh /bin/bash

        # When shell exits, check if other shells are still running
        echo "Checking if other shells are running..."
        num_shells=$(docker compose exec dev-sh ps -eo tty,comm | awk '$1 ~ /^pts\// && $2=="bash" {print $1}' | sort -u | wc -l)
        if [ "$num_shells" -ne 0 ]; then
            echo "${num_shells} still running."
        else
            echo "No more shells detected, stopping container..."
            docker compose stop dev-sh
        fi
        ;;
    claude)
        # Claude Code - runs in ephemeral container
        # The entrypoint handles the special invocation needed for claude
        maybe_build_nocache dev-claude
        docker compose run --rm --build dev-claude claude
        ;;
    codex)
        # OpenAI Codex - runs in ephemeral container
        maybe_build_nocache dev-codex
        docker compose run --rm --build dev-codex codex
        ;;
    test)
        # Run test suite in ephemeral container
        maybe_build_nocache dev-sh
        docker compose run --rm --build dev-sh \
            bash -c 'flake8 . && black --check --line-length 79 . && pytest --cov=gcg --cov-report=term-missing --cov-fail-under=80'
        ;;

    *)
        echo "Usage: ./docker-manage.sh [-b] sh|claude|codex|test"
        echo "  -b  Rebuild container from scratch (no cache)"
        if [ -n "$action" ]; then
            echo "** Unrecognised action: \"$action\"."
        fi
        ;;
esac
