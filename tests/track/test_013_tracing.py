# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import unittest

from rmtc.track.tracing import Tracer


class FakeTracer(Tracer):
    """Minimal concrete Tracer used to exercise the ABC contract"""

    def __init__(self, sources=None, derivatives=None):
        self._sources = sources if sources is not None else []
        self._derivatives = derivatives if derivatives is not None else []

    def trace_sources(self, uris, recurse=False):
        return self._sources

    def trace_derivatives(self, uris, recurse=False):
        return self._derivatives


class TestTracer(unittest.TestCase):

    def test_tracer_is_abstract(self):
        with self.assertRaises(TypeError):
            Tracer()

    def test_concrete_subclass_must_implement_both_methods(self):
        class IncompleteTracer(Tracer):
            def trace_sources(self, uris, recurse=False):
                return []

        with self.assertRaises(TypeError):
            IncompleteTracer()

    def test_concrete_subclass_trace_sources(self):
        tracer = FakeTracer(sources=["a", "b"])
        self.assertEqual(tracer.trace_sources(["uri"]), ["a", "b"])

    def test_concrete_subclass_trace_derivatives(self):
        tracer = FakeTracer(derivatives=["c"])
        self.assertEqual(tracer.trace_derivatives(["uri"]), ["c"])


if __name__ == "__main__":
    unittest.main()
