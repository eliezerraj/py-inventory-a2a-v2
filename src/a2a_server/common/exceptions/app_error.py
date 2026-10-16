from typing import Optional

class AppError(Exception):

    def __init__(self, 
                 message: str,
                 error: Optional[str] = None,
                 error_type: Optional[str] = None,
                 uri: Optional[str] = None, 
                 status_code: Optional[int] = None):
        
        super().__init__(message)
        
        self.uri: Optional[str] = uri
        self.error: Optional[str] = error
        self.error_type: Optional[str] = error_type or self.__class__.__name__
        self.status_code: Optional[int] = status_code
        self.message: str = message
        
    def to_dict(self):
        return {
            "uri": self.uri,
            "error": self.error,
            "error_type": self.error_type,
            "status_code": self.status_code,
            "message": self.message
        }