from src.a2a_server.domain.external.error_response import AppError

class InvalidAccessTokenError(AppError):
    pass

class AuthorizationDeniedError(AppError):
    pass

class MissingTokenError(AppError):
    pass

class ForbiddenError(AppError):
    pass

class MCPAuthorizationProtectionRequired(AppError):
    pass

class A2ARequestError(Exception):
    pass

class A2ARouterError(A2ARequestError):
    pass