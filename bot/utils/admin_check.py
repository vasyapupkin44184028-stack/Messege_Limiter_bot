"""
Утилиты для проверки прав администратора
"""
import os
from pathlib import Path

def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если администратор, False если нет
    """
    admin_file = Path(__file__).parent.parent / "ADMIN_ID.txt"
    
    # Если файла нет, создаем его с ID пользователя (первый запуск)
    if not admin_file.exists():
        print(f"⚠️ Файл ADMIN_ID.txt не найден. Создаю новый...")
        try:
            with open(admin_file, 'w', encoding='utf-8') as f:
                f.write(f"{user_id}\n")
            print(f"✅ Файл создан, добавлен ID: {user_id}")
            return True
        except Exception as e:
            print(f"❌ Ошибка создания файла ADMIN_ID.txt: {e}")
            return False
    
    try:
        with open(admin_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            print(f"⚠️ Файл ADMIN_ID.txt пуст. Добавляю ID: {user_id}")
            with open(admin_file, 'w', encoding='utf-8') as f:
                f.write(f"{user_id}\n")
            return True
        
        # Читаем ID, убираем пустые строки и комментарии
        admin_ids = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                admin_ids.append(line)
        
        return str(user_id) in admin_ids
        
    except Exception as e:
        print(f"❌ Ошибка чтения файла ADMIN_ID.txt: {e}")
        return False

def get_admin_ids() -> list[int]:
    """
    Получает список всех администраторов
    
    Returns:
        list[int]: Список ID администраторов
    """
    admin_file = Path(__file__).parent.parent / "ADMIN_ID.txt"
    
    if not admin_file.exists():
        return []
    
    try:
        with open(admin_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            return []
        
        admin_ids = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if line.isdigit():
                    admin_ids.append(int(line))
        
        return admin_ids
        
    except Exception as e:
        print(f"❌ Ошибка чтения файла ADMIN_ID.txt: {e}")
        return []

def add_admin(user_id: int) -> bool:
    """
    Добавляет нового администратора
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если успешно добавлен
    """
    admin_ids = get_admin_ids()
    
    if user_id in admin_ids:
        print(f"ℹ️ Пользователь {user_id} уже является администратором")
        return True
    
    admin_ids.append(user_id)
    admin_ids = list(set(admin_ids))  # Убираем дубликаты
    
    admin_file = Path(__file__).parent.parent / "ADMIN_ID.txt"
    
    try:
        with open(admin_file, 'w', encoding='utf-8') as f:
            for aid in admin_ids:
                f.write(f"{aid}\n")
        
        print(f"✅ Добавлен администратор: {user_id}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка добавления администратора: {e}")
        return False

def remove_admin(user_id: int) -> bool:
    """
    Удаляет администратора
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если успешно удален
    """
    admin_ids = get_admin_ids()
    
    if user_id not in admin_ids:
        print(f"ℹ️ Пользователь {user_id} не является администратором")
        return True
    
    admin_ids = [aid for aid in admin_ids if aid != user_id]
    
    admin_file = Path(__file__).parent.parent / "ADMIN_ID.txt"
    
    try:
        with open(admin_file, 'w', encoding='utf-8') as f:
            for aid in admin_ids:
                f.write(f"{aid}\n")
        
        print(f"✅ Удален администратор: {user_id}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка удаления администратора: {e}")
        return False

def list_admins() -> str:
    """
    Возвращает список администраторов в виде строки
    
    Returns:
        str: Список администраторов
    """
    admin_ids = get_admin_ids()
    
    if not admin_ids:
        return "📭 Список администраторов пуст"
    
    result = "👮‍♂️ Администраторы бота:\n\n"
    for i, admin_id in enumerate(admin_ids, 1):
        result += f"{i}. ID: `{admin_id}`\n"
    
    result += f"\nВсего: {len(admin_ids)} администраторов"
    return result