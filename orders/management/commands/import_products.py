import yaml
from django.core.management.base import BaseCommand, CommandError

from orders.services.importer import load_yaml, import_shop_data


class Command(BaseCommand):
    help = 'Импортирует товары из YAML-файлов'

    def add_arguments(self, parser):
        # nargs='+': можно передать один или несколько файлов
        parser.add_argument('files', nargs='+', help='Пути к YAML-файлам')

    def handle(self, *args, **options):
        for path in options['files']:
            try:
                data = load_yaml(path)
            except (OSError, yaml.YAMLError) as error:
                raise CommandError(f'Не удалось прочитать {path}: {error}')
            shop, count = import_shop_data(data)
            self.stdout.write(
                self.style.SUCCESS(f'{shop.name}: загружено товаров {count}')
            )