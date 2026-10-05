"""Local OpenAI-compatible endpoint used only for subscription CLI providers."""

import time
import uuid

from flask import Blueprint, jsonify, request

from ..config import Config
from ..services.subscription_llm import SubscriptionProviderError, complete_chat

llm_compat_bp = Blueprint('llm_compat', __name__)


@llm_compat_bp.post('/v1/chat/completions')
def chat_completions():
    if Config.LLM_PROVIDER not in Config.SUBSCRIPTION_PROVIDERS:
        return jsonify({'error': {'message': 'Subscription bridge is disabled'}}), 404

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'error': {'message': 'request body must be an object'}}), 400
    messages = body.get('messages')
    if not isinstance(messages, list) or not messages:
        return jsonify({'error': {'message': 'messages must be a non-empty array'}}), 400
    if any(not isinstance(message, dict) for message in messages):
        return jsonify({'error': {'message': 'each message must be an object'}}), 400

    response_format = body.get('response_format')
    if response_format is not None and not isinstance(response_format, dict):
        return jsonify({'error': {'message': 'response_format must be an object'}}), 400
    response_format = response_format or {}
    if response_format.get('type') in {'json_object', 'json_schema'}:
        messages = list(messages)
        messages.append({
            'role': 'system',
            'content': 'Return only valid JSON matching the requested format. Do not use Markdown fences.',
        })

    try:
        text = complete_chat(messages, body.get('model'))
    except SubscriptionProviderError as exc:
        return jsonify({'error': {'message': str(exc), 'type': 'provider_error'}}), 502
    except Exception:
        return jsonify({'error': {'message': 'Subscription provider request failed'}}), 502

    return jsonify({
        'id': f'chatcmpl-{uuid.uuid4().hex}',
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': body.get('model') or Config.LLM_MODEL_NAME,
        'choices': [{
            'index': 0,
            'message': {'role': 'assistant', 'content': text},
            'finish_reason': 'stop',
        }],
    })
