import inspect
from typing import Any, Callable, Literal

from cyclopts import annotations
from pydantic import ConfigDict, BaseModel, field_serializer, model_serializer, TypeAdapter
from pydantic_core import PydanticUndefinedType, PydanticUndefined
from pydantic_core.core_schema import SerializerFunctionWrapHandler

RequestId = str | int | float
RequestDict = dict[str, Any]

class ErrorDetails(BaseModel):
    code: int
    message: str
    data: Any | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

class ErrorResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: RequestId | None
    error: ErrorDetails

    model_config = ConfigDict(extra="forbid", frozen=True)


class SuccessResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: RequestId
    result: Any

    model_config = ConfigDict(extra="forbid", frozen=True)


Response = SuccessResponse | ErrorResponse
ResponseTypeAdapter = TypeAdapter(Response | list[Response])

class UnsetType:
    pass

Unset = UnsetType()

class ParamDescription(BaseModel):
    name: str
    default: Any = Unset
    varargs: Any = Unset
    kwargs: Any = Unset
    annotations: Any = Unset

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_serializer("default", when_used="json")
    def serialize_default(self, _nxt: SerializerFunctionWrapHandler) -> Any | None:
        return None if self.default is Unset else self.default

    @field_serializer("varargs", when_used="json")
    def serialize_varargs(self, _nxt: SerializerFunctionWrapHandler) -> Any | None:
        return None if self.varargs is Unset else self.varargs

    @field_serializer("kwargs", when_used="json")
    def serialize_kwargs(self, _nxt: SerializerFunctionWrapHandler) -> Any | None:
        return None if self.kwargs is Unset else self.kwargs

    @field_serializer("annotations", when_used="json")
    def serialize_annotations(self, _nxt: SerializerFunctionWrapHandler) -> Any | None:
        return None if self.annotations is Unset else self.annotations

    @model_serializer(mode="wrap", when_used="json")
    def serialize_model(self, nxt: SerializerFunctionWrapHandler) -> Any:
        serialized = nxt(self)
        if self.default is Unset:
            del serialized["default"]
        if self.varargs is Unset:
            del serialized["varargs"]
        if self.kwargs is Unset:
            del serialized["kwargs"]
        return serialized

class MethodDescription(BaseModel):
    description: str | None
    params: list[ParamDescription]
    annotations: str | None

    model_config = ConfigDict(extra="forbid", frozen=True)

class Inspector2:
    """Inspects classes and functions to create a JSON-RPC 2.0 description.

    Inspects a group of classes and functions to create a description of what
    methods they can expose over JSON-RPC 2.0.

    To inspect one or more classes, add them all to the objects mapping. The
    key in the mapping is used as the classes' mounting point in the exposed
    API:

    ```python
    inspector = Inspector(objects={
        'foo': Foo,
        'hello': lambda: 'Hello, world!',
    })
    ```

    Since the inspector is based on inspecting classes and not instances, it
    will not include methods added dynamically. The wrapper works with
    instances, and it will thus export dynamically added methods as well.

    Args:
        objects: Mapping between mounts and exposed functions or classes.
    """

    def __init__(self, objects: dict[str, Callable[..., Any]]) -> None:
        if "" in objects:
            msg = "The empty string is not allowed as an object mount"
            raise AttributeError(msg)
        self.objects = objects

    def describe(self) -> dict[str, MethodDescription]:
        """Inspects the object and returns a description of its API.

        Returns a data structure which describes the available properties and
        methods.
        """
        methods: dict[str, MethodDescription] = {}
        for mount, obj in self.objects.items():
            if inspect.isroutine(obj):
                methods[mount] = self._describe_method(obj)
            else:
                obj_methods = self._get_methods(obj)
                for name, description in obj_methods.items():
                    if mount:
                        name = f"{mount}.{name}"
                    methods[name] = description
        return methods

    def _get_methods(self, obj: Any) -> dict[str, MethodDescription]:
        methods: dict[str, MethodDescription] = {}
        for name, value in inspect.getmembers(obj):
            if name.startswith("_"):
                continue
            if not inspect.isroutine(value):
                continue
            method = self._describe_method(value)
            if method:
                methods[name] = method
        return methods

    def _describe_method(self, method: Callable[..., Any]) -> MethodDescription:
        argspec = inspect.getfullargspec(method)
        annots = argspec.annotations if argspec.annotations is not None else {}
        return MethodDescription(
            description=inspect.getdoc(method),
            params=self._describe_params(method),
            annotations=annots.get("return", "None"),
        )

    def _describe_params(
        self,
        method: Callable[..., Any],
    ) -> list[ParamDescription]:
        argspec = inspect.getfullargspec(method)

        with_defaults: list[Any] = list(argspec.defaults) if argspec.defaults else []
        num_args_without_default = len(argspec.args) - len(with_defaults)
        without_defaults: list[PydanticUndefinedType] = [
            PydanticUndefined
        ] * num_args_without_default
        defaults = without_defaults + with_defaults

        annots = argspec.annotations if argspec.annotations is not None else {}

        params: list[ParamDescription] = []

        for arg, default in zip(argspec.args, defaults, strict=True):
            if arg == "self":
                continue
            annot = annots.get(arg, "None")
            params.append(ParamDescription(name=arg, default=default, annotations=annot))

        if argspec.varargs:
            params.append(ParamDescription(name=argspec.varargs, varargs=True))

        if argspec.varkw:
            params.append(ParamDescription(name=argspec.varkw, kwargs=True))

        for kwonly_arg in argspec.kwonlyargs:
            default = argspec.kwonlydefaults.get(kwonly_arg, Unset) if argspec.kwonlydefaults else Unset
            annot = annots.get(kwonly_arg, Unset)
            params.append(ParamDescription(name=kwonly_arg, default=default, annotations=annot))

        return params
