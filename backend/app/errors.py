"""Domain errors. Routers map these to HTTP responses."""


class AppError(Exception):
    """Base class for expected application failures."""


class InvalidCredentials(AppError):
    pass


class ProjectNotFound(AppError):
    pass


class SourceNotConfigured(AppError):
    pass


class UnknownAdapter(AppError):
    pass


class FixtureError(AppError):
    pass


class MixedCurrencyError(AppError):
    pass
