from copy import deepcopy
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import time
import threading
import unittest
from unittest.mock import patch

from radar_quantum_bench.ollama import AdvisorError, OllamaAdvisor


BASE = {
    "estado": "completo",
    "resumo": {"frase_id": "resumo", "fato_ids": ["shots"]},
    "observacoes": [{"frase_id": "observado", "fato_ids": ["ideal.valid_fraction"]}],
    "limitacoes": [{"frase_id": "simulacao", "fato_ids": ["origem"]}],
    "proximo_teste": None,
}
INPUT = {"fatos": [{"id": "shots", "valor": 20480, "unidade": "medições"}],
         "proposta_base": BASE}
MODEL = {"name": "teste:latest", "model": "teste:latest", "size": 1024,
         "digest": "a" * 64}


class Response:
    def __init__(self, data, status=200, headers=None, raw=None):
        self.status = status
        self.data = raw if raw is not None else json.dumps(data).encode()
        self.position = 0
        self.headers = {"Content-Type": "application/json", **(headers or {})}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read1(self, maximum):
        chunk = self.data[self.position:self.position + maximum]
        self.position += len(chunk)
        return chunk

    def isclosed(self):
        return self.position == len(self.data)


class Connection:
    def __init__(self, response, calls, host, port, timeout):
        self.response = response
        self.calls = calls
        self.sock = None
        self.closed = False
        if (host, port) != ("127.0.0.1", 11434):
            raise AssertionError("O adaptador tentou acessar outro destino.")
        if not 0 < timeout <= 20:
            raise AssertionError("Prazo inválido.")

    def request(self, method, path, body=None, headers=None):
        self.calls.append((method, path, None if body is None else json.loads(body), headers))

    def getresponse(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def close(self):
        self.closed = True


class OllamaTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.connections = []

    def responses(self, *, model=None, shown=None, chat=None):
        return [Response({"version": "0.13.5"}),
                Response({"models": [MODEL if model is None else model]}),
                Response({"details": {"format": "gguf"}} if shown is None else shown),
                Response({"model": "teste:latest", "done": True,
                          "message": {"role": "assistant", "content": json.dumps(BASE)}})
                if chat is None else chat]

    def install(self, responses):
        def connect(host, port, timeout):
            if not responses:
                raise AssertionError("Pedido HTTP inesperado.")
            connection = Connection(responses.pop(0), self.calls, host, port, timeout)
            self.connections.append(connection)
            return connection
        return patch("radar_quantum_bench.ollama.http.client.HTTPConnection", side_effect=connect)

    def assert_failure(self, responses, code, *, source=INPUT):
        with self.install(responses):
            with self.assertRaises(AdvisorError) as raised:
                OllamaAdvisor("teste").propose(source)
        self.assertEqual(raised.exception.code, code)
        self.assertNotIn("INTERNAL_SECRET", str(raised.exception))
        return raised.exception

    def test_valid_proposal_uses_only_loopback_and_records_model_revision(self):
        advisor = OllamaAdvisor("teste")
        self.assertEqual(advisor.model, "teste:latest")
        self.assertIsNone(advisor.identity)
        source = deepcopy(INPUT)
        with self.install(self.responses()):
            self.assertEqual(advisor.propose(source), BASE)
        self.assertEqual(source, INPUT)
        self.assertEqual(advisor.identity, {"name": "teste:latest", "digest": "a" * 64,
                                           "server_version": "0.13.5"})
        copy = advisor.identity
        copy["digest"] = "changed"
        self.assertEqual(advisor.identity["digest"], "a" * 64)
        self.assertEqual([(method, path) for method, path, *_ in self.calls], [
            ("GET", "/api/version"), ("GET", "/api/tags"),
            ("POST", "/api/show"), ("POST", "/api/chat"),
        ])
        self.assertEqual(self.calls[2][2], {"model": "teste:latest"})
        body = self.calls[-1][2]
        self.assertIs(body["stream"], False)
        self.assertNotIn("tools", body)
        self.assertEqual(body["options"]["num_thread"], 1)
        schema = body["format"]
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(schema["properties"]["observacoes"]["items"]["enum"], BASE["observacoes"])
        self.assertEqual(json.loads(body["messages"][1]["content"]), INPUT)
        self.assertTrue(all(connection.closed for connection in self.connections))

    def test_remote_alias_is_rejected_before_facts_are_sent(self):
        for field in ("remote_model", "remote_host"):
            with self.subTest(field=field):
                self.calls.clear()
                model = {**MODEL, field: "INTERNAL_SECRET"}
                self.assert_failure(self.responses(model=model), "modelo_remoto_bloqueado")
                self.assertEqual(len(self.calls), 2)
                self.assertNotIn("/api/chat", str(self.calls))
                self.calls.clear()
                self.assert_failure(self.responses(shown={field: "INTERNAL_SECRET"}),
                                    "modelo_remoto_bloqueado")
                self.assertEqual(len(self.calls), 3)

    def test_uninstalled_missing_digest_or_empty_model_cannot_receive_facts(self):
        for model, code in (({**MODEL, "name": "outro:latest"}, "modelo_indisponivel"),
                            ({**MODEL, "digest": ""}, "modelo_remoto_bloqueado"),
                            ({**MODEL, "size": 0}, "modelo_remoto_bloqueado"),
                            ({**MODEL, "size": True}, "modelo_remoto_bloqueado"),
                            ({**MODEL, "model": "outro:cloud"}, "resposta_invalida")):
            with self.subTest(model=model):
                self.calls.clear()
                self.assert_failure(self.responses(model=model), code)
                self.assertEqual(len(self.calls), 2)

    def test_invalid_configuration_fails_before_any_http_request(self):
        with patch("radar_quantum_bench.ollama.http.client.HTTPConnection") as connect:
            for name in ("", "../teste", "http://127.0.0.1", "usuario/modelo", "a:b:c",
                         "teste:cloud", "teste:8b-cloud", "teste-cloud", "x" * 97, None):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    OllamaAdvisor(name)
            for timeout in (True, 0, -1, 121, float("inf"), float("nan")):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    OllamaAdvisor("teste", timeout=timeout)
            connect.assert_not_called()

    def test_redirect_is_never_followed(self):
        self.assert_failure([Response({}, status=302, headers={"Location": "https://foreign.invalid"})],
                            "resposta_invalida")
        self.assertEqual(len(self.calls), 1)

    def test_transport_errors_are_reduced_to_safe_codes(self):
        for failure, code in ((socket.timeout("INTERNAL_SECRET"), "tempo_esgotado"),
                              (ConnectionRefusedError("INTERNAL_SECRET"), "modelo_indisponivel"),
                              (http.client.BadStatusLine("INTERNAL_SECRET"), "modelo_indisponivel")):
            with self.subTest(error=type(failure).__name__):
                self.assert_failure([failure], code)

    def test_malformed_oversized_or_non_json_http_responses_are_rejected(self):
        for response in (Response({}, raw=b"{bad INTERNAL_SECRET"),
                         Response({}, raw=b'{"version":"one","version":"two"}'),
                         Response({}, raw=b'{"version":NaN}'),
                         Response({}, raw=b"\xff"), Response([]),
                         Response({}, headers={"Content-Type": "text/html"}),
                         Response({}, headers={"Content-Length": str(1024 * 1024 + 1)}),
                         Response({}, headers={"Content-Length": "1000"}),
                         Response({}, headers={"Content-Length": "-1"}),
                         Response({}, status=500)):
            with self.subTest(response=response.data[:30]):
                code = "modelo_indisponivel" if response.status == 500 else "resposta_invalida"
                self.assert_failure([response], code)

    def test_chat_envelope_and_inner_json_are_checked(self):
        examples = [
            {"model": "outro:latest", "done": True,
             "message": {"role": "assistant", "content": json.dumps(BASE)}},
            {"done": False, "message": {"role": "assistant", "content": "{}"}},
            {"done": True, "message": {"role": "user", "content": "{}"}},
            {"done": True, "message": {"role": "assistant", "content": "{}", "tool_calls": [{}]}},
            {"done": True, "message": {"role": "assistant", "content": "[]"}},
            {"done": True, "message": {"role": "assistant", "content": '{"a":1,"a":2}'}},
            {"done": True, "message": {"role": "assistant", "content": '{"a":NaN}'}},
            {"done": True, "message": {"role": "assistant", "content": 42}},
        ]
        for chat in examples:
            with self.subTest(chat=chat):
                self.assert_failure(self.responses(chat=Response({"model": "teste:latest", **chat})),
                                    "resposta_invalida")
        oversized = Response({}, raw=b"x" * (64 * 1024 + 1))
        self.assert_failure(self.responses(chat=oversized), "resposta_invalida")

    def test_invalid_input_does_not_send_http(self):
        with patch("radar_quantum_bench.ollama.http.client.HTTPConnection") as connect:
            for source in ({}, {**INPUT, "extra": "INTERNAL_SECRET"},
                           {"fatos": [], "proposta_base": {}}, [], None):
                with self.subTest(source=source), self.assertRaises(AdvisorError) as raised:
                    OllamaAdvisor("teste").propose(source)
                self.assertEqual(raised.exception.code, "resposta_invalida")
            connect.assert_not_called()

    def test_single_deadline_includes_headers_and_metadata(self):
        response = Response({"version": "0.13.5"})
        original = response.read1

        def slow_read(maximum):
            time.sleep(0.04)
            return original(maximum)

        response.read1 = slow_read
        with self.install([response]):
            started = time.monotonic()
            with self.assertRaises(AdvisorError) as raised:
                OllamaAdvisor("teste", timeout=0.01).propose(INPUT)
            self.assertEqual(raised.exception.code, "tempo_esgotado")
            self.assertLess(time.monotonic() - started, 0.2)
        self.assertEqual(len(self.calls), 1)

    def test_real_http_fixture_and_deadline_without_loading_a_model(self):
        """Real socket transport, with a declared fixture in place of Ollama."""
        slow = threading.Event()
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                seen.append(self.path)
                if slow.is_set():
                    time.sleep(0.3)
                content = {"version": "0.13.5"} if self.path == "/api/version" else {"models": [MODEL]}
                self.send_json(content)

            def do_POST(self):
                seen.append(self.path)
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/api/show":
                    self.send_json({"details": {"format": "gguf"}})
                else:
                    self.send_json({"model": body["model"], "done": True, "message": {
                        "role": "assistant", "content": json.dumps(
                            json.loads(body["messages"][1]["content"])["proposta_base"]
                        ),
                    }})

            def send_json(self, body):
                data = json.dumps(body).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        original_connection = http.client.HTTPConnection

        def transport(host, port, timeout):
            self.assertEqual((host, port), ("127.0.0.1", 11434))
            return original_connection(host, server.server_port, timeout=timeout)

        try:
            with patch("radar_quantum_bench.ollama.http.client.HTTPConnection", side_effect=transport):
                self.assertEqual(OllamaAdvisor("teste").propose(INPUT), BASE)
                self.assertEqual(seen, ["/api/version", "/api/tags", "/api/show", "/api/chat"])
                slow.set()
                started = time.monotonic()
                with self.assertRaises(AdvisorError) as raised:
                    OllamaAdvisor("teste", timeout=0.05).propose(INPUT)
                self.assertEqual(raised.exception.code, "tempo_esgotado")
                self.assertLess(time.monotonic() - started, 0.2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
