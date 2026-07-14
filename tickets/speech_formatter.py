"""
Transforma o texto escrito de uma resposta da IA em texto pronto para fala natural,
antes de mandar para o TTS (ElevenLabs/Google). Nunca muda o significado da
informação — só a forma de falar (remove marcação, troca linguagem burocrática por
formas faladas, quebra em frases curtas, agrupa em pedaços pequenos pra permitir
tocar o áudio por partes conforme vai ficando pronto, e limita a duração falada).

O texto exibido na bolha do chat não passa por aqui — continua sendo o texto
original e completo da IA.
"""
import random
import re
from dataclasses import dataclass, field
from typing import List

WORDS_PER_MINUTE = 135  # estimativa pt-BR no speed=0.92 calibrado no ElevenLabs
MAX_SPOKEN_SECONDS = 40.0
MAX_CHUNK_CHARS = 220  # cada chunk vira uma chamada de TTS — pequeno o bastante pra tocar em pipeline

CONTINUE_PROMPTS = [
    "Prefere que eu continue?",
    "Quer que eu siga com o resto?",
    "Posso continuar?",
]

# Ditas no lugar de blocos "grandes" (resumos, listas de permissões, descrições de
# OS, relatórios) — o conteúdo completo continua escrito no chat, só não é lido em
# voz alta a menos que o usuário peça explicitamente (ver `speak_full` em format()).
POINTER_PHRASES = [
    "Os detalhes estão no chat, dá uma conferida.",
    "Coloquei tudo certinho no chat pra você ler.",
    "Deixei o resumo completo escrito ali no chat.",
]

_LIST_LINE_RE = re.compile(r"^[ \t]*(?:[•\-\*]|\d+[.)])\s+")
_MIN_STRUCTURED_LIST_LINES = 3  # abaixo disso é só uma listinha curta — fala normal

_ABBREVIATIONS = {
    "sr", "sra", "srta", "dr", "dra", "prof", "profa",
    "exmo", "exma", "etc", "ex", "nº", "no", "num", "obs",
}

_MD_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_MD_CODE_INLINE_RE = re.compile(r"`([^`]*)`")
_MD_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MD_HEADER_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MD_BULLET_RE = re.compile(r"^\s*[•\-\*]\s+", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_TABLE_ROW_RE = re.compile(r"^\s*\|?[\s:\-]+\|[\s:\-|]*$", re.MULTILINE)  # linhas tipo |---|---|

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)

_SENTENCE_END_RE = re.compile(r'(?<=[.!?])\s+(?=[A-ZÀ-Úa-z0-9"\'])')

_INTRO_PAUSE_WORDS = ["Olha", "Então", "Bom", "Bem", "Certo"]

# (padrão, forma falada) — aplicado preservando a maiúscula inicial do trecho casado
_DEBUREAUCRATIZE_RULES = [
    (r"\ba\s+seguir\s+est[ãa]o\b", "olha, existem"),
    (r"\bsegue\s+abaixo\b", "vamos lá"),
    (r"\bconforme\s+solicitado\b", "certo"),
    (r"\bconforme\s+mencionado\b", "como eu disse"),
    (r"\bconforme\s+informado\b", "como eu disse"),
    (r"\bprimeiramente\b", "primeiro"),
    (r"\bdessa\s+forma\b", "assim"),
    (r"\bdeste\s+modo\b", "assim"),
    (r"\bcabe\s+ressaltar\s+que\b", "vale lembrar que"),
    (r"\bem\s+conformidade\s+com\b", "de acordo com"),
    (r"\bpor\s+conseguinte\b", "por isso"),
    (r"\bno\s+que\s+tange\s+a\b", "sobre"),
    (r"\ba\s+seguir\b", "agora"),
]

# "OS" (Ordem de Serviço) falado soa estranho/ambíguo em voz (mistura com o artigo
# "os"). Na fala, trocamos por "tíquete" — a escrita no chat continua com "OS"
# normalmente, essa troca é só pra o TTS. Concordância de gênero: "OS" é feminino
# ("a OS"), "tíquete" é masculino ("o tíquete") — as regras abaixo cobrem os
# determinantes/contrações mais comuns antes de "OS"; o resto vira só "tíquete".
# Atenção: NUNCA usar re.IGNORECASE aqui — só a sigla toda maiúscula "OS" deve virar
# "tíquete", nunca a palavra comum "os" (artigo/pronome, minúscula ou início de frase).
_OS_DETERMINER_RULES = [
    (r"(?i:à)\s+OS\b", "ao tíquete"),
    (r"(?i:da)\s+OS\b", "do tíquete"),
    (r"(?i:na)\s+OS\b", "no tíquete"),
    (r"(?i:pela)\s+OS\b", "pelo tíquete"),
    (r"(?i:nessa)\s+OS\b", "nesse tíquete"),
    (r"(?i:nesta)\s+OS\b", "neste tíquete"),
    (r"(?i:dessa)\s+OS\b", "desse tíquete"),
    (r"(?i:desta)\s+OS\b", "deste tíquete"),
    (r"(?i:essa)\s+OS\b", "esse tíquete"),
    (r"(?i:esta)\s+OS\b", "este tíquete"),
    (r"(?i:nenhuma)\s+OS\b", "nenhum tíquete"),
    (r"(?i:uma)\s+OS\b", "um tíquete"),
    (r"(?i:sua)\s+OS\b", "seu tíquete"),
    (r"(?i:minha)\s+OS\b", "meu tíquete"),
    (r"(?i:qual)\s+OS\b", "qual tíquete"),
    (r"(?i:toda)\s+OS\b", "todo tíquete"),
    (r"(?i:outra)\s+OS\b", "outro tíquete"),
    (r"(?i:a)\s+OS\b", "o tíquete"),
]
_OS_FALLBACK_RE = re.compile(r"\bOS\b")
# Depois da troca, IDs formatados tipo "OS-1234" viram "tíquete-1234" — troca o
# hífen por espaço ("tíquete 1234"), senão o TTS tenta ler o hífen junto do número.
_OS_ID_HYPHEN_RE = re.compile(r"\btíquete-(\d+)")

# Números de tíquete são tipo "JMP00067" (prefixo + zero-padding) — ditos por
# extenso o TTS lê tudo enrolado ("zero zero zero meia sete") ou vira um número
# gigante mumbled. Por padrão só fala "final 67" (como se fala no dia a dia);
# só lê os zeros/número completo se o usuário pedir explicitamente (speak_full).
_TICKET_CODE_RE = re.compile(r"\bJMP0*(\d+)\b")

# Depois de trocar "OS" (feminino) por "tíquete" (masculino), o particípio/adjetivo
# logo depois costuma ficar na concordância errada ("o tíquete foi criada"). Corrige
# só os casos mais comuns e próximos de "tíquete" (até 3 palavras de distância —
# cobre "tíquete final 657 foi criada" —, pra não arriscar pegar um adjetivo de
# uma frase seguinte sem relação nenhuma).
_OS_GENDER_AGREEMENT = {
    "criada": "criado", "editada": "editado", "atualizada": "atualizado",
    "excluída": "excluído", "aberta": "aberto", "fechada": "fechado",
    "cancelada": "cancelado", "concluída": "concluído", "finalizada": "finalizado",
    "reaberta": "reaberto", "encontrada": "encontrado", "encaminhada": "encaminhado",
    "associada": "associado", "vinculada": "vinculado", "nova": "novo", "pronta": "pronto",
}
_OS_GENDER_AGREEMENT_RE = re.compile(
    r"\btíquete\b((?:\s+\S+){0,3}?)\s+(" + "|".join(_OS_GENDER_AGREEMENT.keys()) + r")\b",
    re.IGNORECASE,
)


@dataclass
class FormattedSpeech:
    chunks: List[str] = field(default_factory=list)
    spoken_text: str = ""
    is_truncated: bool = False
    estimated_seconds: float = 0.0


class SpeechFormatter:
    """Formata texto escrito para fala natural. Sem dependência de Django/DB —
    testável isoladamente."""

    def format(self, text: str, *, max_seconds: float = MAX_SPOKEN_SECONDS,
               speak_full: bool = False) -> FormattedSpeech:
        reduced = self._reduce_structured_blocks(text or "", speak_full=speak_full)
        cleaned = self._strip_markup(reduced)
        cleaned = self._debureaucratize(cleaned)
        cleaned = self._speak_os_as_ticket(cleaned, speak_full=speak_full)
        sentences = [s for s in self._split_sentences(cleaned) if s.strip()]
        sentences = [self._add_natural_pauses(s) for s in sentences]

        if not sentences:
            return FormattedSpeech()

        full_estimate = self._estimate_seconds(" ".join(sentences))
        is_truncated = full_estimate > max_seconds
        if is_truncated:
            max_words = max(1, int(WORDS_PER_MINUTE * max_seconds / 60))
            sentences = self._truncate_to_budget(sentences, max_words)
            sentences.append(random.choice(CONTINUE_PROMPTS))

        chunks = self._group_into_chunks(sentences)
        return FormattedSpeech(
            chunks=chunks,
            spoken_text=" ".join(chunks),
            is_truncated=is_truncated,
            estimated_seconds=round(full_estimate, 1),
        )

    def _reduce_structured_blocks(self, text: str, *, speak_full: bool) -> str:
        """Corta blocos "grandes" (resumos, listas de permissões, descrições de OS,
        relatórios — parágrafos com 3+ linhas de lista/tópicos) e troca por UMA frase
        curta apontando pro chat, em vez de ditar tudo. Frases normais (mesmo que
        longas) antes/depois do bloco continuam sendo faladas — só o bloco em si é
        substituído. Se o usuário pediu explicitamente pra ouvir tudo (speak_full),
        não corta nada."""
        if speak_full or not text.strip():
            return text

        paragraphs = re.split(r"\n[ \t]*\n", text)
        output: List[str] = []
        pointer_inserted = False
        for paragraph in paragraphs:
            if self._is_structured_paragraph(paragraph):
                if not pointer_inserted:
                    output.append(random.choice(POINTER_PHRASES))
                    pointer_inserted = True
                continue
            output.append(paragraph)
        return "\n\n".join(output)

    def _is_structured_paragraph(self, paragraph: str) -> bool:
        lines = paragraph.split("\n")
        list_lines = sum(1 for line in lines if _LIST_LINE_RE.match(line))
        return list_lines >= _MIN_STRUCTURED_LIST_LINES

    def _strip_markup(self, text: str) -> str:
        text = _MD_CODE_FENCE_RE.sub("", text)
        text = _MD_BOLD_RE.sub(r"\1", text)
        text = _MD_ITALIC_RE.sub(r"\1", text)
        text = _MD_CODE_INLINE_RE.sub(r"\1", text)
        text = _MD_LINK_RE.sub(r"\1", text)
        text = _MD_HEADER_RE.sub("", text)
        text = _MD_BULLET_RE.sub("", text)
        text = _TABLE_ROW_RE.sub("", text)
        text = text.replace("|", ", ")
        text = text.replace("#", "")  # "OS #JMP00067" — o "#" não deve ser lido
        text = _EMOJI_RE.sub("", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip()

    def _debureaucratize(self, text: str) -> str:
        for pattern, replacement in _DEBUREAUCRATIZE_RULES:
            text = re.sub(pattern, self._case_preserving_sub(replacement), text, flags=re.IGNORECASE)
        return text

    def _speak_os_as_ticket(self, text: str, *, speak_full: bool = False) -> str:
        for pattern, replacement in _OS_DETERMINER_RULES:
            text = re.sub(pattern, self._case_preserving_sub(replacement), text)
        text = _OS_FALLBACK_RE.sub("tíquete", text)
        text = _OS_ID_HYPHEN_RE.sub(r"tíquete \1", text)
        if not speak_full:
            text = _TICKET_CODE_RE.sub(lambda m: f"final {m.group(1)}", text)
        text = _OS_GENDER_AGREEMENT_RE.sub(self._fix_os_gender_agreement, text)
        return text

    @staticmethod
    def _fix_os_gender_agreement(match):
        middle, word = match.group(1), match.group(2)
        replacement = _OS_GENDER_AGREEMENT.get(word.lower(), word)
        if word[:1].isupper():
            replacement = replacement[:1].upper() + replacement[1:]
        return f"tíquete{middle} {replacement}"

    @staticmethod
    def _case_preserving_sub(replacement: str):
        def _sub(match):
            matched = match.group(0)
            if matched[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement
        return _sub

    def _split_sentences(self, text: str) -> List[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        raw_parts = [p for p in _SENTENCE_END_RE.split(text) if p]
        merged: List[str] = []
        for part in raw_parts:
            if merged:
                prev = merged[-1]
                abbrev_match = re.search(r"(\w+)\.$", prev)
                if abbrev_match and abbrev_match.group(1).lower() in _ABBREVIATIONS:
                    merged[-1] = f"{prev} {part}"
                    continue
            merged.append(part)
        return [s.strip() for s in merged if s.strip()]

    def _add_natural_pauses(self, sentence: str) -> str:
        for word in _INTRO_PAUSE_WORDS:
            prefix = f"{word},"
            if sentence.startswith(prefix):
                return sentence.replace(prefix, f"{word}...", 1)
        return sentence

    def _group_into_chunks(self, sentences: List[str], max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
        chunks: List[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    def _estimate_seconds(self, text: str) -> float:
        words = len(text.split())
        return (words / WORDS_PER_MINUTE) * 60 if words else 0.0

    def _truncate_to_budget(self, sentences: List[str], max_words: int) -> List[str]:
        kept: List[str] = []
        word_count = 0
        for sentence in sentences:
            w = len(sentence.split())
            if kept and word_count + w > max_words:
                break
            kept.append(sentence)
            word_count += w
        return kept or sentences[:1]
