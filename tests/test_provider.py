import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from helix.core import Profile
from helix.providers import complete, count, stream_complete


def test_loopback_transport_contract():
    captured=[]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append((self.path,body))

            if body.get("stream"):
                chunks = [
                    {"choices":[{"delta":{"content":"hello "}}]},
                    {"choices":[{"delta":{"reasoning_content":"hidden thought","content":"world"}}]},
                    {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":2}},
                ]
                blob = "".join(
                    "data: " + json.dumps(item) + "\n\n"
                    for item in chunks
                ) + "data: [DONE]\n\n"
                payload = blob.encode()
                self.send_response(200)
                self.send_header("Content-Type","text/event-stream")
                self.send_header("Content-Length",str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            result={
                "choices":[{"message":{"content":"local transport test response"}}],
                "usage":{"prompt_tokens":12,"completion_tokens":7},
            }
            blob=json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()

    try:
        profile=Profile(
            role="engineer",
            kind="local",
            model_id="fixture-not-real-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
        )

        result=complete(profile,[{"role":"user","content":"hello"}],128)
        assert result.text == "local transport test response"
        assert result.input_tokens == 12 and result.output_tokens == 7

        streamed=list(stream_complete(
            profile,
            [{"role":"user","content":"hello"}],
            128,
        ))
        visible="".join(chunk.text for chunk in streamed)
        assert visible == "hello world"
        assert "hidden thought" not in visible
        assert streamed[-1].done is True
        assert streamed[-1].input_tokens == 12
        assert streamed[-1].output_tokens == 2

        assert captured[0][0] == "/v1/chat/completions"
        assert captured[0][1]["max_tokens"] == 128
        assert "tools" not in captured[0][1]
        assert captured[1][1]["stream"] is True
        assert captured[1][1]["stream_options"]["include_usage"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_invalid_usage_rejected():
    assert count(-1) is None
    assert count(True) is None
    assert count("100") is None
    assert count(0)==0
