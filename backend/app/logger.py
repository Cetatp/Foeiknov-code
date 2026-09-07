"""
日志系统
基于 Loguru 实现分级日志：控制台彩色输出 + 文件落盘（UTF-8，按天轮转）。
全项目单例：from app.logger import logger
"""
import sys
from pathlib import Path
from loguru import logger

from app.config import settings


def _setup_logger() -> None:
    """配置 Loguru：移除默认 handler，添加控制台 + 文件双输出。"""
    # 移除默认 stderr handler
    logger.remove()

    # 1. 控制台彩色输出
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # 2. 文件落盘（按天轮转，UTF-8 编码，保留 30 天）
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        rotation="00:00",          # 每天零点轮转
        retention="30 days",       # 保留 30 天
        encoding="utf-8",
        enqueue=True,              # 异步写入，避免多进程阻塞
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
    )


# 初始化日志配置
_setup_logger()

# 导出 logger 单例
__all__ = ["logger"]
