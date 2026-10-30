from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import jwt
from django.conf import settings
from django.test import SimpleTestCase
from pymongo.errors import ServerSelectionTimeoutError
from rest_framework.test import APIClient

from .models import User


class MongoDBUnavailableRequestTests(SimpleTestCase):
    def test_subject_request_database_failure_returns_service_unavailable(self):
        token = jwt.encode(
            {
                'user_id': 'test-user',
                'exp': datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            settings.SECRET_KEY,
            algorithm='HS256',
        )

        user_model = Mock()
        user_model.DoesNotExist = User.DoesNotExist
        user_model.objects.get.side_effect = ServerSelectionTimeoutError(
            'database unavailable'
        )

        with patch('accounts.authentication.User', user_model):
            response = APIClient().get(
                '/api/academics/subjects/',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn('temporarily unavailable', response.data['detail'])
