# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The Junction GUI classes - this will likely need to be paritioned
"""

import os
from abc import ABCMeta

from NodeGraphQt import (
    NodeGraph,
    BaseNode,
)

from Qt import QtWidgets, QtGui, QtCore

from rmtc_core.gui.common.dialogs import NewEntityDialog
from rmtc import SystemMessage, track
from rmtc.objects import PropertyMessage, Object
from rmtc.system import RMTCException


def _sanitise_name(name):
    # HACK : prevent names from clashing with NodeGraphQt
    if name == "inputs":
        return "inputs (alias)"
    if name == "outputs":
        return "outputs (alias)"
    if name == "name":
        return "name (alias)"
    return name


def _desanitise_name(name):
    # HACK : prevent names from clashing with NodeGraphQt
    if name == "name (alias)":
        return "name"
    if name == "inputs (alias)":
        return "inputs"
    if name == "outputs (alias)":
        return "outputs"
    return name


def _is_supported(entity):
    return issubclass(
        entity,
        (
            track.Artifact,
            track.Resource,
            track.License,
            track.Model,
            track.Dataset,
            track.Run,
            track.Weights,
            track.Inference,
            track.Asset,
            track.Solution,
            track.Checkpoint,
        ),
    )


class Entity(BaseNode):
    """
    Node representation of an RMTC entity in the graphical interface.
    """

    # NodeGraphQt values
    __identifier__ = "rmtc"
    NODE_NAME = "entity_node"

    def __init__(self, category=""):
        """Initialize the Entity node with UI components and connections."""
        self._entity = None
        self._factory = None
        self._ports_created = False
        self._update_enabled = False
        self._port_map = {}

        super(Entity, self).__init__()
        asset_path = f"{os.getenv('RMTC_RESOURCES')}/icons"
        icon_path = f"{asset_path}/{category.lower()}.svg"
        self.set_icon(icon_path)

        # block proxy mode
        def set_proxy_mode(mode):  # pylint: disable=unused-argument
            pass

        self.view.set_proxy_mode = set_proxy_mode

    def enable_update(self, value):
        """Does the graph connection update the entity model?"""
        self._update_enabled = value

    @property
    def factory(self):
        """Get the RMTC factory associated with this node."""
        return self._factory

    @factory.setter
    def factory(self, factory):
        """Set the RMTC entity for this node."""
        self._factory = factory

    @property
    def entity(self):
        """Get the RMTC entity associated with this node."""
        return self._entity

    @entity.setter
    def entity(self, entity):
        """Set the RMTC entity for this node."""

        # check entity and factory
        if self._entity is not None:
            return
        if self._factory is None:
            raise RMTCException(f"No factory set on entity {entity}")

        # add self output if not a solution (end of chain)
        self.add_input("")
        self.add_output("")
        self._port_map = {}

        # add UUID
        self.add_text_input(name="_uuid", label="UUID", text=str(entity.obj_id))
        self.hide_widget("_uuid")

        # listen for name updates
        entity.properties["name"].broadcaster.add(
            PropertyMessage.UPDATED, lambda data: self.update_property(data)
        )  # pylint: disable=unnecessary-lambda

        self._entity = entity

        # attempt to create ports
        self.create_ports()

    def create_ports(self):
        """Create ports on only synced entties"""

        # do once
        if self._ports_created:
            return

        # only create ports if synced - they are invalid
        if self._entity.requires_sync():
            return

        # add other properties
        for prop in self._entity.properties.values():

            # ports only for objects
            if not prop.is_object():
                continue

            # not a node type
            if not _is_supported(prop.type_class):
                continue

            # create a port
            name = _sanitise_name(prop.name)
            port = None
            if prop.is_input():
                port = self.add_input(name, multi_input=prop.is_array())
                self._port_map[port] = prop
            if prop.is_output():
                port = self.add_output(name)
                self._port_map[port] = prop

            self._ports_created = True
            self._update_enabled = True

    def on_input_connected(self, in_port, out_port):  # pylint: disable=unused-argument
        if not self._update_enabled:
            return
        if in_port.name() != "":
            prop = in_port.node().get_property_from_port(in_port)
            if prop is not None:
                prop.append(out_port.node().entity)
        if out_port.name() != "":
            prop = out_port.node().get_property_from_port(out_port)
            if prop is not None:
                prop.append(in_port.node().entity)

    def on_input_disconnected(
        self, in_port, out_port
    ):  # pylint: disable=unused-argument
        if not self._update_enabled:
            return
        prop = out_port.node().get_property_from_port(out_port)
        if prop is not None:
            prop.remove(self.entity)
        prop = in_port.node().get_property_from_port(in_port)
        if prop is not None:
            prop.remove(self.entity)

    def get_property_from_port(self, port):
        if port in self._port_map:
            return self._port_map[port]
        return None

    def set_property(self, name, value, push_undo=True):
        """Manage property assignment - mainly for name"""
        if self._entity is not None and name in self._entity.properties:
            prop = self._entity.properties[name]
            if value != prop.value:
                prop.value = value
        super(Entity, self).set_property(name, value, push_undo)

    def update_property(self, prop):
        """Manage property assignment - mainly for name"""
        self.set_property(prop.name, prop.value, False)

    @property
    def in_port(self):
        return self.inputs()[""]

    @property
    def out_port(self):
        return self.outputs()[""]

    def get_input(self, prop):
        name = _sanitise_name(prop.name)
        if name in self.inputs():
            return self.inputs()[name]
        return None

    def get_output(self, prop):
        name = _sanitise_name(prop.name)
        if name in self.outputs():
            return self.outputs()[name]
        return None


class QABCMeta(type(QtWidgets.QWidget), ABCMeta):
    pass


class Junction(QtWidgets.QWidget, metaclass=QABCMeta):
    """
    This class provides the primary user interface for exploring the source
    and derivative relationships in the RMTC storage system.
    """

    examine_request = QtCore.Signal(Object)
    publish_request = QtCore.Signal(Object)
    build_request = QtCore.Signal(Object)

    def __init__(self, system):
        """Initialize the RMTC Junction main window."""
        super(Junction, self).__init__()
        asset_path = f"{os.getenv('RMTC_RESOURCES')}/icons"

        system.broadcaster.add(
            SystemMessage.ADDED,
            lambda data: [self.create_nodes(entities=data, factory=system.factory)],
        )
        system.broadcaster.add(SystemMessage.CLEARED, lambda data: self.clear())

        # construct buttons
        self._layout_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/layout_horizontal.svg"), "Layout", self
        )
        self._create_solution = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/solution.svg"), "Create Solution", self
        )
        self._create_dataset = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/dataset.svg"), "Create Dataset", self
        )
        self._create_asset = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/asset.svg"), "Create Asset", self
        )
        self._create_model = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/model.svg"), "Create Model", self
        )
        self._create_license = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/license.svg"), "Create License", self
        )
        self._publish_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/publish.svg"), "Publish Selection", self
        )
        self._create_weights = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/weights.svg"), "Create Weights", self
        )
        self._build_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/build.svg"), "Build Selection", self
        )

        # setup toolbar
        self._toolbar = QtWidgets.QToolBar()
        self._toolbar.addAction(self._create_license)
        self._toolbar.addAction(self._create_model)
        self._toolbar.addAction(self._create_dataset)
        self._toolbar.addAction(self._create_asset)
        self._toolbar.addAction(self._create_solution)
        self._toolbar.addAction(self._create_weights)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._publish_action)
        self._toolbar.addAction(self._build_action)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._layout_action)

        # init the graph
        self._system = system
        self._graph = NodeGraph()
        self._graph.set_acyclic(False)
        self._graph_widget = self._graph.widget
        self._entity_to_node = {}

        # register node wrappers
        self._graph.register_node(License)
        self._graph.register_node(Model)
        self._graph.register_node(Dataset)
        self._graph.register_node(Resource)
        self._graph.register_node(Run)
        self._graph.register_node(Weights)
        self._graph.register_node(Inference)
        self._graph.register_node(Asset)
        self._graph.register_node(Solution)
        self._graph.register_node(Checkpoint)
        self._graph.register_node(Artifact)

        # connect
        self._graph.node_selected.connect(self.examine_node)
        self._create_solution.triggered.connect(self.create_solution)
        self._create_dataset.triggered.connect(self.create_dataset)
        self._create_model.triggered.connect(self.create_model)
        self._create_license.triggered.connect(self.create_license)
        self._create_asset.triggered.connect(self.create_asset)
        self._create_weights.triggered.connect(self.create_weights)
        self._layout_action.triggered.connect(self.layout)
        self._publish_action.triggered.connect(self.publish)
        self._graph.node_double_clicked.connect(self.pull)
        self._build_action.triggered.connect(self.build)

        # add to widget
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._toolbar)
        layout.addWidget(self._graph_widget)
        self.setLayout(layout)

    def pull(self, node):
        """Pull the node down"""
        if node.entity.requires_sync():
            self._system.pull([node.entity])
            self.connect_node(node)

    def zoom(self, k=0.0):
        """Adjust the zoom level of the node graph."""
        z = self._graph.get_zoom()
        z += k
        self._graph.set_zoom(k)

    def update_ui(self):
        """NodeGraphQt update call - noop"""
        pass

    def run(self):
        """Run the graph - noop as this is not supported by RMTC"""
        pass

    def createNode(self):  # pylint: disable=invalid-name
        """Create a new node in the graph."""
        pass

    def deleteNode(self):  # pylint: disable=invalid-name
        """Delete a node from the graph."""
        pass

    def createInputsPair(self):  # pylint: disable=invalid-name
        """Create a pair of input connections."""
        pass

    def debug(self):
        """Return debug information - a noop"""
        return 0

    def get_connection(self):
        """Get a database connection from the system."""
        return self._system.open()

    def examine_node(self, node):
        """Examine a node by adding it to the properties panel."""
        if node is not None:
            self.examine_request.emit([node.entity])

    def publish(self):
        """Call publish on the selected nodes"""
        entities = []
        for node in self._graph.selected_nodes():
            entity = node.entity
            entities.append(entity)
        if len(entities) == 0:
            return
        self.publish_request.emit(entities)

    def build(self):
        """Call publish on the selected nodes"""
        entities = []
        for node in self._graph.selected_nodes():
            entity = node.entity
            entities.append(entity)
        if len(entities) == 0:
            return
        self.build_request.emit(entities)

    def clear(self):
        """Clear the local graph"""
        for node in self._graph.all_nodes():
            node.enable_update(False)
        self._entity_to_node = {}
        self._graph.clear_session()
        self._graph.clear_undo_stack()

    def create_solution(self):
        """Create a solution node"""
        self._system.create_solution()

    def create_model(self):
        """Construct a model node"""
        dialog = NewEntityDialog("Model", self._system.factory)
        if dialog.exec():
            self._system.create_model(object_type=dialog.type_class)

    def create_dataset(self):
        """Construct a dataset node"""
        dialog = NewEntityDialog("Dataset", self._system.factory)
        if dialog.exec():
            self._system.create_dataset(object_type=dialog.type_class)

    def create_asset(self):
        """Construct an asset node"""
        dialog = NewEntityDialog("Asset", self._system.factory)
        if dialog.exec():
            self._system.create_asset(object_type=dialog.type_class)

    def create_license(self):
        """Construct a license node"""
        dialog = NewEntityDialog("License", self._system.factory)
        if dialog.exec():
            self._system.create_license(object_type=dialog.type_class)

    def create_weights(self):
        """Construct a dataset node"""
        dialog = NewEntityDialog("Weights", self._system.factory)
        if dialog.exec():
            self._system.create_weights(object_type=dialog.type_class)

    def layout(self):
        """Automatically layout nodes in the graph."""
        self._graph.auto_layout_nodes()

    def get_node(self, entity):
        """Find node for the given entity"""
        if entity.obj_id in self._entity_to_node:
            return self._entity_to_node[entity.obj_id]
        return None

    def connect_node(self, node):

        # get entity - can only connect if synced
        entity = node.entity
        if entity.requires_sync():
            return
        node.create_ports()

        # prevent any visual connections from effecting the logical connections
        for graph_node in self._graph.all_nodes():
            graph_node.enable_update(False)

        # connect props
        for prop in entity.properties.values():

            # only use object references
            if not prop.is_object():
                continue

            # connect the out ports
            if prop.is_output():
                out_port = node.get_output(prop)
                if out_port is None:
                    continue
                out_port.unlock()
                for other_entity in prop.array_value:
                    other_node = self.get_node(other_entity)
                    if other_node is not None:
                        in_port = other_node.in_port
                        out_port.connect_to(port=in_port, emit_signal=False)
                if prop.is_member():
                    out_port.lock()

            # for inputs, defer to the other node
            if prop.is_input():
                in_port = node.get_input(prop)
                if in_port is None:
                    continue
                in_port.unlock()
                for other_entity in prop.array_value:
                    other_node = self.get_node(other_entity)
                    if other_node is not None:
                        out_port = other_node.out_port
                        out_port.connect_to(port=in_port, emit_signal=False)
                if prop.is_member():
                    in_port.lock()

        # reallow
        for graph_node in self._graph.all_nodes():
            graph_node.enable_update(True)

    def create_nodes(self, entities, factory):
        """Create or retrieve a node for the given entity"""
        for entity in entities:

            # check if we can create a node
            if not _is_supported(entity.__class__):
                continue

            # find
            if self.get_node(entity) is not None:
                continue

            # create
            node = self._graph.create_node(
                f"rmtc.{entity.class_category}",
                entity.name,
            )
            node.factory = factory
            node.entity = entity
            self._entity_to_node[entity.obj_id] = node

        # connect it up
        for node in self._graph.all_nodes():
            self.connect_node(node)


class Solution(Entity):
    NODE_NAME = "solution_node"

    def __init__(self):
        super(Solution, self).__init__(self.__class__.__name__)


class License(Entity):
    NODE_NAME = "license_node"

    def __init__(self):
        super(License, self).__init__(self.__class__.__name__)


class Run(Entity):
    NODE_NAME = "run_node"

    def __init__(self):
        super(Run, self).__init__(self.__class__.__name__)


class Inference(Entity):
    NODE_NAME = "inference_node"

    def __init__(self):
        super(Inference, self).__init__(self.__class__.__name__)


class Asset(Entity):
    NODE_NAME = "asset_node"

    def __init__(self):
        super(Asset, self).__init__(self.__class__.__name__)


class Weights(Entity):
    NODE_NAME = "weights_node"

    def __init__(self):
        super(Weights, self).__init__(self.__class__.__name__)


class Checkpoint(Entity):
    NODE_NAME = "checkpoint_node"

    def __init__(self):
        super(Checkpoint, self).__init__(self.__class__.__name__)


class Model(Entity):
    NODE_NAME = "model_node"

    def __init__(self):
        super(Model, self).__init__(self.__class__.__name__)


class Dataset(Entity):
    NODE_NAME = "dataset_node"

    def __init__(self):
        super(Dataset, self).__init__(self.__class__.__name__)


class Resource(Entity):
    NODE_NAME = "resource_node"

    def __init__(self):
        super(Resource, self).__init__(self.__class__.__name__)


class Artifact(Entity):
    NODE_NAME = "artifact_node"

    def __init__(self):
        super(Artifact, self).__init__(self.__class__.__name__)
