
from django.core.management.base import BaseCommand
from user.models import Country
from django.core.files import File
from django.conf import settings
import json


STATES = ["Alaska", "Alabama", "Arkansas", "American Samoa", "Arizona", "California", "Colorado", "Connecticut", "District of Columbia", "Delaware", "Florida", "Georgia", "Guam", "Hawaii", "Iowa", "Idaho", "Illinois", "Indiana", "Kansas", "Kentucky", "Louisiana", "Massachusetts", "Maryland", "Maine", "Michigan", "Minnesota", "Missouri", "Mississippi", "Montana", "North Carolina", "North Dakota", "Nebraska", "New Hampshire", "New Jersey", "New Mexico", "Nevada", "New York", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Puerto Rico", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Virginia", "Virgin Islands", "Vermont", "Washington", "Wisconsin", "West Virginia", "Wyoming"]

excel_path = 'user/management/countries.xlsx'
svg_path = 'user/management/svg_flags/{name}.svg'

source_folder = settings.BASE_DIR / 'user' / 'management' / 'commands' / 'country_sources'
svg_path = source_folder

country_table_json_file = source_folder / 'countries.json'

"""
python3 manage.py add_countries
"""



class Command(BaseCommand):
    def handle(self, *args, **options):
        country_objects = []
        with open(country_table_json_file, 'r') as f:
            country_objects = json.load(f)

        model_objects = []
        for country_obj in country_objects:
            flag_field = country_obj.pop('flag', None)
            flag_name = flag_field.split('/')[-1]
            flag_path = svg_path / flag_field
            flag_file = File(open(flag_path, 'rb'), name=flag_name)
            country = Country(flag = flag_file, **country_obj)
            model_objects.append(country)

        Country.objects.bulk_create(model_objects)
