"""
Serializers for the search app.
"""
from rest_framework import serializers
from .models import SearchTask, SearchResult


class SearchResultSerializer(serializers.ModelSerializer):
    """
    Serializer for SearchResult model.
    """
    pdf_file = serializers.SerializerMethodField()
    
    class Meta:
        model = SearchResult
        fields = ['id', 'title', 'source_url', 'pdf_file', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_pdf_file(self, obj):
        """
        Return relative path for PDF file instead of full URL.
        This prevents double /media/ in the frontend URL.
        """
        if obj.pdf_file:
            # Return just the relative path (e.g., 'pdfs/filename.pdf')
            # Remove MEDIA_URL prefix if present
            file_path = str(obj.pdf_file)
            if file_path.startswith('/media/'):
                return file_path[7:]  # Remove '/media/' prefix
            elif file_path.startswith('media/'):
                return file_path[6:]  # Remove 'media/' prefix
            return file_path
        return None


class SearchTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for SearchTask model.
    
    Includes nested SearchResult objects in the response.
    """
    results = SearchResultSerializer(many=True, read_only=True)
    error_message = serializers.SerializerMethodField()
    
    class Meta:
        model = SearchTask
        fields = ['id', 'keyword', 'article_count', 'status', 'created_at', 'results', 'error_message']
        read_only_fields = ['id', 'created_at', 'results', 'error_message']
    
    def get_error_message(self, obj):
        """Return error message if task failed."""
        if obj.status == 'failed':
            # Try to get error from Celery result if available
            # This would require additional implementation
            return None
        return None


class SearchTaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating SearchTask.
    
    Requires the keyword field for POST requests.
    Optionally accepts article_count (defaults to 3).
    """
    
    class Meta:
        model = SearchTask
        fields = ['keyword', 'article_count']
    
    def validate_article_count(self, value):
        """Validate that article_count is between 1 and 20."""
        if value is not None:
            if value < 1:
                raise serializers.ValidationError("Article count must be at least 1")
            if value > 20:
                raise serializers.ValidationError("Article count cannot exceed 20")
        return value

