from rest_framework import serializers

class DateSerializer(serializers.Serializer):
    date = serializers.DateField()
