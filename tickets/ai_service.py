"""
Serviço de IA — abstração para múltiplos providers (DeepSeek, OpenAI, Anthropic, Gemini).
Executa o loop de agente: envia mensagens → processa tool calls → retorna resposta final.
"""
import json
import logging
import time

logger = logging.getLogger(__name__)

# Modelos padrão por provider
DEFAULT_MODELS = {
    'deepseek': 'deepseek-chat',
    'openai': 'gpt-4o-mini',
    'anthropic': 'claude-haiku-4-5-20251001',
    'gemini': 'gemini-2.0-flash',
}

# Limitar número de iterações do loop de agente para evitar loops infinitos
MAX_AGENT_ITERATIONS = 10


def _tools_to_openai_format(tools: list) -> list:
    """Converte lista de tools para formato OpenAI/DeepSeek."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            }
        }
        for t in tools
    ]


def _tools_to_anthropic_format(tools: list) -> list:
    """Converte lista de tools para formato Anthropic."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
        }
        for t in tools
    ]


def _run_openai_agent(client, model: str, messages: list, tools: list, tool_executor) -> str:
    """Loop de agente para OpenAI / DeepSeek (API compatível com OpenAI)."""
    oai_tools = _tools_to_openai_format(tools) if tools else []
    history = list(messages)

    for _ in range(MAX_AGENT_ITERATIONS):
        kwargs = {"model": model, "messages": history}
        if oai_tools:
            kwargs["tools"] = oai_tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        # Adiciona resposta do assistente com tool_calls
        history.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in msg.tool_calls
            ]
        })

        # Executa cada tool call
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            result = tool_executor(tc.function.name, args)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "Desculpe, não consegui completar a operação."


def _run_anthropic_agent(client, model: str, messages: list, tools: list, tool_executor) -> str:
    """Loop de agente para Anthropic Claude."""
    # Separa system message das demais
    system_msg = ""
    history = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            history.append({"role": m["role"], "content": m["content"]})

    ant_tools = _tools_to_anthropic_format(tools) if tools else []

    for _ in range(MAX_AGENT_ITERATIONS):
        kwargs = {
            "model": model,
            "max_tokens": 4096,
            "messages": history,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if ant_tools:
            kwargs["tools"] = ant_tools

        response = client.messages.create(**kwargs)

        # Coleta blocos de texto e tool_use
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if not tool_uses:
            return " ".join(text_parts)

        # Adiciona resposta do assistente
        history.append({"role": "assistant", "content": response.content})

        # Executa tools e adiciona resultados
        tool_results = []
        for tu in tool_uses:
            result = tool_executor(tu.name, tu.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        history.append({"role": "user", "content": tool_results})

    return "Desculpe, não consegui completar a operação."


def run_agent(config, messages: list, tools: list, tool_executor, *, expose_errors: bool = True) -> str:
    """
    Executa o loop de agente completo com o provider configurado.

    Args:
        config: objeto com provider, api_key, model (ex: a AIProviderConfig ativa,
            ou um objeto temporário equivalente usado no teste de conexão)
        messages: lista de dicts {role, content} incluindo system prompt
        tools: lista de tool definitions no formato interno
        tool_executor: callable(tool_name, args) → dict
        expose_errors: se True, mostra o texto cru da exceção do provedor na resposta
            (uso interno/admin, ex: teste de conexão). Se False, retorna uma mensagem
            genérica pro usuário final e só loga o detalhe real no servidor — evita
            vazar mensagens de erro internas do provedor de IA pro chat de qualquer
            usuário.

    Returns:
        Texto da resposta final do assistente
    """
    provider = config.provider or 'deepseek'
    api_key = config.api_key or ''
    model = config.model or DEFAULT_MODELS.get(provider, 'deepseek-chat')

    if not api_key:
        return "⚠️ Chave de API não configurada. Acesse Configurações → Inteligência Artificial para configurar."

    t0 = time.perf_counter()
    try:
        if provider == 'anthropic':
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            return _run_anthropic_agent(client, model, messages, tools, tool_executor)

        elif provider == 'gemini':
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            return _run_openai_agent(client, model, messages, tools, tool_executor)

        else:
            # deepseek ou openai
            from openai import OpenAI
            base_url = "https://api.deepseek.com" if provider == 'deepseek' else None
            client = OpenAI(api_key=api_key, **({"base_url": base_url} if base_url else {}))
            return _run_openai_agent(client, model, messages, tools, tool_executor)

    except Exception as e:
        logger.error("Erro no agente IA (%s): %s", provider, e)
        if expose_errors:
            return f"⚠️ Erro ao comunicar com a IA: {e}"
        return "⚠️ Não foi possível obter resposta da IA no momento. Se o problema persistir, avise um administrador."
    finally:
        logger.info("IA (%s/%s) respondeu em %.2fs", provider, model, time.perf_counter() - t0)
