from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Chat(Base):
    """Модель чата"""
    __tablename__ = "chats"
    
    id = Column(BigInteger, primary_key=True)  # Telegram chat_id
    title = Column(String(255))
    message_limit = Column(Integer, default=5)
    exclude_words = Column(JSON, default=list)  # Список исключений для этого чата
    exclude_use_regex = Column(Boolean, default=False)  # Использовать regex в исключениях
    banned_words = Column(JSON, default=None)
    notification_texts = Column(JSON, default=dict)  # Кастомные уведомления для этого чата
    custom_notifications = Column(JSON, default=dict)  # Индивидуальные настройки уведомлений
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Связи
    user_data = relationship("UserChatData", back_populates="chat", cascade="all, delete-orphan")

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True)  # Telegram user_id
    username = Column(String(255), nullable=True)
    first_name = Column(String(255))
    last_name = Column(String(255), nullable=True)
    is_global_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    chat_data = relationship("UserChatData", back_populates="user", cascade="all, delete-orphan")

class UserChatData(Base):
    """Данные пользователя в конкретном чате"""
    __tablename__ = "user_chat_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    chat_id = Column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"))
    
    message_count = Column(Integer, default=0)
    custom_limit = Column(Integer, nullable=True)  # Ручной лимит
    custom_limit_expires_at = Column(DateTime, nullable=True)  # Когда истекает ручной лимит (ДОБАВИТЬ)
    
    is_muted = Column(Boolean, default=False)
    mute_until = Column(DateTime, nullable=True)
    last_reset_date = Column(DateTime, default=datetime.utcnow)  # Дата последнего сброса
    last_custom_reset_date = Column(DateTime, nullable=True)  # Дата последнего сброса ручного лимита
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="chat_data")
    chat = relationship("Chat", back_populates="user_data")
    
    # Уникальный ключ
    __table_args__ = ({"sqlite_autoincrement": True},)

class GlobalSettings(Base):
    """Глобальные настройки"""
    __tablename__ = "global_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_link = Column(String(500), default="")
    default_message_limit = Column(Integer, default=5)
    default_exclude_words = Column(JSON, default=list)
    default_exclude_use_regex = Column(Boolean, default=False)  # Использовать regex в глобальных исключениях
    default_notifications = Column(JSON, default=dict)
    default_banned_words = Column(JSON, default=list)
    auto_unblock_days = Column(Integer, default=30)  # Авторазблокировка через N дней
    security_log_enabled = Column(Boolean, default=True)
    default_min_message_length = Column(Integer, default=20)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    default_banned_words = Column(JSON, default=list)  # Новое поле!

class ActionLog(Base):
    """Логи действий"""
    __tablename__ = "action_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(50))  # Тип действия: message_sent, user_blocked, etc.
    user_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=True)
    details = Column(Text, nullable=True)  # Дополнительная информация
    created_at = Column(DateTime, default=datetime.utcnow)

class Statistics(Base):
    """Статистика"""
    __tablename__ = "statistics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, default=datetime.utcnow)
    total_messages = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    total_chats = Column(Integer, default=0)
    blocked_users = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)