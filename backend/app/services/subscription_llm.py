"""Bridge authenticated subscription CLIs to MiroFish's Chat Completions interface."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from ..config import Config


class SubscriptionProviderError(RuntimeError):
    pass


def _conversation_prompt(messages: List[Dict[str, Any]]) -> tuple[str, str]:
    system_parts = []
    conversation_parts = []
    for message in messages:
        role = str(message.get('role', 'user')).upper()
        content = message.get('content', '')
        if isinstance(content, list):
            content = '\n'.join(
                str(item.get('text', '')) for item in content if isinstance(item, dict)
            )
        content = str(content or '')
        if role in {'SYSTEM', 'DEVELOPER'}:
            system_parts.append(content)
        else:
            conversation_parts.append(f'<{role}>\n{content}')
    return '\n\n'.join(system_parts), '\n\n'.join(conversation_parts)


def _run_cli(command: List[str], prompt: str, *, timeout: int) -> str:
    try:
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=tempfile.gettempdir(),
            env={**os.environ, 'NO_COLOR': '1'},
        )
    except FileNotFoundError as exc:
        raise SubscriptionProviderError(f"CLI richiesto non trovato: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SubscriptionProviderError(
            f"Il provider non ha risposto entro {timeout} secondi"
        ) from exc

    if result.returncode != 0:
        raise SubscriptionProviderError(
            f"{os.path.basename(command[0])} ha terminato con errore (codice {result.returncode}); "
            'controlla lo stato di login del CLI nel Terminale'
        )
    output = result.stdout.strip()
    if not output:
        raise SubscriptionProviderError('Il provider ha restituito una risposta vuota')
    return output


def complete_chat(messages: List[Dict[str, Any]], model: Optional[str] = None) -> str:
    """Run one text-only completion through the user's authenticated CLI session."""
    provider = Config.LLM_PROVIDER
    system_prompt, conversation = _conversation_prompt(messages)
    if not conversation:
        raise SubscriptionProviderError('La richiesta non contiene messaggi utente')

    timeout = int(os.environ.get('LLM_CLI_TIMEOUT_SECONDS', '300'))
    if provider == 'claude_subscription':
        cli = shutil.which('claude')
        if not cli:
            raise SubscriptionProviderError('Claude Code CLI non è installato')
        selected_model = model or Config.LLM_MODEL_NAME or 'sonnet'
        command = [
            cli, '--print', '--output-format', 'json', '--no-session-persistence',
            '--permission-mode', 'dontAsk', '--tools', '', '--strict-mcp-config',
            '--model', selected_model,
        ]
        if system_prompt:
            command.extend(['--system-prompt', system_prompt])
        raw = _run_cli(command, conversation, timeout=timeout)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if payload.get('is_error'):
            raise SubscriptionProviderError(str(payload.get('result', 'Errore Claude Code')))
        return str(payload.get('result', '')).strip()

    if provider == 'codex_subscription':
        cli = shutil.which('codex')
        if not cli:
            raise SubscriptionProviderError('Codex CLI non è installato')
        prompt_parts = []
        if system_prompt:
            prompt_parts.append(f'<SYSTEM INSTRUCTIONS>\n{system_prompt}')
        prompt_parts.append(
            '<TASK>\nRespond as a language model for the requesting application. '
            'Do not use tools, inspect files, or run commands. Return only the requested answer. '
            'Follow the conversation and output-format instructions exactly.'
        )
        prompt_parts.append(conversation)
        cli_prompt = '\n\n'.join(prompt_parts)
        with tempfile.TemporaryDirectory(prefix='mirofish-codex-') as scratch:
            output_path = os.path.join(scratch, 'last-message.txt')
            command = [
                cli, 'exec', '--ignore-user-config', '--ephemeral',
                '--sandbox', 'read-only', '--ask-for-approval', 'never',
                '--disable', 'unified_exec',
                '--disable', 'code_mode', '--disable', 'enable_mcp_apps',
                '--disable', 'shell_tool', '--disable', 'browser_use',
                '--disable', 'browser_use_external', '--disable', 'browser_use_full_cdp_access',
                '--disable', 'computer_use', '--disable', 'in_app_local_automation',
                '--disable', 'view_image', '--disable', 'tool_call_mcp_elicitation',
                '--disable', 'apps', '--disable', 'image_generation',
                '--disable', 'in_app_browser', '--disable', 'code_mode_host',
                '--disable', 'shell_snapshot', '--disable', 'shell_zsh_fork', '--disable', 'plugins',
                '--disable', 'plugin_sharing', '--disable', 'web_search_request',
                '--disable', 'web_search_cached', '--disable', 'standalone_web_search',
                '--skip-git-repo-check', '--color', 'never',
                '--output-last-message', output_path, '-',
            ]
            _run_cli(command, cli_prompt, timeout=timeout)
            try:
                with open(output_path, 'r', encoding='utf-8') as output_file:
                    return output_file.read().strip()
            except OSError as exc:
                raise SubscriptionProviderError(
                    'Codex CLI non ha prodotto il messaggio finale'
                ) from exc

    raise SubscriptionProviderError('Provider in abbonamento non supportato')
