# encoding: utf-8
"""
Dashboard serializers following OpenAPI specification
"""
from rest_framework import serializers


class MonthlyDetailSerializer(serializers.Serializer):
    """Serializer for monthly detail items"""
    title = serializers.CharField(required=False)
    value = serializers.CharField()
    date = serializers.DateTimeField()
    categoryKey = serializers.CharField(required=False)
    details = serializers.CharField(required=False)
    areaKey = serializers.CharField(required=False)
    competencyKey = serializers.CharField(required=False)


class KPIDataSerializer(serializers.Serializer):
    """Serializer for individual KPI data"""
    id = serializers.CharField()
    labelKey = serializers.CharField()
    value = serializers.Field()  # Can be number or string
    unitKey = serializers.CharField(required=False)
    trend = serializers.ChoiceField(choices=['up', 'down', 'stable'], required=False)
    trendValue = serializers.FloatField(required=False)
    trendPeriod = serializers.CharField(required=False)
    tooltipKey = serializers.CharField(required=False)
    hasMonthlyDetails = serializers.BooleanField(default=False)
    monthlyDetails = MonthlyDetailSerializer(many=True, required=False)


class DashboardKPIsSerializer(serializers.Serializer):
    """Serializer for KPIs response"""
    topKpis = KPIDataSerializer(many=True)
    secondaryKpis = KPIDataSerializer(many=True)


class CompetencyAreaDataSerializer(serializers.Serializer):
    """Serializer for competency area data in list view"""
    id = serializers.CharField()
    nameKey = serializers.CharField()
    value = serializers.FloatField()
    weight = serializers.IntegerField()
    userCount = serializers.IntegerField(required=False)
    institutionCount = serializers.IntegerField(required=False)
    color = serializers.CharField()


class CompetencyAreasMetadataSerializer(serializers.Serializer):
    """Serializer for competency areas metadata"""
    totalAreas = serializers.IntegerField()
    totalBadges = serializers.IntegerField()
    totalHours = serializers.IntegerField(required=False)
    totalUsers = serializers.IntegerField(required=False)
    lastUpdated = serializers.DateField()


class CompetencyAreasSerializer(serializers.Serializer):
    """Serializer for competency areas list response"""
    metadata = CompetencyAreasMetadataSerializer()
    data = CompetencyAreaDataSerializer(many=True)


class CompetencyStatisticsSerializer(serializers.Serializer):
    """Serializer for competency area statistics"""
    totalBadges = serializers.IntegerField()
    totalHours = serializers.IntegerField()
    totalUsers = serializers.IntegerField()
    totalInstitutions = serializers.IntegerField()
    percentage = serializers.FloatField()


class CompetencyTrendSerializer(serializers.Serializer):
    """Serializer for competency trend data"""
    direction = serializers.ChoiceField(choices=['up', 'down', 'stable'])
    value = serializers.FloatField()
    period = serializers.CharField()


class TopBadgeInAreaSerializer(serializers.Serializer):
    """Serializer for top badges within a competency area"""
    badgeId = serializers.CharField()
    badgeTitleKey = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.FloatField()


class TopInstitutionSerializer(serializers.Serializer):
    """Serializer for top institutions"""
    institutionId = serializers.CharField()
    institutionName = serializers.CharField()
    badgeCount = serializers.IntegerField()
    userCount = serializers.IntegerField()


class GenderDistributionSerializer(serializers.Serializer):
    """Serializer for gender distribution"""
    male = serializers.FloatField()
    female = serializers.FloatField()
    diverse = serializers.FloatField()
    noAnswer = serializers.FloatField()


class RegionalDistributionSerializer(serializers.Serializer):
    """Serializer for regional distribution"""
    zipCode = serializers.CharField()
    regionName = serializers.CharField()
    percentage = serializers.FloatField()
    count = serializers.IntegerField()


class SubCompetencySerializer(serializers.Serializer):
    """Serializer for sub-competencies"""
    id = serializers.CharField()
    nameKey = serializers.CharField()
    count = serializers.IntegerField()
    hours = serializers.IntegerField()


class CompetencyAreaDetailsSerializer(serializers.Serializer):
    """Serializer for detailed competency area response"""
    id = serializers.CharField()
    nameKey = serializers.CharField()
    descriptionKey = serializers.CharField(required=False)
    statistics = CompetencyStatisticsSerializer()
    trend = CompetencyTrendSerializer(required=False)
    topBadges = TopBadgeInAreaSerializer(many=True, required=False)
    topInstitutions = TopInstitutionSerializer(many=True, required=False)
    genderDistribution = GenderDistributionSerializer(required=False)
    regionalDistribution = RegionalDistributionSerializer(many=True, required=False)
    subCompetencies = SubCompetencySerializer(many=True, required=False)


class CompetencyInfoSerializer(serializers.Serializer):
    """Serializer for competency information in badges"""
    id = serializers.CharField()
    nameKey = serializers.CharField()


class InstitutionInfoSerializer(serializers.Serializer):
    """Serializer for institution information in badges"""
    id = serializers.CharField()
    name = serializers.CharField()
    awardCount = serializers.IntegerField()


class RecentActivitySerializer(serializers.Serializer):
    """Serializer for recent badge activity"""
    lastAwardDate = serializers.DateTimeField()
    awardsThisMonth = serializers.IntegerField()
    trend = serializers.ChoiceField(choices=['up', 'down', 'stable'])
    trendValue = serializers.FloatField()


class VisualizationSerializer(serializers.Serializer):
    """Serializer for badge visualization details"""
    icon = serializers.CharField()
    color = serializers.CharField()


class TopBadgeDataSerializer(serializers.Serializer):
    """Serializer for top badge data"""
    rank = serializers.IntegerField()
    badgeId = serializers.CharField()
    badgeTitleKey = serializers.CharField()
    badgeTitle = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.FloatField()
    hours = serializers.IntegerField()
    categoryKey = serializers.CharField()
    competencies = CompetencyInfoSerializer(many=True)
    institutions = InstitutionInfoSerializer(many=True, required=False)
    recentActivity = RecentActivitySerializer(required=False)
    visualization = VisualizationSerializer()


class TopBadgesMetadataSerializer(serializers.Serializer):
    """Serializer for top badges metadata"""
    totalBadges = serializers.IntegerField()
    lastUpdated = serializers.DateField()
    period = serializers.CharField()
    zipCode = serializers.CharField(required=False)
    regionName = serializers.CharField(required=False)


class TopBadgesSerializer(serializers.Serializer):
    """Serializer for top badges response"""
    metadata = TopBadgesMetadataSerializer()
    badges = TopBadgeDataSerializer(many=True)
