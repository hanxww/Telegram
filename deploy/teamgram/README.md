# Teamgram Server for HaslGram — безопасная подготовка

**Готовность:** только подготовка **отдельной** копии сервера Teamgram и интеграция проверки кода. Не является готовым сервером или APK. Не запускайте оригинальные Docker Compose-файлы публично.

## Что уже сделано

* Выбрана и закреплена ревизия Teamgram Server: `8adf26bc071159c12a62c22ad49625a73e922e79`.
* `stage.sh` клонирует исходный Teamgram в новый каталог, не затрагивая работающий NestJS, PostgreSQL и Docker-тома HaslGram.
* `patch-auth.py` добавляет Go-провайдер `haslgram` для проверки **шестизначного кода** через существующий HaslGram API `POST /api/auth/registration/verify`. Код выпускает только @HaslGramRegBot после отправки собственного контакта; генератор Teamgram в ответ не отдаёт код.
* В `pkg/code/none` отключён небезопасный тестовый вход `12345`; в `auth.sendCode` убран обход бота через код от действующей сессии, тестовый номер или несуществующий SMS-провайдер.
* `preflight.sh` проверяет инфраструктуру и порты **без записи/рестарта**.

**Примечание:** текущий NestJS `verifyRegistration` поглощает код и начисляет бонус 2 000 Stars единожды. Он пока не сохраняет связь между Teamgram user ID и HaslGram wallet; интерфейс подарков пока не подключён. Для повторного входа нужен новый код от бота. Все сетевые маршруты MTProto Android до своего сервера также требуют изменения.

## Шаг 1. Скопировать в VPS только конфигурацию из GitHub

Выполняется на VPS. Не копируйте весь огромный Android-репозиторий; используйте разреженную рабочую копию.

```bash
cd /opt/haslgram
git clone --depth=1 --filter=blob:none --sparse --branch haslgram-teamgram \
  https://github.com/hanxww/Telegram.git haslgram-platform
cd haslgram-platform
git sparse-checkout set deploy/teamgram
bash deploy/teamgram/preflight.sh
```

Если директория `haslgram-platform` уже существует, не клонируйте поверх неё.

## Шаг 2. Подготовить Teamgram без запуска

```bash
cd /opt/haslgram/haslgram-platform
bash deploy/teamgram/stage.sh /opt/haslgram/teamgram-server
```

Команда не меняет текущий работающий backend и не открывает сетевые порты.

## Принцип регистрации

1. В официальном Telegram пользователь открывает @HaslGramRegBot и делится **своим** контактом.
2. Бот выдаёт шестизначный одноразовый код через существующий NestJS.
3. Teamgram `auth.sendCode` создаёт собственный сеансовый `phone_code_hash`, но **не** отправляет свой код.
4. `auth.signIn` передаёт телефон и код через Go-провайдер на внутренний NestJS endpoint.
5. NestJS атомарно проверяет и поглощает код. Только после успеха Teamgram допускает создание/вход в аккаунт.

Вход через бот будет возможен **после безопасного развёртывания**, настройки `HASLGRAM_REGISTRATION_VERIFY_URL` (например `http://api:3000/api/auth/registration/verify` внутри общей Docker-сети), подключения сервера к существующему API и проверки реальных аккаунтов. Пока код нельзя считать интеграционно протестированным.

## Необходимая безопасность до открытия портов

- Создать новую базу Teamgram (MySQL), не импортировать пользователей/чаты Telegram и не удалять старые данные HaslGram.
- Использовать отдельные Docker Compose project, network и тома; проверить, что DNS-сервиса `api` достигает только разрешённый Teamgram контейнер.
- **Не публиковать** MySQL, Redis, Kafka, etcd, MinIO, gRPC сервисы в интернет.
- Заменить стандартные пароли Teamgram в `.env` **и** в конфигурациях `teamgramd/etc2/*.yaml` (захардкоженные DSN/MinIO креды).
- Сгенерировать свой приватный MTProto RSA keypair и правильно сменить fingerprint в `gnetway.yaml` **и** Android-клиенте.
- Убрать все резервные IP дата-центров Telegram/Teamgram из Android.
- Проверить, что отсутствует обход через `auth.signUp`, `auth.resendCode`, `auth.importLoginToken` и любые старые test flows.
- Провести нагрузочные/безопасностные тесты OTP и идемпотентной выдачи 2 000 Stars.
- Зафиксировать критические зависимости и создать бэкапы/восстановление.

## Ограничение Community Teamgram

Даже после запуска сервер Community **не содержит полный Telegram**: каналы, супергруппы, звонки, боты, miniapp и многое другое относятся к Enterprise edition. Нужна лицензируемая редакция или собственная реализация. Заявленная полнота Telegram — требование к проекту, а не текущее свойство кода.

Источники: https://github.com/teamgram/teamgram-server , https://github.com/teamgram/teamgram-android/tree/teamgram2

**Не выполняйте `docker compose up` в скопированном upstream Teamgram. Это пока исходники для разработки, не безопасный production deployment.**
