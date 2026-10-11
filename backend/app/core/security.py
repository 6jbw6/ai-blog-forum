from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import ipaddress
import socket
from urllib.parse import urlparse

import bcrypt
import jwt
from app.core.config import settings
from app.core.response import BusinessException


def assert_safe_llm_endpoint(raw_url: Optional[str]) -> str:
    """校验管理员提交的大模型端点地址，返回去空白后的 URL，不合法直接抛业务异常。

    这些地址会被后端**主动请求**（拉模型列表、连通性测试、之后的真实推理），
    不做校验就是一个 SSRF 入口：可以拿服务器当跳板探测内网服务，或读取云主机的
    169.254.169.254 元数据接口（里面通常躺着临时访问凭证）。

    本机跑 Ollama / LM Studio 这类私网端点时，用 ALLOW_PRIVATE_LLM_ENDPOINTS=true 显式放开。

    残余风险：这里解析一次 DNS 做判定，供应商客户端真正发请求时会再解析一次，
    两次之间理论上能被 DNS 重绑定换成内网结果。要彻底堵死得把已解析的 IP 钉进连接层，
    代价与收益不匹配（入口本身已经是管理员权限），因此只做到「解析后判定」。
    """
    url = (raw_url or "").strip()
    if not url:
        raise BusinessException("大模型端点地址不能为空", code=400)

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BusinessException("大模型端点必须是 http 或 https 地址", code=400)
    host = parsed.hostname
    if not host:
        raise BusinessException("大模型端点缺少主机名", code=400)

    if settings.ALLOW_PRIVATE_LLM_ENDPOINTS:
        return url

    try:
        infos = socket.getaddrinfo(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror:
        raise BusinessException("大模型端点域名无法解析，请检查地址", code=400)

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise BusinessException(
                "大模型端点不能指向内网、本机或链路本地地址；确需接入本地模型服务，"
                "请在服务端开启 ALLOW_PRIVATE_LLM_ENDPOINTS", code=400
            )
    return url


def hash_password(password: str) -> str:
    """对原始明文密码进行安全加盐哈希"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT 鉴权访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """解码并校验 JWT 令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None
