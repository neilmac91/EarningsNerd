"""Build a deterministic offline HTML review aid with exact byte locators.

This module projects text and structure; it does not render CSS, execute markup,
or attest that a human or model reviewed the source semantically.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_UNIT_BYTES = 2 * 1024 * 1024
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
TABLE_TAGS = {"table", "tr", "td", "th"}
BREAK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "caption", "dd", "div", "dl", "dt",
    "figcaption", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li",
    "main", "nav", "ol", "p", "pre", "section", "table", "td", "th", "title", "tr", "ul",
}
HIDDEN_STYLE = re.compile(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\s*(?:;|$)", re.I)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _span(raw: bytes, start: int, end: int) -> dict[str, Any]:
    if not 0 <= start <= end <= len(raw):
        raise ValueError("invalid source byte span")
    payload = raw[start:end]
    return {"start": start, "end": end, "bytes": end - start, "sha256": _sha(payload)}


class _ProjectionParser(HTMLParser):
    def __init__(self, raw: bytes, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self.raw = raw
        self.text = text
        self.char_bytes = [0]
        for char in text:
            self.char_bytes.append(self.char_bytes[-1] + len(char.encode("utf-8")))
        self.line_chars = [0]
        self.line_chars.extend(index + 1 for index, char in enumerate(text) if char == "\n")
        self.events: list[dict[str, Any]] = []
        self.attributes: list[dict[str, Any]] = []
        self.attribute_by_id: dict[str, dict[str, Any]] = {}
        self.units: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []
        self.images: list[dict[str, Any]] = []
        self.exclusions: list[dict[str, Any]] = []
        self.elements: list[dict[str, Any]] = []
        self.table_stack: list[dict[str, Any]] = []
        self.element_stack: list[dict[str, Any]] = []

    def _byte_position(self) -> int:
        line, column = self.getpos()
        if line < 1 or line > len(self.line_chars):
            raise ValueError("parser reported an invalid source position")
        char_index = self.line_chars[line - 1] + column
        if char_index > len(self.text):
            raise ValueError("parser reported an invalid source column")
        return self.char_bytes[char_index]

    def _event(self, kind: str, start: int, end: int, **values: Any) -> dict[str, Any]:
        if end - start > MAX_UNIT_BYTES:
            raise ValueError(f"oversized single parser unit: {end - start} bytes")
        event = {"id": f"E{len(self.events) + 1:06d}", "kind": kind, **_span(self.raw, start, end), **values}
        self.events.append(event)
        return event

    def _markup_end(self, start: int) -> int:
        quote: int | None = None
        for index in range(start + 1, len(self.raw)):
            value = self.raw[index]
            if quote is not None:
                if value == quote:
                    quote = None
            elif value in (34, 39):
                quote = value
            elif value == 62:
                return index + 1
        raise ValueError("truncated markup boundary")

    def _attrs(self, start: int, end: int, tag: str) -> list[str]:
        source = self.raw[start:end].decode("utf-8", "strict")
        prefix = re.match(r"<\s*[^\s/>]+", source)
        if prefix is None:
            raise ValueError("ambiguous start-tag boundary")
        index = prefix.end()
        attribute_ids: list[str] = []
        while index < len(source):
            while index < len(source) and source[index].isspace():
                index += 1
            if index >= len(source) or source[index] == ">" or source.startswith("/>", index):
                break
            name_start = index
            while index < len(source) and not source[index].isspace() and source[index] not in "=/>":
                index += 1
            if index == name_start:
                raise ValueError("ambiguous attribute boundary")
            name_end = index
            while index < len(source) and source[index].isspace():
                index += 1
            value_start: int | None = None
            value_end: int | None = None
            quote = ""
            if index < len(source) and source[index] == "=":
                index += 1
                while index < len(source) and source[index].isspace():
                    index += 1
                if index >= len(source):
                    raise ValueError("truncated attribute value")
                if source[index] in "\"'":
                    quote = source[index]
                    index += 1
                    value_start = index
                    closing = source.find(quote, index)
                    if closing < 0:
                        raise ValueError("unterminated quoted attribute")
                    value_end = closing
                    index = closing + 1
                else:
                    value_start = index
                    while index < len(source) and not source[index].isspace() and source[index] not in ">":
                        index += 1
                    value_end = index
                    if value_start == value_end:
                        raise ValueError("empty unquoted attribute value")
            char_base = self._char_index_for_byte(start)
            raw_start = self.char_bytes[char_base + name_start]
            raw_end = self.char_bytes[char_base + index]
            name_byte_start = self.char_bytes[char_base + name_start]
            name_byte_end = self.char_bytes[char_base + name_end]
            value_span = None
            decoded_value = None
            if value_start is not None and value_end is not None:
                value_byte_start = self.char_bytes[char_base + value_start]
                value_byte_end = self.char_bytes[char_base + value_end]
                value_span = _span(self.raw, value_byte_start, value_byte_end)
                decoded_value = html.unescape(source[value_start:value_end])
            record = {
                "id": f"A{len(self.attributes) + 1:06d}",
                "tag": tag,
                "name": source[name_start:name_end].lower(),
                "value": decoded_value,
                "quote": quote or None,
                "span": _span(self.raw, raw_start, raw_end),
                "name_span": _span(self.raw, name_byte_start, name_byte_end),
                "value_span": value_span,
            }
            self.attributes.append(record)
            self.attribute_by_id[record["id"]] = record
            attribute_ids.append(record["id"])
        return attribute_ids

    def _char_index_for_byte(self, byte_index: int) -> int:
        # Start-tag boundaries always coincide with decoded UTF-8 character boundaries.
        lo, hi = 0, len(self.char_bytes)
        while lo < hi:
            middle = (lo + hi) // 2
            if self.char_bytes[middle] < byte_index:
                lo = middle + 1
            else:
                hi = middle
        if lo == len(self.char_bytes) or self.char_bytes[lo] != byte_index:
            raise ValueError("source byte position is not a UTF-8 character boundary")
        return lo

    def _attribute_map(self, ids: list[str]) -> dict[str, list[str | None]]:
        values: dict[str, list[str | None]] = {}
        for identifier in ids:
            item = self.attribute_by_id[identifier]
            values.setdefault(item["name"], []).append(item["value"])
        return values

    def _hidden_reasons(self) -> list[str]:
        reasons: list[str] = []
        for element in self.element_stack:
            reasons.extend(element["hidden_reasons"])
        return list(dict.fromkeys(reasons))

    def _current_cell(self) -> dict[str, Any] | None:
        for table in reversed(self.table_stack):
            if table.get("cell") is not None:
                return table["cell"]
        return None

    def _close_table_part(self, tag: str) -> None:
        if not self.table_stack:
            return
        state = self.table_stack[-1]
        if tag in {"td", "th"}:
            state["cell"] = None
        elif tag == "tr":
            state["cell"] = None
            state["row"] = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        del attrs_list
        tag = tag.lower()
        start = self._byte_position()
        raw_tag = self.get_starttag_text()
        if raw_tag is None:
            raise ValueError("start tag has no source text")
        end = start + len(raw_tag.encode("utf-8"))
        attribute_ids = self._attrs(start, end, tag)
        event = self._event("start_tag", start, end, tag=tag, attribute_ids=attribute_ids)
        values = self._attribute_map(attribute_ids)
        hidden_reasons = []
        if "hidden" in values:
            hidden_reasons.append("hidden_attribute")
        if any(str(value).lower() == "true" for value in values.get("aria-hidden", [])):
            hidden_reasons.append("aria_hidden_true")
        if any(value and HIDDEN_STYLE.search(value) for value in values.get("style", [])):
            hidden_reasons.append("inline_style_hidden")
        if tag == "ix:hidden":
            hidden_reasons.append("inline_xbrl_hidden")
        element = {
            "tag": tag,
            "event_id": event["id"],
            "content_start": end,
            "hidden_reasons": hidden_reasons,
        }
        node = {
            "id": f"N{len(self.elements) + 1:06d}",
            "tag": tag,
            "start_event_id": event["id"],
            "attribute_ids": attribute_ids,
            "hidden_reasons": hidden_reasons,
        }
        self.elements.append(node)
        element["node_id"] = node["id"]
        element["node"] = node
        parent_cell = self._current_cell()
        if tag == "table":
            table = {
                "id": f"T{len(self.tables) + 1:05d}",
                "event_id": event["id"],
                "parent_table_id": self.table_stack[-1]["table"]["id"] if self.table_stack else None,
                "parent_cell_id": parent_cell["id"] if parent_cell else None,
                "attribute_ids": attribute_ids,
                "rows": [],
            }
            self.tables.append(table)
            if parent_cell is not None:
                parent_cell["nested_table_ids"].append(table["id"])
            self.table_stack.append({"table": table, "row": None, "cell": None})
        elif tag == "tr" and self.table_stack:
            state = self.table_stack[-1]
            state["cell"] = None
            row = {
                "id": f"{state['table']['id']}-R{len(state['table']['rows']) + 1:04d}",
                "event_id": event["id"],
                "attribute_ids": attribute_ids,
                "cells": [],
            }
            state["table"]["rows"].append(row)
            state["row"] = row
        elif tag in {"td", "th"} and self.table_stack:
            state = self.table_stack[-1]
            if state["row"] is None:
                raise ValueError("table cell has no containing row")
            rowspan = self._span_value(values, "rowspan")
            colspan = self._span_value(values, "colspan")
            cell = {
                "id": f"{state['row']['id']}-C{len(state['row']['cells']) + 1:04d}",
                "event_id": event["id"],
                "tag": tag,
                "rowspan": rowspan,
                "colspan": colspan,
                "attribute_ids": attribute_ids,
                "unit_ids": [],
                "nested_table_ids": [],
            }
            state["row"]["cells"].append(cell)
            state["cell"] = cell
        if tag == "img":
            self.images.append(
                {
                    "id": f"I{len(self.images) + 1:05d}",
                    "event_id": event["id"],
                    "attribute_ids": attribute_ids,
                    "src": values.get("src", [None])[-1],
                    "alt": values.get("alt", [None])[-1],
                }
            )
        if tag not in VOID_TAGS:
            self.element_stack.append(element)

    @staticmethod
    def _span_value(values: dict[str, list[str | None]], name: str) -> int:
        raw_value = values.get(name, ["1"])[-1]
        if raw_value is None or not raw_value.isdigit() or int(raw_value) < 1:
            raise ValueError(f"invalid {name} value")
        return int(raw_value)

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs_list)
        if tag.lower() not in VOID_TAGS:
            self.element_stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        start = self._byte_position()
        end = self._markup_end(start)
        event = self._event("end_tag", start, end, tag=tag)
        matching = next((index for index in range(len(self.element_stack) - 1, -1, -1) if self.element_stack[index]["tag"] == tag), None)
        if matching is None:
            # Historical SEC HTML commonly carries harmless unmatched formatting closes.
            if tag in TABLE_TAGS or tag in {"script", "style"}:
                raise ValueError(f"unmatched structural end tag: {tag}")
            return
        element = self.element_stack[matching]
        del self.element_stack[matching:]
        node = element["node"]
        node["end_event_id"] = event["id"]
        if tag in {"script", "style"}:
            content = _span(self.raw, element["content_start"], start)
            self.exclusions.append(
                {
                    "id": f"X{len(self.exclusions) + 1:05d}",
                    "kind": tag,
                    "event_id": element["event_id"],
                    "content": content,
                    "included_in_compact_text": False,
                }
            )
        if tag in {"td", "th"} and self.table_stack and self.table_stack[-1]["cell"] is not None:
            self.table_stack[-1]["cell"]["end_event_id"] = event["id"]
        elif tag == "tr" and self.table_stack and self.table_stack[-1]["row"] is not None:
            self.table_stack[-1]["row"]["end_event_id"] = event["id"]
        if tag in {"td", "th", "tr"}:
            self._close_table_part(tag)
        elif tag == "table":
            if not self.table_stack:
                raise ValueError("unmatched table end tag")
            state = self.table_stack.pop()
            state["table"]["end_event_id"] = event["id"]

    def _text(self, decoded: str, start: int, end: int, event_kind: str) -> None:
        excluded = any(element["tag"] in {"script", "style"} for element in self.element_stack)
        event = self._event(event_kind, start, end, included_in_compact_text=not excluded)
        unit = {
            "id": f"U{len(self.units) + 1:06d}",
            "event_id": event["id"],
            "decoded": decoded,
            "span": _span(self.raw, start, end),
            "included_in_compact_text": not excluded,
            "hidden_reasons": self._hidden_reasons(),
            "element_path": [element["node_id"] for element in self.element_stack],
        }
        self.units.append(unit)
        if not excluded:
            cell = self._current_cell()
            if cell is not None:
                cell["unit_ids"].append(unit["id"])

    def handle_data(self, data: str) -> None:
        start = self._byte_position()
        encoded = data.encode("utf-8")
        end = start + len(encoded)
        if self.raw[start:end] != encoded:
            raise ValueError("parser data cannot be mapped unambiguously to source bytes")
        self._text(data, start, end, "data")

    def handle_entityref(self, name: str) -> None:
        start = self._byte_position()
        source = f"&{name};".encode("ascii")
        if self.raw[start : start + len(source)].lower() != source.lower():
            raise ValueError("ambiguous entity-reference span")
        self._text(html.unescape(source.decode("ascii")), start, start + len(source), "entity_reference")

    def handle_charref(self, name: str) -> None:
        start = self._byte_position()
        source = f"&#{name};".encode("ascii")
        if self.raw[start : start + len(source)].lower() != source.lower():
            raise ValueError("ambiguous character-reference span")
        self._text(html.unescape(source.decode("ascii")), start, start + len(source), "character_reference")

    def handle_comment(self, data: str) -> None:
        start = self._byte_position()
        end_marker = self.raw.find(b"-->", start + 4)
        if end_marker < 0:
            raise ValueError("truncated comment")
        end = end_marker + 3
        event = self._event("comment", start, end, included_in_compact_text=False)
        self.exclusions.append(
            {
                "id": f"X{len(self.exclusions) + 1:05d}",
                "kind": "comment",
                "event_id": event["id"],
                "content": _span(self.raw, start + 4, end_marker),
                "included_in_compact_text": False,
            }
        )

    def handle_decl(self, decl: str) -> None:
        del decl
        start = self._byte_position()
        self._event("declaration", start, self._markup_end(start), included_in_compact_text=False)

    def unknown_decl(self, data: str) -> None:
        raise ValueError(f"unknown declaration cannot be projected safely: {data[:40]}")

    def handle_pi(self, data: str) -> None:
        del data
        start = self._byte_position()
        self._event("processing_instruction", start, self._markup_end(start), included_in_compact_text=False)

    def finish(self) -> dict[str, Any]:
        self.close()
        unclosed_structural = [item["tag"] for item in self.element_stack if item["tag"] in TABLE_TAGS | {"script", "style"}]
        if unclosed_structural or self.table_stack:
            raise ValueError(f"truncated structural markup: {unclosed_structural}")
        cursor = 0
        for event in self.events:
            if event["start"] != cursor or event["end"] < cursor:
                raise ValueError("parser events do not partition the source bytes")
            cursor = event["end"]
        if cursor != len(self.raw):
            raise ValueError("parser events do not cover the complete source")
        return {
            "events": self.events,
            "attributes": self.attributes,
            "units": self.units,
            "elements": self.elements,
            "tables": self.tables,
            "images": self.images,
            "exclusions": self.exclusions,
        }


def _normalize_units(units: list[dict[str, Any]]) -> str:
    output: list[str] = []
    pending_space = False
    offset = 0
    for unit in units:
        unit["compact_spans"] = []
        if not unit["included_in_compact_text"]:
            continue
        segment_start: int | None = None
        for char in unit["decoded"]:
            if char.isspace():
                if output:
                    pending_space = True
                if segment_start is not None:
                    unit["compact_spans"].append({"start": segment_start, "end": offset})
                    segment_start = None
                continue
            if pending_space:
                if segment_start is None:
                    segment_start = offset
                output.append(" ")
                offset += 1
                pending_space = False
            if segment_start is None:
                segment_start = offset
            output.append(char)
            offset += 1
        if segment_start is not None:
            unit["compact_spans"].append({"start": segment_start, "end": offset})
    return "".join(output)


def render_review(projection: dict[str, Any]) -> str:
    """Render a lean ordered review view whose TEXT payloads concatenate exactly.

    Structural marker lines carry no projected source text. ``review_text`` is the
    inverse used to prove that the view neither drops nor duplicates text.
    """
    starts: dict[str, list[str]] = {}
    ends: dict[str, list[str]] = {}
    for table in projection["tables"]:
        starts.setdefault(table["event_id"], []).append(
            f"TABLE {table['id']} parent_table={table['parent_table_id'] or '-'} parent_cell={table['parent_cell_id'] or '-'}"
        )
        if table.get("end_event_id"):
            ends.setdefault(table["end_event_id"], []).append(f"END_TABLE {table['id']}")
        for row in table["rows"]:
            starts.setdefault(row["event_id"], []).append(f"ROW {row['id']}")
            if row.get("end_event_id"):
                ends.setdefault(row["end_event_id"], []).append(f"END_ROW {row['id']}")
            for cell in row["cells"]:
                starts.setdefault(cell["event_id"], []).append(
                    f"CELL {cell['id']} tag={cell['tag']} rowspan={cell['rowspan']} colspan={cell['colspan']}"
                )
                if cell.get("end_event_id"):
                    ends.setdefault(cell["end_event_id"], []).append(f"END_CELL {cell['id']}")
    for image in projection["images"]:
        starts.setdefault(image["event_id"], []).append(
            f"IMAGE {image['id']} src={json.dumps(image['src'], ensure_ascii=False)} "
            f"alt={json.dumps(image['alt'], ensure_ascii=False)}"
        )
    for excluded in projection["exclusions"]:
        starts.setdefault(excluded["event_id"], []).append(
            f"EXCLUDED {excluded['id']} kind={excluded['kind']} "
            f"bytes={excluded['content']['bytes']} sha256={excluded['content']['sha256']}"
        )
    units_by_event = {unit["event_id"]: unit for unit in projection["units"]}
    compact = projection["compact_text"]
    lines = [
        "# E7 offline source review projection",
        f"# source_bytes={projection['source_bytes']} source_sha256={projection['source_sha256']}",
        "# TEXT JSON payloads concatenate to compact_text; markers contain structure only.",
    ]
    for event in projection["events"]:
        lines.extend(f"@{marker}" for marker in starts.get(event["id"], []))
        unit = units_by_event.get(event["id"])
        if unit is not None and unit["included_in_compact_text"]:
            contribution = "".join(compact[item["start"] : item["end"]] for item in unit["compact_spans"])
            if contribution:
                hidden = ",".join(unit["hidden_reasons"]) or "-"
                lines.append(
                    f"@TEXT {unit['id']} bytes={unit['span']['start']}:{unit['span']['end']} hidden={hidden}\t"
                    + json.dumps(contribution, ensure_ascii=False)
                )
        lines.extend(f"@{marker}" for marker in ends.get(event["id"], []))
    return "\n".join(lines) + "\n"


def review_text(review: str) -> str:
    """Recover the normalized stream from detailed or compact review output."""
    pieces = []
    for line in review.splitlines():
        if line.startswith("@TEXT "):
            try:
                _, payload = line.split("\t", 1)
            except ValueError as exc:
                raise ValueError("malformed TEXT review record") from exc
            value = json.loads(payload)
            if not isinstance(value, str):
                raise ValueError("TEXT review payload is not a string")
            pieces.append(value)
        elif line.startswith("@ROW ") and "\t" in line:
            try:
                _, payload = line.split("\t", 1)
            except ValueError as exc:
                raise ValueError("malformed ROW review record") from exc
            cells = json.loads(payload)
            if not isinstance(cells, list) or any(not isinstance(cell, list) or len(cell) < 2 for cell in cells):
                raise ValueError("ROW review payload is not a cell array")
            pieces.extend(cell[1] for cell in cells)
    return "".join(pieces)


def render_reader(projection: dict[str, Any]) -> str:
    """Render a compact document-order reader, aggregating ordinary table rows."""
    events = projection["events"]
    event_index = {event["id"]: index for index, event in enumerate(events)}
    units_by_event = {unit["event_id"]: unit for unit in projection["units"]}
    units_by_id = {unit["id"]: unit for unit in projection["units"]}
    compact = projection["compact_text"]

    def contribution(unit: dict[str, Any]) -> str:
        return "".join(compact[item["start"] : item["end"]] for item in unit["compact_spans"])

    table_starts: dict[str, dict[str, Any]] = {}
    table_ends: dict[str, dict[str, Any]] = {}
    row_starts: dict[str, dict[str, Any]] = {}
    row_ends: dict[str, dict[str, Any]] = {}
    cell_starts: dict[str, dict[str, Any]] = {}
    cell_ends: dict[str, dict[str, Any]] = {}
    simple_rows: dict[str, tuple[dict[str, Any], int]] = {}
    annotated_events = {item["event_id"] for item in projection["images"] + projection["exclusions"]}
    for table in projection["tables"]:
        table_starts[table["event_id"]] = table
        if table.get("end_event_id"):
            table_ends[table["end_event_id"]] = table
        for row in table["rows"]:
            row_starts[row["event_id"]] = row
            if row.get("end_event_id"):
                row_ends[row["end_event_id"]] = row
            for cell in row["cells"]:
                cell_starts[cell["event_id"]] = cell
                if cell.get("end_event_id"):
                    cell_ends[cell["end_event_id"]] = cell
            if not row.get("end_event_id") or any(cell["nested_table_ids"] for cell in row["cells"]):
                continue
            first = event_index[row["event_id"]]
            last = event_index[row["end_event_id"]]
            cell_units = {identifier for cell in row["cells"] for identifier in cell["unit_ids"]}
            contributing = {
                unit["id"]
                for event in events[first : last + 1]
                if (unit := units_by_event.get(event["id"])) is not None and contribution(unit)
            }
            if contributing <= cell_units and not any(events[position]["id"] in annotated_events for position in range(first, last + 1)):
                simple_rows[row["event_id"]] = (row, last)

    element_starts = {
        element["start_event_id"]: element
        for element in projection["elements"]
        if element["tag"] in BREAK_TAGS and element["tag"] not in TABLE_TAGS
    }
    element_ends = {
        element["end_event_id"]: element
        for element in projection["elements"]
        if element["tag"] in BREAK_TAGS and element["tag"] not in TABLE_TAGS and element.get("end_event_id")
    }
    image_starts = {image["event_id"]: image for image in projection["images"]}
    exclusion_starts = {item["event_id"]: item for item in projection["exclusions"]}
    lines = [
        "# E7 compact offline source reader",
        f"# source_bytes={projection['source_bytes']} source_sha256={projection['source_sha256']}",
        "# @ROW cells are [d|h,text]; non-default spans add rowspan,colspan; hidden cells add reasons.",
        "# @TEXT and @ROW text payloads concatenate exactly to compact_text; markers carry no source text.",
    ]
    pending: list[str] = []
    pending_first: dict[str, Any] | None = None
    pending_last: dict[str, Any] | None = None
    pending_hidden: list[str] = []

    def flush() -> None:
        nonlocal pending_first, pending_last
        if not pending:
            return
        assert pending_first is not None and pending_last is not None
        hidden = ",".join(dict.fromkeys(pending_hidden)) or "-"
        lines.append(
            f"@TEXT {pending_first['id']}..{pending_last['id']} "
            f"bytes={pending_first['span']['start']}:{pending_last['span']['end']} hidden={hidden}\t"
            + json.dumps("".join(pending), ensure_ascii=False)
        )
        pending.clear()
        pending_hidden.clear()
        pending_first = None
        pending_last = None

    index = 0
    while index < len(events):
        event = events[index]
        identifier = event["id"]
        if identifier in simple_rows:
            flush()
            row, last = simple_rows[identifier]
            cells = []
            for cell in row["cells"]:
                cell_units = [units_by_id[item] for item in cell["unit_ids"]]
                cell_text = "".join(contribution(unit) for unit in cell_units)
                value: list[Any] = ["h" if cell["tag"] == "th" else "d", cell_text]
                hidden = list(dict.fromkeys(reason for unit in cell_units for reason in unit["hidden_reasons"]))
                if cell["rowspan"] != 1 or cell["colspan"] != 1 or hidden:
                    value.extend((cell["rowspan"], cell["colspan"]))
                if hidden:
                    value.append(hidden)
                cells.append(value)
            lines.append(f"@ROW {row['id']}\t" + json.dumps(cells, ensure_ascii=False, separators=(",", ":")))
            index = last + 1
            continue
        markers_before: list[str] = []
        if identifier in table_starts:
            table = table_starts[identifier]
            markers_before.append(
                f"TABLE {table['id']} parent_table={table['parent_table_id'] or '-'} "
                f"parent_cell={table['parent_cell_id'] or '-'}"
            )
        if identifier in row_starts:
            markers_before.append(f"ROW {row_starts[identifier]['id']}")
        if identifier in cell_starts:
            cell = cell_starts[identifier]
            markers_before.append(
                f"CELL {cell['id']} tag={cell['tag']} rowspan={cell['rowspan']} colspan={cell['colspan']}"
            )
        if identifier in element_starts:
            element = element_starts[identifier]
            markers_before.append(f"BLOCK {element['id']} tag={element['tag']}")
        if identifier in image_starts:
            image = image_starts[identifier]
            markers_before.append(
                f"IMAGE {image['id']} src={json.dumps(image['src'], ensure_ascii=False)} "
                f"alt={json.dumps(image['alt'], ensure_ascii=False)}"
            )
        if identifier in exclusion_starts:
            excluded = exclusion_starts[identifier]
            markers_before.append(
                f"EXCLUDED {excluded['id']} kind={excluded['kind']} bytes={excluded['content']['bytes']} "
                f"sha256={excluded['content']['sha256']}"
            )
        if markers_before:
            flush()
            lines.extend(f"@{marker}" for marker in markers_before)
        unit = units_by_event.get(identifier)
        if unit is not None and unit["included_in_compact_text"]:
            text = contribution(unit)
            if text:
                if pending_first is None:
                    pending_first = unit
                pending_last = unit
                pending.append(text)
                pending_hidden.extend(unit["hidden_reasons"])
        markers_after: list[str] = []
        if identifier in cell_ends:
            markers_after.append(f"END_CELL {cell_ends[identifier]['id']}")
        if identifier in row_ends:
            markers_after.append(f"END_ROW {row_ends[identifier]['id']}")
        if identifier in element_ends:
            element = element_ends[identifier]
            markers_after.append(f"END_BLOCK {element['id']} tag={element['tag']}")
        if identifier in table_ends:
            markers_after.append(f"END_TABLE {table_ends[identifier]['id']}")
        if markers_after:
            flush()
            lines.extend(f"@{marker}" for marker in markers_after)
        index += 1
    flush()
    rendered = "\n".join(lines) + "\n"
    if review_text(rendered) != compact:
        raise ValueError("compact reader changed the projected text stream")
    return rendered


def verify_projection(raw: bytes, projection: dict[str, Any]) -> None:
    """Recheck byte identity, event partitioning, unit locators and text projection."""
    if projection.get("source_bytes") != len(raw) or projection.get("source_sha256") != _sha(raw):
        raise ValueError("projection source identity mismatch")
    cursor = 0
    event_ids: set[str] = set()
    for event in projection.get("events", []):
        if event.get("id") in event_ids:
            raise ValueError("duplicate projection event id")
        event_ids.add(event.get("id"))
        start, end = event.get("start"), event.get("end")
        if start != cursor or not isinstance(end, int) or end < start or end > len(raw):
            raise ValueError("projection event partition mismatch")
        if event.get("bytes") != end - start or event.get("sha256") != _sha(raw[start:end]):
            raise ValueError("projection event locator mismatch")
        cursor = end
    if cursor != len(raw):
        raise ValueError("projection event coverage mismatch")
    text_events = {
        event["id"]: event
        for event in projection["events"]
        if event["kind"] in {"data", "entity_reference", "character_reference"}
    }
    unit_ids: set[str] = set()
    unit_events: set[str] = set()
    for unit in projection.get("units", []):
        if unit.get("id") in unit_ids:
            raise ValueError("duplicate projection text-unit id")
        unit_ids.add(unit.get("id"))
        event_id = unit.get("event_id")
        if event_id not in text_events or event_id in unit_events:
            raise ValueError("projection text unit does not map one-to-one to a text event")
        unit_events.add(event_id)
        event = text_events[event_id]
        location = unit.get("span", {})
        start, end = location.get("start"), location.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or location.get("sha256") != _sha(raw[start:end]):
            raise ValueError("projection text-unit locator mismatch")
        if (start, end) != (event["start"], event["end"]):
            raise ValueError("projection text unit differs from its source event span")
        source = raw[start:end].decode("utf-8", "strict")
        decoded = source if event["kind"] == "data" else html.unescape(source)
        if unit.get("decoded") != decoded:
            raise ValueError("projection text-unit decoding mismatch")
        if unit.get("included_in_compact_text") != event.get("included_in_compact_text"):
            raise ValueError("projection text-unit inclusion mismatch")
    if unit_events != set(text_events):
        raise ValueError("projection text events and units differ")
    attribute_ids: set[str] = set()
    for attribute in projection.get("attributes", []):
        if attribute.get("id") in attribute_ids:
            raise ValueError("duplicate projection attribute id")
        attribute_ids.add(attribute.get("id"))
        for key in ("span", "name_span"):
            location = attribute.get(key, {})
            start, end = location.get("start"), location.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or location.get("sha256") != _sha(raw[start:end]):
                raise ValueError("projection attribute locator mismatch")
        location = attribute.get("value_span")
        if location is not None and location.get("sha256") != _sha(raw[location["start"] : location["end"]]):
            raise ValueError("projection attribute value locator mismatch")
    referenced_attributes = {
        identifier
        for event in projection["events"]
        for identifier in event.get("attribute_ids", [])
    }
    if referenced_attributes != attribute_ids:
        raise ValueError("projection attributes and start-tag references differ")
    rebuilt = _normalize_units(json.loads(json.dumps(projection.get("units", []))))
    if rebuilt != projection.get("compact_text") or _sha(rebuilt.encode("utf-8")) != projection.get("compact_text_sha256"):
        raise ValueError("projection compact text mismatch")


def project_html(raw: bytes) -> dict[str, Any]:
    """Project one UTF-8 HTML source without changing or executing it."""
    if not raw:
        raise ValueError("empty HTML source")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("HTML source exceeds offline review limit")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ValueError("HTML source is not strict UTF-8") from exc
    parser = _ProjectionParser(raw, text)
    parser.feed(text)
    records = parser.finish()
    compact_text = _normalize_units(records["units"])
    projection = {
        "schema_version": 1,
        "kind": "e7_offline_html_source_view",
        "source_bytes": len(raw),
        "source_sha256": _sha(raw),
        "encoding": "utf-8",
        "compact_text": compact_text,
        "compact_text_sha256": _sha(compact_text.encode("utf-8")),
        "semantic_coverage_attested": False,
        "markup_is_reviewed_content": False,
        "css_rendering_evaluated": False,
        "limitations": [
            "This is a deterministic text and table projection, not a browser rendering.",
            "Non-content markup and excluded script, style, and comment bytes do not imply reviewed content.",
            "Hidden text is retained when expressed by HTML attributes or inline style; external CSS is not evaluated.",
            "Source review and semantic coverage are not attested.",
        ],
        **records,
    }
    verify_projection(raw, projection)
    if review_text(render_review(projection)) != compact_text:
        raise ValueError("structural review view changed the compact text stream")
    render_reader(projection)
    return projection


def build_source_view(source: Path, expected_sha256: str, expected_bytes: int, output: Path) -> dict[str, Any]:
    """Build one new hash-bound view directory, refusing overwrite or source drift."""
    if output.exists() or output.is_symlink():
        raise ValueError("source-view output must not already exist")
    raw = source.read_bytes()
    if len(raw) != expected_bytes or _sha(raw) != expected_sha256:
        raise ValueError("source size/hash mismatch")
    projection = project_html(raw)
    payload = (json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    compact = (projection["compact_text"] + "\n").encode("utf-8")
    reader = render_reader(projection).encode("utf-8")
    final = source.read_bytes()
    if len(final) != expected_bytes or _sha(final) != expected_sha256 or final != raw:
        raise ValueError("source changed during view construction")
    output.mkdir(parents=True, exist_ok=False)
    (output / "compact.txt").write_bytes(compact)
    (output / "reader.txt").write_bytes(reader)
    (output / "source-view.json").write_bytes(payload)
    manifest = {
        "schema_version": 1,
        "kind": "e7_offline_html_source_view_bundle",
        "source": {"path": str(source), "bytes": expected_bytes, "sha256": expected_sha256},
        "semantic_coverage_attested": False,
        "files": {
            "compact_text": {"path": "compact.txt", "bytes": len(compact), "sha256": _sha(compact)},
            "reader": {"path": "reader.txt", "bytes": len(reader), "sha256": _sha(reader)},
            "projection": {"path": "source-view.json", "bytes": len(payload), "sha256": _sha(payload)},
        },
    }
    manifest_payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "manifest.json").write_bytes(manifest_payload)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_source_view(args.source, args.expected_sha256, args.expected_bytes, args.output)
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
