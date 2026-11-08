# Teamgram Server for HaslGram — безопасная подготовка

**Готовность:** только подготовка **отдельной** копии сервера Teamgram и интеграция проверки кода. Не является готовым сервером или APK. Не запускайте оригинальные Docker Compose-файлы публично.

## Что уже сделано

* Выбрана и закреплена ревизия Teamgram Server: `8adf26bc071159c12a62c22ad49625a73e922e79`.
* `stage.sh` клонирует исходный Teamgram в новый каталог, не затрагивая работающий NestJS, PostgreSQL и Docker-тома HaslGram.
* `patch-auth.py` добавляет Go-провайдер `haslgram` для проверки **шестизначного кода** через существующий HaslGram API `POST /api/auth/registration/verify`. Код выпускает только @HaslGramRegBot после отправки собственного контакта; генератор Teamgram в ответ не отдаёт код.
* В `pkg/code/none` отключён небезопасный тестовый вход `12345`; в `auth.sendCode` убран обход бота через код от действующей сессии, тестовый номер или несуществующий SMS-провайдер.
* `preflight.sh` проверяет инфраструктуру и порты **без записи/рестарта**.

**Зависимость от backend (пока не проверена):** endpoint регистрации NestJS должен атомарно поглощать код бота и начислять приветственный бонус 2 000 Hasl Stars ровно один раз. Исходники NestJS не были доступны в этом репозитории, поэтому фактическая работа endpoint и связь Teamgram user ID с HaslGram wallet здесь не проверены и не изменялись. Интерфейс подарков ещё не подключён к ledger HaslGram. Для повторного входа потребуется новый код от бота.

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


## Required runtime environment

The BFF container must receive these values from a private .env/secret store before it starts:

~~~dotenv
HASLGRAM_API_ID=<your my.telegram.org api_id>
HASLGRAM_API_HASH=<your my.telegram.org api_hash>
HASLGRAM_REGISTRATION_VERIFY_URL=http://api:3000/api/auth/registration/verify
HASLGRAM_REGISTRATION_PHONE_FIELD=phoneE164
HASLGRAM_REGISTRATION_SUCCESS_FIELD=success
# Optional if the NestJS endpoint requires a service-to-service bearer token:
HASLGRAM_REGISTRATION_VERIFY_TOKEN=<private service token>
~~~

The URL and body field above are integration defaults, not proof of the current NestJS controller contract. Verify the real route and DTO in the existing gift-engine backend before starting BFF. Set HASLGRAM_REGISTRATION_PHONE_FIELD=phoneNumber if that is the DTO field. Set HASLGRAM_REGISTRATION_SUCCESS_FIELD to the boolean response field returned by the controller (success, valid, verified, or ok). The adapter fails closed unless that field is true. For public endpoints use HTTPS; plain HTTP is accepted only for the named private Docker services in the adapter. The API hash is not written into Git or server logs.

Teamgram's login screen reports a six-digit code length, but the code itself is issued by @HaslGramRegBot; the internal Teamgram random value is never accepted. auth.resendCode is deliberately disabled so a client cannot obtain an alternate code through the old SMS path. Ask the bot for a fresh code instead.

## Android application credentials and network routing

The HaslGram Android build reads these from ignored local.properties or environment variables:

~~~properties
HASLGRAM_API_ID=123456
HASLGRAM_API_HASH=0123456789abcdef0123456789abcdef
HASLGRAM_MTPROTO_HOST=mtproto.your-domain.example
HASLGRAM_MTPROTO_PORT=10443
~~~

The values above are examples only. The API ID/hash must match the BFF container values. The native client now has one MTProto datacenter, pointing only to the configured HaslGram gateway; it no longer contains Telegram production/test DC fallbacks. The default host is loopback for safe local builds and is not suitable for a public device.

Push notifications remain disabled until a separate HaslGram Firebase project and matching google-services.json files are configured. The official Telegram Firebase project files have been removed from this branch. A debug APK is a test artifact, not a production release.
