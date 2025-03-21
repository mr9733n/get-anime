Примечание: Это приложение предназначено для личного использования и не должно использоваться для нарушения авторских прав или других законов.

# AnimePlayerApp
AnimePlayerApp - это приложение на основе Qt, предназначенное для просмотра и управления аниме контентом. Создает локальную базу данных для хранения ссылок и постеров, позволяет пользователям просматривать расписание аниме, искать аниме по названию, просматривать детальную информацию о выбранном аниме, сохранять плейлисты и воспроизводить их через встроенный проигрыватель, либо через VLC Media Player.

AnimePlayerAppLite - это приложение на основе Tkinter, предназначенное для просмотра и управления аниме контентом. Оно позволяет пользователям просматривать расписание аниме, искать аниме по названию, просматривать детальную информацию о выбранном аниме, сохранять плейлисты и воспроизводить их через VLC Media Player.

## Особенности
- Просмотр расписания аниме на разные дни недели.
- Обновление расписания.
- Поиск аниме по названию.
- Отображение подробной информации о выбранном аниме, включая описание, статус, жанры и год выпуска.
- Возможность указать историю просмотра.
- Возможность отметить рейтинг.
- Возможность отметить посмотреть позже для тайтла
- Отображение списка тайтлов, франшиз и списка посмотреть позже. 
- Показать список аниме по статусу, году, жанру, участников команды.
- Сохранение плейлистов с сериями аниме.
- Воспроизведение плейлистов через VLC Media Player.
- Выбор качества просмотра (FHD, HD, SD).
- Скачивание торрент-файлов и передача в торрент-клиент

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

#### Check all tables for duplicates interactively
```commandline
python enhanced_duplicate_finder.py
```
#### Auto-fix duplicates in all tables, keeping the latest records
```commandline
python enhanced_duplicate_finder.py --auto-fix
```
#### Check only specific tables
```commandline
python enhanced_duplicate_finder.py --tables title_team_relation,posters
```
#### Auto-fix duplicates, but keep the oldest records
```commandline
python enhanced_duplicate_finder.py --auto-fix --keep-oldest
```
#### Specify a custom output file
```commandline
python enhanced_duplicate_finder.py --output /logs/find_duplicates_result.txt
```

## Использование приложения:

Используйте кнопки дней недели для просмотра расписания.
Нажмите RS⮂ для обновления данных по текущему отображенному дню недели.

Нажмите "Random" для выбора случайного аниме.

Используйте поле ввода и кнопку "Find" для поиска по названию или ID (поддерживается ввод нескольких ID через запятую).
Нажмите UT⮂ для обновления данных по title_id в поле ввода или текущему тайтлу.

Плейлист открытого аниме сохраняется автоматически.

Создавайте комплексные плейлисты из нескольких тайтлов с помощью соответствующих кнопок.

При закрытии приложения текущее состояние сохраняется и восстанавливается при следующем запуске.

## Логирование:
Приложение ведет журнал своей работы, сохраняя логи в папке logs. 
