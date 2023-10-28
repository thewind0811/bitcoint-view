from rest_framework.serializers import ModelSerializer

from posts import models


class PostSerializer(ModelSerializer):
    class Meta:
        model = models.Post
        fields = ['created_at', 'author', 'body', 'pk']
        read_only_fields = ['author', 'created_at']

    def create(self, validated_data):
        validated_data['author'] = self.context.get('scope').get('user')
        return super().create(validated_data)