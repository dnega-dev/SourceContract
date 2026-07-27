"""Strict reference adapter for the SourceContract XML fixture envelope."""

import re
from typing import List, Optional
import xml.etree.ElementTree as ET

from ..contract import CONTRACT_NAME, CONTRACT_VERSION, AdapterContext, AdapterResult
from ..errors import AdapterInputError, ContractVersionError, PartialFetchError
from ..model import Relationship, SourceRecord, hash_payload

_FORBIDDEN_XML = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


class XMLReferenceAdapter:
    """Convert a small, namespace-free XML source envelope into canonical records."""

    contract_name = CONTRACT_NAME
    contract_version = CONTRACT_VERSION
    name = "xml-reference"
    fixture_family = "xml"

    def ingest(self, payload: bytes, context: AdapterContext) -> AdapterResult:
        context.require_complete()
        if not isinstance(payload, bytes):
            raise AdapterInputError("XML adapter payload must be bytes")
        if _FORBIDDEN_XML.search(payload):
            raise AdapterInputError("DOCTYPE and ENTITY declarations are not permitted")
        try:
            root = ET.fromstring(payload)
        except (ET.ParseError, RecursionError, UnicodeDecodeError) as exc:
            raise AdapterInputError("XML payload is not well-formed", detail=str(exc)) from exc
        if root.tag != "source":
            raise AdapterInputError("XML root element must be <source>")
        self._allowed_attributes(root, {"complete", "contract_version"}, "source")
        if root.attrib.get("contract_version") != CONTRACT_VERSION:
            raise ContractVersionError(
                "XML envelope contract_version {!r} is unsupported".format(
                    root.attrib.get("contract_version")
                )
            )
        if root.attrib.get("complete") != "true":
            raise PartialFetchError("XML envelope does not assert complete=\"true\"")
        children = list(root)
        if not children or children[0].tag != "document":
            raise AdapterInputError("XML source must begin with one <document> element")
        if sum(child.tag == "document" for child in children) != 1:
            raise AdapterInputError("XML source must contain exactly one <document>")
        if any(child.tag not in ("document", "record") for child in children):
            raise AdapterInputError("XML source may contain only document and record children")
        document = children[0]
        self._allowed_attributes(document, set(), "document")
        if list(document):
            raise AdapterInputError("XML <document> must contain text only")
        source_text = document.text or ""
        digest = hash_payload(payload)
        records = tuple(
            self._record(element, source_text, digest, context)
            for element in children[1:]
        )
        return AdapterResult(records=records)

    @classmethod
    def _record(
        cls,
        element: ET.Element,
        source_text: str,
        digest: str,
        context: AdapterContext,
    ) -> SourceRecord:
        cls._allowed_attributes(
            element,
            {
                "stable_id",
                "source_url",
                "title",
                "start",
                "end",
                "effective_from",
                "effective_to",
                "status",
            },
            "record",
        )
        required = {"stable_id", "title", "start", "end"}
        missing = required - set(element.attrib)
        if missing:
            raise AdapterInputError(
                "XML record is missing attributes: {}".format(", ".join(sorted(missing)))
            )
        try:
            start = int(element.attrib["start"])
            end = int(element.attrib["end"])
        except ValueError as exc:
            raise AdapterInputError("XML record start and end must be integers") from exc
        if start < 0 or end < start or end > len(source_text):
            raise AdapterInputError("XML record text span is outside document text")
        allowed_children = {"path", "relationships"}
        if any(child.tag not in allowed_children for child in element):
            raise AdapterInputError("XML record may contain only path and relationships")
        paths = element.findall("path")
        if len(paths) != 1:
            raise AdapterInputError("XML record must contain exactly one path")
        path = paths[0]
        cls._allowed_attributes(path, set(), "path")
        segments: List[str] = []
        for segment in path:
            if segment.tag != "segment":
                raise AdapterInputError("XML path may contain only segment elements")
            cls._allowed_attributes(segment, set(), "segment")
            if list(segment):
                raise AdapterInputError("XML path segment must contain text only")
            segments.append(segment.text or "")
        relationship_containers = element.findall("relationships")
        if len(relationship_containers) > 1:
            raise AdapterInputError("XML record may contain at most one relationships element")
        relationships: List[Relationship] = []
        if relationship_containers:
            container = relationship_containers[0]
            cls._allowed_attributes(container, set(), "relationships")
            for edge in container:
                if edge.tag != "relationship":
                    raise AdapterInputError(
                        "XML relationships may contain only relationship elements"
                    )
                cls._allowed_attributes(edge, {"type", "target", "detail"}, "relationship")
                if not {"type", "target"}.issubset(edge.attrib):
                    raise AdapterInputError("XML relationship requires type and target")
                if list(edge) or (edge.text and edge.text.strip()):
                    raise AdapterInputError("XML relationship must be empty")
                relationships.append(
                    Relationship(
                        type=edge.attrib["type"],
                        target=edge.attrib["target"],
                        detail=edge.attrib.get("detail"),
                    )
                )
        effective_from = cls._optional_attr(element, "effective_from")
        effective_to = cls._optional_attr(element, "effective_to")
        return SourceRecord(
            stable_id=element.attrib["stable_id"],
            source_url=element.attrib.get("source_url", context.source_url),
            title=element.attrib["title"],
            hierarchy_path=tuple(segments),
            effective_from=effective_from,
            effective_to=effective_to,
            exact_text=source_text[start:end],
            source_hash=digest,
            retrieved_at=context.retrieved_at,
            status=element.attrib.get("status", "active"),
            relationships=tuple(relationships),
        )

    @staticmethod
    def _optional_attr(element: ET.Element, name: str) -> Optional[str]:
        value = element.attrib.get(name)
        return value if value not in (None, "") else None

    @staticmethod
    def _allowed_attributes(
        element: ET.Element, allowed: set, element_name: str
    ) -> None:
        unknown = set(element.attrib) - allowed
        if unknown:
            raise AdapterInputError(
                "XML {} contains unknown attributes: {}".format(
                    element_name, ", ".join(sorted(unknown))
                )
            )
