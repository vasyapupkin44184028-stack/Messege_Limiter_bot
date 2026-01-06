"""
Сервисы для бота
"""

from .scheduler import scheduler, start_scheduler, stop_scheduler, get_scheduler_info

__all__ = [
    'scheduler',
    'start_scheduler',
    'stop_scheduler',
    'get_scheduler_info'
]