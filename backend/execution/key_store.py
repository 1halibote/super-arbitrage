"""
API 密钥安全存储模块
使用 AES-256 加密存储，密钥派生自机器指纹
"""
import os
import json
import base64
import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 密钥存储路径
KEYS_FILE = Path(__file__).parent.parent / "data" / "api_keys.enc"
SALT_FILE = Path(__file__).parent.parent / "data" / ".salt"

def _get_machine_id() -> str:
    """获取机器指纹作为加密密钥的一部分"""
    import platform
    import uuid
    
    # 组合多个系统信息生成唯一标识
    info = f"{platform.node()}-{uuid.getnode()}-{os.getenv('USERNAME', 'default')}"
    return hashlib.sha256(info.encode()).hexdigest()[:32]

def _get_or_create_salt() -> bytes:
    """获取或创建加密盐值"""
    SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    else:
        # Create persistent salt for this installation
        salt = os.urandom(16)
        SALT_FILE.write_bytes(salt)
        return salt

def _derive_key() -> bytes:
    """派生加密密钥"""
    machine_id = _get_machine_id().encode()
    salt = _get_or_create_salt()
    
    try:
        # Try modern interface (cryptography >= 3.1)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
    except TypeError:
        # Fallback for ancient versions (< 3.1) that require 'backend'
        from cryptography.hazmat.backends import default_backend
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    return key

class ApiKeyStore:
    """API 密钥安全存储"""
    
    def __init__(self):
        self._fernet = Fernet(_derive_key())
        self._keys: Dict[str, Dict[str, str]] = {}
        self._load()
    
    def _load(self):
        """从加密文件加载密钥"""
        if KEYS_FILE.exists():
            try:
                encrypted = KEYS_FILE.read_bytes()
                decrypted = self._fernet.decrypt(encrypted)
                self._keys = json.loads(decrypted.decode())
                logging.info(f"Loaded API keys for {len(self._keys)} exchanges")
            except Exception as e:
                logging.error(f"Failed to load API keys: {e}")
                self._keys = {}
        else:
            self._keys = {}
    
    def _save(self):
        """保存密钥到加密文件"""
        KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self._keys).encode()
        encrypted = self._fernet.encrypt(data)
        KEYS_FILE.write_bytes(encrypted)
        logging.info("API keys saved")
    
    def set_key(self, exchange: str, api_key: str, api_secret: str, passphrase: str = ""):
        """设置交易所 API 密钥"""
        self._keys[exchange.lower()] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "passphrase": passphrase
        }
        self._save()
    
    def get_key(self, exchange: str) -> Optional[Dict[str, str]]:
        """获取交易所 API 密钥"""
        return self._keys.get(exchange.lower())
    
    def delete_key(self, exchange: str):
        """删除交易所 API 密钥"""
        if exchange.lower() in self._keys:
            del self._keys[exchange.lower()]
            self._save()
    
    def list_exchanges(self) -> list:
        """列出已配置的交易所"""
        return list(self._keys.keys())
    
    def has_key(self, exchange: str) -> bool:
        """检查是否已配置某交易所"""
        return exchange.lower() in self._keys

# 全局实例
api_key_store = ApiKeyStore()
