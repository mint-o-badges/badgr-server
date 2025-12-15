import json
from issuer.models import BadgeClassExtension
from django.core.cache import cache


class CompetencyService:
    CACHE_KEY = 'dashboard_competency_areas'
    CACHE_TIMEOUT = 3600  # 1 hour

    @classmethod
    def get_competency_areas(cls):
        """Load Competency Areas from the database."""

        areas = {}
        extensions = BadgeClassExtension.objects.filter(
            name='extensions:CompetencyExtension'
        ).values_list('original_json', flat=True)

        for ext_json in extensions:
            if isinstance(ext_json, str):
                try:
                    ext_json = json.loads(ext_json)
                except json.JSONDecodeError:
                    continue

            if not isinstance(ext_json, list):
                continue

            for comp in ext_json:
                area = comp.get('name')
                if area:
                    area_key = area.lower().replace(' ', '_').replace('-', '_')
                if area and area_key and area_key not in areas:
                    areas[area_key] = {
                        'nameKey': f'{area}',
                        'displayName': area,
                    }

        cache.set(cls.CACHE_KEY, areas, cls.CACHE_TIMEOUT)
        return areas

    @classmethod
    def invalidate_cache(cls):
        """Invalidate the competency areas cache."""
        cache.delete(cls.CACHE_KEY)
