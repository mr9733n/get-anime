Примечание: Это приложение предназначено для личного использования и не должно использоваться для нарушения авторских прав или других законов.

# AnimePlayerApp
AnimePlayerApp - это приложение на основе Qt, предназначенное для просмотра и управления аниме контентом. Создает локальную базу данных для хранения ссылок и постеров, позволяет пользователям просматривать расписание аниме, искать аниме по названию, просматривать детальную информацию о выбранном аниме, сохранять плейлисты и воспроизводить их через встроенный проигрыватель, либо через VLC Media Player.

AnimePlayerAppLite - это приложение на основе Tkinter, предназначенное для просмотра и управления аниме контентом. Оно позволяет пользователям просматривать расписание аниме, искать аниме по названию, просматривать детальную информацию о выбранном аниме, сохранять плейлисты и воспроизводить их через VLC Media Player.

## Особенности
- Просмотр расписания аниме на разные дни недели.
- Поиск аниме по названию.
- Отображение подробной информации о выбранном аниме, включая описание, статус, жанры и год выпуска.
- Возможность просмотра постеров аниме.
- Сохранение плейлистов с сериями аниме.
- Воспроизведение плейлистов через VLC Media Player.
- Выбор качества просмотра (FHD, HD, SD).

## Настройка и использование
Установка зависимостей:
Перед запуском приложения убедитесь, что у вас установлен Python 3 и VLC Player. Также вам потребуется установить необходимые зависимости:
Установите необходимые библиотеки, используя pip:

```bash
pip install -r requirements.txt
```
## Конфигурация:
Настройте файл config.ini с соответствующими параметрами, включая URL API, путь к VLC Media Player и другие настройки.

## Запуск приложения:
Запустите приложение, выполнив скрипт Python:

```bash
python main.py
```

## Получение текущего списка тайтлов с сайта:
```bash
cd midnight
python scrapper.py
```

## Сравнить полученный список тайтлов с локальной базой данных:
```bash
cd midnight
python compare_titles.py
```

## Собрать приложение
```bash
pyinstaller build.spec --noconfirm
```

## Создать архив скомпилированных production версий
```bash
cd midnight
python create_archive.py
```

## Использование приложения:

Используйте кнопки дней недели для просмотра расписания аниме.

Введите название аниме в поле поиска и нажмите "Отобразить информацию", чтобы получить детали.

Используйте кнопку "Random", чтобы получить случайное аниме.

Сохраняйте и воспроизводите плейлисты с помощью соответствующих кнопок.

## Логирование:
Приложение ведет журнал своей работы, сохраняя логи в папке logs. Это может помочь в диагностике проблем или отслеживании активности приложения.
