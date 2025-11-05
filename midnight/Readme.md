# Utilises


## Get the current list of titles from the website:
```bash
cd midnight
python scrapper.py
```

## Compare the retrieved list of titles with the local database:
```bash
cd midnight
python compare_titles.py
```

## Create an archive of compiled production versions
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
