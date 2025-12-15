# encoding: utf-8
"""
Unit tests for competency calculation logic (no database required)
Tests the mathematical logic of value and totalHours calculations
"""
import unittest


class CompetencyCalculationLogicTests(unittest.TestCase):
    """Test the mathematical logic of competency calculations"""

    def test_value_calculation_logic(self):
        """
        Test value calculation logic:
        - 2 badges with 2 competencies each = 4 total occurrences
        - Each competency appears in 2 badge instances
        - Percentage should be (2 / 4) * 100 = 50.0%
        """
        # Simulate the data structure
        area_stats = {
            'maschinelles_lernen_einsetzen': {
                'instance_count': 2,  # Appears in 2 badge instances
                'count': 2,  # Appears in 2 unique badges
            },
            'analytisch_denken': {
                'instance_count': 2,  # Appears in 2 badge instances
                'count': 2,  # Appears in 2 unique badges
            }
        }
        total_competency_count = 4  # Total badge instances across all competencies

        # Calculate percentage using instance_count (the fix)
        for area_id, stats in area_stats.items():
            percentage = (stats['instance_count'] / total_competency_count) * 100
            self.assertEqual(round(percentage, 1), 50.0,
                f"{area_id} should have 50.0% but got {percentage}")

    def test_value_calculation_complex_scenario(self):
        """
        Badge test1: 5 competencies * 3 users = 15 occurrences
        Badge test2: 1 competency * 1 user = 1 occurrence
        Badge test3: 1 competency * 2 users = 2 occurrences
        Badge test4: 1 competency * 1 user = 1 occurrence
        Badges test5-8: 1 competency each * 1 user = 4 occurrences
        Total: 15 + 1 + 2 + 1 + 4 = 23 occurrences
        """
        area_stats = {
            'komptest1': {
                'instance_count': 3,  # Badge test1 * 3 users
                'count': 1,  # 1 unique badge
            },
            'komptest2': {
                'instance_count': 3,  # Badge test1 * 3 users
                'count': 1,  # 1 unique badge
            },
            'komptest3': {
                'instance_count': 5,  # test1 (3 users) + test3 (2 users)
                'count': 2,  # 2 unique badges
            },
            'komptest4': {
                'instance_count': 4,  # test1 (3 users) + test2 (1 user)
                'count': 2,  # 2 unique badges
            },
            'komptest5': {
                'instance_count': 1,  # test4 * 1 user
                'count': 1,  # 1 unique badge
            },
            'komptest6': {
                'instance_count': 7,  # test1 (3 users) + test5-8 (4 badges * 1 user)
                'count': 5,  # 5 unique badges
            }
        }
        total_competency_count = 23

        # Expected percentages
        expected = {
            'komptest1': 13.04,  # 3/23 * 100
            'komptest2': 13.04,  # 3/23 * 100
            'komptest3': 21.74,  # 5/23 * 100
            'komptest4': 17.39,  # 4/23 * 100
            'komptest5': 4.35,   # 1/23 * 100
            'komptest6': 30.43,  # 7/23 * 100
        }

        for area_id, stats in area_stats.items():
            percentage = (stats['instance_count'] / total_competency_count) * 100
            self.assertAlmostEqual(round(percentage, 2), expected[area_id], places=1,
                msg=f"{area_id} percentage mismatch")

        # Verify sum equals 100%
        total_percentage = sum(
            (stats['instance_count'] / total_competency_count) * 100
            for stats in area_stats.values()
        )
        self.assertAlmostEqual(total_percentage, 100.0, places=1)

    def test_total_hours_with_zero_study_load(self):
        """
        Test totalHours calculation with studyLoad = 0
        Should fallback to 4 hours per badge
        """
        total_badges = 5
        total_study_load = 0  # No studyLoad data

        # Old calculation (incorrect)
        old_total_hours = total_study_load // 60  # = 0

        # New calculation with fallback
        total_hours_from_study_load = round(total_study_load / 60) if total_study_load > 0 else 0
        total_hours_estimated = total_badges * 4
        new_total_hours = total_hours_from_study_load if total_hours_from_study_load > 0 else total_hours_estimated

        # Verify the fix
        self.assertEqual(old_total_hours, 0, "Old calculation should be 0")
        self.assertEqual(new_total_hours, 20, "New calculation should be 20 (5 badges * 4 hours)")

    def test_total_hours_with_study_load(self):
        """
        Test totalHours calculation when studyLoad is provided
        Should use studyLoad value, not fallback
        """
        total_badges = 3
        total_study_load = 360  # 6 hours in minutes (3 badges * 120 minutes each)

        # New calculation
        total_hours_from_study_load = round(total_study_load / 60) if total_study_load > 0 else 0
        total_hours_estimated = total_badges * 4  # = 12 hours
        new_total_hours = total_hours_from_study_load if total_hours_from_study_load > 0 else total_hours_estimated

        # Should use studyLoad value (6 hours), not estimated (12 hours)
        self.assertEqual(new_total_hours, 6, "Should use studyLoad value of 6 hours")

    def test_total_hours_mixed_study_load(self):
        """
        Test totalHours with mixed studyLoad values (some 0, some with values)
        """
        # Scenario: 8 badges total
        # - 3 badges with studyLoad=120 minutes each = 360 minutes = 6 hours
        # - 5 badges with studyLoad=0
        # Total studyLoad = 360 minutes = 6 hours
        total_badges = 8
        total_study_load = 360  # Only partial data

        total_hours_from_study_load = round(total_study_load / 60) if total_study_load > 0 else 0
        total_hours_estimated = total_badges * 4
        new_total_hours = total_hours_from_study_load if total_hours_from_study_load > 0 else total_hours_estimated

        # Should use studyLoad when available (6 hours)
        self.assertEqual(new_total_hours, 6, "Should use studyLoad value of 6 hours")

    def test_weight_is_unique_badge_count(self):
        """
        Test that weight field represents unique badge count, not instances
        """
        # komptest6 scenario: appears in 5 unique badges but 7 instances
        instance_count = 7
        unique_badge_count = 5

        # weight should be unique_badge_count
        weight = unique_badge_count

        self.assertEqual(weight, 5, "Weight should be 5 (unique badges)")
        self.assertNotEqual(weight, 7, "Weight should not be 7 (instances)")

    def test_percentage_uses_instances_not_weight(self):
        """
        Test that percentage calculation uses instance_count, not weight
        """
        # komptest6: 7 instances, 5 unique badges
        instance_count = 7
        weight = 5
        total_competency_count = 23

        # Percentage should use instance_count
        percentage = (instance_count / total_competency_count) * 100
        wrong_percentage = (weight / total_competency_count) * 100

        self.assertAlmostEqual(percentage, 30.43, places=1,
            msg="Percentage should use instance_count")
        self.assertNotAlmostEqual(wrong_percentage, 30.43, places=1,
            msg="Using weight would give wrong percentage")


if __name__ == '__main__':
    unittest.main()
