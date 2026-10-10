"""Domain errors. Routers map these to HTTP responses."""


class AppError(Exception):
    """Base class for expected application failures."""


class InvalidCredentials(AppError):
    pass


class InvalidProject(AppError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


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


class InvalidPayload(AppError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class InvalidDataSource(AppError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)
