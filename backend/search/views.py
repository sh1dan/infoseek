"""
Views for the search app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import SearchTask, SearchResult
from .serializers import SearchTaskSerializer, SearchTaskCreateSerializer
from .tasks import scrape_news_task


class SearchTaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SearchTask model.
    
    Provides CRUD operations for search tasks.
    On POST, creates a task and triggers the scrape_news_task Celery task.
    """
    queryset = SearchTask.objects.all()
    pagination_class = None  # Disable pagination to return all tasks
    
    def get_serializer_class(self):
        """
        Return the appropriate serializer class based on the action.
        """
        if self.action == 'create':
            return SearchTaskCreateSerializer
        return SearchTaskSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Create a new SearchTask and trigger the Celery scraping task.
        
        Returns the task ID (UUID) in the response.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create the SearchTask instance
        search_task = serializer.save()
        
        try:
            # Trigger the Celery task asynchronously with task_id, keyword, and article_count
            celery_task = scrape_news_task.delay(
                str(search_task.id), 
                search_task.keyword,
                search_task.article_count
            )
            logger.info(f"Created search task {search_task.id} with Celery task {celery_task.id} for {search_task.article_count} articles")
        except Exception as e:
            # If Celery task creation fails, mark task as failed
            logger.error(f"Failed to create Celery task for {search_task.id}: {str(e)}")
            search_task.status = 'failed'
            search_task.save()
            return Response(
                {
                    'id': str(search_task.id),
                    'keyword': search_task.keyword,
                    'status': 'failed',
                    'error': 'Failed to start background task. Please check Celery worker.',
                    'created_at': search_task.created_at,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Return the SearchTask ID
        return Response(
            {
                'id': str(search_task.id),
                'keyword': search_task.keyword,
                'status': search_task.status,
                'created_at': search_task.created_at,
                'celery_task_id': celery_task.id,
            },
            status=status.HTTP_201_CREATED
        )

