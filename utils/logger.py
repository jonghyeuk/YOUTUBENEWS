import logging
import sys
from typing import Optional


def setup_logger(name: str = "SeniorVideoFactory",
                level: int = logging.INFO,
                log_file: Optional[str] = None) -> logging.Logger:
    """
    로거 설정

    Args:
        name: 로거 이름
        level: 로깅 레벨
        log_file: 로그 파일 경로 (None이면 콘솔만 출력)

    Returns:
        설정된 로거
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 포맷 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (선택적)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
