# encoding: utf-8
# TODO: Is this still used?

# import responses

# from allauth.socialaccount.models import SocialAccount, SocialApp
# from django.shortcuts import reverse
# from django.contrib.sites.models import Site
# from django.test import override_settings

# from badgeuser.models import BadgeUser, UserRecipientIdentifier
# from mainsite.tests import BadgrTestCase

MOCK_TWITTER_PROFILE_RESPONSE = """
{"follow_request_sent":false,"profile_use_background_image":true,"id":45671919,"verified":false,
"profile_text_color":"333333","profile_image_url_https":"https://pbs.twimg.com/profile_images/793142149/r_normal.png",
"profile_sidebar_fill_color":"DDEEF6","is_translator":false,"geo_enabled":false,"entities":{"description":{"urls":[]}},
"followers_count":43,"protected":false,"location":"The Netherlands","default_profile_image":false,"id_str":"45671919",
"status":{"contributors":null,"truncated":false,"text":"...","in_reply_to_status_id":null,"id":400658301702381600,
"favorite_count":0,"source":"","retweeted":true,
"coordinates":null,"entities":{"symbols":[],"user_mentions":[{"indices":[3,16],"screen_name":"denibertovic",
"id":23508244,"name":"Doobie Bones","id_str":"23508344"}],"hashtags":[{"indices":[135,139],"text":"dja"}],"urls":[]},
"in_reply_to_screen_name":null,"id_str":"400658301702381568","retweet_count":6,"in_reply_to_user_id":null,
"favorited":false,"retweeted_status":{"lang":"en","favorited":false,"in_reply_to_user_id":null,"contributors":null,
"truncated":false,"text":"Allauth example data","created_at":"Sun Jul 28 19: 56: 26 + 0000 2013","retweeted":true,
"in_reply_to_status_id":null,"coordinates":null,"id":361575897674956800,"entities":{"symbols":[],"user_mentions":[],
"hashtags":[{"indices":[117,124],"text":"django"}],"urls":[]},"in_reply_to_status_id_str":null,
"in_reply_to_screen_name":null,"source":"web","place":null,"retweet_count":6,"geo":null,"in_reply_to_user_id_str":null,
"favorite_count":8,"id_str":"361575897674956800"},"geo":null,"in_reply_to_user_id_str":null,"lang":"en",
"created_at":"Wed Nov 13 16:15:57 +0000 2013","in_reply_to_status_id_str":null,"place":null},"utc_offset":3600,
"statuses_count":39,"description":"","friends_count":83,"profile_link_color":"0084B4",
"profile_image_url":"http://pbs.twimg.com/profile_images/793142149/r_normal.png","notifications":false,
"profile_background_image_url_https":"https://abs.twimg.com/images/themes/theme1/bg.png",
"profile_background_color":"C0DEED","profile_background_image_url":"http://abs.twimg.com/images/themes/theme1/bg.png",
"name":"Raymond Penners","lang":"nl","profile_background_tile":false,"favourites_count":0,"screen_name":"pennersr",
"url":null,"created_at":"Mon Jun 08 21:10:45 +0000 2009","contributors_enabled":false,"time_zone":"Amsterdam",
"profile_sidebar_border_color":"C0DEED","default_profile":true,"following":false,"listed_count":1}
"""

MOCK_REQUEST_TOKEN_RESPONSE = """{
"oauth_token":"NPcudxy0yU5T3tBzho7iCotZ3cnetKwcTIRlX0iwRl0",
"oauth_token_secret":"veNRnAWe6inFuo8o2u8SLLZLjolYDmDP7SzL0YfYI"
"oauth_callback_confirmed":true
}"""

# class TwitterOAuthFlowTests(BadgrTestCase):
#     def setUp(self):
#         super(TwitterOAuthFlowTests, self).setUp()
#         responses.add(
#             responses.POST, 'https://api.twitter.com/oauth/request_token',
#             body='{"access_token":"2YotnFZFEjr1zCsicMWpAA","token_type":"bearer","expires_in":3600}',
#             status=200, content_type='application/json'
#         )
#         responses.add(
#             responses.POST, 'https://api.twitter.com/oauth/access_token',
#             body='{"access_token":"2YotnFZFEjr1zCsicMWpAA","token_type":"bearer","expires_in":3600}',
#             status=200, content_type='application/json'
#         )
#
#         responses.add(
#             responses.GET, 'https://api.twitter.com/1.1/account/verify_credentials.json',
#             body=MOCK_TWITTER_PROFILE_RESPONSE,
#             status=200, content_type='application/json'
#         )
#
#         sa = SocialApp.objects.create(
#             provider='icc_oauth',
#             name='ICC OAuth',
#             client_id='BADGR_TESTS',
#             secret='BADGR_IS_AFRAID_OF_THE_DARK',
#         )
#         sa.sites.add(Site.objects.first())
#
#         self.badgr_app.signup_redirect = 'http://TEST.UI/signup/success/'
#         self.badgr_app.ui_login_redirect = 'http://TEST.UI/login/'
#         self.badgr_app.save()
#
#     @responses.activate
#     def test_twitter_initiated_signup_flow(self):
#         response = self.client.get(reverse('icc_oauth_callback') + '?code=abc123')
#         self.assertEqual(response.status_code, 302)
#         self.assertIn(self.badgr_app.ui_login_redirect, response._headers.get('location')[1],
#                       "User is directed to the site with a token, fully logged in")
#
#     @responses.activate
#     def test_twitter_initiated_login_flow(self):
#         """
#         When a user shows up a second time, are they properly reconnected to their account?
#         """
#         signup_response = self.client.get(reverse('twitter_callback') + '?code=abc123')
#         self.assertEqual(signup_response.status_code, 302)
#         uri = UserRecipientIdentifier.objects.last()
#         self.assertEqual(uri.identifier, 'https://twitter.com/pennersr')
#         self.assertTrue(uri.verified)
#
#         login_response = self.client.get(reverse('twitter_callback') + '?code=zyx098')
#         self.assertEqual(login_response.status_code, 302)
#         self.assertIn(self.badgr_app.ui_login_redirect, login_response._headers.get('location')[1])
#         self.assertEqual(BadgeUser.objects.count(), 1)
