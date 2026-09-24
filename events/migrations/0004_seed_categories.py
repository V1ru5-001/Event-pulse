from django.db import migrations

CATEGORIES = [
    ('academic',      'Academic',           '📚', '#4B6BF1'),
    ('social',        'Social',             '🎉', '#F15B4B'),
    ('sports',        'Sports',             '⚽', '#2FBF71'),
    ('career',        'Career',             '💼', '#8A5CF6'),
    ('arts',          'Arts & Culture',     '🎨', '#F1A73B'),
    ('music',         'Music & Parties',    '🎵', '#F13B9F'),
    ('international', 'International',      '🌍', '#3BC7F1'),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('events', 'Category')
    for slug, name, icon, colour in CATEGORIES:
        Category.objects.update_or_create(
            slug=slug,
            defaults={'name': name, 'icon': icon, 'colour': colour},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_eventmedia'),
    ]

    operations = [
        migrations.RunPython(seed_categories, noop),
    ]
