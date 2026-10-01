"""RSS news fetching must not hang the engine and must still parse feeds (local servers only)."""
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import sentiment_analysis

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Demo feed</title>
<item><title>BTC demo headline</title><link>http://example.invalid/1</link></item>
<item><title>Unrelated headline</title><link>http://example.invalid/2</link></item>
</channel></rss>"""


def test_stalled_rss_server_does_not_block_forever(monkeypatch):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    accepted = []
    threading.Thread(target=lambda: accepted.append(server.accept()), daemon=True).start()

    monkeypatch.setattr(sentiment_analysis, "RSS_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(sentiment_analysis, "RSS_FEEDS", [f"http://127.0.0.1:{server.getsockname()[1]}/rss"])
    analyzer = sentiment_analysis.SentimentAnalyzer()

    result = []
    worker = threading.Thread(target=lambda: result.append(analyzer._fetch_rss_news("BTC")), daemon=True)
    started = time.time()
    worker.start()
    worker.join(15)
    server.close()
    assert result == [[]], "RSS fetch hung on a server that never answers"
    assert time.time() - started < 15


def test_rss_feed_is_parsed_and_filtered(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml")
            self.end_headers()
            self.wfile.write(RSS)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(sentiment_analysis, "RSS_FEEDS", [f"http://127.0.0.1:{httpd.server_port}/rss"])
        news = sentiment_analysis.SentimentAnalyzer()._fetch_rss_news("BTC")
    finally:
        httpd.shutdown()
    assert [n["title"] for n in news] == ["BTC demo headline"]
