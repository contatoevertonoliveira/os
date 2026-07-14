import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from tickets.models import SystemSettings, AIProviderConfig
from tickets.speech_formatter import FormattedSpeech


class AIChatViewSpeechFieldTest(TestCase):
    """Confirma que /ai/chat/ ganhou a chave 'speech' sem perder nenhuma chave
    existente na resposta — a mudança é puramente aditiva."""

    def setUp(self):
        self.user = User.objects.create_user(username='jota4user', password='password')
        SystemSettings.objects.create(pk=1, ai_enabled=True)
        AIProviderConfig.objects.create(
            name='Teste', provider='anthropic', model='claude-haiku-4-5-20251001',
            api_key='fake-key', is_active=True,
        )
        self.client.login(username='jota4user', password='password')

    @patch('tickets.views_ai.run_agent')
    def test_response_includes_speech_key(self, mock_run_agent):
        mock_run_agent.return_value = "Tudo certo com a sua OS."

        resp = self.client.post(
            reverse('ai_chat'),
            data=json.dumps({"message": "oi"}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Chaves que já existiam antes desta mudança continuam presentes
        for key in ("ok", "session_id", "response", "clear_chat", "new_ticket_id",
                    "new_ticket_formatted_id", "updated_ticket_id", "ticket_list_changed",
                    "open_private_chat", "navigate_url"):
            self.assertIn(key, data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["response"], "Tudo certo com a sua OS.")
        # Chave nova, aditiva
        self.assertIn("speech", data)
        self.assertIsNotNone(data["speech"])
        self.assertIn("chunks", data["speech"])
        self.assertIn("is_truncated", data["speech"])
        self.assertIn("estimated_seconds", data["speech"])
        self.assertGreater(len(data["speech"]["chunks"]), 0)

    @patch('tickets.views_ai.SpeechFormatter')
    @patch('tickets.views_ai.run_agent')
    def test_speech_formatter_error_degrades_gracefully(self, mock_run_agent, mock_formatter_cls):
        """Se o SpeechFormatter falhar, a resposta de texto continua indo normalmente
        e 'speech' vira None em vez de quebrar o endpoint inteiro."""
        mock_run_agent.return_value = "Resposta normal."
        mock_formatter_cls.return_value.format.side_effect = RuntimeError("boom")

        resp = self.client.post(
            reverse('ai_chat'),
            data=json.dumps({"message": "oi"}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["response"], "Resposta normal.")
        self.assertIsNone(data["speech"])

    @patch('tickets.views_ai.SpeechFormatter')
    @patch('tickets.views_ai.run_agent')
    def test_normal_message_does_not_request_full_speech(self, mock_run_agent, mock_formatter_cls):
        mock_run_agent.return_value = "Aqui está o resumo completo."
        mock_formatter_cls.return_value.format.return_value = FormattedSpeech(
            chunks=["ok"], spoken_text="ok", is_truncated=False, estimated_seconds=1.0
        )

        self.client.post(
            reverse('ai_chat'),
            data=json.dumps({"message": "quantas OS estão abertas?"}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        _, kwargs = mock_formatter_cls.return_value.format.call_args
        self.assertFalse(kwargs["speak_full"])

    @patch('tickets.views_ai.SpeechFormatter')
    @patch('tickets.views_ai.run_agent')
    def test_explicit_read_aloud_request_sets_speak_full(self, mock_run_agent, mock_formatter_cls):
        mock_run_agent.return_value = "Aqui está o resumo completo."
        mock_formatter_cls.return_value.format.return_value = FormattedSpeech(
            chunks=["ok"], spoken_text="ok", is_truncated=False, estimated_seconds=1.0
        )

        self.client.post(
            reverse('ai_chat'),
            data=json.dumps({"message": "pode ler o resumo pra mim?"}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        _, kwargs = mock_formatter_cls.return_value.format.call_args
        self.assertTrue(kwargs["speak_full"])


class AITTSViewTest(TestCase):
    """Guarda de regressão: confirma que /ai/chat/tts/ continua funcionando pra
    chamadas repetidas (uma por chunk, no pipeline de reprodução do frontend),
    sem exigir nenhum endpoint novo."""

    def setUp(self):
        self.user = User.objects.create_user(username='ttsuser', password='password')
        SystemSettings.objects.create(pk=1, ai_enabled=True)
        self.client.login(username='ttsuser', password='password')

    @patch('tickets.ai_tools.tts_synthesize')
    def test_repeated_chunk_calls_succeed(self, mock_tts_synthesize):
        mock_tts_synthesize.return_value = b"fake-mp3-bytes"

        for chunk_text in ["Primeira frase.", "Segunda frase."]:
            resp = self.client.post(
                reverse('ai_chat_tts'),
                data=json.dumps({"text": chunk_text}),
                content_type='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp['Content-Type'], 'audio/mpeg')
            self.assertEqual(resp.content, b"fake-mp3-bytes")

    def test_empty_text_returns_400(self):
        resp = self.client.post(
            reverse('ai_chat_tts'),
            data=json.dumps({"text": ""}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 400)
