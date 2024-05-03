import contextlib, tempfile, os

# from typing import TypeVar, Callable, Any, Generic

# F = TypeVar("F", bound=Callable[..., Any])


# class copy_signature(Generic[F]):
#     def __init__(self, target: F) -> None: ...
#     def __call__(self, wrapped: Callable[..., Any]) -> F: ...


# this is a backport of delete_on_close functionality from 3.12
@contextlib.contextmanager
# @copy_signature(tempfile.NamedTemporaryFile)
def CustomTempFile(*args, **kwargs):
    """
    Context manager for tempfile.NamedTemporaryFile which implements automatic file deletion on exit.
    """
    kwargs["delete"] = False
    file = tempfile.NamedTemporaryFile(*args, **kwargs)
    try:
        yield file
    finally:
        file.close()
        with contextlib.suppress(FileNotFoundError):
            os.remove(file.name)
