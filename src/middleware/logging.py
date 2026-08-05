import logging
import time
from fastapi import Request
import json
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from typing import Callable
import uuid


class StructuredLogginFormat(logging.Formatter):
    def format(seld, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:5S", time.localtime(record.created)),
            "module": record.module,
            "level_name": record.levelname,
            "function": record.funcName,
            "message": record.getMessage(),
            "line_no": record.lineno
        }
        
        
        for field in ("request_id", "user_id", "status_code", "query_param",
                      "path", "client_ip", "duration","detail"):
            if hasattr(record, field):
                log_entry[field] = getattr(record, field )
        return json.dumps(log_entry)
    
    
    
def logger(name: str) -> logging.Logger:
    
    logger = logging.getLogger(name)
    
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogginFormat)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    return logger




class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        start_time = time.perf_counter()
        
        logging.debug(f"Request Received", 
                      extra={
                          "request_id": request_id,
                          "path": request.url.path, 
                          "query_params": str(request.query_params) if request.query_params else None,
                          "method": request.method
                      })
        
        try:
            
            response = await call_next(request)
        except Exception as e:
            duration = time.perf_counter() - start_time
            logging.error("Request Error", 
                          extra={
                              "request_id": request_id,
                              "path": request.url.path,
                              "query_params": str(request.query_params) if request.query_params else None,
                              "method": request.method,
                              "duration": duration,
                              "detail": str(e)
                          })

            raise 
        
        duration = time.perf_counter() - start_time
        logging.info("Request Completed", 
                     extra={
                         "request_id": request_id,
                         "path": request.url.path,
                         "query_params": str(request.query_params) if request.query_params else None,
                         "method": request.method,
                         "status_code": response.status_code,
                         "duration": duration
                     })
        return response