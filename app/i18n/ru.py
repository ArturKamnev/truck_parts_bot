from __future__ import annotations

translations = {
    # Customer buttons
    "customer.ask_ai": "🤖 Задать вопрос",
    "customer.contact_manager": "👨‍💼 Связаться с менеджером",
    "customer.broadcasts_on": "🔔 Рассылки: включены",
    "customer.broadcasts_off": "🔕 Рассылки: выключены",
    "customer.cancel": "❌ Отмена",
    "customer.cancel_request": "❌ Отменить обращение",
    "customer.close_chat": "✅ Завершить диалог",
    
    # Manager buttons
    "manager.new_tickets": "📥 Новые обращения",
    "manager.active_chats": "💬 Мои активные диалоги",
    "manager.stats": "📊 Моя статистика",
    "manager.notifications_on": "🔔 Уведомления: включены",
    "manager.notifications_off": "🔕 Уведомления: выключены",
    "manager.close_ticket": "🔒 Закрыть вопрос",
    "manager.exit_reply": "⏸ Выйти из режима ответа",
    "manager.my_dialogs": "↩️ Мои диалоги",
    
    # Owner buttons
    "owner.choose_model": "🤖 Выбрать модель ИИ",
    "owner.stats": "📊 Статистика",
    "owner.tickets": "📂 Обращения",
    "owner.broadcast": "📨 Разослать",
    "owner.broadcast_history": "📋 История рассылок",
    "owner.managers": "👨‍💼 Менеджеры",
    "owner.promote_manager": "➕ Назначить менеджера",
    "owner.manager_stats": "📊 Статистика менеджеров",
    "owner.cancel": "❌ Отмена",
    "owner.back": "↩️ Назад",
    
    # Bot UI strings
    "bot.welcome": "Добро пожаловать в службу поддержки! Выберите интересующий вас раздел.",
    "bot.language_btn": "🌐 Язык / Language / Тил",
    "bot.choose_language": "Выберите язык / Choose language / Тилди тандаңыз:",
    "bot.language_switched": "Язык изменен на Русский 🇷🇺",
    "bot.open_miniapp": "💬 Открыть Mini App",
    
    # Ticket actions
    "ticket.cancel_confirm": "Подтвердите отмену обращения.",
    "ticket.close_confirm": "Подтвердите закрытие обращения.",
    "ticket.closed_by_customer": "Диалог завершен клиентом.",
    "ticket.closed_by_manager": "Обращение #{id} закрыто менеджером.",
    "ticket.closed_by_supervisor": "Обращение #{id} закрыто супервизором.",
    "ticket.claimed": "К вашему обращению #{id} подключился менеджер {name}.",
    "ticket.created": "Обращение #{id} создано. Пожалуйста, подождите ответа менеджера.",
    "ticket.no_active": "У вас нет активных обращений.",
    "ticket.already_active": "У вас уже есть активное обращение.",
    "ticket.open_dialog": "💬 Открыть диалог",
    "ticket.history": "👁 История",
    "ticket.claim": "✅ Взять в работу",
    "ticket.open_id": "💬 Открыть #{id}",
    "ticket.close_yes": "Да, закрыть",
    
    # AI Messages
    "ai.thinking": "⏳ Думаю...",
    "ai.warn_unverified": "⚠️ Ответ сгенерирован ИИ-ассистентом и может быть неточным.",
    
    # Broadcast Flow
    "broadcast.enter_content": "Пожалуйста, отправьте сообщение, которое вы хотите разослать. Поддерживаются фото, видео и текст.",
    "broadcast.choosing_buttons": "Выберите кнопки для рассылки:",
    "broadcast.preview": "Предпросмотр рассылки:",
    "broadcast.confirm": "Подтвердите запуск рассылки на {count} пользователей.",
    "broadcast.sending": "Рассылка запущена. Это может занять некоторое время...",
    "broadcast.completed": "Рассылка #{id} завершена!\nУспешно доставлено: {delivered}\nОшибок: {failed}\nЗаблокировано: {blocked}",
    "broadcast.cancelled": "Рассылка отменена.",
    "broadcast.no_buttons": "Без кнопок",
    "broadcast.site": "Официальный сайт",
    "broadcast.both_buttons": "Instagram + сайт",
    "broadcast.test_me": "🧪 Отправить тест мне",
    "broadcast.send_all": "✅ Отправить всем",
    "broadcast.restart": "✏️ Создать заново",
    "broadcast.confirm_send": "✅ Подтверждаю отправку",
    "broadcast.open_report": "Открыть отчёт",
    
    # Broadcast formatting specific keys
    "broadcast.recipients": "Получателей",
    "broadcast.message_preview": "Сообщение",
    "broadcast.buttons": "Кнопки",
    "broadcast.confirm_title": "Подтвердите массовую отправку.",
    "broadcast.confirm_footer": "После подтверждения сообщение будет отправлено клиентам.",

    # Owner specific UI labels
    "owner.disable_manager": "❌ Деактивировать",
    "owner.enable_manager": "✅ Активировать",
    "owner.disable_manager_confirm": "Да, деактивировать",
    "owner.promote_confirm": "Да, назначить",
    "owner.model_selection": "Выберите модель AI\nАктивная модель: {model}",
    "owner.normal_panel": "Панель владельца\nАктивная модель: {model}",
    
    # Menu flow screens
    "manager.main_menu": "Панель менеджера открыта. Выберите действие.",
    "customer.requesting": "Опишите ваш вопрос одним сообщением или приложите фото, видео или документ. Менеджер увидит ваше обращение.",
    "customer.waiting": "У вас уже есть открытое обращение. Ожидаем свободного менеджера. Вы можете отправить дополнительные сообщения или файлы.",
    "customer.chatting": "Менеджер уже подключен. Напишите сообщение в этот чат.",
    "customer.ai_chat_welcome": "Здравствуйте! Я AI-ассистент компании. Напишите вопрос или выберите действие.",
    
    # Common strings
    "common.error": "Произошла ошибка.",
    "common.back": "Назад",
    "common.cancel": "Отмена",
    "common.yes": "Да",
    "common.no": "Нет",
    "common.saved": "Сохранено.",
    "common.additional_options": "Дополнительные опции:",
    
    # Ticket chat view text
    "ticket.chat_text": "Вы отвечаете клиенту по обращению #{id}. Все отправленные сейчас сообщения и файлы будут переданы этому клиенту.\n\nКлиент: {client}\nСтатус: {status}\n\nПоследние сообщения:\n{history}",
    "ticket.chat_empty": "История обращения пока пуста.",
    "ticket.status_claimed": "В работе",
    "ticket.status_open": "Открыто",

    # Inline Keyboards
    "inline.cancel_yes": "Да, отменить",
    "inline.cancel_no": "Нет",
    "inline.claim_ticket": "✅ Взять в работу",
    "inline.history": "👁 История",
    "inline.close_question": "🔒 Закрыть вопрос",
    "inline.exit_reply": "⏸ Выйти из режима ответа",
    "inline.my_dialogs": "↩️ Мои диалоги",
    "inline.open_dialog": "💬 Открыть диалог",
    "inline.turn_off_notify": "Выключить уведомления",
    "inline.turn_on_notify": "Включить уведомления",
    "inline.go_back": "⬅️ Назад",
    "inline.open_ticket_id": "💬 Открыть #{id}",
    "inline.no_buttons": "Без кнопок",
    "inline.official_site": "Официальный сайт",
    "inline.both_buttons": "Instagram + сайт",
    "inline.send_test_me": "🧪 Отправить тест мне",
    "inline.send_all": "✅ Отправить всем",
    "inline.create_new": "✏️ Создать заново",
    "inline.confirm_send": "✅ Подтверждаю отправку",
    "inline.open_report": "Открыть отчёт",
    "inline.disable_manager": "❌ Деактивировать",
    "inline.enable_manager": "✅ Активировать",
    "inline.disable_manager_confirm": "Да, деактивировать",
    "inline.promote_confirm": "Да, назначить",
}
