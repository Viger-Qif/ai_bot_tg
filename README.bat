# 🧠 Прогрессор — AI-навигатор обучения

## Быстрый старт

### Требования
- Python 3.9+
- pip

### Установка

```bash
# 1. Установить зависимости
cd backend
pip install -r requirements.txt

# 2. Запустить бэкенд
python app.py

# 3. В другом терминале — фронтенд
cd progressor
python -m http.server 8000

progressor/
├── index.html
├── css/styles.css
├── js/ (app.js, chat.js, roadmap.js, leaderboard.js)
├── pages/ (chat.html, roadmap.html, leaderboard.html)
├── public/ (manifest.json, service-worker.js)
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── requirements.txt
│   ├── services/ (llm, interview, roadmap, test, gamification, leaderboard, analytics)
│   ├── cleaned_courses.csv
│   └── hh_super_puper_update(1).csv
├── start.bat (для Windows)
└── README.md

Деплой на сервер
Вариант 1: Простой (VPS)

bash
# На сервере
git clone <repo>
cd progressor/backend
pip install -r requirements.txt

# Запустить в screen/tmux
screen -S progressor
python app.py
# Ctrl+A, D — отсоединиться

# Для фронтенда — использовать nginx

Вариант 2: С nginx (продакшн)

server {
    listen 80;
    server_name your-domain.com;

    # Фронтенд
    location / {
        root /path/to/progressor;
        index index.html;
    }

    # Бэкенд
    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}


server {
    listen 80;
    server_name your-domain.com;

    # Фронтенд
    location / {
        root /path/to/progressor;
        index index.html;
    }

    # Бэкенд
    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}



Переменные окружения (опционально)
Создайте .env в папке backend/:

OPENROUTER_API_KEY=sk-or-v1-...
FLASK_ENV=production
SECRET_KEY=your-secret-key



---

## 🎯 ШАГ 7: Финальный тест

Запусти всё и проверь по чек-листу:

```powershell
# Терминал 1: Бэкенд
cd C:\Users\Dmitry\Downloads\hahaon\progressor\backend
python app.py

# Терминал 2: Фронтенд
cd C:\Users\Dmitry\Downloads\hahaon\progressor
python -m http.server 8000



# 🚀 Инструкция для Димы: Деплой на сервер

## 📋 Что у нас есть:
- **Flask бэкенд** (Python) на порту 5000
- **Статический фронтенд** (HTML/CSS/JS)
- **Арендованный домен** (например, `progressor.com`)
- **Telegram Mini App** → нужен **HTTPS** обязательно!

---

## 🛠 Что Диме нужно сделать (пошагово)

### 1️⃣ Подключиться к серверу

```bash
ssh root@IP_СЕРВЕРА
# или
ssh user@IP_СЕРВЕРА
```

---

### 2️⃣ Установить всё необходимое

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить Python и зависимости
sudo apt install -y python3 python3-pip python3-venv nginx git

# Установить Certbot для SSL
sudo apt install -y certbot python3-certbot-nginx
```

---

### 3️⃣ Склонировать проект

```bash
# Перейти в нужную папку
cd /var/www

# Склонировать репозиторий (или залить через SCP/SFTP)
git clone https://github.com/ваш-репо/progressor.git
cd progressor
```

**Если нет Git репозитория** — залить файлы через SFTP (FileZilla, WinSCP):
```
/var/www/progressor/
├── index.html
├── css/
├── js/
├── pages/
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── requirements.txt
│   └── services/
└── ...
```

---

### 4️⃣ Настроить Python окружение

```bash
cd /var/www/progressor/backend

# Создать виртуальное окружение
python3 -m venv venv

# Активировать
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Установить gunicorn для продакшена
pip install gunicorn
```

---

### 5️⃣ Создать `.env` файл с секретами

```bash
nano /var/www/progressor/backend/.env
```

Вставить:
```env
FLASK_ENV=production
SECRET_KEY=сгенерируй-случайный-ключ-32-символа
OPENROUTER_API_KEY=sk-or-v1-ваш-ключ
TELEGRAM_BOT_TOKEN=ваш-токен-если-есть
DEBUG=False
```

Сгенерировать SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

### 6️⃣ Настроить Systemd Service (автозапуск)

```bash
sudo nano /etc/systemd/system/progressor.service
```

Вставить:
```ini
[Unit]
Description=Progressor Backend
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/progressor/backend
Environment="PATH=/var/www/progressor/backend/venv/bin"
EnvironmentFile=/var/www/progressor/backend/.env
ExecStart=/var/www/progressor/backend/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Запустить:
```bash
# Создать папку для сессий с правами
sudo mkdir -p /var/www/progressor/backend/sessions
sudo chown -R www-data:www-data /var/www/progressor

# Включить и запустить сервис
sudo systemctl daemon-reload
sudo systemctl enable progressor
sudo systemctl start progressor

# Проверить статус
sudo systemctl status progressor
```

---

### 7️⃣ Настроить Nginx

```bash
sudo nano /etc/nginx/sites-available/progressor
```

Вставить (заменив `progressor.com` на ваш домен):
```nginx
server {
    listen 80;
    server_name progressor.com www.progressor.com;

    # Фронтенд (статические файлы)
    location / {
        root /var/www/progressor;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API (бэкенд)
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Для Telegram WebApp
        proxy_set_header X-Session-Id $http_x_session_id;
    }

    # Кэширование статики
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        root /var/www/progressor;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

Активировать:
```bash
# Создать симлинк
sudo ln -s /etc/nginx/sites-available/progressor /etc/nginx/sites-enabled/

# Удалить дефолтный сайт
sudo rm /etc/nginx/sites-enabled/default

# Проверить конфиг
sudo nginx -t

# Перезапустить nginx
sudo systemctl restart nginx
```

---

### 8️⃣ Получить SSL сертификат (HTTPS)

**Это ОБЯЗАТЕЛЬНО для Telegram Mini App!**

```bash
# Убедиться что DNS домена указывает на IP сервера
# Проверить: ping progressor.com

# Получить сертификат
sudo certbot --nginx -d progressor.com -d www.progressor.com

# Следовать инструкциям (ввести email, согласиться с условиями)
```

Certbot автоматически обновит конфиг Nginx и настроит автопродление.

---

### 9️⃣ Настроить Firewall (если включен)

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

---

### 🔟 Проверить работу

```bash
# Проверить что бэкенд запущен
curl http://127.0.0.1:5000/api/health

# Проверить логи
sudo journalctl -u progressor -f

# Проверить nginx
sudo tail -f /var/log/nginx/error.log
```

Открыть в браузере: `https://progressor.com`

---

## 🔧 Настройка Telegram Mini App

В **BotFather** указать:
```
/newapp → выбрать бота → указать URL: https://progressor.com
```

---

## 📁 Итоговая структура на сервере

```
/var/www/progressor/
├── index.html              # Главная страница
├── css/styles.css
├── js/
├── pages/
├── backend/
│   ├── venv/               # Виртуальное окружение
│   ├── .env                # Секреты
│   ├── app.py
│   ├── models.py
│   ├── requirements.txt
│   ├── sessions/           # Сессии пользователей
│   ├── cleaned_courses.csv
│   ├── hh_super_puper_update(1).csv
│   └── services/
└── ...
```

---

## ⚠️ Что может пойти не так

| Проблема | Решение |
|----------|---------|
| `ModuleNotFoundError` | Не активирован venv или не установлены зависимости |
| `Permission denied` | `sudo chown -R www-data:www-data /var/www/progressor` |
| `502 Bad Gateway` | Бэкенд не запущен: `sudo systemctl status progressor` |
| `404 Not Found` | Проверить `root` в конфиге Nginx |
| SSL ошибка | DNS не указывает на сервер или certbot не прошёл |
| Бот не открывает WebApp | Нужен HTTPS, проверить URL в BotFather |

---

## 🚀 Быстрый чек-лист для Димы

```bash
# 1. Подключиться к серверу
ssh root@IP

# 2. Установить всё
sudo apt update && sudo apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx

# 3. Залить проект
cd /var/www && git clone ... (или залить через SFTP)

# 4. Настроить Python
cd progressor/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt gunicorn

# 5. Создать .env
nano .env  # Вставить ключи

# 6. Настроить systemd
sudo nano /etc/systemd/system/progressor.service
sudo systemctl daemon-reload && sudo systemctl enable progressor && sudo systemctl start progressor

# 7. Настроить Nginx
sudo nano /etc/nginx/sites-available/progressor
sudo ln -s /etc/nginx/sites-available/progressor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# 8. Получить SSL
sudo certbot --nginx -d ваш-домен.com

# 9. Проверить
curl http://127.0.0.1:5000/api/health
```

---

## 📞 Если что-то сломается

Дима может:
1. Посмотреть логи: `sudo journalctl -u progressor -f`
2. Перезапустить: `sudo systemctl restart progressor`
3. Проверить статус: `sudo systemctl status progressor`

**Весь процесс займёт 30-60 минут** если всё идёт гладко. У Димы всё получится! 💪