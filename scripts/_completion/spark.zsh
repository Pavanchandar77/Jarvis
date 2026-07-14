#compdef spark spark-backup spark-calendar spark-contacts spark-cookbook spark-docs spark-gallery spark-mail spark-mcp spark-memory spark-notes spark-personal spark-preset spark-research spark-sessions spark-signature spark-skills spark-tasks spark-theme spark-webhook
# Zsh tab-completion for the spark umbrella + sub-CLIs.
#
# Drop in any directory on $fpath, e.g.:
#     fpath=(/path/to/spark-ui/scripts/_completion $fpath)
#     autoload -U compinit; compinit
#
# Then `spark <tab>` completes subcommands; `spark mail <tab>`
# completes mail subcommands; `spark-mail <tab>` works the same.

_spark_scripts_dir() {
    local self="${(%):-%x}"
    while [[ -L "$self" ]]; do self="$(readlink "$self")"; done
    cd "${self:h}/.." && pwd
}

typeset -gA _spark_subs

_spark_refresh() {
    _spark_subs=()
    local dir="$(_spark_scripts_dir)"
    local py="$dir/../venv/bin/python"
    [[ -x "$py" ]] || py="$(command -v python3)"
    local f sub help_out commands
    for f in "$dir"/spark-*; do
        [[ -x "$f" ]] || continue
        case "$f" in
            *.bak|*.pyc|*.pre-*) continue ;;
        esac
        sub="${${f:t}#spark-}"
        help_out=$("$py" "$f" --help 2>/dev/null) || continue
        commands=$(echo "$help_out" | grep -oE '\{[a-z0-9_,-]+\}' | head -1 \
            | tr -d '{}' | tr ',' ' ')
        _spark_subs[$sub]="$commands"
    done
}

_spark() {
    [[ ${#_spark_subs} -eq 0 ]] && _spark_refresh

    local cmd="${words[1]}"

    if [[ "$cmd" == "spark" ]]; then
        if (( CURRENT == 2 )); then
            local -a subs=(${(k)_spark_subs} help)
            _describe 'subcommand' subs
            return
        fi
        local sub="${words[2]}"
        if [[ "$sub" == "help" ]] && (( CURRENT == 3 )); then
            local -a subs=(${(k)_spark_subs})
            _describe 'subcommand' subs
            return
        fi
        if (( CURRENT == 3 )); then
            local -a sc=(${(s/ /)_spark_subs[$sub]})
            _describe 'command' sc
            return
        fi
        return
    fi

    # spark-foo <tab>
    local sub="${cmd#spark-}"
    if (( CURRENT == 2 )); then
        local -a sc=(${(s/ /)_spark_subs[$sub]})
        _describe 'command' sc
        return
    fi
}

_spark "$@"
