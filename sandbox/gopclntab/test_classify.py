import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import affected, check, named, osv, stated

DUMP = {
    "go": "go1.27.1",
    "modules": {"golang.org/x/net": "v0.58.0", "go.opentelemetry.io/otel/sdk": "v1.44.0", "example.com/vendored": "v1.0.0"},
    "funcs": {"net/http.(*persistConn).readLoop", "golang.org/x/net/html.init", "os.(*Root).Chmod"},
    "funcnames": ["net/http.(*persistConn).readLoop", "net/http.(*conn).serve", "golang.org/x/net/html.init",
                  "os.(*Root).Chmod", "golang.org/x/net/http2.(*Framer).readMetaFrame", "example.com/vendored/api.Serve"],
    "files": ["/usr/local/go/src/net/http/transport.go", "/usr/local/go/src/os/root_unix.go",
              "golang.org/x/net@v0.58.0/html/const.go", "go.opentelemetry.io/otel/sdk@v1.44.0/trace/span.go",
              "k8s.io/kubernetes/vendor/example.com/vendored/api/serve.go"],
}
STD_FIXED = [{"introduced": "0"}, {"fixed": "1.26.9"}, {"introduced": "1.27.0-0"}, {"fixed": "1.27.2"}]


def report(module, events, *imports):
    return {"affected": [{"package": {"name": module}, "ranges": [{"type": "SEMVER", "events": events}],
                          **({"ecosystem_specific": {"imports": list(imports)}} if imports else {})}]}


class Versions(unittest.TestCase):
    def test_ranges(self):
        self.assertTrue(affected("1.26.8", STD_FIXED))
        self.assertFalse(affected("1.26.10", STD_FIXED))
        self.assertTrue(affected("1.27.1", STD_FIXED))
        self.assertFalse(affected("1.27.2", STD_FIXED))
        self.assertTrue(affected("v0.58.0", [{"introduced": "0"}, {"fixed": "0.58.1-0.20261009181718-2f1f834330b2"}]))
        self.assertTrue(affected("v0.0.0-20200101000000-abcdef123456", [{"introduced": "0"}, {"fixed": "0.1.0"}]))
        self.assertFalse(affected("v1.4.9", [{"introduced": "1.5.0"}, {"fixed": "1.45.0"}]))
        self.assertTrue(affected("1.4.0", [{"introduced": "0"}, {"last_affected": "1.4.0"}]))
        self.assertFalse(affected("1.4.1", [{"introduced": "0"}, {"last_affected": "1.4.0"}]))
        with self.assertRaises(ValueError):
            affected("1.4.1", [{"introduced": "0"}, {"limit": "1.5.0"}])


class Statements(unittest.TestCase):
    def test_outcome_from_the_gopclntab_sentence(self):
        cases = {
            "Its .gopclntab holds no function or source file of golang.org/x/crypto/ssh.": "none",
            "Its .gopclntab holds no Windows source file of os and nothing of internal/syscall/windows.": "none",
            "Its .gopclntab holds net/http without parseRange, the Range header parser of GO-2026-6609.": "package",
            "Its .gopclntab holds the tokenizer of golang.org/x/net/html, not childTextNodesAreLiteral of GO-2026-6866.": "package",
            "Its .gopclntab holds only the package initializer of golang.org/x/net/html, none of the parser functions.": "package",
            # "without" and "none" in a later sentence do not count.
            "Its .gopclntab holds stateBeginValue of github.com/go-jose/go-jose/v4/json, which the fix changes. "
            "conftest test reads none in its container without network.": "functions",
            "GO-2026-6505 lists no functions, and its .gopclntab holds code of all three.": "functions",
            "kube-apiserver v1.37.2 links golang.org/x/text v0.40.0.": None,
        }
        for text, want in cases.items():
            self.assertEqual(stated(text), want, text)

    def test_named_versions(self):
        self.assertEqual(named("conftest v0.71.1, the newest release, is built with Go 1.27.1 and links golang.org/x/net v0.58.0. "
                               "Its .gopclntab holds (*Framer).readMetaFrame of golang.org/x/net/http2, the HTTP/2 code."),
                         [("stdlib", "1.27.1"), ("golang.org/x/net", "v0.58.0")])
        self.assertEqual(named("links go.opentelemetry.io/otel/exporters/otlp/otlptrace, otlptrace/otlptracegrpc and otel/sdk v1.44.0."), [])


class Check(unittest.TestCase):
    def test_outcomes(self):
        cases = [
            ("functions", report("stdlib", STD_FIXED, {"path": "net/http", "symbols": ["persistConn.readLoop"]})),
            ("package", report("golang.org/x/net", [{"introduced": "0"}, {"fixed": "0.62.0"}],
                               {"path": "golang.org/x/net/html", "symbols": ["Parse"]})),
            ("none", report("golang.org/x/net", [{"introduced": "0"}, {"fixed": "0.60.0"}],
                            {"path": "golang.org/x/net/websocket", "symbols": ["Dial"]})),
            # os.(*Root).Chmod is linked, but GO-2026-6604 is Windows code and no _windows.go file is.
            ("none", report("stdlib", STD_FIXED, {"path": "os", "goos": ["windows"], "symbols": ["Root.Chmod"]})),
            ("functions", report("go.opentelemetry.io/otel/sdk", [{"introduced": "0"}, {"fixed": "1.45.0"}])),
            # A vendored or GOPATH build records file paths without @version; the function names still count.
            ("functions", report("example.com/vendored", [{"introduced": "0"}, {"fixed": "1.1.0"}])),
        ]
        for want, rep in cases:
            level, problems, why = check(f"Its .gopclntab holds {'no function' if want == 'none' else 'x'}"
                                         f"{' without y' if want == 'package' else ''}.", DUMP, [rep])
            self.assertEqual((level, problems), (want, []), why)

    def test_inlined_only(self):
        _, _, why = check("Its .gopclntab holds x.", DUMP, [osv("golang.org/x/net", "0.60.0",
                                                                {"golang.org/x/net/http2": ["Framer.readMetaFrame"]})])
        self.assertIn("Framer.readMetaFrame (inlined only)", why)

    def test_mismatch(self):
        net_http = report("stdlib", STD_FIXED, {"path": "net/http", "symbols": ["persistConn.readLoop"]})
        self.assertEqual(check("Its .gopclntab holds no function of net/http.", DUMP, [net_http])[1],
                         ["the statement says none"])
        self.assertEqual(check("It is built with Go 1.27.0 and links golang.org/x/net v0.57.0. Its .gopclntab holds x.",
                               DUMP, [net_http])[1],
                         ["Go is 1.27.1, the statement says 1.27.0", "golang.org/x/net is v0.58.0, the statement says v0.57.0"])
        fixed = report("stdlib", [{"introduced": "0"}, {"fixed": "1.27.0"}], {"path": "net/http"})
        self.assertEqual(check("Its .gopclntab holds x.", DUMP, [fixed])[:2], ("-", ["the binary links no affected version"]))
        self.assertEqual(check("Its .gopclntab holds x.", DUMP, [])[1], ["no vuln.go.dev entry"])


if __name__ == "__main__":
    unittest.main()
