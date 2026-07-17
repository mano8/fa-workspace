#!/usr/bin/env bash

m8_import_workspace_env() {
    local profile=""
    local validate_only=0
    local skip_availability=0
    local argument

    for argument in "$@"; do
        case "${argument}" in
            local|devcontainer)
                profile="${argument}"
                ;;
            --validate-only)
                validate_only=1
                ;;
            --skip-availability)
                skip_availability=1
                ;;
            *)
                echo "Unknown workspace environment argument." >&2
                return 1
                ;;
        esac
    done

    if [[ -z "${profile}" ]]; then
        if [[ -f /.dockerenv || -n "${REMOTE_CONTAINERS:-}" ]]; then
            profile="devcontainer"
        else
            profile="local"
        fi
    fi

    local script_dir
    local workspace_root
    local profile_file
    script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    workspace_root="$(dirname -- "${script_dir}")"
    profile_file="${workspace_root}/.env.${profile}"

    if [[ ! -f "${profile_file}" ]]; then
        echo "Missing workspace environment profile. Copy its example and configure it locally." >&2
        return 1
    fi

    declare -A values=()
    local raw_line
    local line
    local key
    local value
    local line_number=0

    while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
        line_number=$((line_number + 1))
        raw_line="${raw_line%$'\r'}"
        line="${raw_line#"${raw_line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"

        if [[ -z "${line}" || "${line}" == \#* ]]; then
            continue
        fi

        if [[ "${line}" != *=* ]]; then
            echo "Invalid environment entry at line ${line_number}." >&2
            return 1
        fi

        key="${line%%=*}"
        value="${line#*=}"
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"

        if [[ ! "${key}" =~ ^[A-Z][A-Z0-9_]*$ ]]; then
            echo "Invalid environment key at line ${line_number}." >&2
            return 1
        fi

        if [[ -n "${values[${key}]+configured}" ]]; then
            echo "Duplicate environment key in workspace profile." >&2
            return 1
        fi

        if [[ ${#value} -ge 2 ]]; then
            if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
                value="${value:1:${#value}-2}"
            elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
                value="${value:1:${#value}-2}"
            fi
        fi

        values["${key}"]="${value}"
    done < "${profile_file}"

    local required=(
        M8_WORKSPACE_ROOT
        M8_RUNTIME
        M8_HOST_OS
        M8_PYTHON_ENV_KIND
        M8_JS_RUNTIME_KIND
        M8_PACKAGE_MANAGER_KIND
        M8_VCS_KIND
        M8_CONTAINER_ENGINE_KIND
        M8_COMPOSE_KIND
    )

    for key in "${required[@]}"; do
        if [[ -z "${values[${key}]+configured}" || -z "${values[${key}]}" || "${values[${key}]}" == "changethis" ]]; then
            echo "A required workspace environment key is missing or not configured." >&2
            return 1
        fi
    done

    local expected_runtime="devcontainer"
    if [[ "${profile}" == "local" ]]; then
        expected_runtime="local"
    fi

    if [[ "${values[M8_RUNTIME]}" != "${expected_runtime}" ]]; then
        echo "Workspace environment runtime does not match its profile." >&2
        return 1
    fi

    if [[ ! "${values[M8_HOST_OS]}" =~ ^(windows|linux|macos)$ ]]; then
        echo "M8_HOST_OS must be windows, linux, or macos." >&2
        return 1
    fi

    if [[ "${profile}" == "devcontainer" && "${values[M8_HOST_OS]}" != "linux" ]]; then
        echo "The devcontainer profile must set M8_HOST_OS=linux." >&2
        return 1
    fi

    local commands_to_check=()

    validate_tool_group() {
        local kind_key="$1"
        local command_key="$2"
        local allowed_pattern="$3"
        local kind="${values[${kind_key}]}"
        local command_value="${values[${command_key}]:-}"

        if [[ ! "${kind}" =~ ${allowed_pattern} ]]; then
            echo "Unsupported workspace tool kind." >&2
            return 1
        fi

        if [[ "${kind}" == "none" ]]; then
            if [[ -n "${command_value}" ]]; then
                echo "A disabled workspace tool must have an empty command." >&2
                return 1
            fi
        elif [[ -z "${command_value}" || "${command_value}" == "changethis" ]]; then
            echo "An enabled workspace tool is missing its command." >&2
            return 1
        else
            commands_to_check+=("${command_key}")
        fi
    }

    validate_tool_group M8_PYTHON_ENV_KIND M8_PYTHON '^(conda|venv|virtualenv|uv|poetry|pipenv|pyenv|system|other|none)$' || return 1
    validate_tool_group M8_JS_RUNTIME_KIND M8_JS_RUNTIME '^(node|bun|deno|other|none)$' || return 1
    validate_tool_group M8_PACKAGE_MANAGER_KIND M8_PACKAGE_MANAGER '^(npm|pnpm|yarn|bun|other|none)$' || return 1
    validate_tool_group M8_VCS_KIND M8_VCS '^(git|other)$' || return 1
    validate_tool_group M8_CONTAINER_ENGINE_KIND M8_CONTAINER_ENGINE '^(docker|podman|other|none)$' || return 1
    validate_tool_group M8_COMPOSE_KIND M8_COMPOSE '^(docker-plugin|docker-compose|podman-compose|other|none)$' || return 1

    local optional_command
    for optional_command in M8_PYTHON_MANAGER M8_PACKAGE_EXECUTOR; do
        if [[ -n "${values[${optional_command}]:-}" ]]; then
            if [[ "${values[${optional_command}]}" == "changethis" ]]; then
                echo "An optional workspace command is not configured." >&2
                return 1
            fi
            commands_to_check+=("${optional_command}")
        fi
    done

    for key in "${!values[@]}"; do
        if [[ "${key}" == M8_TOOL_* ]]; then
            if [[ -z "${values[${key}]}" || "${values[${key}]}" == "changethis" ]]; then
                echo "An additional workspace tool is declared but not configured." >&2
                return 1
            fi
            commands_to_check+=("${key}")
        fi
    done

    if [[ ${skip_availability} -eq 0 ]]; then
        if [[ ! -d "${values[M8_WORKSPACE_ROOT]}" ]]; then
            echo "M8_WORKSPACE_ROOT does not resolve to a directory." >&2
            return 1
        fi

        local command_key
        local command_value
        for command_key in "${commands_to_check[@]}"; do
            command_value="${values[${command_key}]}"
            if [[ "${command_value}" == */* ]]; then
                if [[ ! -x "${command_value}" ]]; then
                    echo "A configured workspace command is not executable." >&2
                    return 1
                fi
            elif ! command -v "${command_value}" >/dev/null 2>&1; then
                echo "A configured workspace command is not available." >&2
                return 1
            fi
        done

    fi

    if [[ ${validate_only} -eq 0 ]]; then
        for key in "${!values[@]}"; do
            export "${key}=${values[${key}]}"
        done
    fi

    local mode="loaded"
    if [[ ${validate_only} -eq 1 ]]; then
        mode="validated"
    fi
    echo "Workspace environment profile '${profile}' ${mode} successfully."
}

m8_import_workspace_env "$@"
result=$?
unset -f m8_import_workspace_env validate_tool_group
return "${result}" 2>/dev/null || exit "${result}"
