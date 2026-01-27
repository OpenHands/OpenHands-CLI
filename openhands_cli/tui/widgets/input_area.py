"""Input area container for status lines and input field.

This container is docked to the bottom of MainDisplay and holds:
- WorkingStatusLine (shows running status and elapsed time)
- InputField (user input)
- InfoStatusLine (shows mode and metrics)

The child widgets are composed by AppState (not this container) to enable
data_bind() to work properly. AppState.compose() uses this container as a
context manager and yields the children inside it.
"""

from textual.containers import Container


class InputAreaContainer(Container):
    """Container for the input area with status lines and input field.
    
    This is a simple container widget - children are yielded by AppState.compose()
    using `with InputAreaContainer(...):` context manager syntax.
    """

    pass
