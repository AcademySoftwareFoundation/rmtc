# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import unittest

import pytest

pytest.importorskip("Qt")
pytest.importorskip("NodeGraphQt")

from rmtc.track.entities import License, Resource, Run, Model
from rmtc.gui.ingestion.widgets import EntityNode


class _StubPort:
    """Stand-in for a NodeGraphQt port: a name owning a node"""

    def __init__(self, name, node):
        self._name = name
        self._node = node

    def name(self):
        return self._name

    def node(self):
        return self._node


class _StubNode:
    """Stand-in for an ingestion Entity node: an entity and its port->property map"""

    def __init__(self, entity):
        self.entity = entity
        self._port_map = {}
        self.block_input_connections = False

    def add_port(self, name, prop):
        port = _StubPort(name, self)
        if prop is not None:
            self._port_map[port] = prop
        return port

    def get_property_from_port(self, port):
        return self._port_map.get(port)


class TestIngestionDisconnect(unittest.TestCase):
    """The disconnect handler must remove the upstream entity, not the node's own entity"""

    def test_disconnect_removes_upstream_from_input_array(self):
        license_a = License(name="A")
        license_b = License(name="B")
        resource = Resource(name="Test")
        resource.add_licenses([license_a, license_b])

        upstream = _StubNode(license_a)
        downstream = _StubNode(resource)
        out_port = upstream.add_port("", None)
        in_port = downstream.add_port("licenses", resource.properties["licenses"])

        EntityNode.on_input_disconnected(downstream, in_port, out_port)

        self.assertEqual([lic.name for lic in resource.licenses], ["B"])

    def test_disconnect_clears_single_reference(self):
        model = Model(name="Test Model")
        run = Run(name="Test Run")
        run.model = model

        upstream = _StubNode(model)
        downstream = _StubNode(run)
        out_port = upstream.add_port("", None)
        in_port = downstream.add_port("model", run.properties["model"])

        EntityNode.on_input_disconnected(downstream, in_port, out_port)

        self.assertIsNone(run.model)

    def test_connect_appends_upstream_to_input_array(self):
        license_a = License(name="A")
        resource = Resource(name="Test")

        upstream = _StubNode(license_a)
        downstream = _StubNode(resource)
        out_port = upstream.add_port("", None)
        in_port = downstream.add_port("licenses", resource.properties["licenses"])

        EntityNode.on_input_connected(downstream, in_port, out_port)

        self.assertEqual([lic.name for lic in resource.licenses], ["A"])

    def test_connect_sets_single_reference(self):
        model = Model(name="Test Model")
        run = Run(name="Test Run")

        upstream = _StubNode(model)
        downstream = _StubNode(run)
        out_port = upstream.add_port("", None)
        in_port = downstream.add_port("model", run.properties["model"])

        EntityNode.on_input_connected(downstream, in_port, out_port)

        self.assertIs(run.model, model)

    def test_connect_blocked_when_flag_set(self):
        license_a = License(name="A")
        resource = Resource(name="Test")

        upstream = _StubNode(license_a)
        downstream = _StubNode(resource)
        downstream.block_input_connections = True
        out_port = upstream.add_port("", None)
        in_port = downstream.add_port("licenses", resource.properties["licenses"])

        EntityNode.on_input_connected(downstream, in_port, out_port)

        self.assertEqual(len(resource.licenses), 0)