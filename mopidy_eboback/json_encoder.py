import json

# Source - https://stackoverflow.com/a/54577313
# Posted by jmm, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-10, License - CC BY-SA 4.0

class CompactJSONEncoder(json.JSONEncoder):
    """A JSON Encoder that puts small lists on single lines."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.indentation_level = 0

    def encode(self, o):
        """Encode JSON object *o* with respect to single line lists."""

        if isinstance(o, (list, tuple)):
            if self._is_single_line_list(o):
                return "[" + ", ".join(json.dumps(el) for el in o) + "]"
            else:
                self.indentation_level += 1
                output = [self.indent_str + self.encode(el) for el in o]
                self.indentation_level -= 1
                return "[\n" + ",\n".join(output) + "\n" + self.indent_str + "]"

        elif isinstance(o, dict):
            if self._is_single_line_list(o):
                self.indentation_level += 1
                output = [f"{json.dumps(k)}: {self.encode(v)}" for k, v in o.items()]
                self.indentation_level -= 1
                return "{" + ", ".join(output) + "}"
            else:
                self.indentation_level += 1
                output = [self.indent_str + f"{json.dumps(k)}: {self.encode(v)}" for k, v in o.items()]
                self.indentation_level -= 1
                return "{\n" + ",\n".join(output) + "\n" + self.indent_str + "}"

        else:
            return json.dumps(o)

    @staticmethod
    def _is_single_line_list(o):
        if isinstance(o, (list, tuple, dict)):
            return not any(isinstance(el, (list, tuple, dict)) for el in o) \
                and len(o) <= 2 \
                and len(str(o)) - 2 <= 160
        return False

    @property
    def indent_str(self) -> str:
        return " " * self.indentation_level * self.indent

    def iterencode(self, o, **kwargs):
        """Required to also work with `json.dump`."""
        return self.encode(o)
