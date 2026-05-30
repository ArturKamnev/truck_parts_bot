from __future__ import annotations

translations = {
    # Customer buttons
    "customer.ask_ai": "🤖 Суроо берүү",
    "customer.contact_manager": "👨‍💼 Менеджер менен байланышуу",
    "customer.broadcasts_on": "🔔 Билдирүүлөр: күйгүзүлгөн",
    "customer.broadcasts_off": "🔕 Билдирүүлөр: өчүрүлгөн",
    "customer.cancel": "❌ Жокко чыгаруу",
    "customer.cancel_request": "❌ Кайрылууну жокко чыгаруу",
    "customer.close_chat": "✅ Диалогду аяктоо",
    
    # Manager buttons
    "manager.new_tickets": "📥 Жаңы кайрылуулар",
    "manager.active_chats": "💬 Активдүү диалогдорум",
    "manager.stats": "📊 Менин статистикам",
    "manager.notifications_on": "🔔 Билдирүүлөр: күйгүзүлгөн",
    "manager.notifications_off": "🔕 Билдирүүлөр: өчүрүлгөн",
    "manager.close_ticket": "🔒 Суроону жабуу",
    "manager.exit_reply": "⏸ Жооп берүүдөн чыгуу",
    "manager.my_dialogs": "↩️ Менин диалогдорум",
    
    # Owner buttons
    "owner.choose_model": "🤖 ИИ моделин тандоо",
    "owner.stats": "📊 Статистика",
    "owner.tickets": "📂 Кайрылуулар",
    "owner.broadcast": "📨 Кабар жөнөтүү",
    "owner.broadcast_history": "📋 Кабарлардын тарыхы",
    "owner.managers": "👨‍💼 Менеджерлер",
    "owner.promote_manager": "➕ Менеджер дайындоо",
    "owner.manager_stats": "📊 Менеджерлердин статистикасы",
    "owner.cancel": "❌ Жокко чыгаруу",
    "owner.back": "↩️ Артка",
    
    # Bot UI strings
    "bot.welcome": "Колдоо кызматына кош келиңиз! Төмөнкү бөлүмдөрдүн бирин тандаңыз.",
    "bot.language_btn": "🌐 Тил / Language / Язык",
    "bot.choose_language": "Тилди тандаңыз / Choose language / Выберите язык:",
    "bot.language_switched": "Тил Кыргызчага өзгөртүлдү 🇰🇬",
    "bot.open_miniapp": "💬 Mini App'ти ачуу",
    
    # Ticket actions
    "ticket.cancel_confirm": "Кайрылууну жокко чыгарууну ырастаңыз.",
    "ticket.close_confirm": "Кайрылууну жабууну ырастаңыз.",
    "ticket.closed_by_customer": "Диалог кардар тарабынан аяктады.",
    "ticket.closed_by_manager": "Кайрылуу #{id} менеджер тарабынан жабылды.",
    "ticket.closed_by_supervisor": "Кайрылуу #{id} супервизор тарабынан жабылды.",
    "ticket.claimed": "Кайрылууңузга #{id} менеджер {name} кошулду.",
    "ticket.created": "Кайрылуу #{id} түзүлдү. Сураныч, менеджердин жообун күтүңүз.",
    "ticket.no_active": "Сизде активдүү кайрылуулар жок.",
    "ticket.already_active": "Сизде активдүү кайрылуу бар.",
    "ticket.open_dialog": "💬 Диалогду ачуу",
    "ticket.history": "👁 Тарыхы",
    "ticket.claim": "✅ Жумушка алуу",
    "ticket.open_id": "💬 #{id} ачуу",
    "ticket.close_yes": "Ооба, жабуу",
    
    # AI Messages
    "ai.thinking": "⏳ Ойлонуп жатам...",
    "ai.warn_unverified": "⚠️ Жооп ИИ-ассистент тарабынан даярдалды жана так эмес болушу мүмкүн.",
    
    # Broadcast Flow
    "broadcast.enter_content": "Сураныч, жөнөтө турган билдирүүнү жөнөтүңүз. Сүрөт, видео жана текст колдоого алынат.",
    "broadcast.choosing_buttons": "Кабар үчүн баскычтарды тандаңыз:",
    "broadcast.preview": "Кабардын алдын ала көрүнүшү:",
    "broadcast.confirm": "Кабарды {count} колдонуучуга жөнөтүүнү ырастаңыз.",
    "broadcast.sending": "Жөнөтүү башталды. Бул бир аз убакытты алышы мүмкүн...",
    "broadcast.completed": "Кабар жөнөтүү #{id} аяктады!\nИйгиликтүү жеткирилди: {delivered}\nКаталар: {failed}\nБөгөттөлдү: {blocked}",
    "broadcast.cancelled": "Кабар жөнөтүү жокко чыгарылды.",
    
    # Broadcast formatting specific keys
    "broadcast.recipients": "Алуучулар",
    "broadcast.message_preview": "Билдирүү",
    "broadcast.buttons": "Баскычтар",
    "broadcast.confirm_title": "Жапырт билдирүү жөнөтүүнү ырастаңыз.",
    "broadcast.confirm_footer": "Ырасталгандан кийин билдирүү кардарларга жөнөтүлөт.",

    # Owner specific UI labels
    "owner.model_selection": "ИИ моделин тандаңыз\nАктивдүү модель: {model}",
    "owner.normal_panel": "Ээсинин панели\nАктивдүү модель: {model}",
    
    # Menu flow screens
    "manager.main_menu": "Менеджер панели ачык. Аракетти тандаңыз.",
    "customer.requesting": "Сурооңузду бир билдирүү менен жазыңыз же сүрөт, видео же документ тиркеңиз. Менеджер сиздин кайрылууңузду көрөт.",
    "customer.waiting": "Сизде активдүү кайрылуу бар. Бош менеджерди күтүп жатабыз. Сиз кошумча билдирүүлөрдү же файлдарды жөнөтө аласыз.",
    "customer.chatting": "Менеджер кошулду. Бул чатка билдирүү жазыңыз.",
    "customer.ai_chat_welcome": "Саламатсызбы! Мен компаниянын ИИ-ассистентимин. Суроо жазыңыз же аракетти тандаңыз.",
    
    # Common strings
    "common.error": "Ката кетти.",
    "common.back": "Артка",
    "common.cancel": "Жокко чыгаруу",
    "common.yes": "Ооба",
    "common.no": "Жок",
    "common.saved": "Сакталды.",
    "common.additional_options": "Кошумча параметрлер:",
    
    # Ticket chat view text
    "ticket.chat_text": "Сиз кардарга #{id} кайрылуусу боюнча жооп берип жатасыз. Азыр жөнөтүлгөн бардык билдирүүлөр жана файлдар ушул кардарга берилет.\n\nКардар: {client}\nСтатус: {status}\n\nАкыркы билдирүүлөр:\n{history}",
    "ticket.chat_empty": "Кайрылуунун тарыхы бош.",
    "ticket.status_claimed": "Жумушта",
    "ticket.status_open": "Ачык",

    # Inline Keyboards
    "inline.cancel_yes": "Ооба, жокко чыгаруу",
    "inline.cancel_no": "Жок",
    "inline.claim_ticket": "✅ Жумушка алуу",
    "inline.history": "👁 Тарыхы",
    "inline.close_question": "🔒 Суроону жабуу",
    "inline.exit_reply": "⏸ Жооп берүүдөн чыгуу",
    "inline.my_dialogs": "↩️ Менин диалогдорум",
    "inline.open_dialog": "💬 Диалогду ачуу",
    "inline.turn_off_notify": "Билдирүүлөрдү өчүрүү",
    "inline.turn_on_notify": "Билдирүүлөрдү күйгүзүү",
    "inline.go_back": "⬅️ Артка",
    "inline.open_ticket_id": "💬 #{id} ачуу",
    "inline.no_buttons": "Баскычтарсыз",
    "inline.official_site": "Расмий сайт",
    "inline.both_buttons": "Instagram + сайт",
    "inline.send_test_me": "🧪 Тестти мага жөнөтүү",
    "inline.send_all": "✅ Баарына жөнөтүү",
    "inline.create_new": "✏️ Кайра түзүү",
    "inline.confirm_send": "✅ Жөнөтүүнү ырастайм",
    "inline.open_report": "Отчетту ачуу",
    "inline.disable_manager": "❌ Деактивациялоо",
    "inline.enable_manager": "✅ Активдештирүү",
    "inline.disable_manager_confirm": "Ооба, деактивациялоо",
    "inline.promote_confirm": "Ооба, дайындоо",
}
