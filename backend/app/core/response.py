from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger("app.response")

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "操作成功") -> "Result[T]":
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int = 500, message: str = "系统异常", data: Optional[T] = None) -> "Result[T]":
        return cls(code=code, message=message, data=data)


class PageResult(BaseModel, Generic[T]):
    list: list[T]
    total: int
    page: int
    size: int
    total_pages: int

    @classmethod
    def create(cls, items: list[T], total: int, page: int, size: int) -> "PageResult[T]":
        total_pages = (total + size - 1) // size if size > 0 else 0
        return cls(
            list=items,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages
        )


class BusinessException(Exception):
    """业务异常类，携带业务状态码与提示信息"""
    def __init__(self, message: str, code: int = 400, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，实现企业级统一格式输出"""

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        logger.warning(f"Business exception on {request.url.path}: {exc.message} (code={exc.code})")
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # 业务错误在企业规范中通常通过 code 标识
            content={"code": exc.code, "message": exc.message, "data": exc.data}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # 自定义校验器抛出的 ValueError 会原样挂在 errors()[*].ctx.error 上，
        # 直接塞进 JSONResponse 会 TypeError（表现为 500）；jsonable_encoder 负责转成可序列化结构
        errors = jsonable_encoder(exc.errors())
        err_msg = "; ".join([f"{e.get('loc', ['field'])[-1]}: {e.get('msg', 'invalid')}" for e in errors])
        logger.warning(f"Validation error on {request.url.path}: {err_msg}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"code": 422, "message": f"参数校验失败: {err_msg}", "data": errors}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(f"HTTP exception on {request.url.path}: {exc.detail} (status={exc.status_code})")
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": str(exc.detail), "data": None}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled system error on {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": 500, "message": "服务器内部错误，请联系系统管理员", "data": None}
        )
