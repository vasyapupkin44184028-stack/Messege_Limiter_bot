from aiogram.fsm.state import State, StatesGroup

# Патч для быстрого добавления отсутствующих состояний
'''def patch_admin_states():
    """Добавляет отсутствующие состояния в класс AdminStates"""
    if not hasattr(AdminStates, 'waiting_for_chat_search'):
        setattr(AdminStates, 'waiting_for_chat_search', State())
    
    if not hasattr(AdminStates, 'waiting_for_user_search'):
        setattr(AdminStates, 'waiting_for_user_search', State())

# Вызываем патч при импорте
patch_admin_states()'''

class AdminStates(StatesGroup):
    """
    Состояния для админ-панели.
    Используются для обработки последовательных действий администратора.
    """
    
    # ===== УПРАВЛЕНИЕ ЛИМИТАМИ =====
    waiting_for_global_limit = State()
    """Ожидание ввода нового глобального лимита сообщений"""
    
    waiting_for_chat_limit = State()
    """Ожидание ввода нового лимита для конкретного чата"""
    
    waiting_for_user_limit = State()
    """Ожидание ввода нового индивидуального лимита для пользователя"""
    
    # ===== ПОИСК ЧАТОВ И ПОЛЬЗОВАТЕЛЕЙ =====
    waiting_for_chat_search = State()      # ← ДОБАВИТЬ ЭТО
    """Ожидание ввода текста для поиска чатов"""
    
    waiting_for_user_search = State()      # ← И ЭТО (уже есть, но убедитесь)
    """Ожидание ввода имени или ID пользователя для поиска"""
    
    # ===== УПРАВЛЕНИЕ ИСКЛЮЧЕНИЯМИ =====
    waiting_for_exception_word = State()
    """Ожидание ввода нового слова для исключений или запрещенных слов"""
    
    # ===== УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ =====
    waiting_for_notification_text = State()
    """Ожидание ввода нового текста уведомления"""
    
    waiting_for_empty_notification = State()
    """Ожидание ввода текста уведомления для пустых сообщений"""
    
    waiting_for_warning_notification = State()
    """Ожидание ввода текста предупреждения"""
    
    waiting_for_limit_notification = State()
    """Ожидание ввода текста при исчерпании лимита"""
    
    waiting_for_blocked_notification = State()
    """Ожидание ввода текста для заблокированных пользователей"""
    
    # ===== ГЛОБАЛЬНЫЕ НАСТРОЙКИ =====
    waiting_for_contact_link = State()
    """Ожидание ввода новой контактной ссылки"""
    
    # ===== НОВЫЕ СОСТОЯНИЯ ДЛЯ НАСТРОЕК СООБЩЕНИЙ =====
    waiting_for_min_length = State()
    """Ожидание ввода новой минимальной длины сообщений (5-100 символов)"""
    
    waiting_for_test_text = State()
    """Ожидание ввода текста для тестирования длины сообщений"""
    
    waiting_for_banned_word = State()
    """Ожидание ввода нового запрещенного слова"""
    
    waiting_for_chat_min_length = State()
    """Ожидание ввода минимальной длины для конкретного чата"""
    
    waiting_for_chat_banned_word = State()
    """Ожидание ввода запрещенного слова для конкретного чата"""
    
    # ===== НАСТРОЙКИ ВРЕМЕНИ И ТАЙМАУТОВ =====
    waiting_for_notification_delay = State()
    """Ожидание ввода времени показа уведомлений (в секундах)"""
    
    waiting_for_empty_message_delay = State()
    """Ожидание ввода задержки удаления пустых сообщений"""
    
    waiting_for_mute_duration = State()
    """Ожидание ввода длительности мута (в днях)"""
    
    # ===== НАСТРОЙКИ ПРАВИЛ ЧАТА =====
    waiting_for_chat_rules = State()
    """Ожидание ввода правил чата"""
    
    waiting_for_welcome_message = State()
    """Ожидание ввода приветственного сообщения"""
    
    waiting_for_goodbye_message = State()
    """Ожидание ввода прощального сообщения"""
    
    # ===== УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ =====
    waiting_for_admin_id = State()
    """Ожидание ввода ID нового администратора"""
    
    waiting_for_admin_remove = State()
    """Ожидание ввода ID администратора для удаления"""
    
    # ===== СТАТИСТИКА И ЭКСПОРТ =====
    waiting_for_export_format = State()
    """Ожидание выбора формата экспорта статистики"""
    
    waiting_for_statistics_period = State()
    """Ожидание выбора периода для статистики"""
    
    # ===== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====
    waiting_for_backup_type = State()
    """Ожидание выбора типа резервного копирования"""
    
    waiting_for_restore_confirm = State()
    """Ожидание подтверждения восстановления из резервной копии"""
    
    # ===== НАСТРОЙКИ БЕЗОПАСНОСТИ =====
    waiting_for_security_level = State()
    """Ожидание выбора уровня безопасности"""
    
    waiting_for_log_retention = State()
    """Ожидание ввода срока хранения логов (в днях)"""
    
    waiting_for_auto_unblock_days = State()
    """Ожидание ввода дней до авторазблокировки"""
    
    # ===== НАСТРОЙКИ ФИЛЬТРОВ СООБЩЕНИЙ =====
    waiting_for_filter_type = State()
    """Ожидание выбора типа фильтра сообщений"""
    
    waiting_for_regex_pattern = State()
    """Ожидание ввода регулярного выражения для фильтрации"""
    
    waiting_for_media_filter = State()
    """Ожидание настройки фильтра медиа-сообщений"""
    
    # ===== УПРАВЛЕНИЕ ЧАТАМИ =====
    waiting_for_chat_title = State()
    """Ожидание ввода нового названия чата"""
    
    waiting_for_chat_status = State()
    """Ожидание изменения статуса чата (активен/неактивен)"""
    
    waiting_for_chat_transfer = State()
    """Ожидание подтверждения передачи прав на чат"""
    
    # ===== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====
    waiting_for_user_search = State()
    """Ожидание ввода имени или ID пользователя для поиска"""
    
    waiting_for_user_action = State()
    """Ожидание выбора действия с пользователем"""
    
    waiting_for_unblock_reason = State()
    """Ожидание ввода причины разблокировки"""
    
    waiting_for_custom_limit_duration = State()
    """Ожидание ввода длительности индивидуального лимита"""
    
    # ===== НАСТРОЙКИ УВЕДОМЛЕНИЙ В ЧАТЕ =====
    waiting_for_chat_notification = State()
    """Ожидание настройки уведомлений в чате"""
    
    waiting_for_silent_mode = State()
    """Ожидание включения/выключения тихого режима"""
    
    waiting_for_pin_notifications = State()
    """Ожидание настройки закрепления уведомлений"""
    
    # ===== ИНТЕГРАЦИИ И API =====
    waiting_for_api_key = State()
    """Ожидание ввода API ключа для интеграций"""
    
    waiting_for_webhook_url = State()
    """Ожидание ввода URL вебхука"""
    
    waiting_for_integration_type = State()
    """Ожидание выбора типа интеграции"""
    
    # ===== СИСТЕМНЫЕ НАСТРОЙКИ =====
    waiting_for_system_language = State()
    """Ожидание выбора языка системы"""
    
    waiting_for_timezone = State()
    """Ожидание выбора часового пояса"""
    
    waiting_for_date_format = State()
    """Ожидание выбора формата даты"""
    
    # ===== ДИАГНОСТИКА И ОТЛАДКА =====
    waiting_for_debug_command = State()
    """Ожидание ввода отладочной команды"""
    
    waiting_for_log_level = State()
    """Ожидание выбора уровня логирования"""
    
    waiting_for_diagnostic_type = State()
    """Ожидание выбора типа диагностики"""
    
    # ===== МАССОВЫЕ ОПЕРАЦИИ =====
    waiting_for_bulk_action = State()
    """Ожидание выбора массового действия"""
    
    waiting_for_bulk_confirm = State()
    """Ожидание подтверждения массовой операции"""
    
    waiting_for_recipient_list = State()
    """Ожидание ввода списка получателей"""
    
    # ===== ШАБЛОНЫ И АВТОМАТИЗАЦИЯ =====
    waiting_for_template_name = State()
    """Ожидание ввода имени шаблона"""
    
    waiting_for_template_content = State()
    """Ожидание ввода содержимого шаблона"""
    
    waiting_for_automation_rule = State()
    """Ожидание настройки правила автоматизации"""
    
    # ===== ПЛАНИРОВЩИК ЗАДАЧ =====
    waiting_for_schedule_time = State()
    """Ожидание ввода времени выполнения задачи"""
    
    waiting_for_schedule_frequency = State()
    """Ожидание ввода частоты выполнения"""
    
    waiting_for_task_type = State()
    """Ожидание выбора типа задачи"""
    
    # ===== ОБУЧЕНИЕ И СПРАВКА =====
    waiting_for_tutorial_step = State()
    """Ожидание выбора шага обучения"""
    
    waiting_for_help_topic = State()
    """Ожидание выбора темы справки"""
    
    waiting_for_feedback = State()
    """Ожидание ввода отзыва или предложения"""
    waiting_for_chat_search = State()      # Поиск чатов
    waiting_for_user_search = State()


class UserStates(StatesGroup):
    """
    Состояния для обычных пользователей.
    Используются для взаимодействия пользователей с ботом.
    """
    
    waiting_for_support_message = State()
    """Ожидание ввода сообщения в поддержку"""
    
    waiting_for_feedback = State()
    """Ожидание ввода отзыва о боте"""
    
    waiting_for_report_reason = State()
    """Ожидание ввода причины жалобы"""
    
    waiting_for_purchase_confirm = State()
    """Ожидание подтверждения покупки дополнительных сообщений"""
    
    waiting_for_contact_request = State()
    """Ожидание ввода контактной информации"""
    
    waiting_for_settings_preference = State()
    """Ожидание выбора предпочтений настроек"""


class GroupStates(StatesGroup):
    """
    Состояния для групповых взаимодействий.
    Используются для обработки событий в группах и чатах.
    """
    waiting_for_user_search = State()
    """Ожидание ввода текста для поиска чатов"""

    waiting_for_chat_search = State()
    """Ожидание ввода имени или ID пользователя для поиска"""

    waiting_for_chat_confirmation = State()
    """Ожидание подтверждения добавления бота в чат"""
    
    waiting_for_admin_rights = State()
    """Ожидание предоставления прав администратора"""
    
    waiting_for_chat_rules_accept = State()
    """Ожидание принятия правил чата"""
    
    waiting_for_verification = State()
    """Ожидание верификации пользователя в чате"""
    
    waiting_for_chat_poll = State()
    """Ожидание создания опроса в чате"""
    
    waiting_for_chat_announcement = State()
    """Ожидание создания объявления в чате"""


class ModeratorStates(StatesGroup):
    """
    Состояния для модераторов чатов.
    Используются для управления чатами на уровне модерации.
    """
    
    waiting_for_warn_reason = State()
    """Ожидание ввода причины предупреждения"""
    
    waiting_for_mute_duration = State()
    """Ожидание ввода длительности мута"""
    
    waiting_for_ban_reason = State()
    """Ожидание ввода причины бана"""
    
    waiting_for_report_review = State()
    """Ожидание рассмотрения жалобы"""
    
    waiting_for_verification_request = State()
    """Ожидание обработки запроса на верификацию"""
    
    waiting_for_chat_cleanup = State()
    """Ожидание подтверждения очистки чата"""
    


class SystemStates(StatesGroup):
    """
    Системные состояния.
    Используются для внутренних операций бота.
    """
    
    maintenance_mode = State()
    """Режим технического обслуживания"""
    
    update_in_progress = State()
    """Выполняется обновление системы"""
    
    backup_in_progress = State()
    """Выполняется резервное копирование"""
    
    restore_in_progress = State()
    """Выполняется восстановление из резервной копии"""
    
    migration_in_progress = State()
    """Выполняется миграция данных"""
    
    diagnostics_in_progress = State()
    """Выполняется диагностика системы"""


# ===== КОМПОЗИЦИЯ ВСЕХ СОСТОЯНИЙ =====

class AllStates:
    """
    Контейнер для всех состояний бота.
    Позволяет легко получить доступ к любому состоянию.
    """
    
    admin = AdminStates
    user = UserStates
    group = GroupStates
    moderator = ModeratorStates
    system = SystemStates
    
    @classmethod
    def get_all_states(cls):
        """Возвращает список всех состояний"""
        all_states = []
        
        # Добавляем состояния из всех групп
        for group_name in ['admin', 'user', 'group', 'moderator', 'system']:
            group_class = getattr(cls, group_name)
            for state_name in dir(group_class):
                state = getattr(group_class, state_name)
                if isinstance(state, State):
                    all_states.append({
                        'group': group_name,
                        'name': state_name,
                        'state': state
                    })
        
        return all_states
    
    @classmethod
    def find_state_by_name(cls, state_name: str):
        """Находит состояние по имени во всех группах"""
        for group_name in ['admin', 'user', 'group', 'moderator', 'system']:
            group_class = getattr(cls, group_name)
            if hasattr(group_class, state_name):
                return getattr(group_class, state_name)
        return None
    
    @classmethod
    def clear_all_states(cls):
        """Создает новые экземпляры всех групп состояний (для сброса)"""
        cls.admin = AdminStates()
        cls.user = UserStates()
        cls.group = GroupStates()
        cls.moderator = ModeratorStates()
        cls.system = SystemStates()


# ===== УТИЛИТЫ ДЛЯ РАБОТЫ СО СОСТОЯНИЯМИ =====

def get_state_info(state):
    """
    Получает информацию о состоянии.
    
    Args:
        state: Объект состояния
        
    Returns:
        dict: Информация о состоянии
    """
    if not state:
        return None
    
    # Пытаемся найти состояние во всех группах
    for group_name in ['admin', 'user', 'group', 'moderator', 'system']:
        group_class = getattr(AllStates, group_name)
        for state_name in dir(group_class):
            if getattr(group_class, state_name) == state:
                return {
                    'group': group_name,
                    'name': state_name,
                    'description': get_state_description(group_name, state_name)
                }
    
    return None


def get_state_description(group_name: str, state_name: str) -> str:
    """
    Возвращает описание состояния на основе его имени.
    
    Args:
        group_name: Название группы состояний
        state_name: Название состояния
        
    Returns:
        str: Описание состояния
    """
    descriptions = {
        'admin': {
            'waiting_for_global_limit': 'Изменение глобального лимита сообщений',
            'waiting_for_chat_limit': 'Изменение лимита для конкретного чата',
            'waiting_for_user_limit': 'Настройка индивидуального лимита пользователя',
            'waiting_for_exception_word': 'Добавление слова в исключения или запрещенные слова',
            'waiting_for_notification_text': 'Изменение текста уведомления',
            'waiting_for_empty_notification': 'Настройка уведомления для пустых сообщений',
            'waiting_for_warning_notification': 'Настройка предупреждения',
            'waiting_for_limit_notification': 'Настройка уведомления при исчерпании лимита',
            'waiting_for_blocked_notification': 'Настройка уведомления для заблокированных',
            'waiting_for_contact_link': 'Изменение контактной ссылки',
            'waiting_for_min_length': 'Настройка минимальной длины сообщений',
            'waiting_for_test_text': 'Тестирование длины сообщений',
            'waiting_for_banned_word': 'Добавление запрещенного слова',
            'waiting_for_chat_min_length': 'Настройка минимальной длины для чата',
            'waiting_for_chat_banned_word': 'Добавление запрещенного слова для чата',
            'waiting_for_notification_delay': 'Настройка времени показа уведомлений',
            'waiting_for_empty_message_delay': 'Настройка задержки удаления пустых сообщений',
            'waiting_for_mute_duration': 'Настройка длительности мута',
        },
        'user': {
            'waiting_for_support_message': 'Обращение в поддержку',
            'waiting_for_feedback': 'Отзыв о боте',
            'waiting_for_report_reason': 'Жалоба на пользователя или контент',
        },
        'group': {
            'waiting_for_chat_confirmation': 'Подтверждение добавления в чат',
            'waiting_for_admin_rights': 'Предоставление прав администратора',
        },
        'moderator': {
            'waiting_for_warn_reason': 'Выдача предупреждения пользователю',
            'waiting_for_mute_duration': 'Настройка длительности мута',
        }
    }
    
    return descriptions.get(group_name, {}).get(state_name, 'Неизвестное состояние')


def is_admin_state(state) -> bool:
    """
    Проверяет, является ли состояние административным.
    
    Args:
        state: Объект состояния
        
    Returns:
        bool: True если состояние административное
    """
    state_info = get_state_info(state)
    return state_info and state_info['group'] == 'admin'


def is_user_state(state) -> bool:
    """
    Проверяет, является ли состояние пользовательским.
    
    Args:
        state: Объект состояния
        
    Returns:
        bool: True если состояние пользовательское
    """
    state_info = get_state_info(state)
    return state_info and state_info['group'] == 'user'


def is_group_state(state) -> bool:
    """
    Проверяет, является ли состояние групповым.
    
    Args:
        state: Объект состояния
        
    Returns:
        bool: True если состояние групповое
    """
    state_info = get_state_info(state)
    return state_info and state_info['group'] == 'group'


# ===== ЭКСПОРТ ОСНОВНЫХ КЛАССОВ =====

# Экспортируем основные классы состояний
__all__ = [
    'AdminStates',
    'UserStates', 
    'GroupStates',
    'ModeratorStates',
    'SystemStates',
    'AllStates',
    'get_state_info',
    'get_state_description',
    'is_admin_state',
    'is_user_state',
    'is_group_state'
]