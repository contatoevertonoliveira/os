from django.test import TestCase

from tickets.speech_formatter import SpeechFormatter, MAX_CHUNK_CHARS, CONTINUE_PROMPTS, POINTER_PHRASES


class SpeechFormatterTest(TestCase):
    def setUp(self):
        self.formatter = SpeechFormatter()

    def test_empty_input_does_not_crash(self):
        result = self.formatter.format("")
        self.assertEqual(result.chunks, [])
        self.assertEqual(result.spoken_text, "")
        self.assertFalse(result.is_truncated)

    def test_whitespace_only_input(self):
        result = self.formatter.format("   \n\n  ")
        self.assertEqual(result.chunks, [])

    def test_sentence_splitting(self):
        result = self.formatter.format("Primeira frase. Segunda frase! Terceira frase?")
        self.assertEqual(len(result.chunks), 1)
        self.assertIn("Primeira frase.", result.spoken_text)
        self.assertIn("Segunda frase!", result.spoken_text)
        self.assertIn("Terceira frase?", result.spoken_text)

    def test_abbreviation_does_not_split_sentence(self):
        result = self.formatter.format("Fale com o Sr. Fulano sobre a OS.")
        # "Sr." não deve virar um corte de frase indevido
        self.assertNotIn("Fulano", result.chunks[0].split("Sr.")[0])

    def test_debureaucratize_a_seguir_estao(self):
        result = self.formatter.format("A seguir estão três possibilidades.")
        # "Olha," vira "Olha..." pela inserção de pausa natural — comportamento esperado
        self.assertIn("existem três possibilidades", result.spoken_text.lower())
        self.assertTrue(result.spoken_text.lower().startswith("olha"))
        self.assertNotIn("a seguir estão", result.spoken_text.lower())

    def test_debureaucratize_segue_abaixo(self):
        result = self.formatter.format("Segue abaixo a lista de clientes.")
        self.assertIn("vamos lá", result.spoken_text.lower())
        self.assertNotIn("segue abaixo", result.spoken_text.lower())

    def test_debureaucratize_conforme_solicitado(self):
        result = self.formatter.format("Conforme solicitado, a OS foi criada.")
        self.assertIn("certo", result.spoken_text.lower())
        self.assertNotIn("conforme solicitado", result.spoken_text.lower())

    def test_debureaucratize_primeiramente(self):
        result = self.formatter.format("Primeiramente, preciso confirmar o cliente.")
        self.assertIn("primeiro", result.spoken_text.lower())
        self.assertNotIn("primeiramente", result.spoken_text.lower())

    def test_debureaucratize_preserves_capitalization(self):
        result = self.formatter.format("Primeiramente, vamos confirmar os dados.")
        self.assertTrue(result.spoken_text.startswith("Primeiro"))

    def test_strips_markdown_bold_and_code(self):
        result = self.formatter.format("O ticket **OS-1234** foi criado com `status: aberto`.")
        # "OS-1234" falado vira "tíquete 1234" (ver testes de OS -> tíquete abaixo)
        self.assertIn("tíquete 1234", result.spoken_text)
        self.assertIn("status: aberto", result.spoken_text)
        self.assertNotIn("**", result.spoken_text)
        self.assertNotIn("`", result.spoken_text)

    def test_strips_headers_and_bullets(self):
        result = self.formatter.format("# Resumo\n- Cliente: Acme\n- Status: aberto")
        self.assertNotIn("#", result.spoken_text)
        self.assertNotIn("- Cliente", result.spoken_text)
        self.assertIn("Cliente: Acme", result.spoken_text)

    def test_strips_markdown_links_keeping_label(self):
        result = self.formatter.format("Veja o [chamado OS-1234](https://example.com/1234) criado.")
        self.assertIn("chamado tíquete 1234", result.spoken_text)
        self.assertNotIn("https://", result.spoken_text)

    def test_strips_emoji(self):
        result = self.formatter.format("Histórico limpo! 🧹 Como posso ajudar? 👋")
        self.assertNotIn("🧹", result.spoken_text)
        self.assertNotIn("👋", result.spoken_text)
        self.assertIn("Como posso ajudar", result.spoken_text)

    def test_preserves_numbers_and_names(self):
        text = "A OS-4821 do cliente Acme Corp foi aberta às 14h30."
        result = self.formatter.format(text)
        self.assertIn("tíquete 4821", result.spoken_text)
        self.assertIn("Acme Corp", result.spoken_text)
        self.assertIn("14h30", result.spoken_text)

    def test_chunks_never_exceed_max_chars_for_normal_sentences(self):
        text = " ".join(f"Esta é a frase número {i} do teste de agrupamento em pedaços." for i in range(20))
        result = self.formatter.format(text, max_seconds=1000)
        for chunk in result.chunks:
            self.assertLessEqual(len(chunk), MAX_CHUNK_CHARS)

    def test_chunks_concatenate_back_to_spoken_text(self):
        result = self.formatter.format("Primeira frase. Segunda frase. Terceira frase.")
        self.assertEqual(" ".join(result.chunks), result.spoken_text)

    def test_short_text_is_not_truncated(self):
        result = self.formatter.format("Tudo certo com a sua OS.")
        self.assertFalse(result.is_truncated)
        self.assertNotIn("continuar", result.spoken_text.lower())

    def test_long_text_is_truncated_with_continue_prompt(self):
        long_text = " ".join(f"Esta é a frase número {i} de uma resposta bem longa." for i in range(40))
        result = self.formatter.format(long_text, max_seconds=40.0)
        self.assertTrue(result.is_truncated)
        self.assertTrue(any(prompt in result.spoken_text for prompt in CONTINUE_PROMPTS))
        spoken_word_count = len(result.spoken_text.split())
        # orçamento de ~40s a 135 palavras/min ~ 90 palavras, + a frase de continuação
        self.assertLess(spoken_word_count, 110)

    def test_estimated_seconds_reflects_original_untruncated_length(self):
        long_text = " ".join(f"Esta é a frase número {i} de uma resposta bem longa." for i in range(40))
        result = self.formatter.format(long_text, max_seconds=40.0)
        self.assertGreater(result.estimated_seconds, 40.0)

    # ── Blocos estruturados (resumos/listas grandes) não são ditados por padrão ──

    def test_large_bullet_block_replaced_by_pointer_phrase(self):
        text = (
            "Você é Super Admin, Everton — tá tudo liberado pra você! Olha só seu status:\n\n"
            "- Chat IA: ativado\n"
            "- Ver OS: sim\n"
            "- Criar OS: sim\n"
            "- Editar OS: sim\n"
            "- Excluir OS: sim\n\n"
            "Quer que eu ative o chat pra mais alguém?"
        )
        result = self.formatter.format(text)
        self.assertIn("tá tudo liberado", result.spoken_text)
        self.assertIn("Quer que eu ative o chat", result.spoken_text)
        self.assertNotIn("Ver OS", result.spoken_text)
        self.assertNotIn("Criar OS", result.spoken_text)
        self.assertIn("chat", result.spoken_text.lower())

    def test_consecutive_structured_paragraphs_collapse_into_one_pointer(self):
        text = (
            "Resumo do que eu faço:\n\n"
            "Usuários:\n- Listar\n- Editar\n- Resetar senha\n\n"
            "Permissões:\n- Criar nível\n- Bloquear página\n- Liberar acesso\n\n"
            "Nada mais é necessário da sua parte."
        )
        result = self.formatter.format(text)
        pointer_count = sum(1 for phrase in POINTER_PHRASES if phrase in result.spoken_text)
        self.assertEqual(pointer_count, 1)
        self.assertNotIn("Listar", result.spoken_text)
        self.assertNotIn("Criar nível", result.spoken_text)
        self.assertIn("Nada mais é necessário", result.spoken_text)

    def test_small_list_is_still_spoken_normally(self):
        text = "Temos duas opções:\n- Fazer agora\n- Fazer depois\nQual prefere?"
        result = self.formatter.format(text)
        self.assertIn("Fazer agora", result.spoken_text)
        self.assertIn("Fazer depois", result.spoken_text)
        for phrase in POINTER_PHRASES:
            self.assertNotIn(phrase, result.spoken_text)

    def test_speak_full_bypasses_pointer_replacement(self):
        text = (
            "Aqui está o resumo:\n\n"
            "- Cliente: Acme\n- Status: aberto\n- Prazo: sexta\n\n"
            "Confirma?"
        )
        result = self.formatter.format(text, speak_full=True)
        self.assertIn("Cliente: Acme", result.spoken_text)
        self.assertIn("Status: aberto", result.spoken_text)
        for phrase in POINTER_PHRASES:
            self.assertNotIn(phrase, result.spoken_text)

    def test_all_structured_content_with_no_prose_still_returns_pointer(self):
        text = "- Item um\n- Item dois\n- Item três\n- Item quatro"
        result = self.formatter.format(text)
        self.assertTrue(any(phrase in result.spoken_text for phrase in POINTER_PHRASES))
        self.assertNotIn("Item um", result.spoken_text)

    # ── "OS" falada como "tíquete" (nunca a palavra comum "os") ──────────────

    def test_os_replaced_with_ticket(self):
        result = self.formatter.format("A OS foi criada com sucesso.")
        self.assertIn("tíquete", result.spoken_text.lower())
        self.assertNotIn("OS", result.spoken_text)

    def test_lowercase_os_article_is_not_touched(self):
        result = self.formatter.format("Os clientes que estão na OS são esses.")
        self.assertTrue(result.spoken_text.startswith("Os clientes"))
        self.assertIn("no tíquete", result.spoken_text.lower())

    def test_os_determiner_gender_agreement(self):
        cases = {
            "A OS foi criada com sucesso.": "o tíquete foi criado",
            "Essa OS já está aberta.": "esse tíquete já está aberto",
            "Não encontrei nenhuma OS com esse número.": "nenhum tíquete",
            "Esta OS foi excluída.": "este tíquete foi excluído",
            "Confirma a criação da OS?": "do tíquete",
        }
        for text, expected_fragment in cases.items():
            result = self.formatter.format(text)
            self.assertIn(expected_fragment, result.spoken_text.lower(), msg=text)

    def test_bare_os_falls_back_to_ticket(self):
        result = self.formatter.format("Criar OS para o cliente Acme.")
        self.assertIn("Criar tíquete", result.spoken_text)

    # ── Código de tíquete (JMP00067) falado como "final 67", sem os zeros ────

    def test_ticket_code_speaks_final_number_without_zeros(self):
        result = self.formatter.format("OS #JMP00067 excluída com sucesso.")
        self.assertIn("final 67", result.spoken_text)
        self.assertNotIn("JMP", result.spoken_text)
        self.assertNotIn("00067", result.spoken_text)
        self.assertNotIn("#", result.spoken_text)

    def test_ticket_code_gender_agreement_still_applies(self):
        result = self.formatter.format("A OS #JMP00657 foi criada com sucesso.")
        self.assertIn("final 657 foi criado", result.spoken_text)

    def test_ticket_code_speak_full_keeps_raw_code(self):
        result = self.formatter.format("OS #JMP00067 excluída com sucesso.", speak_full=True)
        self.assertIn("JMP00067", result.spoken_text)
        self.assertNotIn("final", result.spoken_text)

    def test_stray_hash_symbol_is_stripped(self):
        result = self.formatter.format("Confira o item #3 da lista.")
        self.assertNotIn("#", result.spoken_text)
        self.assertIn("item 3", result.spoken_text)

    # ── Risada escrita ("kkk"/"hahaha"/"rsrs") falada como "ha ha" ───────────

    def test_kkk_laugh_becomes_spoken_ha(self):
        result = self.formatter.format("kkkkk que isso")
        self.assertNotIn("kkk", result.spoken_text.lower())
        self.assertIn("ha ha", result.spoken_text.lower())

    def test_hahaha_laugh_becomes_spoken_ha(self):
        result = self.formatter.format("hahahaha isso foi engraçado")
        self.assertNotIn("hahaha", result.spoken_text.lower())
        self.assertIn("ha ha ha", result.spoken_text.lower())

    def test_rsrs_laugh_becomes_spoken_ha(self):
        result = self.formatter.format("rsrsrs verdade")
        self.assertNotIn("rsrs", result.spoken_text.lower())
        self.assertIn("ha ha", result.spoken_text.lower())

    def test_uppercase_laugh_stays_uppercase(self):
        result = self.formatter.format("KKKK muito bom")
        self.assertIn("HA HA", result.spoken_text)

    def test_short_laugh_has_minimum_two_syllables(self):
        result = self.formatter.format("kk")
        self.assertEqual(result.spoken_text.strip(), "ha ha")

    def test_single_rs_is_not_treated_as_laugh(self):
        # "rs" sozinho (sem repetição) é ambíguo (ex: sigla de estado) — não mexe
        result = self.formatter.format("Vou verificar rs")
        self.assertIn("rs", result.spoken_text.lower())
        self.assertNotIn("ha ha", result.spoken_text.lower())

    def test_laugh_pattern_inside_word_is_not_touched(self):
        result = self.formatter.format("Fomos fazer trekking na trilha")
        self.assertIn("trekking", result.spoken_text.lower())
