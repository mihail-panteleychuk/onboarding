from threading import local


class AppContext(local):
    """
    A thread-local context for storing for any variable that should be accessible from anywhere,
    despite that it wasn't provided as an argument.
    To change list of allowed keys - change `keys` attribute.

    Example:
        app_context.set(request=request, user=user, user_id=user.id, trace_id=trace_id)
        print(app_context.trace_id)
    """

    keys = ("request", "user", "user_id", "trace_id", "logging_enabled")

    def __init__(self):
        self.clear()

    def __repr__(self):
        attr_text = ", ".join([f"{k}={getattr(self, k)}" for k in self.keys])
        return f"<{self.__class__.__name__}: {attr_text}>"

    def set(self, **kwargs):
        for k in self.keys:
            v = kwargs.pop(k, None)
            if v is not None:
                setattr(self, k, v)
        if kwargs:
            raise ValueError(
                f"Unexpected keys: '{kwargs.keys()}', only '{self.keys}' are allowed.",
            )

    def clear(self):
        for k in self.keys:
            setattr(self, k, None)


app_context = AppContext()
