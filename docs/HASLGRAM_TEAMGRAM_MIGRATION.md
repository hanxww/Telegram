# HaslGram × Teamgram — план интеграции

**Статус:** архитектура согласована; интеграция и APK **не выполнены**. Эта ветка не заменяет рабочую сборку Telegram на `master`.

## Что берём из Teamgram

- Android-клиент: https://github.com/teamgram/teamgram-android (ветки `teamgram`, `teamgram2`).
- Сервер: https://github.com/teamgram/teamgram-server — отдельная реализация **MTProto 2.0** на Go.
- Пользователи, диалоги, личные сообщения, контакты и базовые группы — зона Teamgram Server.

## Что сохраняем из существующего HaslGram

- NestJS API, PostgreSQL, Redis и уже работающего Telegram-бота @HaslGramRegBot.
- Начисления Hasl Stars, кошелёк, покупки, улучшения и владение подарками.
- Код подтверждения, выдаваемый ботом, должен проверяться сервером при **реальном** MTProto-входе.
- База данных PostgreSQL и данные о подарках сохраняются без удаления или миграции «наугад».

## Схема работы

```text
HaslGram Android (fork Teamgram Android)
    |--- MTProto/TCP ---> Teamgram gnetway ---> Teamgram user/chat/message services
    |--- HTTPS/JWT ----> HaslGram NestJS API --> PostgreSQL (Stars/gifts/wallet)
                               ^
                               | authenticated internal verification
Teamgram auth.sendCode/signIn --+
                               |
Telegram @HaslGramRegBot ---> HaslGram registration code service
```

Должна быть **одна авторизованная личность**: Teamgram user ID однозначно связывается
с HaslGram user ID после проверки одноразового кода, а не по номеру, присланному клиентом.
Нельзя считать независимый JWT HaslGram доказательством успешной MTProto-аутентификации
без серверной проверки и привязки сессии.

## Критически важные ограничения

1. Наш существующий NestJS API — REST; он **не** является MTProto-сервером.
   В Teamgram-клиенте недостаточно заменить HTTP URL. Требуется развернуть
   `teamgram-server` с отдельными MySQL, Redis, etcd, Kafka, MinIO, FFmpeg
   (или обоснованно переиспользовать изолированные сервисы).
2. Патч адреса Teamgram-клиента документирован в
   https://github.com/teamgram/teamgram-server/blob/master/clients/teamgram-android.md.
   Код `TMessagesProj/jni/tgnet/ConnectionsManager.cpp` в `teamgram2`
   содержит вшитые адреса **чужого Teamgram test server** и адреса
   официальных дата-центров Telegram. Перед выпуском убрать все нежелательные
   запасные маршруты и проверить, куда идут соединения.
3. **Никогда** не использовать тестовый код `12345` из примера Teamgram в продукте.
   Реализовать проверку одноразового кода с TTL, лимитами попыток, защитой от
   перебора и строго проверяемой привязкой телефона к Telegram ID.
4. Community-версия Teamgram не обещает весь функционал Telegram:
   каналы, звонки, встроенные боты, пуши и др. указаны как enterprise-функции.
   Наш `@HaslGramRegBot` — отдельный бот в **официальном** Telegram;
   он не требует внутренней подсистемы ботов Teamgram.
5. Teamgram Android — GPL-2.0; изменения клиента распространяются с исходниками
   согласно лицензии. Teamgram Server — Apache-2.0.
   Не выпускать APK с чужими ключами подписи, именем и логотипом Telegram.
6. Не развертывать Teamgram поверх работающего `haslgram-gift-engine`:
   отдельный каталог, отдельный Docker Compose project, volumes, секреты и backup.
7. Для Android API подарков нужен публичный HTTPS endpoint. MTProto-порт
   отдельно от HTTPS API; шифрование и сертификаты обязательны для API.

## Последовательность работ

- [x] Проверены репозитории Teamgram и актуальная архитектура.
- [x] Изолирована ветка `haslgram-teamgram` в `hanxww/Telegram`.
- [ ] Проверить RAM/CPU/disk на VPS; снять резервные копии, подтвердить свободные порты.
- [ ] Развернуть Teamgram в отдельном окружении; проверить локальную MTProto-авторизацию
      с **исключённым** тестовым кодом `12345`.
- [ ] Перенести/адаптировать Teamgram Android в отдельную сборку, заменить все DC
      на HaslGram, обновить `applicationId`, брендинг и ключи подписи.
- [ ] Интегрировать `auth.sendCode` и `auth.signIn` с проверкой одноразового кода
      HaslGram. Добавить двустороннюю привязку идентификаторов пользователей.
- [ ] Добавить UI подарков и Stars к Teamgram Android, вызывающий существующий API.
- [ ] Проверить авторизацию двух реальных пользователей, текстовые сообщения в обе
      стороны, перезапуск/синхронизацию, кошелёк и покупки подарков.
- [ ] Проверить безопасность трафика, зависимости, права, нагрузки, подпись APK;
      затем создать workflow и финальную сборку.

## Полезные ссылки

- https://github.com/teamgram/teamgram-server
- https://github.com/teamgram/teamgram-android/tree/teamgram2
- https://github.com/teamgram/teamgram-server/blob/master/specs/architecture.md
- https://github.com/teamgram/teamgram-server/blob/master/specs/roadmap.md
- https://github.com/teamgram/teamgram-server/blob/master/clients/teamgram-android.md

**Внимание:** создание этой ветки и документа **не означает**, что Teamgram Server
уже запущен на VPS или что существует готовый HaslGram APK.
