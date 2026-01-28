# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The SignalBox GUI classes - this will likely need to be paritioned
"""


import os
from abc import ABCMeta

from NodeGraphQt import (
    NodeGraph,
    BaseNode,
    NodeBaseWidget,
)

from Qt import QtWidgets, QtGui, QtSvg, QtCore

from rmtc_core.gui.common import ICON_SIZE
from rmtc import SystemMessage, track
from rmtc.system import Datetime, URI
from rmtc.objects import Object, ObjectMessage, PropertyMessage
from rmtc.track import EntityMessage, Direction

SPLITTER_SIZE = [500, 100]
REPORT_SIZE = [650, 500]


def _is_supported(entity):
    return issubclass(
        entity,
        (
            track.License,
            track.Model,
            track.Dataset,
            track.Resource,
            track.Run,
            track.Weights,
            track.Inference,
            track.Asset,
            track.Solution,
            track.Checkpoint,
        ),
    )


class SVGWidget(QtSvg.QSvgWidget):
    """
    SVG widget with fixed icon sizing.

    This widget extends QSvgWidget to display SVG graphics with a fixed
    size suitable for icons. It automatically sets the widget size to
    the predefined ICON_SIZE constant.
    """

    def __init__(self, path="", parent=None):
        """Initialize the SVG widget with fixed icon size."""
        super(SVGWidget, self).__init__(path, parent=parent)
        self.setFixedSize(ICON_SIZE, ICON_SIZE)


class NodeWidgetWrapper(NodeBaseWidget):
    """This wrapper connects QWidgets with NodeGraphQt's widget system."""

    def __init__(self, parent=None, widget=None, name=""):
        """Initialize the node widget wrapper."""
        super(NodeWidgetWrapper, self).__init__(parent)
        self.set_name(name)
        self.set_custom_widget(widget)

    def get_value(self):
        """Get the current value from the wrapped widget."""
        return 0

    def set_value(self, value):
        """Set a value on the wrapped widget."""
        pass


class Entity(BaseNode):
    """
    Node representation of an RMTC entity in the graphical interface.

    The Entity node displays an icon representing the entity type and provides
    expand/collapse functionality in both upward and downward directions. It
    manages entity properties as text inputs and handles synchronization with
    the database connection.

    It does not 'listen' to the DB - operations must happen from the UI down
    as it will not follow underlying changes.
    """

    # HACK - NodeGraphQt prevents true signals coming out of nodes
    expand_clicked = None

    __identifier__ = "rmtc"
    NODE_NAME = "entity_node"

    def __init__(self, category=""):
        """Initialize the Entity node with UI components and connections."""

        super(Entity, self).__init__()

        self._in = self.add_input("", multi_input=True)
        self._out = self.add_output("", multi_output=True)

        asset_path = f"{os.getenv('RMTC_RESOURCES')}/icons"
        icon_path = f"{asset_path}/{category.lower()}.svg"

        self._expand_up = QtWidgets.QPushButton(QtGui.QIcon(f"{asset_path}/up.svg"), "")
        self._expand_up.setFlat(True)
        self._expand_up.clicked.connect(self.do_expand_up)

        self._expand_down = QtWidgets.QPushButton(
            QtGui.QIcon(f"{asset_path}/down.svg"), ""
        )
        self._expand_down.setFlat(True)
        self._expand_down.clicked.connect(self.do_expand_down)

        self._icon_widget = SVGWidget(path=f"{asset_path}/{category.lower()}.svg")
        self._icon_widget.setEnabled(False)
        self.set_icon(icon_path)

        self._up = NodeWidgetWrapper(
            self.view, self._expand_up, name="widget_expand_up"
        )
        self._icon = NodeWidgetWrapper(self.view, self._icon_widget, name="widget_icon")
        self._down = NodeWidgetWrapper(
            self.view, self._expand_down, name="widget_expand_down"
        )
        self._icon.setOpacity(0.3)

        self.add_custom_widget(self._up)
        self.add_custom_widget(self._icon)
        self.add_custom_widget(self._down)

        self._entity = None
        self._visible_props = False
        self._up_expanded = False
        self._down_expanded = False

        # block proxy mode
        def set_proxy_mode(mode):  # pylint: disable=unused-argument
            pass

        self.view.set_proxy_mode = set_proxy_mode

        self.update_node()

    def do_expand_up(self):
        """Handle upward expansion button click."""
        self.expand_clicked(self, Direction.SOURCES)  # pylint: disable=not-callable

    def do_expand_down(self):
        """Handle downward expansion button click."""
        self.expand_clicked(self, Direction.DERIVATIVES)  # pylint: disable=not-callable

    @property
    def entity(self):
        """Get the RMTC entity associated with this node."""
        return self._entity

    def sync(self, connection):
        """Synchronize the entity with the database and update UI"""
        connection.sync([self._entity])

    def update_name(self, prop):
        """Manage property assignment - mainly for name"""
        self.set_property(prop.name, prop.value, False)

    def update_node(self, obj=None):  # pylint: disable=unused-argument

        # show/hide the expansions
        self._expand_up.show()
        if self._up_expanded:
            self._expand_up.hide()
        self._expand_down.show()
        if self._down_expanded:
            self._expand_down.hide()

        # set opacity
        if self._entity is not None and not self._entity.requires_sync():
            self._icon.setOpacity(1.0)
        else:
            self._icon.setOpacity(0.3)

    @entity.setter
    def entity(self, entity):
        """
        Set the RMTC entity for this node.

        Assigns an RMTC entity to this node and sets up the UI with system
        properties and required entity properties. Only allows setting the
        entity once to prevent overwriting existing configurations.

        The method creates text input widgets for:
        - System properties: class (entity type name) and entity_id
        - Required non-object properties from the entity's property collection

        All created widgets are initially hidden and can be made visible
        through the toggle_properties method. The "name" property is skipped
        as it's typically handled separately in the node interface.
        """

        # create cbs
        obj_cb = lambda obj: self.update_node()  # pylint: disable=unnecessary-lambda
        prop_cb = lambda data: self.update_name(data)

        # remove listeners
        if self._entity is not None:
            self._entity.broadcaster.remove(ObjectMessage.PROPERTY_UPDATED, obj_cb)
            self._entity.broadcaster.remove(EntityMessage.SYNCED, obj_cb)
            self._entity.properties["name"].broadcaster.remove(
                PropertyMessage.UPDATED, prop_cb
            )

        # assign
        self._entity = entity

        # add listeners
        if self._entity is not None:
            self._entity.broadcaster.add(ObjectMessage.PROPERTY_UPDATED, obj_cb)
            self._entity.broadcaster.add(EntityMessage.SYNCED, obj_cb)
            self._entity.properties["name"].broadcaster.add(
                PropertyMessage.UPDATED, prop_cb
            )

        # update
        self.update_node()

    def lock(self):
        """
        Lock the node's input and output ports.
        Entity properties are only definable in the class schemas,
        not the UI, so we lock them on creation.
        """
        self.in_port.lock()
        self.out_port.lock()

    def unlock(self):
        """
        Unlock the node's input and output ports for updating,
        occurs when you expand an entity.
        """
        self.in_port.unlock()
        self.out_port.unlock()

    @property
    def in_port(self):
        """Get the input port for this node - there is only 1"""
        return self._in

    @property
    def out_port(self):
        """Get the output port for this node - there is only 1"""
        return self._out

    def expanded(self, direction=None):
        """Check if the node is expanded in the specified direction."""
        if direction is None:
            return self._up_expanded and self._down_expanded
        if direction == Direction.SOURCES:
            return self._up_expanded
        return self._down_expanded

    def set_expanded(self, direction, value):
        """Set the expansion state for the specified direction."""
        if direction == Direction.SOURCES:
            self._up_expanded = value
        if direction == Direction.DERIVATIVES:
            self._down_expanded = value
        self.update_node()


class QABCMeta(type(QtWidgets.QWidget), ABCMeta):
    pass


# create a node class object inherited from BaseNode.
class SignalBox(QtWidgets.QWidget, metaclass=QABCMeta):
    """
    This class provides the primary user interface for exploring the source
    and derivative relationships in the RMTC storage system.
    """

    examine_request = QtCore.Signal(Object)

    def __init__(self, system):
        """Initialize the RMTC SignalBox main window."""
        super(SignalBox, self).__init__()
        asset_path = f"{os.getenv('RMTC_RESOURCES')}/icons"

        # construct buttons
        self._expand_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/expand.svg"), "Expand", self
        )
        self._layout_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/layout_vertical.svg"), "Layout", self
        )
        self._report_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/report.svg"), "Report", self
        )

        # setup toolbar
        self._toolbar = QtWidgets.QToolBar()
        self._toolbar.addAction(self._expand_action)
        self._toolbar.addAction(self._layout_action)
        self._toolbar.addAction(self._report_action)

        system.broadcaster.add(
            SystemMessage.ADDED,
            lambda data: [self.create_nodes(entities=data, factory=system.factory)],
        )
        system.broadcaster.add(SystemMessage.CLEARED, lambda data: self.clear())

        # init the graph
        self._system = system
        self._graph = NodeGraph()
        self._graph.set_acyclic(False)
        self._graph.set_layout_direction(1)
        self._graph_widget = self._graph.widget
        self._entity_to_node = {}
        self._has_cycle = False

        # setup drag and drop
        graphics_view = self._graph_widget.findChild(QtWidgets.QGraphicsView)

        def custom_drag_event(event):
            if event.mimeData().hasUrls():
                event.accept()
            else:
                event.ignore()

        def custom_drop_event(event):
            urls = event.mimeData().urls()
            for url in urls:
                uri = URI(scheme="file", host="localhost", path=url.toLocalFile())
                self._create_asset(uri)
            if len(urls) > 0:
                event.accept()
            else:
                event.ignore()

        graphics_view.dragEnterEvent = custom_drag_event
        graphics_view.dropEvent = custom_drop_event

        # register node wrappers
        self._graph.register_node(License)
        self._graph.register_node(Model)
        self._graph.register_node(Dataset)
        self._graph.register_node(Run)
        self._graph.register_node(Weights)
        self._graph.register_node(Inference)
        self._graph.register_node(Asset)
        self._graph.register_node(Solution)
        self._graph.register_node(Checkpoint)
        self._graph.register_node(Resource)

        # connect
        self._graph.node_selected.connect(self.examine_node)
        self._graph.node_double_clicked.connect(self.pull)
        self._expand_action.triggered.connect(self.expand_selection)
        self._layout_action.triggered.connect(self.layout)
        self._report_action.triggered.connect(self.report)

        # add to widget
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._toolbar)
        layout.addWidget(self._graph_widget)
        self.setLayout(layout)

    def update_ui(self):
        """NodeGraphQt update call - noop"""
        pass

    def zoom(self, k=0.0):
        """Adjust the zoom level of the node graph."""
        z = self._graph.get_zoom()
        z += k
        self._graph.set_zoom(k)

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

    def pull(self, node):
        """Pull the node down"""
        self._system.pull([node.entity])
        self.connect_node(node)
        self.expand_node(node, Direction.SOURCES)
        self.expand_node(node, Direction.DERIVATIVES)
        self.layout()

    def _collate_entities(self, node, category=None):
        """
        Recursively collate entities from a node tree structure.

        Traverses a hierarchical node structure and collects entities,
        optionally filtering by entity type name. The method recursively
        processes child nodes to build a flat list of entities.
        """
        entities = []
        if category is not None:
            if node[0].class_category == category:
                entities.append(node[0])
        else:
            entities.append(node[0])
        for child in node[1]:
            entities.extend(self._collate_entities(child, category))
        return entities

    def clear(self):
        self._entity_to_node = {}
        self._graph.clear_session()
        self._graph.clear_undo_stack()
        self._has_cycle = False

    def report(self):
        """
        Generate and display an MD provenance report for selected nodes.

        Creates a detailed provenance report showing the source entities
        and their relationships for all currently selected nodes. The report
        is organized by entity type and displayed in a markdown-formatted
        dialog window.
        """

        # build reports
        reports = []
        for node in self._graph.selected_nodes():
            sources = self._system.trace_sources(node.entity)
            entities = []
            for source in sources[1]:
                entities.extend(self._collate_entities(source))
            category_map = {}
            for entity in entities:
                if entity.class_category not in category_map:
                    category_map[entity.class_category] = []
                if entity not in category_map[entity.class_category]:
                    category_map[entity.class_category].append(entity)
            output = f"\n## {node.entity.name} ({node.entity.class_category})\n"
            for key, value in category_map.items():
                output += f"\n### {key}"
                for entity in value:
                    output += f"\n* {entity.name}"
            reports.append(output)

        # build dialog
        if len(reports) > 0:
            timestamp = Datetime()
            reports = "\n---\n".join(reports)
            markdown = f"# Provenance Report [{timestamp}]\n---\n{reports}"
            dialog = QtWidgets.QDialog()
            text_widget = QtWidgets.QTextEdit()
            dialog.resize(REPORT_SIZE[0], REPORT_SIZE[1])
            text_widget.setReadOnly(True)
            text_widget.setMarkdown(markdown)
            close_button = QtWidgets.QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(text_widget)
            layout.addWidget(close_button)
            dialog.setLayout(layout)
            dialog.exec_()

    def layout(self):
        """
        Automatically layout nodes in the graph.

        Applies automatic layout to all nodes in the graph to improve
        visual organization. If the graph contains cycles, shows an error
        message instead of attempting layout, as cyclic graphs cannot be
        automatically arranged.
        """
        # connect it up
        for node in self._graph.all_nodes():
            self.connect_node(node)

        if self._has_cycle:
            error_dialog = QtWidgets.QErrorMessage()
            error_dialog.showMessage("Graph has a cycle, cannot auto layout")
            error_dialog.exec_()
        else:
            self._graph.auto_layout_nodes()

    def expand_selection(self):
        """
        Expand all currently selected nodes in both directions.

        Expands all selected nodes by revealing their source entities (upward)
        and derivative entities (downward). This provides a comprehensive view
        of the entity relationships for the selected nodes.
        """
        connection = self.get_connection()
        if connection is None:
            return
        for node in self._graph.selected_nodes():
            node.sync(connection)
            self.expand_node(node, Direction.SOURCES)
            self.expand_node(node, Direction.DERIVATIVES)
        self.layout()
        connection.close()
        self._graph.auto_layout_nodes()

    def expand(self, node, direction):
        """
        Expand a specific node in the specified direction.

        Expands a single node by revealing related entities in the specified
        direction. This method is typically called in response to user
        interaction with expansion buttons on individual nodes.
        """
        connection = self.get_connection()
        if connection is None:
            return
        node.sync(connection)
        self.expand_node(node, direction)
        connection.close()
        self._graph.auto_layout_nodes()

    def _create_asset(self, uri):
        """
        Create asset nodes from a URI at the specified position.

        Uses the D&D system to find the file path referenced.

        Attempts to create asset entities from the given URI and places
        corresponding nodes at the specified coordinates in the graph.
        Includes a fallback mechanism that removes the host from the URI
        if no assets are found initially, as files sometimes omit host information.

        If no assets can be found after both attempts, displays an error
        dialog to inform the user of the failure. Each successfully created
        asset gets positioned slightly offset from the drop coordinates.
        """
        entities = self._system.get_assets(uri=str(uri), sync=False)
        if len(entities) == 0:  # HACK - remove host - files sometimes skip them
            uri.host = ""
            entities = self._system.get_assets(uri=str(uri), sync=False)
        for entity in entities:
            self.create_nodes([entity], self._system.factory)
        if len(entities) == 0:
            error_dialog = QtWidgets.QErrorMessage()
            error_dialog.showMessage(f"Failed to find artifact: {uri}")
            error_dialog.exec_()

    def lock(self):
        """Lock all nodes in the graph to prevent connections."""
        for node in self._graph.all_nodes():
            node.lock()

    def unlock(self):
        """Unlock all nodes in the graph to allow connections."""
        for node in self._graph.all_nodes():
            node.unlock()

    def get_node(self, entity):
        if entity is None:
            return None
        if entity.obj_id in self._entity_to_node:
            return self._entity_to_node[entity.obj_id]
        return None

    def connect_node(self, node):
        entity = node.entity
        if entity.requires_sync():
            return
        for prop in entity.properties.values():
            if not prop.is_object():
                continue
            in_port = node.in_port
            if prop.is_input():
                for other_entity in prop.array_value:
                    other_node = self.get_node(other_entity)
                    if other_node is not None:
                        out_port = other_node.out_port
                        out_port.connect_to(in_port)
            out_port = node.out_port
            if prop.is_output():
                for other_entity in prop.array_value:
                    other_node = self.get_node(other_entity)
                    if other_node is not None:
                        in_port = other_node.in_port
                        out_port.connect_to(in_port)

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
            node.set_layout_direction(1)
            node.factory = factory
            node.entity = entity
            node.expand_clicked = (
                self.expand
            )  # HACK: NodeGraphQt doesn't allow me to do a real signal
            self._entity_to_node[entity.obj_id] = node

        # connect it up
        for node in self._graph.all_nodes():
            self.connect_node(node)

    def expand_node(self, node, direction=Direction.DERIVATIVES):
        """Expand a node by revealing related entities in the specified direction."""

        if node.expanded(direction):
            return
        entity = node.entity

        # expand sources
        if direction == Direction.SOURCES:
            sources = self._system.trace_sources(entity, recurse=False)
            in_port = node.in_port
            for other_entity in sources[1]:
                other_node = self.get_node(other_entity)
                if other_node is not None:
                    other_node.out_port.connect_to(in_port)

        # expand derivatives
        if direction == Direction.DERIVATIVES:
            derivatives = self._system.trace_derivatives(entity, recurse=False)
            out_port = node.out_port
            for other_entity in derivatives[1]:
                other_node = self.get_node(other_entity)
                if other_node is not None:
                    out_port.connect_to(other_node.in_port)

        node.set_expanded(direction, True)


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
