"""Tokenizer for Endless Sky's indented text data format.

Mirrors DataFile::LoadData and DataNode::IsNumber / DataNode::Value from the
game's source, so a file parses into the same tree the game builds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Same grammar as DataNode::IsNumber: [+-]?[0-9]*[.]?[0-9]*([eE][+-]?[0-9]*)?
# Like the game, this accepts edge cases such as "", "-" and "1e".
_NUMBER = re.compile(r"[+-]?[0-9]*\.?[0-9]*(?:[eE][+-]?[0-9]*)?")
_PARTIAL_EXPONENT = re.compile(r"[eE][+-]?$")


def is_number(token: str) -> bool:
    return _NUMBER.fullmatch(token) is not None


def to_number(token: str) -> float:
    """Convert a token the way DataNode::Value does (non-numbers become 0)."""
    if not is_number(token):
        return 0.0
    # An exponent with no digits counts as e0 in the game.
    text = _PARTIAL_EXPONENT.sub("", token)
    if not any(c.isdigit() for c in text):
        return 0.0
    return float(text)


@dataclass
class Node:
    tokens: list[str]
    children: list["Node"] = field(default_factory=list)
    file: str = ""
    line: int = 0

    @property
    def key(self) -> str:
        return self.tokens[0] if self.tokens else ""

    @property
    def size(self) -> int:
        return len(self.tokens)

    def token(self, index: int) -> str:
        return self.tokens[index] if index < len(self.tokens) else ""

    def value(self, index: int) -> float:
        return to_number(self.token(index))

    def is_number(self, index: int) -> bool:
        return index < len(self.tokens) and is_number(self.tokens[index])

    def __iter__(self) -> Iterator["Node"]:
        return iter(self.children)

    def where(self) -> str:
        return f"{self.file}:{self.line}"


def parse_text(text: str, file: str = "") -> list[Node]:
    """Parse data-file text into a list of top-level nodes."""
    if text.startswith("﻿"):
        text = text[1:]
    root = Node([])
    # Stack of (indentation, node); the root sits at indentation -1.
    stack: list[tuple[int, Node]] = [(-1, root)]

    for line_number, line in enumerate(text.split("\n"), start=1):
        line = line.rstrip("\r")
        # Leading whitespace: every character <= ' ' counts as one separator.
        indent = 0
        while indent < len(line) and line[indent] <= " ":
            indent += 1
        if indent == len(line) or line[indent] == "#":
            continue

        tokens = _tokenize(line, indent)
        while stack[-1][0] >= indent:
            stack.pop()
        node = Node(tokens, file=file, line=line_number)
        stack[-1][1].children.append(node)
        stack.append((indent, node))

    return root.children


def _tokenize(line: str, pos: int) -> list[str]:
    tokens: list[str] = []
    end = len(line)
    while pos < end:
        quote = line[pos]
        if quote in ('"', "`"):
            close = line.find(quote, pos + 1)
            if close < 0:
                close = end
            tokens.append(line[pos + 1:close])
            pos = close + 1
        else:
            start = pos
            while pos < end and line[pos] > " ":
                pos += 1
            tokens.append(line[start:pos])
        # Skip whitespace to the next token; a '#' here starts a comment.
        while pos < end and line[pos] <= " ":
            pos += 1
        if pos < end and line[pos] == "#":
            break
    return tokens


def parse_file(path: Path, label: str | None = None) -> list[Node]:
    text = path.read_text(encoding="utf-8")
    return parse_text(text, file=label if label is not None else str(path))


def data_files(data_dir: Path) -> list[Path]:
    """All files under a data directory, in the game's load order.

    The game sorts std::filesystem paths, which compare component by component.
    """
    files = [p for p in data_dir.rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(data_dir).parts)
