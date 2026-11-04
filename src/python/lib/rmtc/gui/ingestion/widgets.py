# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The Junction GUI classes - this will likely need to be paritioned
"""

from abc import ABCMeta

from NodeGraphQt import (
    NodeGraph,
    BaseNode,
)

from Qt import QtWidgets, QtGui, QtCore

from rmtc.gui.common.dialogs import NewEntityDialog
from rmtc.system.objects import PropertyMessage, Object
from rmtc.system import RMTCException
from rmtc.track import TrackingMessage
from rmtc.track.store import EntityMessage
from rmtc.ops.scheduling import Status
from rmtc.gui.common import get_icon_path

import rmtc.track.entities
import rmtc.ops.artifacts
import rmtc.ops.train
import rmtc.ops.infer


def _sanitise_name(name):
    # HACK : prevent names from clashing with NodeGraphQt
    if name == "inputs":
        return "(inputs)"
    if name == "outputs":
        return "(outputs)"
    if name == "name":
        return "(name)"
    return name


def _desanitise_name(name):
    # HACK : prevent names from clashing with NodeGraphQt
    if name == "(name)":
        return "name"
    if name == "(inputs)":
        return "inputs"
    if name == "(outputs)":
        return "outputs"
    return name


def _is_supported(entity):
    return issubclass(
        entity,
        (
            rmtc.track.entities.Right,
            rmtc.track.entities.Artifact,
            rmtc.track.entities.Resource,
            rmtc.track.entities.License,
            rmtc.track.entities.Model,
            rmtc.track.entities.Dataset,
            rmtc.track.entities.Run,
            rmtc.track.entities.Weights,
            rmtc.track.entities.Inference,
            rmtc.track.entities.Asset,
            rmtc.track.entities.Solution,
            rmtc.track.entities.Checkpoint,
            rmtc.track.entities.Right,
        ),
    )


class EntityNode(BaseNode):
    """
    Node representation of an RMTC entity in the graphical interface.
    """

    # NodeGraphQt values
    __identifier__ = "rmtc"
    NODE_NAME = "entity_node"
    DEFAULT_COLOR = (13, 18, 23)
    UPDATE_COLOR = (60, 65, 90)

    def __init__(self, category):
        """Initialize the Entity node with UI components and connections."""
        self._entity = None
        self._factory = None
        self._ports_created = False
        self._port_map = {}
        self._block_input_connections = False  # HACK : avoid double connections

        super(EntityNode, self).__init__()
        icon_path = get_icon_path(category.lower())
        self.set_icon(icon_path)

        def set_proxy_mode(mode):
            pass

        self.view.set_proxy_mode = set_proxy_mode

        self._default_color = self.color()

    @property
    def block_input_connections(self):
        return self._block_input_connections

    @block_input_connections.setter
    def block_input_connections(self, value):
        self._block_input_connections = value

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
        entity.get_property("name").broadcaster.add(
            PropertyMessage.UPDATED, lambda data: self._update_entity()
        )  # pylint: disable=unnecessary-lambda

        # listen for status updates
        status_prop = entity.get_property("status")
        if status_prop is not None:
            status_prop.broadcaster.add(
                PropertyMessage.UPDATED, lambda data: self._update_entity()
            )  # pylint: disable=unnecessary-lambda

        # listen for entity sync updates
        entity.broadcaster.add(
            EntityMessage.REQUIRES_UPDATE, lambda data: self._update_entity()
        )  # pylint: disable=unnecessary-lambda
        entity.broadcaster.add(
            EntityMessage.UPDATED, lambda data: self._update_entity()
        )  # pylint: disable=unnecessary-lambda
        entity.broadcaster.add(
            EntityMessage.SYNCED, lambda data: self._update_entity()
        )  # pylint: disable=unnecessary-lambda

        self._entity = entity

        # update internal node properties
        self._update_entity()

    def _update_entity(self):

        if self._entity is None:
            return

        # attempt to create ports
        self.create_ports()

        # update color
        if self._entity.requires_update():
            self.set_color(*self.UPDATE_COLOR)
        else:
            self.set_color(*self.DEFAULT_COLOR)

        # update node
        self.set_property("name", self._entity.name)

        # update icon
        status_prop = self._entity.get_property("status")
        if status_prop is None:
            return
        category = self._entity.category().lower()
        icon_path = get_icon_path(category.lower())
        self.set_disabled(False)
        if status_prop.value in (
            Status.INVALID,
            Status.FAILED,
        ):
            icon_path = get_icon_path(f"{category}_invalid")
        elif status_prop.value in (Status.FINISHED,):
            icon_path = get_icon_path(f"{category}_finished")
        elif status_prop.value in (
            Status.RUNNING,
            Status.PAUSED,
        ):
            icon_path = get_icon_path(f"{category}_running")
            self.set_disabled(True)
        self.set_icon(icon_path)

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

    def on_input_connected(self, in_port, out_port):
        if self.block_input_connections:
            return
        if in_port.name() != "":
            prop = in_port.node().get_property_from_port(in_port)
            if prop is not None:
                if prop.is_array():
                    prop.append(out_port.node().entity)
                else:
                    prop.set(out_port.node().entity)
        if out_port.name() != "":
            prop = out_port.node().get_property_from_port(out_port)
            if prop is not None:
                if prop.is_array():
                    prop.append(in_port.node().entity)
                else:
                    prop.set(in_port.node().entity)

    def on_input_disconnected(self, in_port, out_port):
        prop = out_port.node().get_property_from_port(out_port)
        if prop is not None:
            if prop.is_array():
                prop.remove(in_port.node().entity)
            else:
                prop.set(None)
        prop = in_port.node().get_property_from_port(in_port)
        if prop is not None:
            if prop.is_array():
                prop.remove(out_port.node().entity)
            else:
                prop.set(None)

    def get_property_from_port(self, port):
        if port in self._port_map:
            return self._port_map[port]
        return None

    def set_property(self, name, value, push_undo=True):
        if self._entity is not None and name in self._entity.properties:
            prop = self._entity.properties[name]
            if value != prop.value:
                prop.value = value
        super(EntityNode, self).set_property(name, value, push_undo)

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
    train_request = QtCore.Signal(Object)
    infer_request = QtCore.Signal(Object)

    def __init__(self, system):
        """Initialize the RMTC Junction main window."""
        super(Junction, self).__init__()

        system.track.broadcaster.add(
            TrackingMessage.ADDED,
            lambda data: [self.create_nodes(entities=data, factory=system.factory)],
        )
        system.track.broadcaster.add(
            TrackingMessage.REMOVED,
            lambda data: [self.delete_nodes(entities=data, factory=system.factory)],
        )
        system.track.broadcaster.add(TrackingMessage.CLEARED, lambda data: self.clear())

        # construct buttons
        self._layout_action = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("layout_horizontal")), "Layout", self
        )
        self._create_solution = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("solution")), "Create Solution", self
        )
        self._create_dataset = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("dataset")), "Create Dataset", self
        )
        self._create_asset = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("asset")), "Create Asset", self
        )
        self._create_model = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("model")), "Create Model", self
        )
        self._create_license = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("license")), "Create License", self
        )
        self._create_inference = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("inference")), "Create Inference", self
        )
        self._create_run = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("run")), "Create Run", self
        )
        self._create_weights = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("weights")), "Create Weights", self
        )
        self._create_checkpoint = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("checkpoint")), "Create Checkpoint", self
        )
        self._create_rights = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("right")), "Create Right", self
        )

        self._publish_action = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("publish")), "Publish Selection", self
        )
        self._build_action = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("build")), "Build Selection", self
        )
        self._execute_action = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("execute")), "Execute Selection", self
        )

        # setup toolbar
        self._toolbar = QtWidgets.QToolBar()
        self._toolbar.addAction(self._create_license)
        self._toolbar.addAction(self._create_rights)
        self._toolbar.addAction(self._create_model)
        self._toolbar.addAction(self._create_dataset)
        self._toolbar.addAction(self._create_asset)
        self._toolbar.addAction(self._create_weights)
        self._toolbar.addAction(self._create_checkpoint)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._create_solution)
        self._toolbar.addAction(self._create_inference)
        self._toolbar.addAction(self._create_run)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._publish_action)
        self._toolbar.addAction(self._build_action)
        self._toolbar.addAction(self._execute_action)
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
        self._graph.register_node(Right)

        # connect
        self._graph.node_selected.connect(self.examine_node)
        self._create_solution.triggered.connect(self.create_solution)
        self._create_dataset.triggered.connect(self.create_dataset)
        self._create_model.triggered.connect(self.create_model)
        self._create_license.triggered.connect(self.create_license)
        self._create_asset.triggered.connect(self.create_asset)
        self._create_weights.triggered.connect(self.create_weights)
        self._create_checkpoint.triggered.connect(self.create_checkpoint)
        self._create_rights.triggered.connect(self.create_rights)
        self._create_run.triggered.connect(self.create_run)
        self._create_inference.triggered.connect(self.create_inference)
        self._layout_action.triggered.connect(self._layout)
        self._publish_action.triggered.connect(self.publish)
        self._execute_action.triggered.connect(self.execute)
        self._graph.node_double_clicked.connect(self.pull)
        self._build_action.triggered.connect(self.build)

        # add to widget
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._toolbar)
        layout.addWidget(self._graph_widget)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            entities = [node.entity for node in self._graph.selected_nodes()]
            self._system.remove_entities(entities)
            return True
        return False

    def pull(self, node):
        """Pull the node down"""
        if node.entity.requires_sync():
            self._system.pull([node.entity])
            self.setup_node_connections(node)

    def zoom(self, k=0.0):
        """Adjust the zoom level of the node graph."""
        z = self._graph.get_zoom()
        z += k
        self._graph.set_zoom(k)

    def get_connection(self):
        """Get a database connection from the system."""
        return self._system.track.open()

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

    def execute(self):
        """Call publish on the selected nodes"""
        runs = []
        inferences = []
        for node in self._graph.selected_nodes():
            entity = node.entity
            if isinstance(entity, rmtc.ops.train.Run):
                if not entity.is_complete() and not entity.is_inflight():
                    runs.append(entity)
            if isinstance(entity, rmtc.ops.infer.Inference):
                if not entity.is_complete() and not entity.is_inflight():
                    inferences.append(entity)
        if len(runs) > 0:
            self.train_request.emit(runs[0])
        if len(inferences) > 0:
            self.infer_request.emit(inferences[0])

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
        """Construct a weights node"""
        dialog = NewEntityDialog("Weights", self._system.factory)
        if dialog.exec():
            self._system.create_weights(object_type=dialog.type_class)

    def create_checkpoint(self):
        """Construct a checkpoint node"""
        dialog = NewEntityDialog("Checkpoint", self._system.factory)
        if dialog.exec():
            self._system.create_checkpoint(object_type=dialog.type_class)

    def create_inference(self):
        """Construct an inference node"""
        dialog = NewEntityDialog("Inference", self._system.factory)
        if dialog.exec():
            self._system.create_inference(object_type=dialog.type_class)

    def create_run(self):
        """Construct a run node"""
        dialog = NewEntityDialog("Run", self._system.factory)
        if dialog.exec():
            self._system.create_run(object_type=dialog.type_class)

    def create_rights(self):
        """Construct a right node"""
        text, ok = QtWidgets.QInputDialog.getText(None, "Create Rights", "Enter Name:")
        if ok:
            self._system.create_rights(name=text)

    def _layout(self):
        self._graph.auto_layout_nodes()

    def layout(self, entities=None):
        """Automatically layout nodes in the graph."""
        nodes = []
        if entities is not None:
            for entity in entities:
                node = self.get_node(entity)
                if node:
                    nodes.append(node)
        self._graph.auto_layout_nodes(nodes)

    def get_node(self, entity):
        """Find node for the given entity"""
        if entity is None:
            return None
        if entity.obj_id in self._entity_to_node:
            return self._entity_to_node.get(entity.obj_id)
        return None

    def setup_node_connections(self, node):

        # get entity - can only connect if synced
        entity = node.entity
        if entity.requires_sync():
            return
        node.create_ports()

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
                for other_entity in prop.array_value:
                    other_node = self.get_node(other_entity)
                    if other_node is not None:
                        in_port = other_node.in_port

                        # emit signal doesn't appear to control connection callback
                        other_node.block_input_connections = True
                        out_port.connect_to(port=in_port, emit_signal=False)
                        other_node.block_input_connections = False

            # for inputs, defer to the other node
            if prop.is_input():
                in_port = node.get_input(prop)
                if in_port is None:
                    continue
                for other_entity in prop.array_value:
                    other_node = self.get_node(other_entity)
                    if other_node is not None:
                        out_port = other_node.out_port

                        # emit signal doesn't appear to control connection callback
                        node.block_input_connections = True
                        out_port.connect_to(port=in_port, emit_signal=False)
                        node.block_input_connections = False

    def create_nodes(self, entities, factory):
        """Create or retrieve a node for the given entity"""
        nodes = []
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
            nodes.append(node)

        # connect it up
        for node in self._graph.all_nodes():
            self.setup_node_connections(node)

        # layout new nodes
        self._graph.auto_layout_nodes(nodes=nodes)

    def delete_nodes(self, entities, factory):
        """Delete local nodes - BUT DON'T DELETE FROM STORE"""
        for entity in entities:

            # check if we can create a node
            if not _is_supported(entity.__class__):
                continue

            # find
            node = self.get_node(entity)
            if node is None:
                continue

            # remove from graph
            self._graph.delete_node(node)
            self._entity_to_node.pop(entity.obj_id, None)


class Solution(EntityNode):
    NODE_NAME = "solution_node"

    def __init__(self):
        super(Solution, self).__init__(self.__class__.__name__)


class License(EntityNode):
    NODE_NAME = "license_node"

    def __init__(self):
        super(License, self).__init__(self.__class__.__name__)


class Run(EntityNode):
    NODE_NAME = "run_node"

    def __init__(self):
        super(Run, self).__init__(self.__class__.__name__)


class Inference(EntityNode):
    NODE_NAME = "inference_node"

    def __init__(self):
        super(Inference, self).__init__(self.__class__.__name__)


class Asset(EntityNode):
    NODE_NAME = "asset_node"

    def __init__(self):
        super(Asset, self).__init__(self.__class__.__name__)


class Weights(EntityNode):
    NODE_NAME = "weights_node"

    def __init__(self):
        super(Weights, self).__init__(self.__class__.__name__)


class Checkpoint(EntityNode):
    NODE_NAME = "checkpoint_node"

    def __init__(self):
        super(Checkpoint, self).__init__(self.__class__.__name__)


class Model(EntityNode):
    NODE_NAME = "model_node"

    def __init__(self):
        super(Model, self).__init__(self.__class__.__name__)


class Dataset(EntityNode):
    NODE_NAME = "dataset_node"

    def __init__(self):
        super(Dataset, self).__init__(self.__class__.__name__)


class Resource(EntityNode):
    NODE_NAME = "resource_node"

    def __init__(self):
        super(Resource, self).__init__(self.__class__.__name__)


class Artifact(EntityNode):
    NODE_NAME = "artifact_node"

    def __init__(self):
        super(Artifact, self).__init__(self.__class__.__name__)


class Right(EntityNode):
    NODE_NAME = "right_node"

    def __init__(self):
        super(Right, self).__init__(self.__class__.__name__)
