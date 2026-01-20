"""
Models for the search app.
"""
import uuid
from django.db import models
from django.utils import timezone


class SearchTask(models.Model):
    """
    Model representing a search task.
    
    Attributes:
        id: UUID primary key
        keyword: Search keyword string
        status: Task status (pending, processing, completed, failed)
        created_at: Timestamp when task was created
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    keyword = models.CharField(max_length=255)
    article_count = models.IntegerField(default=3, help_text='Number of articles to scrape')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Search Task'
        verbose_name_plural = 'Search Tasks'
    
    def __str__(self):
        return f"SearchTask({self.keyword} - {self.status})"


class SearchResult(models.Model):
    """
    Model representing a search result.
    
    Attributes:
        task: Foreign key to SearchTask
        title: Title of the result
        source_url: URL of the source
        pdf_file: FileField for the generated PDF
    """
    
    task = models.ForeignKey(SearchTask, on_delete=models.CASCADE, related_name='results')
    title = models.CharField(max_length=500)
    source_url = models.URLField(max_length=1000)
    pdf_file = models.FileField(upload_to='pdfs/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Search Result'
        verbose_name_plural = 'Search Results'
    
    def __str__(self):
        return f"SearchResult({self.title[:50]}...)"

