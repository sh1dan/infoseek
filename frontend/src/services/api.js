import axios from 'axios';

/**
 * API service for communicating with the Django backend.
 */
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Create a new search task.
 * 
 * @param {string} keyword - The search keyword
 * @param {number} articleCount - Number of articles to scrape (optional, defaults to 3)
 * @returns {Promise<Object>} The created task with task_id
 */
export const createSearchTask = async (keyword, articleCount = 3) => {
  const response = await api.post('/api/tasks/', { keyword, article_count: articleCount });
  return response.data;
};

/**
 * Get a search task by ID.
 * 
 * @param {string} taskId - The task UUID
 * @returns {Promise<Object>} The task object with status and results
 */
export const getSearchTask = async (taskId) => {
  const response = await api.get(`/api/tasks/${taskId}/`);
  return response.data;
};

/**
 * Get all search tasks.
 * 
 * @returns {Promise<Array>} Array of all search tasks
 */
export const getAllSearchTasks = async () => {
  const response = await api.get('/api/tasks/');
  return response.data;
};

/**
 * Update a search task status.
 * 
 * @param {string} taskId - The task UUID
 * @param {string} status - The new status ('pending', 'processing', 'completed', 'failed')
 * @returns {Promise<Object>} The updated task object
 */
export const updateTaskStatus = async (taskId, status) => {
  const response = await api.patch(`/api/tasks/${taskId}/`, { status });
  return response.data;
};

/**
 * Get the media URL for a PDF file.
 * 
 * @param {string} pdfPath - The relative path to the PDF file (or full URL)
 * @returns {string} The full URL to the PDF file
 */
export const getPdfUrl = (pdfPath) => {
  if (!pdfPath) return '';
  
  // If it's already a full URL, extract the relative path
  if (pdfPath.startsWith('http://') || pdfPath.startsWith('https://')) {
    // Extract path after /media/
    const mediaIndex = pdfPath.indexOf('/media/');
    if (mediaIndex !== -1) {
      pdfPath = pdfPath.substring(mediaIndex + '/media/'.length);
    } else {
      // If no /media/ found, try to extract just the filename
      const lastSlash = pdfPath.lastIndexOf('/');
      if (lastSlash !== -1) {
        pdfPath = pdfPath.substring(lastSlash + 1);
      }
    }
  }
  
  // Remove leading slash if present to avoid double slashes
  const cleanPath = pdfPath.startsWith('/') ? pdfPath.slice(1) : pdfPath;
  
  // Remove /media/ prefix if it exists
  const finalPath = cleanPath.startsWith('media/') ? cleanPath.substring('media/'.length) : cleanPath;
  
  return `${API_BASE_URL}/media/${finalPath}`;
};

export default api;

