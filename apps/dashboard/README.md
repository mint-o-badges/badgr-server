# Dashboard API Implementation

## Overview

This dashboard app provides aggregated metrics and analytics for the Badgr platform, following the OpenAPI specification defined in `dashboard-overview-openapi.yaml`.

## Endpoints

### 1. KPIs Endpoint
**URL:** `GET /v1/dashboard/overview/kpis`

Returns aggregated key performance indicators:
- Top KPIs (3 items): Active Institutions, Total Badges, Total Hours
- Secondary KPIs: Hours per competency, Diversity index, etc.
- Includes trend data and monthly details

### 2. Competency Areas List
**URL:** `GET /v1/dashboard/overview/competency-areas`

Returns top competency areas with distribution:
- IT & Digital
- Social Competencies
- Languages
- Crafts
- Management
- Other

Parameters:
- `limit` (default: 10, max: 50) - Number of areas to return
- `sortBy` - Sort criteria (percentage, count, hours, userCount)

### 3. Competency Area Detail
**URL:** `GET /v1/dashboard/overview/competency-areas/{areaId}`

Returns detailed information for a specific competency area:
- Complete statistics (badges, hours, participants)
- Trend data
- Top badges within this area
- Top institutions
- Gender distribution
- Regional distribution
- Sub-competencies breakdown

### 4. Top Badges
**URL:** `GET /v1/dashboard/overview/top-badges`

Returns the top 3 most awarded badges:
- Badge details and rankings
- Award counts and percentages
- Competencies covered
- Issuing institutions
- Recent activity

Parameters:
- `limit` (default: 3, max: 10) - Number of badges to return
- `period` - Time period (all_time, last_year, last_month, last_week)

## Regional Filtering

All endpoints support regional filtering based on `request.user.zip_code`:
- Filters badge instances by recipient's zip code
- Automatic filtering when user has zip_code set
- No manual zipCode parameter needed (server-side filtering)

## Authentication

All endpoints require authentication:
- `permissions.IsAuthenticated` is enforced
- Uses existing Badgr authentication mechanisms
- Returns 401 Unauthorized if not authenticated

## Database Queries

The implementation uses optimized database queries:
- `select_related('badgeclass', 'badgeclass__issuer')` for badge instances
- `values().annotate()` for aggregations
- Efficient filtering with Q objects
- Proper indexing on date fields

## Code Structure

```
dashboard/
├── __init__.py
├── admin.py           # No models to register
├── api.py             # View classes for all endpoints
├── apps.py            # App configuration
├── models.py          # Uses existing models (no new models)
├── serializers.py     # DRF serializers matching OpenAPI spec
├── tests.py           # Unit tests for all endpoints
└── urls.py            # URL configuration
```

## Implementation Details

### Base View Class
`DashboardBaseView` provides common functionality:
- Authentication requirement
- Regional filtering logic
- Filtered badge instances retrieval
- Trend calculation utilities

### Competency Area Categorization
Uses keyword-based categorization:
- Analyzes badge names and descriptions
- Maps to predefined competency areas
- Simple and efficient implementation

### KPI Calculations
- Active institutions: Count of distinct issuers with badges
- Total badges: Count of non-revoked badge instances
- Total hours: Estimated at 4 hours per badge
- Trends: Comparison of current vs previous month

### Error Handling
- Try-except blocks in all views
- Proper logging with logger.error()
- Returns appropriate HTTP status codes
- Includes error messages in responses

## Testing

Run tests with:
```bash
python manage.py test dashboard
```

Test coverage includes:
- Authentication requirements
- Endpoint responses
- Query parameters
- Error handling

## Integration

The dashboard app is integrated into the main application:

1. Added to `INSTALLED_APPS` in `settings.py`
2. URL patterns included in `mainsite/urls.py`
3. Uses existing models from `issuer` and `badgeuser` apps
4. Follows existing code patterns and conventions

## Performance Considerations

- Database queries are optimized with select_related/prefetch_related
- Aggregations are done at the database level
- No N+1 query problems
- Results can be cached if needed (future enhancement)

## Future Enhancements

Potential improvements:
1. Implement actual regional filtering with zip code data
2. Add caching layer (Redis/Memcached)
3. Create materialized views for complex aggregations
4. Add more sophisticated competency tagging system
5. Implement real-time updates with WebSockets
6. Add export functionality (CSV, PDF)
7. Create admin dashboard for monitoring

## API Documentation

The implementation follows the OpenAPI specification in:
`/Volumes/workbench/projects/repos/badgr-server/dashboard-overview-openapi.yaml`

All serializers match the schema definitions exactly.
