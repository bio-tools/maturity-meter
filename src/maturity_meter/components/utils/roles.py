"""Roles of helper functions, recorded by the lineage tracing.

Tagging a helper with its role lets the lineage tell, for example, scaling
(which applies to data fields) from reconciliation (which belongs to a metric).
"""

from collections.abc import Callable
from typing import Literal, TypeVar

Role = Literal["scaling", "reconciliation", "aggregation"]
ROLE_ATTRIBUTE = "__lineage_role__"

F = TypeVar("F", bound=Callable[..., object])


def role(name: Role) -> Callable[[F], F]:
    """Tag a helper function with its role.

    Parameters
    ----------
    name : {"scaling", "reconciliation", "aggregation"}
        ``scaling`` turns a raw field value into a score, ``reconciliation``
        combines values from several sources into one metric value, and
        ``aggregation`` combines metric scores into a dimension score.

    Returns
    -------
    callable
        A decorator that returns the function unchanged, apart from the tag.
    """

    def tag(function: F) -> F:
        setattr(function, ROLE_ATTRIBUTE, name)
        return function

    return tag
