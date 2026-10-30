import logging

from pymongo.errors import PyMongoError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def mongo_exception_handler(exc, context):
    if isinstance(exc, PyMongoError):
        logger.warning('MongoDB request failed (%s)', type(exc).__name__)
        return Response(
            {'detail': 'Data storage is temporarily unavailable. Please try again.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return exception_handler(exc, context)
