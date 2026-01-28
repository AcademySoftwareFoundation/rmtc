# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import Datetime
from rmtc.track import Report, Direction


class MarkdownReport(Report):
    """Basic markdown provenance report"""

    def __init__(self, system, direction=Direction.SOURCES):
        super(MarkdownReport, self).__init__(system=system, direction=direction)

    def _collate_entities(self, node, category=None):
        entities = []
        if category is not None:
            if node[0].class_category == category:
                entities.append(node[0])
        else:
            entities.append(node[0])
        for child in node[1]:
            entities.extend(self._collate_entities(child, category))
        return entities

    def __call__(self, entities=None):

        # build reports
        reports = []
        for entity in entities:
            items = []
            if self.direction == Direction.SOURCES:
                items = self.system.trace_sources(entity)
            else:
                items = self.system.trace_derivatives(entity)
            collated_entities = []
            for item in items[1]:
                collated_entities.extend(self._collate_entities(item))
            category_map = {}
            for collated_entity in collated_entities:
                if collated_entity.class_category not in category_map:
                    category_map[collated_entity.class_category] = []
                if collated_entity not in category_map[collated_entity.class_category]:
                    category_map[collated_entity.class_category].append(collated_entity)
            output = f"\n## {entity.name} ({entity.class_category})\n"
            for key, value in category_map.items():
                output += f"\n### {key}"
                for entity in value:
                    output += f"\n* {entity.name}"
            reports.append(output)

        # build markdown
        markdown = f"# Provenance Report [{Datetime()}]\n---\n"
        if len(reports) > 0:
            markdown += "\n---\n".join(reports)
        else:
            markdown += "Empty report"

        return markdown
