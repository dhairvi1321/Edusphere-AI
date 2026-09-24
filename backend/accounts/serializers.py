from rest_framework import serializers
from .models import User


class RegisterSerializer(serializers.Serializer):
    username = serializers.EmailField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(default='')

    def validate_email(self, value):
        if User.objects(email=value).first():
            raise serializers.ValidationError('A user with that email already exists.')
        return value

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
        )
        user.set_password(validated_data['password'])
        user.save()
        return user
