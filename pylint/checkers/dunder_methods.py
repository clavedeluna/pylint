# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import Instance, Uninferable, nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages, safe_infer
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint import PyLinter


DUNDER_METHODS: dict[tuple[int, int], dict[str, str]] = {
    (0, 0): {
        "__init__": "Instantiate class directly",
        "__del__": "Use del keyword",
        "__repr__": "Use repr built-in function",
        "__str__": "Use str built-in function",
        "__bytes__": "Use bytes built-in function",
        "__format__": "Use format built-in function, format string method, or f-string",
        "__lt__": "Use < operator",
        "__le__": "Use <= operator",
        "__eq__": "Use == operator",
        "__ne__": "Use != operator",
        "__gt__": "Use > operator",
        "__ge__": "Use >= operator",
        "__hash__": "Use hash built-in function",
        "__bool__": "Use bool built-in function",
        "__getattr__": "Access attribute directly or use getattr built-in function",
        "__getattribute__": "Access attribute directly or use getattr built-in function",
        "__setattr__": "Set attribute directly or use setattr built-in function",
        "__delattr__": "Use del keyword",
        "__dir__": "Use dir built-in function",
        "__get__": "Use get method",
        "__set__": "Use set method",
        "__delete__": "Use del keyword",
        "__instancecheck__": "Use isinstance built-in function",
        "__subclasscheck__": "Use issubclass built-in function",
        "__call__": "Invoke instance directly",
        "__len__": "Use len built-in function",
        "__length_hint__": "Use length_hint method",
        "__getitem__": "Access item via subscript",
        "__setitem__": "Set item via subscript",
        "__delitem__": "Use del keyword",
        "__iter__": "Use iter built-in function",
        "__next__": "Use next built-in function",
        "__reversed__": "Use reversed built-in function",
        "__contains__": "Use in keyword",
        "__add__": "Use + operator",
        "__sub__": "Use - operator",
        "__mul__": "Use * operator",
        "__matmul__": "Use @ operator",
        "__truediv__": "Use / operator",
        "__floordiv__": "Use // operator",
        "__mod__": "Use % operator",
        "__divmod__": "Use divmod built-in function",
        "__pow__": "Use ** operator or pow built-in function",
        "__lshift__": "Use << operator",
        "__rshift__": "Use >> operator",
        "__and__": "Use & operator",
        "__xor__": "Use ^ operator",
        "__or__": "Use | operator",
        "__radd__": "Use + operator",
        "__rsub__": "Use - operator",
        "__rmul__": "Use * operator",
        "__rmatmul__": "Use @ operator",
        "__rtruediv__": "Use / operator",
        "__rfloordiv__": "Use // operator",
        "__rmod__": "Use % operator",
        "__rdivmod__": "Use divmod built-in function",
        "__rpow__": "Use ** operator or pow built-in function",
        "__rlshift__": "Use << operator",
        "__rrshift__": "Use >> operator",
        "__rand__": "Use & operator",
        "__rxor__": "Use ^ operator",
        "__ror__": "Use | operator",
        "__iadd__": "Use += operator",
        "__isub__": "Use -= operator",
        "__imul__": "Use *= operator",
        "__imatmul__": "Use @= operator",
        "__itruediv__": "Use /= operator",
        "__ifloordiv__": "Use //= operator",
        "__imod__": "Use %= operator",
        "__ipow__": "Use **= operator",
        "__ilshift__": "Use <<= operator",
        "__irshift__": "Use >>= operator",
        "__iand__": "Use &= operator",
        "__ixor__": "Use ^= operator",
        "__ior__": "Use |= operator",
        "__neg__": "Multiply by -1 instead",
        "__pos__": "Multiply by +1 instead",
        "__abs__": "Use abs built-in function",
        "__invert__": "Use ~ operator",
        "__complex__": "Use complex built-in function",
        "__int__": "Use int built-in function",
        "__float__": "Use float built-in function",
        "__round__": "Use round built-in function",
        "__trunc__": "Use math.trunc function",
        "__floor__": "Use math.floor function",
        "__ceil__": "Use math.ceil function",
        "__enter__": "Invoke context manager directly",
        "__aenter__": "Invoke context manager directly",
        "__copy__": "Use copy.copy function",
        "__deepcopy__": "Use copy.deepcopy function",
        "__fspath__": "Use os.fspath function instead",
    },
    (3, 10): {
        "__aiter__": "Use aiter built-in function",
        "__anext__": "Use anext built-in function",
    },
}


EXTRA_DUNDER_METHODS: list = [
    "__new__",
    "__subclasses__",
    "__init_subclass__",
    "__set_name__",
    "__class_getitem__",
    "__missing__",
    "__exit__",
    "__await__",
    "__aexit__",
    "__getnewargs_ex__",
    "__getnewargs__",
    "__getstate__",
    "__setstate__",
    "__reduce__",
    "__reduce_ex__",
    "__post_init__",  #  part of dataclasses module
]

DUNDER_PROPERTIES: list = [
    "__class__",
    "__dict__",
    "__doc__",
    "__format__",
    "__module__",
    "__sizeof__",
    "__subclasshook__",
    "__weakref__",
]


class DunderChecker(BaseChecker):
    """Checks related to dunder methods.

    Docs: https://docs.python.org/3/reference/datamodel.html#basic-customization

    For `unnecessary-dunder-call` we exclude dunder names in list
    `EXTRA_DUNDER_METHODS` since these either have no alternative
    method of being called or have a genuine use case for being called manually.

    Additionally, we exclude classes that are not instantiated since these
    might be used to access the dunder methods of a base class of an instance.
    We also exclude dunder method calls on super() since
    these can't be written in an alternative manner.
    """

    name = "dunder"
    priority = -1
    msgs = {
        "C2801": (
            "Unnecessarily calls dunder method %s. %s.",
            "unnecessary-dunder-call",
            "Used when a dunder method is manually called instead "
            "of using the corresponding function/method/operator.",
        ),
        "C2802": (
            "Bad or misspelled dunder method name %s.",
            "bad-dunder-name",
            "Used when a dunder method is misspelled or defined with a name "
            "not within the predefined list of dunder names.",
        ),
    }
    options = ()

    def open(self) -> None:
        self._dunder_methods: dict[str, str] = {}
        for since_vers, dunder_methods in DUNDER_METHODS.items():
            if since_vers <= self.linter.config.py_version:
                self._dunder_methods.update(dunder_methods)

    @staticmethod
    def within_dunder_def(node: nodes.NodeNG) -> bool:
        """Check if dunder method call is within a dunder method definition."""
        parent = node.parent
        while parent is not None:
            if (
                isinstance(parent, nodes.FunctionDef)
                and parent.name.startswith("__")
                and parent.name.endswith("__")
            ):
                return True
            parent = parent.parent
        return False

    @only_required_for_messages("bad-dunder-name")
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check if known dunder method is misspelled or dunder name is not one
        of the pre-defined names.
        """
        # ignore module-level functions
        if not node.is_method():
            return

        if (
            # Detect something that could be a dunder method
            # It must start with `__` to be private, but could end
            # with `_` if there is a misspelling.
            node.name.startswith("__")
            and node.name.endswith("_")
            and node.name not in self._dunder_methods
            and node.name not in EXTRA_DUNDER_METHODS + DUNDER_PROPERTIES
        ):
            self.add_message(
                "bad-dunder-name",
                node=node,
                args=(node.name),
                confidence=HIGH,
            )

    @only_required_for_messages("unnecessary-dunder-call")
    def visit_call(self, node: nodes.Call) -> None:
        """Check if method being called is an unnecessary dunder method."""
        if (
            isinstance(node.func, nodes.Attribute)
            and node.func.attrname in self._dunder_methods
            and not self.within_dunder_def(node)
            and not (
                isinstance(node.func.expr, nodes.Call)
                and isinstance(node.func.expr.func, nodes.Name)
                and node.func.expr.func.name == "super"
            )
        ):
            inf_expr = safe_infer(node.func.expr)
            if not (inf_expr in {None, Uninferable} or isinstance(inf_expr, Instance)):
                # Skip dunder calls to non instantiated classes.
                return

            self.add_message(
                "unnecessary-dunder-call",
                node=node,
                args=(node.func.attrname, self._dunder_methods[node.func.attrname]),
                confidence=HIGH,
            )


def register(linter: PyLinter) -> None:
    linter.register_checker(DunderChecker(linter))
