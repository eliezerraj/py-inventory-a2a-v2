from src.a2a_server.common.exceptions.app_error import AppError

class InvalidAccessTokenError(AppError):
    pass

class AuthorizationDeniedError(AppError):
    pass

class MissingTokenError(AppError):
    pass