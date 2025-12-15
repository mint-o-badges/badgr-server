# encoding: utf-8
"""
Dashboard API endpoints
"""
from django.http import Http404
from django.db.models import Count, Q, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from issuer.models import BadgeInstance, BadgeClass, Issuer, BadgeClassExtension
from .serializers import (
    DashboardKPIsSerializer,
    CompetencyAreasSerializer,
    CompetencyAreaDetailsSerializer,
    TopBadgesSerializer,
)
from .mixins import RegionalFilterMixin
from .services.competency_service import CompetencyService

import logging

logger = logging.getLogger("Badgr.Events")


class DashboardBaseView(RegionalFilterMixin, APIView):
    """Base view for dashboard endpoints with common functionality"""
    permission_classes = (permissions.IsAuthenticated,)

    def calculate_trend(self, current_count, previous_count):
        """Calculate trend direction and absolute value difference"""
        if previous_count == 0:
            if current_count > 0:
                return 'up', current_count
            return 'stable', 0

        change = current_count - previous_count
        if change > 0:
            return 'up', change
        elif change < 0:
            return 'down', abs(change)
        else:
            return 'stable', 0


class DashboardKPIsView(DashboardBaseView):
    """
    GET /v1/dashboard/overview/kpis
    Returns aggregated KPI metrics
    """

    def get(self, request, **kwargs):
        """Get dashboard KPIs"""
        try:
            # Get filtered badge instances
            badge_instances = self.get_regional_badge_instances(request)

            # Calculate date ranges
            now = timezone.now()
            last_month_start = now - timedelta(days=30)
            two_months_ago = now - timedelta(days=60)

            # Current month counts
            current_badges = badge_instances.filter(created_at__gte=last_month_start).count()
            total_badges = badge_instances.count()

            # Previous month counts for trends
            previous_badges = badge_instances.filter(
                created_at__gte=two_months_ago,
                created_at__lt=last_month_start
            ).count()

            # Calculate active institutions (issuers with badges awarded)
            active_issuers_current = badge_instances.filter(
                created_at__gte=last_month_start
            ).values('badgeclass__issuer').distinct().count()

            active_issuers_previous = badge_instances.filter(
                created_at__gte=two_months_ago,
                created_at__lt=last_month_start
            ).values('badgeclass__issuer').distinct().count()

            total_active_issuers = badge_instances.values(
                'badgeclass__issuer'
            ).distinct().count()

            # Calculate competency hours (estimate: 4 hours per badge)
            # This is a simplified calculation
            total_hours = total_badges * 4
            current_hours = current_badges * 4
            previous_hours = previous_badges * 4

            # Calculate trends
            badge_trend, badge_trend_value = self.calculate_trend(current_badges, previous_badges)
            issuer_trend, issuer_trend_value = self.calculate_trend(
                active_issuers_current, active_issuers_previous
            )
            hours_trend, hours_trend_value = self.calculate_trend(current_hours, previous_hours)

            # Build top KPIs
            top_kpis = [
                {
                    'id': 'institutions_active',
                    'labelKey': 'Dashboard.kpi.institutions',
                    'value': total_active_issuers,
                    'unitKey': 'Dashboard.unit.institutions',
                    'trend': issuer_trend,
                    'trendValue': issuer_trend_value,
                    'trendPeriod': 'lastMonth',
                    'tooltipKey': 'Dashboard.tooltip.institutions',
                    'hasMonthlyDetails': False,
                },
                {
                    'id': 'badges_total',
                    'labelKey': 'Dashboard.kpi.totalBadges',
                    'value': total_badges,
                    'unitKey': 'Dashboard.unit.badges',
                    'trend': badge_trend,
                    'trendValue': badge_trend_value,
                    'trendPeriod': 'lastMonth',
                    'hasMonthlyDetails': True,
                    'monthlyDetails': self._get_recent_badge_details(badge_instances, limit=5),
                },
                {
                    'id': 'competency_hours',
                    'labelKey': 'Dashboard.kpi.totalHours',
                    'value': total_hours,
                    'unitKey': 'Dashboard.unit.hours',
                    'trend': hours_trend,
                    'trendValue': hours_trend_value,
                    'trendPeriod': 'lastMonth',
                    'hasMonthlyDetails': False,
                },
            ]

            # Build secondary KPIs
            avg_hours_per_competency = round(total_hours / max(total_badges, 1), 1)
            secondary_kpis = [
                {
                    'id': 'hours_per_competency',
                    'labelKey': 'Dashboard.kpi.hoursPerCompetency',
                    'value': avg_hours_per_competency,
                    'unitKey': 'Dashboard.unit.hoursPerCompetency',
                    'trend': 'stable',
                    'trendValue': 0.2,
                },
                {
                    'id': 'diversity_index',
                    'labelKey': 'Dashboard.kpi.diversityIndex',
                    'value': 0.78,
                    'unitKey': 'Dashboard.unit.index',
                    'trend': 'up',
                    'trendValue': 0.05,
                },
            ]

            data = {
                'topKpis': top_kpis,
                'secondaryKpis': secondary_kpis,
            }

            serializer = DashboardKPIsSerializer(data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error in DashboardKPIsView: {str(e)}")
            return Response(
                {'error': 'Internal Server Error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_recent_badge_details(self, badge_instances, limit=5):
        """Get recent badge award details"""
        recent_badges = badge_instances.order_by('-created_at')[:limit]

        details = []
        for badge in recent_badges:
            details.append({
                'title': badge.badgeclass.name,
                'value': '1 Badge',
                'date': badge.created_at,
                'categoryKey': 'badge.category.competency',
                'details': f'Issued by {badge.badgeclass.issuer.name}',
            })

        return details


class CompetencyAreasListView(DashboardBaseView):
    """
    GET /v1/dashboard/overview/competency-areas
    Returns top competency areas with distribution
    """

    def get(self, request, **kwargs):
        """Get top competency areas"""
        try:
            limit = int(request.query_params.get('limit', 10))
            limit = min(max(limit, 1), 50)

            # Get competency areas from database
            competency_areas = CompetencyService.get_competency_areas()

            # Get filtered badge instances
            badge_instances = self.get_regional_badge_instances(request)
            total_badge_instances = badge_instances.count()
            # Fix: Count unique badge CLASSES, not instances, for percentage calculation
            total_unique_badge_classes = badge_instances.values('badgeclass_id').distinct().count()

            if total_badge_instances == 0:
                # Return empty response
                data = {
                    'metadata': {
                        'totalAreas': 0,
                        'totalBadges': 0,
                        'totalHours': 0,
                        'totalUsers': 0,
                        'lastUpdated': timezone.now().date(),
                    },
                    'data': [],
                }
                serializer = CompetencyAreasSerializer(data)
                return Response(serializer.data)

            # Categorize badges by competency area
            area_stats, total_hours, total_competency_count = self._categorize_badges(
                badge_instances, competency_areas, total_badge_instances
            )

            # Sort by count and limit
            sorted_areas = sorted(
                area_stats.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:limit]

            # Calculate sum of all weights for percentage calculation
            # This ensures percentages sum to 100%
            total_weight = sum(stats['count'] for _, stats in sorted_areas)

            # Build response
            data_list = []
            for area_id, stats in sorted_areas:
                # Calculate percentage relative to sum of all weights
                # This ensures all percentages sum to 100%
                # Example: weight=1, total_weight=12 → (1/12)*100 = 8.33%
                percentage = (stats['count'] / total_weight) * 100 if total_weight > 0 else 0
                data_list.append({
                    'id': area_id,
                    'nameKey': stats.get('nameKey', area_id),
                    'value': round(percentage, 2),
                    'weight': stats['count'],
                    'userCount': stats['user_count'],
                    'institutionCount': stats['institution_count'],
                    'color': '#492E98',
                })

            data = {
                'metadata': {
                    'totalAreas': len(sorted_areas),
                    'totalBadges': total_unique_badge_classes,  # Use unique badge classes, not instances
                    'totalHours': total_hours,
                    'totalUsers': badge_instances.values('user').distinct().count(),
                    'lastUpdated': timezone.now().date(),
                },
                'data': data_list,
            }

            serializer = CompetencyAreasSerializer(data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error in CompetencyAreasListView: {str(e)}")
            return Response(
                {'error': 'Internal Server Error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _categorize_badges(self, badge_instances, competency_areas, total_badge_instances):
        """Categorize badges into competency areas based on BadgeClassExtension data"""
        import json

        # Use the passed total_badge_instances for fallback hours estimation
        total_badges = total_badge_instances

        area_stats = {}
        area_names = {}  # Map area_id -> display name
        total_study_load = 0  # In minutes
        total_competency_count = 0  # Total number of competency occurrences

        # Get all badge class IDs from the instances
        badge_class_ids = badge_instances.values_list('badgeclass_id', flat=True).distinct()

        # Query all CompetencyExtension data for these badge classes
        competency_extensions = BadgeClassExtension.objects.filter(
            badgeclass_id__in=badge_class_ids,
            name='extensions:CompetencyExtension'
        ).select_related('badgeclass')

        # Build a mapping of badgeclass_id -> competencies
        badgeclass_competencies = {}
        for ext in competency_extensions:
            try:
                # Parse the JSON data
                ext_data = ext.original_json
                if isinstance(ext_data, str):
                    ext_data = json.loads(ext_data)

                # Handle both single competency and array of competencies
                if not isinstance(ext_data, list):
                    ext_data = [ext_data]

                competencies = []
                for comp in ext_data:
                    if isinstance(comp, dict) and 'name' in comp:
                        competencies.append({
                            'name': comp.get('name'),
                            'studyLoad': comp.get('studyLoad', 0),
                            'description': comp.get('description', ''),
                        })

                badgeclass_competencies[ext.badgeclass_id] = competencies

            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                logger.warning(f"Failed to parse competency extension for badgeclass {ext.badgeclass_id}: {e}")
                continue

        # Now iterate through badge instances and categorize by competency
        for badge in badge_instances.select_related('badgeclass', 'badgeclass__issuer'):
            competencies = badgeclass_competencies.get(badge.badgeclass_id, [])

            for comp in competencies:
                comp_name = comp['name']
                study_load = comp.get('studyLoad', 0)

                # Create area_id from competency name
                area_id = comp_name.lower().replace(' ', '_').replace('-', '_')

                # Store the display name
                if area_id not in area_names:
                    area_names[area_id] = comp_name

                # Initialize area stats if not exists
                if area_id not in area_stats:
                    area_stats[area_id] = {
                        'count': 0,
                        'instance_count': 0,  # Track total badge instances with this competency
                        'user_count': 0,
                        'institution_count': 0,
                        'users': set(),
                        'institutions': set(),
                        'badges': set(),  # Track unique badge classes per competency
                        'study_load': 0,
                        'nameKey': comp_name,  # Store the original competency name
                    }

                # Update statistics
                area_stats[area_id]['count'] += 1  # Temporary counter for instances
                area_stats[area_id]['instance_count'] += 1  # Track badge instances
                area_stats[area_id]['users'].add(badge.user_id)
                area_stats[area_id]['institutions'].add(badge.badgeclass.issuer_id)
                area_stats[area_id]['badges'].add(badge.badgeclass_id)  # Track unique badges for this competency
                area_stats[area_id]['study_load'] += study_load
                total_study_load += study_load
                total_competency_count += 1  # Track total competency occurrences

        # Convert sets to counts and remove temporary fields
        for area_id in area_stats:
            area_stats[area_id]['user_count'] = len(area_stats[area_id]['users'])
            area_stats[area_id]['institution_count'] = len(area_stats[area_id]['institutions'])
            # Fix: weight should be the number of unique badges that grant this competency
            area_stats[area_id]['count'] = len(area_stats[area_id]['badges'])
            # Keep instance_count for percentage calculation
            del area_stats[area_id]['users']
            del area_stats[area_id]['institutions']
            del area_stats[area_id]['badges']
            del area_stats[area_id]['study_load']

        # Fix: Convert total study load from minutes to hours with fallback
        # If studyLoad data is missing/zero, estimate 4 hours per badge instance
        total_hours_from_study_load = round(total_study_load / 60) if total_study_load > 0 else 0
        total_hours_estimated = total_badges * 4
        total_hours = total_hours_from_study_load if total_hours_from_study_load > 0 else total_hours_estimated

        # Store total competency count for percentage calculation
        return area_stats, total_hours, total_competency_count


class CompetencyAreaDetailView(DashboardBaseView):
    """
    GET /v1/dashboard/overview/competency-areas/{areaId}
    Returns detailed information for a specific competency area
    """

    def _normalize_id(self, area_id: str) -> str:
        """Normalize an area ID for comparisons."""
        if not area_id:
            return ''
        return area_id.lower().replace('-', '_').replace(' ', '_')

    def _find_area(self, normalized_input: str, competency_areas: dict):
        """
        Find an area with various matching strategies.
        Returns: (area_info, matched_id) or (None, None)
        """
        # Strategy 1: Exact match with normalized keys
        for key, data in competency_areas.items():
            if self._normalize_id(key) == normalized_input:
                return data, key

        # Strategy 2: Match via displayName
        for key, data in competency_areas.items():
            display_name = data.get('displayName', '')
            if self._normalize_id(display_name) == normalized_input:
                return data, key

        # Strategy 3: Match via nameKey
        for key, data in competency_areas.items():
            name_key = data.get('nameKey', '')
            # nameKey format: "competency.area.bienenhaus" -> extract last part
            name_key_suffix = name_key.split('.')[-1] if name_key else ''
            if self._normalize_id(name_key_suffix) == normalized_input:
                return data, key

        # Strategy 4: Partial match (contains)
        for key, data in competency_areas.items():
            if normalized_input in self._normalize_id(key):
                return data, key
            display_name = data.get('displayName', '')
            if normalized_input in self._normalize_id(display_name):
                return data, key

        return None, None

    def get(self, request, area_id, **kwargs):
        """Get competency area details"""
        try:
            # Get competency areas from database
            competency_areas = CompetencyService.get_competency_areas()

            # Normalize the incoming area_id
            normalized_input = self._normalize_id(area_id)

            # Find area with normalization
            area_info, matched_id = self._find_area(normalized_input, competency_areas)

            if not area_info:
                available_areas = list(competency_areas.keys())[:20]
                return Response(
                    {
                        'error': 'Not Found',
                        'message': f"Competency area '{area_id}' not found",
                        'requested_id': area_id,
                        'normalized_id': normalized_input,
                        'available_areas': available_areas,
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get filtered badge instances
            badge_instances = self.get_regional_badge_instances(request)

            # Filter badges for this competency area - use matched_id instead of original area_id
            area_badges = self._filter_area_badges(badge_instances, matched_id, area_info)

            # Get badge class IDs that have this competency (for counting institutions and badges)
            badge_class_ids_with_competency = self._get_badge_class_ids_for_competency(matched_id, area_info)

            if area_badges.count() == 0 and len(badge_class_ids_with_competency) == 0:
                return Response(
                    {'error': 'Not Found', 'message': f'No data for competency area {area_id}'},
                    status=status.HTTP_404_NOT_FOUND
                )

            total_badges = badge_instances.count()
            area_badge_count = area_badges.count()
            percentage = (area_badge_count / total_badges * 100) if total_badges > 0 else 0

            # Calculate statistics
            # Fix: badgeCount should count unique badge CLASSES that offer this competency,
            # not badge instances. Count from all badge classes with this competency.
            from issuer.models import BadgeClass
            regional_issuer_ids = self.get_regional_issuer_ids(request)

            badge_class_query = BadgeClass.objects.filter(id__in=badge_class_ids_with_competency)
            if regional_issuer_ids is not None:
                badge_class_query = badge_class_query.filter(issuer_id__in=regional_issuer_ids)

            unique_badge_classes = badge_class_query.count()

            # Fix: totalInstitutions should count institutions that OFFER badges with this competency,
            # not just those whose badges were issued. Count from badge classes, not instances.
            unique_institutions = badge_class_query.values('issuer').distinct().count()

            # userCount correctly counts users who have EARNED badges with this competency (from instances)
            unique_users = area_badges.values('user').distinct().count()

            statistics = {
                'totalBadges': unique_badge_classes,  # Count unique badge classes that offer this competency
                'totalHours': area_badge_count * 4,  # Calculate hours based on issued instances (earned hours)
                'totalUsers': unique_users,
                'totalInstitutions': unique_institutions,
                'percentage': round(percentage, 1),
            }

            # Calculate trend (simplified)
            now = timezone.now()
            last_month = now - timedelta(days=30)
            current_count = area_badges.filter(created_at__gte=last_month).count()
            trend = {
                'direction': 'up' if current_count > 0 else 'stable',
                'value': 12.5,
                'period': 'lastMonth',
            }

            # Get top badges in this area
            top_badges_data = self._get_top_badges_in_area(area_badges, limit=5)

            # Get top institutions - pass badge_class_ids to include institutions that offer badges but haven't issued any
            top_institutions_data = self._get_top_institutions(
                area_badges,
                badge_class_ids_with_competency,
                self.get_regional_issuer_ids(request),
                limit=5
            )

            data = {
                'id': matched_id,  # Use matched_id for consistency
                'nameKey': area_info['nameKey'],
                'descriptionKey': f'{area_info["nameKey"]}.description',
                'statistics': statistics,
                'trend': trend,
                'topBadges': top_badges_data,
                'topInstitutions': top_institutions_data,
            }

            serializer = CompetencyAreaDetailsSerializer(data)
            return Response(serializer.data)

        except Http404:
            raise
        except Exception as e:
            logger.error(f"Error in CompetencyAreaDetailView: {str(e)}")
            return Response(
                {'error': 'Internal Server Error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_badge_class_ids_for_competency(self, area_id, area_info):
        """
        Get all badge class IDs that have this competency.
        This is used to count badges and institutions regardless of whether badges were issued.

        Returns:
            set: Set of badge class IDs that have this competency
        """
        import json

        # Collect all badge class IDs that have this competency
        badge_class_ids_with_competency = set()

        # Query BadgeClassExtension for CompetencyExtension
        extensions = BadgeClassExtension.objects.filter(
            name='extensions:CompetencyExtension'
        ).values_list('badgeclass_id', 'original_json')

        normalized_area = self._normalize_id(area_id)
        display_name = area_info.get('displayName', '')

        for badgeclass_id, ext_json in extensions:
            try:
                if isinstance(ext_json, str):
                    ext_json = json.loads(ext_json)

                if not isinstance(ext_json, list):
                    ext_json = [ext_json]

                for comp in ext_json:
                    if isinstance(comp, dict):
                        comp_name = comp.get('name', '')
                        normalized_comp = self._normalize_id(comp_name)

                        # Match: normalized IDs or displayName
                        if (normalized_comp == normalized_area or
                            comp_name == display_name or
                            normalized_area in normalized_comp):
                            badge_class_ids_with_competency.add(badgeclass_id)
                            break

            except (json.JSONDecodeError, TypeError):
                continue

        return badge_class_ids_with_competency

    def _filter_area_badges(self, badge_instances, area_id, area_info):
        """
        Filter badge instances for a specific competency area.
        Uses BadgeClassExtension for precise filtering based on competency metadata.
        """
        badge_class_ids_with_competency = self._get_badge_class_ids_for_competency(area_id, area_info)

        if not badge_class_ids_with_competency:
            logger.warning(f"No badge classes found for competency: {area_id}")
            return badge_instances.none()

        return badge_instances.filter(badgeclass_id__in=badge_class_ids_with_competency)

    def _get_top_badges_in_area(self, area_badges, limit=5):
        """Get top badges in this competency area"""
        badge_counts = area_badges.values(
            'badgeclass__entity_id',
            'badgeclass__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        total = area_badges.count()
        top_badges = []
        for item in badge_counts:
            percentage = (item['count'] / total * 100) if total > 0 else 0
            top_badges.append({
                'badgeId': item['badgeclass__entity_id'],
                'badgeTitleKey': f'badge.title.{item["badgeclass__entity_id"]}',
                'count': item['count'],
                'percentage': round(percentage, 1),
            })

        return top_badges

    def _get_top_institutions(self, area_badges, badge_class_ids_with_competency, regional_issuer_ids, limit=5):
        """
        Get top institutions in this competency area.

        Args:
            area_badges: QuerySet of badge instances that have been issued for this competency
            badge_class_ids_with_competency: Set of badge class IDs that offer this competency
            regional_issuer_ids: List of issuer IDs in the user's region (None = no filter)
            limit: Maximum number of institutions to return

        Returns:
            List of institution dictionaries with:
            - badgeCount: Number of badge CLASSES the institution offers with this competency
            - userCount: Number of unique users who earned badges with this competency from this institution
        """
        from issuer.models import BadgeClass

        # Get all badge classes that offer this competency (filtered by region)
        badge_class_query = BadgeClass.objects.filter(id__in=badge_class_ids_with_competency)
        if regional_issuer_ids is not None:
            badge_class_query = badge_class_query.filter(issuer_id__in=regional_issuer_ids)

        # Get all institutions that offer badges with this competency
        institutions = badge_class_query.values(
            'issuer__entity_id',
            'issuer__name'
        ).annotate(
            issuer_id=F('issuer__id')
        ).distinct()

        # For each institution, count badge CLASSES offered and unique users who earned them
        top_institutions = []
        for inst in institutions:
            issuer_id = inst['issuer_id']

            # Fix: Count badge CLASSES offered by this institution (not instances)
            badge_count = badge_class_query.filter(issuer_id=issuer_id).count()

            # Count unique users who earned badges from this institution for this competency
            institution_badges = area_badges.filter(badgeclass__issuer_id=issuer_id)
            user_count = institution_badges.values('user').distinct().count()

            top_institutions.append({
                'institutionId': inst['issuer__entity_id'],
                'institutionName': inst['issuer__name'],
                'badgeCount': badge_count,  # Number of badge classes offered
                'userCount': user_count,     # Number of users who earned badges
            })

        # Sort by badge count (descending) and limit
        top_institutions.sort(key=lambda x: x['badgeCount'], reverse=True)
        return top_institutions[:limit]


class TopBadgesView(DashboardBaseView):
    """
    GET /v1/dashboard/overview/top-badges
    Returns top 3 most awarded badges
    """

    RANK_ICONS = {
        1: {'icon': 'lucideTrophy', 'color': '#FFCC00'},
        2: {'icon': 'lucideMedal', 'color': '#492E98'},
        3: {'icon': 'lucideAward', 'color': '#492E98'},
    }

    def get(self, request, **kwargs):
        """Get top badges"""
        try:
            limit = int(request.query_params.get('limit', 3))
            limit = min(max(limit, 1), 10)

            period = request.query_params.get('period', 'all_time')

            # Get filtered badge instances
            badge_instances = self.get_regional_badge_instances(request)

            # Apply period filter
            if period != 'all_time':
                badge_instances = self._apply_period_filter(badge_instances, period)

            total_badges = badge_instances.count()

            if total_badges == 0:
                # Return empty response
                data = {
                    'metadata': {
                        'totalBadges': 0,
                        'lastUpdated': timezone.now().date(),
                        'period': period,
                    },
                    'badges': [],
                }
                serializer = TopBadgesSerializer(data)
                return Response(serializer.data)

            # Get badge class counts
            badge_counts = badge_instances.values(
                'badgeclass__entity_id',
                'badgeclass__name',
                'badgeclass__description',
                'badgeclass__issuer__entity_id',
                'badgeclass__issuer__name',
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:limit]

            # Build badge data
            badges_data = []
            for rank, item in enumerate(badge_counts, start=1):
                # Validate item before processing
                if not item or not isinstance(item, dict):
                    continue

                percentage = (item['count'] / total_badges * 100) if total_badges > 0 else 0

                badge_data = {
                    'rank': rank,
                    'badgeId': item.get('badgeclass__entity_id'),
                    'badgeTitleKey': f'badge.title.{item.get("badgeclass__entity_id", "")}',
                    'badgeTitle': item.get('badgeclass__name', ''),
                    'count': item.get('count', 0),
                    'percentage': round(percentage, 2),
                    'hours': item.get('count', 0) * 4,
                    'categoryKey': 'badge.category.competency',
                    'competencies': self._get_badge_competencies(item),
                    'institutions': [{
                        'id': item.get('badgeclass__issuer__entity_id'),
                        'name': item.get('badgeclass__issuer__name', ''),
                        'awardCount': item.get('count', 0),
                    }],
                    'visualization': self.RANK_ICONS.get(rank, self.RANK_ICONS[3]),
                }

                badges_data.append(badge_data)

            data = {
                'metadata': {
                    'totalBadges': total_badges,
                    'lastUpdated': timezone.now().date(),
                    'period': period,
                },
                'badges': badges_data,
            }

            serializer = TopBadgesSerializer(data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error in TopBadgesView: {str(e)}")
            return Response(
                {'error': 'Internal Server Error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _apply_period_filter(self, queryset, period):
        """Apply period filter to queryset"""
        now = timezone.now()

        if period == 'last_week':
            start_date = now - timedelta(days=7)
        elif period == 'last_month':
            start_date = now - timedelta(days=30)
        elif period == 'last_year':
            start_date = now - timedelta(days=365)
        else:
            return queryset

        return queryset.filter(created_at__gte=start_date)

    def _get_badge_competencies(self, badge_item):
        """Extract competencies from badge description (simplified)"""
        # This is a simplified implementation
        # In production, you would have a proper competency tagging system

        # Guard against None or invalid input
        if badge_item is None or not isinstance(badge_item, dict):
            return []

        competencies = []

        description = (badge_item.get('badgeclass__description') or '').lower()
        name = badge_item.get('badgeclass__name', '').lower()
        text = f"{name} {description}"

        # Simple keyword extraction
        if 'marketing' in text or 'social media' in text:
            competencies.append({
                'id': 'digital_marketing',
                'nameKey': 'competency.name.digitalMarketing',
            })
        if 'web' in text or 'html' in text or 'css' in text:
            competencies.append({
                'id': 'web_development',
                'nameKey': 'competency.name.webDevelopment',
            })
        if 'project' in text or 'management' in text:
            competencies.append({
                'id': 'project_management',
                'nameKey': 'competency.name.projectManagement',
            })

        # Default competency if none found
        if not competencies:
            competencies.append({
                'id': 'general',
                'nameKey': 'competency.name.general',
            })

        return competencies
