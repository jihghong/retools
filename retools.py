from __future__ import annotations

import re
from dataclasses import MISSING, fields as dataclass_fields, is_dataclass
from datetime import date as _date, datetime as _datetime, time as _time
from decimal import Decimal
from types import UnionType
from typing import Any, Union, get_args, get_origin
from uuid import UUID

_PLACEHOLDER_RE = re.compile(r"<([A-Za-z_][A-Za-z0-9_]*)>")
_GROUP_NAME_RE = re.compile(r"\(\?P<([A-Za-z][A-Za-z0-9_]*)>")

_TYPE_PATTERNS: list[tuple[type, str]] = [
    (bool, r"(?i:true|false|1|0)"),
    (int, r"-?\d+"),
    (float, r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"),
    (Decimal, r"-?(?:\d+(?:\.\d*)?|\.\d+)"),
    (_datetime, r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?"),
    (_date, r"\d{4}-\d{2}-\d{2}"),
    (_time, r"\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?"),
    (UUID, r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),
    (str, r".+?"),
]

_TYPE_CONVERTERS: dict[type, Any] = {
    bool: lambda value: value.lower() in {"true", "1"},
    Decimal: Decimal,
    _date: _date.fromisoformat,
    _datetime: _datetime.fromisoformat,
    _time: _time.fromisoformat,
    UUID: UUID,
}


class _Spec:
    __slots__ = ("cls", "token", "fields", "regex", "dataclass_fields")

    def __init__(
        self,
        cls: type,
        token: str,
        fields: dict[str, str],
        regex: str,
        dataclass_fields_info: tuple,
    ) -> None:
        self.cls = cls
        self.token = token
        self.fields = fields
        self.regex = regex
        self.dataclass_fields = dataclass_fields_info


class _FieldBinding:
    __slots__ = ("groups", "nested")

    def __init__(
        self,
        groups: list[str] | None = None,
        nested: list["_NestedBinding"] | None = None,
    ) -> None:
        self.groups = groups or []
        self.nested = nested or []


class _NestedBinding:
    __slots__ = ("spec", "field_bindings")

    def __init__(self, spec: _Spec, field_bindings: dict[str, _FieldBinding]) -> None:
        self.spec = spec
        self.field_bindings = field_bindings


class _Occurrence:
    __slots__ = ("spec", "field_bindings")

    def __init__(self, spec: _Spec, field_bindings: dict[str, _FieldBinding]) -> None:
        self.spec = spec
        self.field_bindings = field_bindings


class _NameGenerator:
    def __init__(self, reserved: set[str]) -> None:
        self._reserved = set(reserved)
        self._counter = 0

    def next(self) -> str:
        while True:
            name = f"reclass_{self._counter}"
            self._counter += 1
            if name not in self._reserved:
                self._reserved.add(name)
                return name


def _collect_named_groups(patterns: list[str]) -> set[str]:
    names: set[str] = set()
    for pattern in patterns:
        names.update(_GROUP_NAME_RE.findall(pattern))
    return names


def _collect_named_groups_in_pattern(pattern: str) -> set[str]:
    return set(_GROUP_NAME_RE.findall(pattern))


def _count_capturing_groups(pattern: str) -> int:
    count = 0
    i = 0
    in_class = False
    length = len(pattern)
    while i < length:
        char = pattern[i]
        if char == "\\":
            i += 2
            continue
        if char == "[":
            in_class = True
            i += 1
            continue
        if char == "]" and in_class:
            in_class = False
            i += 1
            continue
        if not in_class and char == "(":
            if i + 1 < length and pattern[i + 1] == "?":
                if pattern.startswith("(?P<", i):
                    count += 1
            else:
                count += 1
        i += 1
    return count


def _unwrap_type(field_type: Any) -> Any:
    origin = get_origin(field_type)
    if origin is None:
        return field_type
    if origin is Union or origin is UnionType:
        args = [arg for arg in get_args(field_type) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    if origin is list or origin is dict or origin is tuple:
        return field_type
    return field_type


def _default_pattern_for_type(field_type: Any) -> str | None:
    target = _unwrap_type(field_type)
    if target is Any:
        return None
    for candidate, pattern in _TYPE_PATTERNS:
        try:
            if target is candidate or (
                isinstance(target, type) and issubclass(target, candidate)
            ):
                return pattern
        except TypeError:
            continue
    return None


def _convert_value(value: str | None, field_type: Any) -> Any:
    if value is None:
        return None
    if field_type is Any:
        return value
    target_type = _unwrap_type(field_type)
    if target_type is Any:
        return value
    if target_type is str:
        return value
    converter = _TYPE_CONVERTERS.get(target_type)
    if converter is not None:
        try:
            return converter(value)
        except Exception:
            return value
    try:
        return target_type(value)
    except Exception:
        return value


def _expand_token(
    spec: _Spec,
    registry: "Builder",
    name_gen: _NameGenerator,
    occurrences: list["_Occurrence"],
) -> tuple[str, list[tuple[_Spec, dict[str, _FieldBinding]]]]:
    candidates = [
        candidate
        for candidate in registry._by_class.values()
        if issubclass(candidate.cls, spec.cls)
    ]
    if not candidates:
        candidates = [spec]
    if len(candidates) > 1:
        candidates.sort(
            key=lambda candidate: (-len(candidate.cls.mro()), candidate.cls.__name__)
        )
    expanded_parts: list[str] = []
    variants: list[tuple[_Spec, dict[str, _FieldBinding]]] = []
    for candidate in candidates:
        candidate_expanded, bindings = _expand_spec(
            candidate, registry, name_gen, occurrences
        )
        _validate_mapping(candidate, bindings)
        occurrences.append(_Occurrence(spec=candidate, field_bindings=bindings))
        expanded_parts.append(f"(?:{candidate_expanded})")
        variants.append((candidate, bindings))
    if len(expanded_parts) == 1:
        return candidate_expanded, variants
    return f"(?:{'|'.join(expanded_parts)})", variants


def _expand_field_pattern(
    pattern: str,
    registry: "Builder",
    name_gen: _NameGenerator,
    occurrences: list["_Occurrence"],
) -> tuple[str, list[_NestedBinding]]:
    nested: list[_NestedBinding] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        spec = registry._by_token.get(name)
        if spec is None:
            return match.group(0)
        expanded, variants = _expand_token(spec, registry, name_gen, occurrences)
        for variant_spec, bindings in variants:
            nested.append(_NestedBinding(spec=variant_spec, field_bindings=bindings))
        return f"(?:{expanded})"

    expanded = _PLACEHOLDER_RE.sub(replace, pattern)
    return expanded, nested


def _expand_spec(
    spec: _Spec,
    registry: "Builder",
    name_gen: _NameGenerator,
    occurrences: list["_Occurrence"],
) -> tuple[str, dict[str, _FieldBinding]]:
    bindings: dict[str, _FieldBinding] = {}

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in spec.fields:
            token_spec = registry._by_token.get(name)
            if token_spec is None:
                return match.group(0)
            if token_spec.cls is spec.cls:
                return match.group(0)
            if issubclass(spec.cls, token_spec.cls):
                expanded, inherited_bindings = _expand_spec(
                    token_spec, registry, name_gen, occurrences
                )
                for field_name, binding in inherited_bindings.items():
                    current = bindings.setdefault(field_name, _FieldBinding())
                    current.groups.extend(binding.groups)
                    current.nested.extend(binding.nested)
                return f"(?:{expanded})"
            expanded, _ = _expand_token(token_spec, registry, name_gen, occurrences)
            return f"(?:{expanded})"
        field_pattern = spec.fields[name]
        expanded, nested = _expand_field_pattern(
            field_pattern, registry, name_gen, occurrences
        )
        binding = bindings.setdefault(name, _FieldBinding())
        if nested:
            binding.nested.extend(nested)
            return f"(?:{expanded})"
        group_name = name_gen.next()
        binding.groups.append(group_name)
        return f"(?P<{group_name}>{expanded})"

    expanded = _PLACEHOLDER_RE.sub(replace, spec.regex)
    return expanded, bindings


def _validate_mapping(spec: _Spec, mapping: dict[str, _FieldBinding]) -> None:
    missing = [
        f.name
        for f in spec.dataclass_fields
        if f.name not in mapping
        or (not mapping[f.name].groups and not mapping[f.name].nested)
    ]
    if missing:
        raise ValueError(
            f"Missing fields in regex template for {spec.cls.__name__}: {', '.join(missing)}"
        )


def _expand_pattern_with_user_groups(
    pattern: str,
    registry: "Builder",
    name_gen: _NameGenerator,
    occurrences: list["_Occurrence"],
) -> tuple[str, list[int], list[tuple[str, Any]]]:
    parts: list[str] = []
    user_group_map: list[int] = []
    elements: list[tuple[str, Any]] = []
    group_count = 0
    i = 0
    in_class = False
    length = len(pattern)
    while i < length:
        char = pattern[i]
        if char == "\\":
            if i + 1 < length:
                parts.append(pattern[i : i + 2])
                i += 2
                continue
            parts.append(char)
            i += 1
            continue
        if char == "[":
            in_class = True
            parts.append(char)
            i += 1
            continue
        if char == "]" and in_class:
            in_class = False
            parts.append(char)
            i += 1
            continue
        if not in_class and char == "<":
            placeholder = _PLACEHOLDER_RE.match(pattern, i)
            if placeholder:
                name = placeholder.group(1)
                spec = registry._by_token.get(name)
                if spec is not None:
                    expanded, variants = _expand_token(
                        spec, registry, name_gen, occurrences
                    )
                    parts.append(f"(?:{expanded})")
                    group_count += _count_capturing_groups(expanded)
                    elements.append(("token", variants))
                    i = placeholder.end()
                    continue
        if not in_class and char == "(":
            if i + 1 < length and pattern[i + 1] == "?":
                if pattern.startswith("(?P<", i):
                    group_count += 1
                    elements.append(("named_group", group_count))
                parts.append(char)
                i += 1
                continue
            group_count += 1
            user_group_map.append(group_count)
            elements.append(("group", group_count))
            parts.append(char)
            i += 1
            continue
        parts.append(char)
        i += 1
    return "".join(parts), user_group_map, elements


def _binding_group_names(bindings: dict[str, _FieldBinding]) -> list[str]:
    names: list[str] = []
    for binding in bindings.values():
        names.extend(binding.groups)
        for nested in binding.nested:
            names.extend(_binding_group_names(nested.field_bindings))
    return names


def _allows_none(field_type: Any) -> bool:
    if field_type is Any:
        return True
    origin = get_origin(field_type)
    if origin is Union or origin is UnionType:
        return any(arg is type(None) for arg in get_args(field_type))
    return False


def _build_from_bindings(
    match: re.Match[str],
    spec: _Spec,
    bindings: dict[str, _FieldBinding],
) -> Any:
    values: dict[str, Any] = {}
    group_names = _binding_group_names(bindings)
    if group_names and all(match.group(name) is None for name in group_names):
        return None
    for field in spec.dataclass_fields:
        binding = bindings.get(field.name)
        value = None
        if binding is not None:
            if binding.nested:
                for nested in binding.nested:
                    nested_value = _build_from_bindings(
                        match, nested.spec, nested.field_bindings
                    )
                    if nested_value is not None:
                        value = nested_value
                        break
            if value is None and binding.groups:
                raw = None
                for group_name in binding.groups:
                    candidate = match.group(group_name)
                    if candidate is not None:
                        raw = candidate
                        break
                if raw is not None:
                    value = _convert_value(raw, field.type)
        if value is None:
            if field.default is not MISSING:
                value = field.default
            elif field.default_factory is not MISSING:  # type: ignore[comparison-overlap]
                value = field.default_factory()  # type: ignore[misc]
            elif _allows_none(field.type):
                value = None
            else:
                raise ValueError(
                    f"Missing field '{field.name}' for {spec.cls.__name__}."
                )
        values[field.name] = value
    return spec.cls(**values)


class _ReclassMatch:
    __slots__ = ("_match", "_occurrences", "_user_group_map", "_user_named_groups")

    def __init__(
        self,
        match: re.Match[str],
        occurrences: list[_Occurrence],
        user_group_map: list[int],
        user_named_groups: set[str],
    ) -> None:
        self._match = match
        self._occurrences = occurrences
        self._user_group_map = user_group_map
        self._user_named_groups = user_named_groups

    @property
    def match(self) -> re.Match[str]:
        return self._match

    def _map_group_index(self, index: int) -> int:
        if index == 0:
            return 0
        if index < 0 or index > len(self._user_group_map):
            raise IndexError("no such group")
        return self._user_group_map[index - 1]

    def group(self, *args: Any) -> Any:
        if not args:
            return self._match.group(0)
        if len(args) == 1:
            arg = args[0]
            if isinstance(arg, int):
                return self._match.group(self._map_group_index(arg))
            return self._match.group(arg)
        return tuple(self.group(arg) for arg in args)

    def groups(self, default: Any = None) -> tuple[Any, ...]:
        results: list[Any] = []
        for actual_index in self._user_group_map:
            value = self._match.group(actual_index)
            if value is None:
                value = default
            results.append(value)
        return tuple(results)

    def groupdict(self, default: Any = None) -> dict[str, Any]:
        raw = self._match.groupdict(default)
        return {name: raw[name] for name in self._user_named_groups if name in raw}

    def start(self, *args: Any) -> int:
        return self._match.start(*args)

    def end(self, *args: Any) -> int:
        return self._match.end(*args)

    def span(self, *args: Any) -> tuple[int, int]:
        return self._match.span(*args)

    def expand(self, template: str) -> str:
        return self._match.expand(template)

    @property
    def re(self) -> re.Pattern[str]:
        return self._match.re

    @property
    def string(self) -> str:
        return self._match.string

    @property
    def pos(self) -> int:
        return self._match.pos

    @property
    def endpos(self) -> int:
        return self._match.endpos

    @property
    def lastindex(self) -> int | None:
        return self._match.lastindex

    @property
    def lastgroup(self) -> str | None:
        return self._match.lastgroup

    @property
    def regs(self) -> tuple[tuple[int, int], ...]:
        return self._match.regs

    def __getitem__(self, key: int | str) -> Any:
        return self.group(key)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._match, name)

    def get(self, cls: type, index: int = 1) -> Any:
        if index < 1:
            raise IndexError("Index is 1-based and must be >= 1.")
        count = 0
        for occ in self._occurrences:
            if not issubclass(occ.spec.cls, cls):
                continue
            value = _build_from_bindings(self._match, occ.spec, occ.field_bindings)
            if value is None:
                continue
            count += 1
            if count == index:
                return value
        raise IndexError("No such occurrence for the requested class.")


class _ReclassRegex:
    def __init__(
        self,
        compiled: re.Pattern[str],
        occurrences: list[_Occurrence],
        user_group_map: list[int],
        user_named_groups: set[str],
        findall_elements: list[tuple[str, Any]],
    ) -> None:
        self._compiled = compiled
        self._occurrences = occurrences
        self._user_group_map = user_group_map
        self._user_named_groups = user_named_groups
        self._findall_elements = findall_elements

    def match(self, text: str) -> _ReclassMatch | None:
        match = self._compiled.match(text)
        if match is None:
            return None
        return _ReclassMatch(
            match,
            self._occurrences,
            self._user_group_map,
            self._user_named_groups,
        )

    def search(self, text: str) -> _ReclassMatch | None:
        match = self._compiled.search(text)
        if match is None:
            return None
        return _ReclassMatch(
            match,
            self._occurrences,
            self._user_group_map,
            self._user_named_groups,
        )

    def fullmatch(self, text: str) -> _ReclassMatch | None:
        match = self._compiled.fullmatch(text)
        if match is None:
            return None
        return _ReclassMatch(
            match,
            self._occurrences,
            self._user_group_map,
            self._user_named_groups,
        )

    def finditer(self, text: str) -> list[_ReclassMatch]:
        return [
            _ReclassMatch(
                match,
                self._occurrences,
                self._user_group_map,
                self._user_named_groups,
            )
            for match in self._compiled.finditer(text)
        ]

    def findall(self, text: str) -> list[Any]:
        if not self._findall_elements:
            return self._compiled.findall(text)
        results: list[Any] = []
        for match in self._compiled.finditer(text):
            values: list[Any] = []
            for kind, payload in self._findall_elements:
                if kind == "token":
                    value = None
                    for spec, bindings in payload:
                        value = _build_from_bindings(match, spec, bindings)
                        if value is not None:
                            break
                    values.append(value)
                    continue
                value = match.group(payload)
                values.append(value)
            if len(values) == 1:
                results.append(values[0])
            else:
                results.append(tuple(values))
        return results

    def split(self, text: str, maxsplit: int = 0) -> list[str]:
        return self._compiled.split(text, maxsplit)

    def sub(self, repl: str, text: str, count: int = 0) -> str:
        return self._compiled.sub(repl, text, count)

    def subn(self, repl: str, text: str, count: int = 0) -> tuple[str, int]:
        return self._compiled.subn(repl, text, count)

    @property
    def pattern(self) -> str:
        return self._compiled.pattern

    @property
    def flags(self) -> int:
        return self._compiled.flags

    @property
    def groups(self) -> int:
        return self._compiled.groups

    @property
    def groupindex(self) -> dict[str, int]:
        return self._compiled.groupindex


class Builder:
    def __init__(self) -> None:
        self._by_token: dict[str, _Spec] = {}
        self._by_class: dict[type, _Spec] = {}
        self._cache: dict[tuple[str, int], _ReclassRegex] = {}

    def __call__(
        self,
        cls: type | str | None = None,
        regex: str | None = None,
        *,
        fields: dict[str, str] | None = None,
        token: str | None = None,
    ) -> Any:
        if isinstance(cls, str) and regex is None:
            regex = cls
            cls = None
        if cls is None:
            def decorator(target: type) -> type:
                return self._register(target, token=token, fields=fields, regex=regex)

            return decorator
        return self._register(cls, token=token, fields=fields, regex=regex)

    def reclass(
        self,
        cls: type | str | None = None,
        regex: str | None = None,
        *,
        fields: dict[str, str] | None = None,
        token: str | None = None,
    ) -> Any:
        return self.__call__(cls, regex, fields=fields, token=token)

    def _register(
        self,
        cls: type,
        *,
        token: str | None,
        fields: dict[str, str] | None,
        regex: str | None,
    ) -> type:
        if token is None:
            token = cls.__name__
        if not isinstance(token, str) or not token:
            raise ValueError("token must be a non-empty string.")
        if fields is None:
            fields = {}
        if not isinstance(fields, dict):
            raise ValueError("fields must be a dict.")
        if not is_dataclass(cls):
            raise TypeError("reclass can only be applied to dataclasses.")
        dataclass_fields_info = dataclass_fields(cls)
        dataclass_names = {f.name for f in dataclass_fields_info}
        field_names = set(fields.keys())
        unknown_fields = field_names - dataclass_names
        if unknown_fields:
            raise ValueError(
                f"Unknown fields for {cls.__name__}: {', '.join(sorted(unknown_fields))}"
            )
        resolved_fields = dict(fields)
        missing_fields = []
        base_specs = [
            self._by_class[base]
            for base in cls.__mro__[1:]
            if base in self._by_class
        ]
        for field in dataclass_fields_info:
            if field.name in resolved_fields:
                continue
            for base_spec in base_specs:
                if field.name in base_spec.fields:
                    resolved_fields[field.name] = base_spec.fields[field.name]
                    break
            if field.name in resolved_fields:
                continue
            inferred_type = _unwrap_type(field.type)
            nested_spec = self._by_class.get(inferred_type)
            if nested_spec is None:
                default_pattern = _default_pattern_for_type(field.type)
                if default_pattern is None:
                    missing_fields.append(field.name)
                    continue
                resolved_fields[field.name] = default_pattern
            else:
                resolved_fields[field.name] = f"<{nested_spec.token}>"
        if missing_fields:
            raise ValueError(
                f"Missing fields for {cls.__name__}: {', '.join(sorted(missing_fields))}"
            )
        if regex is None:
            if len(resolved_fields) == 1:
                only_field = next(iter(resolved_fields))
                regex = f"<{only_field}>"
            else:
                raise ValueError("regex is required when multiple fields are defined.")
        if token in self._by_token and self._by_token[token].cls is not cls:
            raise ValueError(f"token already registered: {token}")
        spec = _Spec(
            cls=cls,
            token=token,
            fields=resolved_fields,
            regex=regex,
            dataclass_fields_info=tuple(dataclass_fields_info),
        )
        self._by_token[token] = spec
        self._by_class[cls] = spec
        self._cache.clear()
        return cls

    def compile(self, pattern: str, flags: int = 0) -> _ReclassRegex:
        if not isinstance(pattern, str):
            raise TypeError("pattern must be a string.")
        cache_key = (pattern, flags)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        patterns: list[str] = [pattern]
        for spec in self._by_class.values():
            patterns.append(spec.regex)
            patterns.extend(spec.fields.values())
        reserved_names = _collect_named_groups(patterns)
        name_gen = _NameGenerator(reserved_names)
        occurrences: list[_Occurrence] = []

        user_named_groups = _collect_named_groups_in_pattern(pattern)
        expanded_pattern, user_group_map, findall_elements = _expand_pattern_with_user_groups(
            pattern, self, name_gen, occurrences
        )
        compiled = re.compile(expanded_pattern, flags)
        result = _ReclassRegex(
            compiled=compiled,
            occurrences=occurrences,
            user_group_map=user_group_map,
            user_named_groups=user_named_groups,
            findall_elements=findall_elements,
        )
        self._cache[cache_key] = result
        return result

    def match(self, pattern: str, text: str, flags: int = 0) -> _ReclassMatch | None:
        compiled = self.compile(pattern, flags)
        return compiled.match(text)

    def search(self, pattern: str, text: str, flags: int = 0) -> _ReclassMatch | None:
        compiled = self.compile(pattern, flags)
        return compiled.search(text)

    def fullmatch(
        self, pattern: str, text: str, flags: int = 0
    ) -> _ReclassMatch | None:
        compiled = self.compile(pattern, flags)
        return compiled.fullmatch(text)

    def finditer(self, pattern: str, text: str, flags: int = 0) -> list[_ReclassMatch]:
        compiled = self.compile(pattern, flags)
        return compiled.finditer(text)

    def findall(self, pattern: str, text: str, flags: int = 0) -> list[Any]:
        compiled = self.compile(pattern, flags)
        return compiled.findall(text)

    def split(self, pattern: str, text: str, maxsplit: int = 0, flags: int = 0) -> list[str]:
        compiled = self.compile(pattern, flags)
        return compiled.split(text, maxsplit)

    def sub(self, pattern: str, repl: str, text: str, count: int = 0, flags: int = 0) -> str:
        compiled = self.compile(pattern, flags)
        return compiled.sub(repl, text, count)

    def subn(
        self, pattern: str, repl: str, text: str, count: int = 0, flags: int = 0
    ) -> tuple[str, int]:
        compiled = self.compile(pattern, flags)
        return compiled.subn(repl, text, count)


reclass = Builder()
