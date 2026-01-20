import React, { useState, useEffect, useRef } from 'react';
import { createSearchTask, getSearchTask, getAllSearchTasks, getPdfUrl, updateTaskStatus } from '../services/api';

/**
 * NewsSearch component for searching news and displaying results.
 * 
 * Features:
 * - Input field for search keyword
 * - POST request to create search task
 * - Polling every 2 seconds to check task status
 * - Display spinner during processing
 * - Display results with PDF download links when completed
 * 
 * @returns {JSX.Element} The rendered NewsSearch component
 */
function NewsSearch() {
  const [keyword, setKeyword] = useState('');
  const [taskId, setTaskId] = useState(null);
  const [taskKeyword, setTaskKeyword] = useState(null); // Keyword of the current task being displayed
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeView, setActiveView] = useState('active'); // 'active', 'history'
  const [activeTasks, setActiveTasks] = useState([]);
  const [historyTasks, setHistoryTasks] = useState([]);
  const [expandedHistoryTaskId, setExpandedHistoryTaskId] = useState(null); // Track which history task is expanded
  const [historyPage, setHistoryPage] = useState(1); // Current page for history pagination
  const removedTaskIdsRef = useRef(new Set()); // Track manually removed task IDs
  const textareaRef = useRef(null);
  const pollingIntervalRef = useRef(null);

  // Load removed task IDs from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('removedTaskIds');
      if (saved) {
        const ids = JSON.parse(saved);
        removedTaskIdsRef.current = new Set(ids);
      }
    } catch (err) {
      console.error('Failed to load removed task IDs from localStorage:', err);
    }
  }, []);

  /**
   * Cleanup polling interval on unmount.
   */
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  /**
   * Load and filter tasks from the API.
   * Separates tasks into active and history based on status.
   * Removed tasks are excluded from active but remain in history.
   * 
   * @returns {Promise<void>}
   */
  const loadTasks = async () => {
    try {
      const tasks = await getAllSearchTasks();
      
      // Handle both array and object response formats
      const tasksArray = Array.isArray(tasks) ? tasks : (tasks.results || []);
      
      // Filter active tasks and move stuck tasks to history
      const now = new Date();
      const STUCK_TASK_TIMEOUT = 15 * 60 * 1000; // 15 minutes in milliseconds
      
      // Active tasks: pending/processing that are not removed and not stuck
      const active = tasksArray.filter(task => {
        // Don't include manually removed tasks in Active
        if (removedTaskIdsRef.current.has(task.id)) {
          return false;
        }
        
        if (task.status === 'pending' || task.status === 'processing') {
          // Check if task is stuck (older than 15 minutes)
          const taskAge = now - new Date(task.created_at);
          if (taskAge > STUCK_TASK_TIMEOUT) {
            // Task is stuck, move to history
            return false;
          }
          return true;
        }
        return false;
      });
      
      // Stuck tasks: pending/processing older than 15 minutes (not removed)
      const stuckTasks = tasksArray.filter(task => {
        // Don't include manually removed tasks
        if (removedTaskIdsRef.current.has(task.id)) {
          return false;
        }
        
        if (task.status === 'pending' || task.status === 'processing') {
          const taskAge = now - new Date(task.created_at);
          return taskAge > STUCK_TASK_TIMEOUT;
        }
        return false;
      }).map(task => ({ ...task, status: 'failed' }));
      
      // History: completed, failed, and stuck tasks (removed tasks remain in history)
      // Use Map to deduplicate by task ID to avoid duplicates
      const historyMap = new Map();
      
      // First, preserve ALL completed/failed tasks that are currently in local history
      // This prevents losing tasks during race conditions when server hasn't updated yet
      // We preserve them even if server doesn't return them (they might be in transition)
      historyTasks.forEach(task => {
        // Preserve all tasks that are in history (completed or failed)
        // This ensures we don't lose tasks when server data is temporarily out of sync
        if (task.status === 'completed' || task.status === 'failed') {
          historyMap.set(task.id, task);
        }
      });
      
      // Add completed and failed tasks from server (this will overwrite local ones with fresh server data)
      // Server data takes precedence as it's the source of truth
      tasksArray.filter(task => task.status === 'completed' || task.status === 'failed').forEach(task => {
        historyMap.set(task.id, task);
      });
      
      // Add stuck tasks (they may already be in map, so this will update them)
      stuckTasks.forEach(task => {
        historyMap.set(task.id, task);
      });
      
      // Convert map to array and sort by creation date (newest first)
      const history = Array.from(historyMap.values()).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      
      setActiveTasks(active);
      setHistoryTasks(history);
    } catch (err) {
      console.error('Failed to load tasks:', err);
      console.error('Error details:', err.response?.data || err.message);
    }
  };

  /**
   * Load active tasks and history when component mounts.
   */
  useEffect(() => {
    loadTasks();
  }, []);

  /**
   * Refresh tasks when viewing active/history tabs.
   */
  useEffect(() => {
    // Load tasks immediately when switching tabs
    if (activeView === 'active' || activeView === 'history') {
      // Use a small delay to avoid race conditions
      const timeoutId = setTimeout(() => {
        loadTasks();
      }, 100);
      // Then refresh every 5 seconds
      const interval = setInterval(() => {
        loadTasks();
      }, 5000);
      return () => {
        clearTimeout(timeoutId);
        clearInterval(interval);
      };
    }
  }, [activeView]);

  /**
   * Auto-resize textarea based on content.
   */
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [keyword]);

  /**
   * Reset history page if current page is out of bounds.
   */
  useEffect(() => {
    if (activeView === 'history' && historyTasks.length > 0) {
      const maxPage = Math.ceil(historyTasks.length / 3);
      if (historyPage > maxPage) {
        setHistoryPage(maxPage || 1);
      }
    }
  }, [historyTasks.length, activeView, historyPage]);

  /**
   * Cancel current search task.
   */
  const cancelSearch = async () => {
    if (!taskId) return;

    // Stop polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }

    // Update task status to 'failed' in the database
    try {
      await updateTaskStatus(taskId, 'failed');
    } catch (err) {
      console.error('Failed to cancel task in DB:', err);
    }

    // Reset state
    setIsLoading(false);
    setStatus('failed');
    setTaskId(null);
    setTaskKeyword(null);
    setResults([]);

    // Reload tasks to update the list
    await loadTasks();
  };

  /**
   * Handle search form submission or cancellation.
   * 
   * @param {Event} e - Form submit event
   */
  const handleSearch = async (e) => {
    e.preventDefault();
    
    // If search is in progress, cancel it
    if (isLoading || status === 'processing' || status === 'pending') {
      await cancelSearch();
      return;
    }
    
    if (!keyword.trim()) {
      setError('Please enter a keyword');
      return;
    }

    // Parse keyword and article count from input
    // Formats supported:
    // - "keyword, 5"
    // - "keyword, 5 статьи"
    // - "keyword, 5 статей"
    // - "keyword, 5 article"
    // - "keyword, 5 articles"
    // - "keyword" (defaults to 3)
    const input = keyword.trim();
    let searchKeyword = input;
    let articleCount = 3; // Default
    
    // Check if input contains a comma
    if (input.includes(',')) {
      const parts = input.split(',').map(p => p.trim());
      if (parts.length >= 2) {
        searchKeyword = parts[0].trim();
        const countPart = parts.slice(1).join(',').trim(); // Join in case there are multiple commas
        
        // Try to extract number from the count part
        // Match patterns like: "5", "5 статьи", "5 статей", "5 article", "5 articles", etc.
        const numberMatch = countPart.match(/^(\d+)\s*(?:статьи|статей|статья|article|articles)?\s*$/i);
        if (numberMatch) {
          const parsedCount = parseInt(numberMatch[1], 10);
          if (parsedCount > 0 && parsedCount <= 20) {
            articleCount = parsedCount;
          }
        }
      }
    } else {
      // If no comma, check if last word is a number (backward compatibility)
      const parts = input.split(/\s+/);
      if (parts.length > 1) {
        const lastPart = parts[parts.length - 1];
        // Check if it's just a number or number with text
        const numberMatch = lastPart.match(/^(\d+)\s*(?:статьи|статей|статья|article|articles)?\s*$/i);
        if (numberMatch) {
          const parsedCount = parseInt(numberMatch[1], 10);
          if (parsedCount > 0 && parsedCount <= 20) {
            articleCount = parsedCount;
            // Remove the number part from keyword
            searchKeyword = parts.slice(0, -1).join(' ').trim();
          }
        }
      }
    }
    
    if (!searchKeyword) {
      setError('Please enter a valid keyword');
      return;
    }

    // Switch to active view immediately when form is submitted
    setActiveView('active');
    // Reset history page when switching to active
    setHistoryPage(1);
    
    setIsLoading(true);
    setError(null);
    setStatus(null);
    setResults([]);
    setTaskId(null);
    setTaskKeyword(null);

    // Clear any existing polling interval
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }

    try {
      // Create search task with parsed keyword and article count
      const taskData = await createSearchTask(searchKeyword, articleCount);
      setTaskId(taskData.id);
      setTaskKeyword(taskData.keyword); // Save task keyword separately
      setStatus(taskData.status);

      // Update active tasks list
      setActiveTasks(prev => [...prev, taskData]);

      // Start polling for task status
      startPolling(taskData.id);
      
      // Don't reload tasks immediately after creating - let polling handle updates
      // This prevents race conditions where history gets overwritten before server updates
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create search task');
      setIsLoading(false);
    }
  };

  /**
   * Handle Enter key press (submit) or Shift+Enter (new line).
   * 
   * @param {KeyboardEvent} e - Keyboard event
   */
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && keyword.trim()) {
        handleSearch(e);
      }
    }
  };

  /**
   * Start polling for task status every 2 seconds.
   * 
   * @param {string} id - The task ID to poll
   */
  const startPolling = (id) => {
    // Clear any existing interval
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    // Poll immediately, then every 2 seconds
    pollTaskStatus(id);
    pollingIntervalRef.current = setInterval(() => {
      pollTaskStatus(id);
    }, 2000);
  };

  /**
   * Poll the backend for task status.
   * 
   * @param {string} id - The task ID to check
   */
  const pollTaskStatus = async (id) => {
    try {
      const taskData = await getSearchTask(id);
      setStatus(taskData.status);
      
      // Update task keyword if it's the current task
      if (taskId === id) {
        setTaskKeyword(taskData.keyword);
      }
      
      // Update task in active tasks list
      setActiveTasks(prev => prev.map(task => 
        task.id === id ? { ...task, ...taskData } : task
      ));

      if (taskData.status === 'completed') {
        // Stop polling
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        setIsLoading(false);
        
        // Don't remove from activeTasks immediately if it's the current task being viewed
        // Keep it visible in Active Searches until user switches to another task
        if (taskId === id) {
          // Keep the completed task in activeTasks so it remains visible
          setActiveTasks(prev => prev.map(task => 
            task.id === id ? { ...taskData, status: 'completed' } : task
          ));
        } else {
          // Move task from active to history if it's not the current task
          setActiveTasks(prev => prev.filter(task => task.id !== id));
        }
        
        // Always add to history
        setHistoryTasks(prev => {
          const exists = prev.find(task => task.id === id);
          if (exists) {
            return prev.map(task => task.id === id ? taskData : task);
          }
          return [taskData, ...prev].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        });
        
        // Reload tasks to sync with server
        await loadTasks();
        
        // Fetch and set results
        if (taskData.results && taskData.results.length > 0) {
          setResults(taskData.results);
        } else {
          setResults([]);
        }
        
        // Switch to active view when search completes
        setActiveView('active');
      } else if (taskData.status === 'failed') {
        // Stop polling on failure
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        setIsLoading(false);
        
        // Don't remove from activeTasks if it's the current task being viewed
        // Keep failed task visible in Active Searches until user switches
        if (taskId === id) {
          // Keep the failed task in activeTasks so it remains visible
          setActiveTasks(prev => prev.map(task => 
            task.id === id ? { ...taskData, status: 'failed' } : task
          ));
        } else {
          // Move task from active to history if it's not the current task
          setActiveTasks(prev => prev.filter(task => task.id !== id));
        }
        
        // Always add to history
        setHistoryTasks(prev => {
          const exists = prev.find(task => task.id === id);
          if (exists) {
            return prev.map(task => task.id === id ? taskData : task);
          }
          return [taskData, ...prev].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        });
        
        // Reload tasks to sync with server after a short delay
        // This ensures the server has fully processed the task status change
        setTimeout(() => {
          loadTasks();
        }, 300);
        
        const errorMsg = taskData.error_message 
          ? `Search task failed: ${taskData.error_message}` 
          : 'Search task failed. Please check Celery worker logs or try again.';
        setError(errorMsg);
      }
      // If status is 'processing' or 'pending', continue polling
    } catch (err) {
      // On error, stop polling
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      setIsLoading(false);
      setError(err.response?.data?.detail || err.message || 'Failed to fetch task status');
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto flex flex-col items-center">
      {/* Welcome Message - Always Visible */}
      <div className="flex-shrink-0 w-full flex flex-col items-center">
        {!error && (
          <>
            {/* InfoSeek Logo Text */}
            <div className="flex items-center justify-center mb-6 w-full">
              <h1 className="text-[#5686fe] font-semibold text-7xl tracking-tighter" style={{ fontFamily: 'Silkscreen, monospace', letterSpacing: '-0.04em', fontWeight: 700, lineHeight: '1.1' }}>
                infoseek
              </h1>
            </div>
            
            <div className="flex items-center justify-center gap-3 mb-6">
              <div className="flex-shrink-0">
                <img
                  src="/infoseek_logo.png"
                  alt="InfoSeek Logo"
                  className="w-20 h-20 object-contain"
                />
              </div>
              <div className="text-white/90 font-semibold text-center" style={{ fontFamily: 'Inter, system-ui, -apple-system, sans-serif', fontSize: '24px' }}>Which word are we looking for today?</div>
            </div>
          </>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-6 text-center backdrop-blur-sm">
            {error}
          </div>
        )}

        {/* Search Input Section - Always Visible */}
        <form onSubmit={handleSearch} className="relative w-full">
          <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 focus-within:border-blue-500/50 focus-within:ring-2 focus-within:ring-blue-500/50 transition-all duration-200">
            {/* Textarea Row */}
            <div className="px-4 pt-3">
              <textarea
                ref={textareaRef}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message InfoSeek"
                rows={2}
                className="w-full bg-transparent text-white placeholder-white/40 resize-none focus:outline-none text-base leading-6 py-2"
                disabled={isLoading || status === 'processing'}
                style={{ minHeight: '44px', maxHeight: '200px' }}
              />
            </div>
            
            {/* Tip Section */}
            <div className="px-4 pb-2">
              <div className="flex items-start gap-2 mt-2">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-blue-400/80 mt-0.5 flex-shrink-0">
                  <path d="M8 1C4.13401 1 1 4.13401 1 8C1 11.866 4.13401 15 8 15C11.866 15 15 11.866 15 8C15 4.13401 11.866 1 8 1ZM8 13.5C4.96243 13.5 2.5 11.0376 2.5 8C2.5 4.96243 4.96243 2.5 8 2.5C11.0376 2.5 13.5 4.96243 13.5 8C13.5 11.0376 11.0376 13.5 8 13.5Z" fill="currentColor"/>
                  <path d="M8 5C7.58579 5 7.25 5.33579 7.25 5.75V8.25C7.25 8.66421 7.58579 9 8 9C8.41421 9 8.75 8.66421 8.75 8.25V5.75C8.75 5.33579 8.41421 5 8 5Z" fill="currentColor"/>
                  <path d="M8 10.5C8.41421 10.5 8.75 10.1642 8.75 9.75C8.75 9.33579 8.41421 9 8 9C7.58579 9 7.25 9.33579 7.25 9.75C7.25 10.1642 7.58579 10.5 8 10.5Z" fill="currentColor"/>
                </svg>
                <div className="flex-1">
                  <p className="text-xs text-white/60 leading-relaxed">
                    <span className="text-white/80 font-medium">Tip:</span> Use format <span className="text-blue-400/90 font-mono">keyword, count</span> to specify number of articles. Examples: <span className="text-blue-400/90 font-mono">Chopin, 5 </span> or <span className="text-blue-400/90 font-mono">Economy, 10 статей</span>
                  </p>
                </div>
              </div>
            </div>
            
            {/* Active, History Buttons and Submit Button - Bottom Row */}
            <div className="flex items-center justify-between px-4 pb-3">
              <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveView('active')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 border ${
                  activeView === 'active'
                    ? 'bg-white/10 text-white border-white/20 backdrop-blur-sm'
                    : 'bg-transparent text-white/60 border-white/10 hover:bg-white/5 hover:text-white/80'
                }`}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path fillRule="evenodd" clipRule="evenodd" d="M7 0.150391C10.7832 0.150391 13.8496 3.21685 13.8496 7C13.8496 10.7832 10.7832 13.8496 7 13.8496C3.21685 13.8496 0.150391 10.7832 0.150391 7C0.150391 3.21685 3.21685 0.150391 7 0.150391ZM5.37793 7.59961C5.42667 9.03204 5.64751 10.2965 5.97363 11.2197C6.15993 11.7471 6.36943 12.1301 6.57324 12.3701C6.77748 12.6105 6.9234 12.6504 7 12.6504C7.0766 12.6504 7.22252 12.6105 7.42676 12.3701C7.63057 12.1301 7.84007 11.7471 8.02637 11.2197C8.35249 10.2965 8.57333 9.03204 8.62207 7.59961H5.37793ZM1.38184 7.59961C1.61453 9.80492 3.1159 11.6304 5.14258 12.3359C5.03265 12.1128 4.93224 11.8724 4.84277 11.6191C4.46339 10.5451 4.22772 9.13988 4.17871 7.59961H1.38184ZM9.82129 7.59961C9.77228 9.13988 9.53661 10.5451 9.15723 11.6191C9.06771 11.8726 8.96645 12.1127 8.85645 12.3359C10.8836 11.6307 12.3854 9.80524 12.6182 7.59961H9.82129ZM7 1.34961C6.9234 1.34961 6.77748 1.38949 6.57324 1.62988C6.36943 1.86988 6.15993 2.25291 5.97363 2.78027C5.64751 3.70351 5.42667 4.96796 5.37793 6.40039H8.62207C8.57333 4.96796 8.35249 3.70351 8.02637 2.78027C7.84007 2.25291 7.63057 1.86988 7.42676 1.62988C7.22252 1.38949 7.0766 1.34961 7 1.34961ZM8.85645 1.66309C8.9666 1.88656 9.0676 2.12715 9.15723 2.38086C9.53661 3.45487 9.77228 4.86012 9.82129 6.40039H12.6182C12.3854 4.19465 10.8837 2.36828 8.85645 1.66309ZM5.14258 1.66309C3.11575 2.3685 1.61454 4.19497 1.38184 6.40039H4.17871C4.22772 4.86012 4.46339 3.45487 4.84277 2.38086C4.93234 2.1273 5.03249 1.88645 5.14258 1.66309Z" fill="currentColor"></path>
                </svg>
                <span>Active ({activeTasks.length})</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveView('history');
                  setHistoryPage(1); // Reset to first page when switching to history
                }}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 border ${
                  activeView === 'history'
                    ? 'bg-white/10 text-white border-white/20 backdrop-blur-sm'
                    : 'bg-transparent text-white/60 border-white/10 hover:bg-white/5 hover:text-white/80'
                }`}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M7.06428 5.93342C7.6876 5.93342 8.19304 6.43904 8.19319 7.06233C8.19319 7.68573 7.68769 8.19123 7.06428 8.19123C6.44096 8.19113 5.93537 7.68567 5.93537 7.06233C5.93552 6.43911 6.44105 5.93353 7.06428 5.93342Z" fill="currentColor"></path>
                  <path fillRule="evenodd" clipRule="evenodd" d="M8.68147 0.963693C10.1168 0.447019 11.6266 0.374829 12.5633 1.31135C13.5 2.24805 13.4276 3.75776 12.911 5.19319C12.7126 5.74431 12.4385 6.31796 12.0965 6.89729C12.4969 7.54638 12.8141 8.19018 13.036 8.80647C13.5527 10.2419 13.625 11.7516 12.6883 12.6883C11.7516 13.625 10.2419 13.5527 8.80647 13.036C8.19019 12.8141 7.54638 12.4969 6.89729 12.0965C6.31794 12.4386 5.74432 12.7125 5.19319 12.911C3.75774 13.4276 2.24807 13.5 1.31135 12.5633C0.374829 11.6266 0.447019 10.1168 0.963693 8.68147C1.17182 8.10338 1.46318 7.50063 1.82893 6.8924C1.52179 6.35711 1.27232 5.82825 1.08869 5.31819C0.572038 3.88278 0.499683 2.37306 1.43635 1.43635C2.37304 0.499655 3.88277 0.572044 5.31819 1.08869C5.82825 1.27232 6.35712 1.5218 6.8924 1.82893C7.50063 1.46318 8.10338 1.17181 8.68147 0.963693ZM11.3572 8.01154C10.9083 8.62253 10.3901 9.22873 9.8094 9.8094C9.22874 10.3901 8.62252 10.9083 8.01154 11.3572C8.42567 11.5841 8.82867 11.7688 9.21272 11.9071C10.5455 12.3868 11.4246 12.2547 11.8397 11.8397C12.2547 11.4246 12.3869 10.5456 11.9071 9.21272C11.7688 8.82866 11.5841 8.42568 11.3572 8.01154ZM2.56526 8.02912C2.3734 8.39322 2.21492 8.74796 2.0926 9.08772C1.61288 10.4204 1.74509 11.2995 2.15998 11.7147C2.57502 12.1297 3.45412 12.2618 4.78694 11.7821C5.11053 11.6656 5.44783 11.5164 5.79377 11.3367C5.24897 10.9223 4.70919 10.4533 4.19026 9.9344C3.57575 9.31987 3.03166 8.67633 2.56526 8.02912ZM6.90705 3.2469C6.24062 3.70479 5.56457 4.26321 4.91389 4.91389C4.26322 5.56456 3.70479 6.24063 3.2469 6.90705C3.72671 7.63325 4.32774 8.37459 5.03889 9.08576C5.6494 9.69627 6.2818 10.2265 6.90803 10.6678C7.59365 10.2025 8.29077 9.63076 8.96076 8.96076C9.63077 8.29075 10.2025 7.59366 10.6678 6.90803C10.2265 6.2818 9.69628 5.6494 9.08576 5.03889C8.37459 4.32773 7.63325 3.72672 6.90705 3.2469ZM11.7147 2.15998C11.2995 1.74509 10.4204 1.61288 9.08772 2.0926C8.74832 2.21479 8.39379 2.37271 8.0301 2.56428C8.67725 3.03065 9.31992 3.5758 9.9344 4.19026C10.4533 4.7092 10.9223 5.24896 11.3367 5.79377C11.5164 5.44785 11.6656 5.11052 11.7821 4.78694C12.2618 3.45416 12.1297 2.57502 11.7147 2.15998ZM4.91194 2.2176C3.57918 1.73788 2.70001 1.86995 2.28498 2.28498C1.86998 2.70003 1.73788 3.5792 2.2176 4.91194C2.31706 5.18822 2.44109 5.47427 2.58674 5.7674C3.01928 5.1887 3.51471 4.6158 4.06526 4.06526C4.61581 3.5147 5.18869 3.01928 5.7674 2.58674C5.47428 2.4411 5.18821 2.31706 4.91194 2.2176Z" fill="currentColor"></path>
                </svg>
                <span>History ({historyTasks.length})</span>
              </button>
            </div>
            
            {/* Submit/Cancel Button - Circular Blue */}
              <button
                type="submit"
                disabled={!keyword.trim() && !(isLoading || status === 'processing' || status === 'pending')}
                className="w-8 h-8 rounded-full bg-[#5686fe] text-white flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-[#5686fe] hover:bg-[#4578e8] hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                title={(isLoading || status === 'processing' || status === 'pending') ? 'Cancel search (Enter)' : 'Send message (Enter)'}
              >
                {(isLoading || status === 'processing' || status === 'pending') ? (
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="2" y="2" width="8" height="8" rx="1" fill="currentColor"/>
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M8.3125 0.981587C8.66767 1.0545 8.97902 1.20558 9.2627 1.43374C9.48724 1.61438 9.73029 1.85933 9.97949 2.10854L14.707 6.83608L13.293 8.25014L9 3.95717V15.0431H7V3.95717L2.70703 8.25014L1.29297 6.83608L6.02051 2.10854C6.26971 1.85933 6.51277 1.61438 6.7373 1.43374C6.97662 1.24126 7.28445 1.04542 7.6875 0.981587C7.8973 0.94841 8.1031 0.956564 8.3125 0.981587Z" fill="currentColor"></path>
                  </svg>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Active Tasks View - Below Input */}
      <div className="w-full max-w-3xl mt-4 h-[450px] flex flex-col">
        {activeView === 'active' && (
          <>
            {activeTasks.length === 0 && !taskId ? null : (
              <>
                <h2 className="text-xl font-semibold text-white mb-3">Active Searches</h2>
                <div className="space-y-2 flex-1 overflow-y-auto">
              {/* Show current task if exists (even if completed, keep it visible) */}
              {taskId && (() => {
                const currentTask = activeTasks.find(t => t.id === taskId);
                const taskCreatedAt = currentTask?.created_at || new Date().toISOString();
                return (
                  <div className="bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg p-3 transition-all duration-200 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="text-base font-medium text-white mb-0.5">
                          {taskKeyword || keyword}
                          {status === 'completed' && results.length > 0 && (
                            <span className="text-white/60 font-normal">, {results.length} {results.length === 1 ? 'article' : 'articles'}</span>
                          )}
                        </h3>
                        <div className="flex items-center gap-2 text-xs">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            status === 'processing' 
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                              : status === 'completed'
                              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                              : status === 'failed'
                              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                              : 'bg-white/10 text-white/60 border border-white/10'
                          }`}>
                            {status === 'processing' ? 'Processing...' : 
                             status === 'completed' ? 'Completed' :
                             status === 'failed' ? 'Failed' :
                             'Pending'}
                          </span>
                          <span className="text-white/50 text-xs">
                            {new Date(taskCreatedAt).toLocaleString()}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={async () => {
                            // Stop polling if this task is being polled
                            if (pollingIntervalRef.current) {
                              clearInterval(pollingIntervalRef.current);
                              pollingIntervalRef.current = null;
                            }
                            
                            // Clear taskId
                            setTaskId(null);
                            setStatus(null);
                            setResults([]);
                            setTaskKeyword(null);
                            
                            // Update task status to 'failed' in the database
                            try {
                              await updateTaskStatus(taskId, 'failed');
                            } catch (err) {
                              console.error('Failed to update task status in DB:', err);
                            }
                            
                            // Mark task as removed so it won't come back to Active from API updates
                            removedTaskIdsRef.current.add(taskId);
                            
                            // Save to localStorage for persistence across page reloads
                            try {
                              localStorage.setItem('removedTaskIds', JSON.stringify(Array.from(removedTaskIdsRef.current)));
                            } catch (err) {
                              console.error('Failed to save removed task IDs to localStorage:', err);
                            }
                            
                            // Reload tasks to get updated status from DB (task will appear in History)
                            await loadTasks();
                          }}
                          className="w-8 h-8 flex items-center justify-center bg-transparent text-[#f25a5a] rounded transition-colors"
                          title="Remove task"
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                        <button
                          onClick={() => {
                            // View button is disabled during processing/pending
                            if (status === 'processing' || status === 'pending') {
                              return;
                            }
                            // Already viewing this task, no action needed
                          }}
                          disabled={status === 'processing' || status === 'pending'}
                          className={`w-8 h-8 flex items-center justify-center bg-transparent rounded transition-colors ${
                            status === 'processing' || status === 'pending'
                              ? 'text-white/30 cursor-not-allowed opacity-50'
                              : 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/10'
                          }`}
                          title={status === 'processing' || status === 'pending' ? 'View unavailable during processing' : 'View task'}
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M8 3C4.5 3 1.73 5.11 0 8C1.73 10.89 4.5 13 8 13C11.5 13 14.27 10.89 16 8C14.27 5.11 11.5 3 8 3ZM8 11C6.34 11 5 9.66 5 8C5 6.34 6.34 5 8 5C9.66 5 11 6.34 11 8C11 9.66 9.66 11 8 11ZM8 6.5C7.17 6.5 6.5 7.17 6.5 8C6.5 8.83 7.17 9.5 8 9.5C8.83 9.5 9.5 8.83 9.5 8C9.5 7.17 8.83 6.5 8 6.5Z" fill="currentColor"/>
                          </svg>
                        </button>
                      </div>
                    </div>
                  
                  {/* Show results if completed */}
                  {status === 'completed' && (
                    <div className="mt-2 space-y-2">
                      {results.length === 0 ? (
                        <p className="text-white/60 text-sm">No results found.</p>
                      ) : (
                        <>
                          <p className="text-white/80 mb-2 text-sm">Found {results.length} result{results.length !== 1 ? 's' : ''}:</p>
                          {results.map((result) => (
                            <div
                              key={result.id}
                              className="border border-white/10 rounded-lg p-2 bg-white/5 hover:bg-white/10 transition-all duration-200 backdrop-blur-sm"
                            >
                              <h4 className="text-sm font-medium text-white/90 mb-1.5">
                                {result.title}
                              </h4>
                              <div className="flex items-center justify-between gap-3 flex-wrap">
                                <a
                                  href={result.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-400 hover:text-blue-300 text-xs truncate flex-1 min-w-0 transition-colors"
                                >
                                  {result.source_url}
                                </a>
                                {result.pdf_file && (
                                  <a
                                    href={getPdfUrl(result.pdf_file)}
                                    download
                                    className="px-3 py-1.5 bg-[#22c55e] text-white rounded flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-[#22c55e] transition-colors text-xs font-medium"
                                    title="Download PDF"
                                  >
                                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                      <path d="M3 2C2.44772 2 2 2.44772 2 3V13C2 13.5523 2.44772 14 3 14H13C13.5523 14 14 13.5523 14 13V3C14 2.44772 13.5523 2 13 2H3ZM3.5 3H12.5V13H3.5V3ZM4 4V12H12V4H4ZM5 5H11V6H5V5ZM5 7H11V8H5V7ZM5 9H8V10H5V9Z" fill="currentColor"/>
                                    </svg>
                                    <span>PDF</span>
                                  </a>
                                )}
                              </div>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}
                </div>
                );
              })()}
              
              {/* Show other active tasks */}
              {activeTasks.filter(task => !taskId || task.id !== taskId).map((task) => {
                const taskAge = new Date() - new Date(task.created_at);
                const isStuck = taskAge > 15 * 60 * 1000; // 15 minutes
                
                return (
                  <div
                    key={task.id}
                    className="bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg p-3 transition-all duration-200 backdrop-blur-sm"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h3 className="text-base font-medium text-white mb-0.5">
                          {task.keyword}
                          {task.status === 'processing' && (
                            <span className="text-white/60 font-normal">, processing...</span>
                          )}
                        </h3>
                        <div className="flex items-center gap-2 text-xs">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            task.status === 'processing' 
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                              : 'bg-white/10 text-white/60 border border-white/10'
                          }`}>
                            {task.status === 'processing' ? 'Processing...' : 'Pending'}
                          </span>
                          <span className="text-white/50 text-xs">
                            {new Date(task.created_at).toLocaleString()}
                          </span>
                          {isStuck && (
                            <span className="text-red-400 text-xs">
                              (Stuck)
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={async () => {
                            // Stop polling if this task is being polled
                            if (taskId === task.id && pollingIntervalRef.current) {
                              clearInterval(pollingIntervalRef.current);
                              pollingIntervalRef.current = null;
                            }
                            
                            // Clear taskId if this is the current task
                            if (taskId === task.id) {
                              setTaskId(null);
                              setStatus(null);
                              setResults([]);
                              setTaskKeyword(null);
                            }
                            
                            // Update task status to 'failed' in the database
                            try {
                              await updateTaskStatus(task.id, 'failed');
                            } catch (err) {
                              console.error('Failed to update task status in DB:', err);
                            }
                            
                            // Mark task as removed so it won't come back to Active from API updates
                            removedTaskIdsRef.current.add(task.id);
                            
                            // Save to localStorage for persistence across page reloads
                            try {
                              localStorage.setItem('removedTaskIds', JSON.stringify(Array.from(removedTaskIdsRef.current)));
                            } catch (err) {
                              console.error('Failed to save removed task IDs to localStorage:', err);
                            }
                            
                            // Reload tasks to get updated status from DB (task will appear in History)
                            await loadTasks();
                          }}
                          className="w-8 h-8 flex items-center justify-center bg-transparent text-red-400 hover:text-red-300 rounded transition-colors hover:bg-red-500/10"
                          title="Remove task"
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                        <button
                          onClick={() => {
                            // View button is disabled during processing/pending
                            if (task.status === 'processing' || task.status === 'pending') {
                              return;
                            }
                            setTaskId(task.id);
                            setStatus(task.status);
                            setTaskKeyword(task.keyword);
                            if (task.results) {
                              setResults(task.results);
                            }
                          }}
                          disabled={task.status === 'processing' || task.status === 'pending'}
                          className={`w-8 h-8 flex items-center justify-center bg-transparent rounded transition-colors ${
                            task.status === 'processing' || task.status === 'pending'
                              ? 'text-white/30 cursor-not-allowed opacity-50'
                              : 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/10'
                          }`}
                          title={task.status === 'processing' || task.status === 'pending' ? 'View unavailable during processing' : 'View task'}
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M8 3C4.5 3 1.73 5.11 0 8C1.73 10.89 4.5 13 8 13C11.5 13 14.27 10.89 16 8C14.27 5.11 11.5 3 8 3ZM8 11C6.34 11 5 9.66 5 8C5 6.34 6.34 5 8 5C9.66 5 11 6.34 11 8C11 9.66 9.66 11 8 11ZM8 6.5C7.17 6.5 6.5 7.17 6.5 8C6.5 8.83 7.17 9.5 8 9.5C8.83 9.5 9.5 8.83 9.5 8C9.5 7.17 8.83 6.5 8 6.5Z" fill="currentColor"/>
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
                </div>
              </>
            )}
          </>
        )}

        {/* History View - Below Input */}
        {activeView === 'history' && (
          <>
            {historyTasks.length === 0 ? null : (
              <>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xl font-semibold text-white">Search History</h2>
                  {historyTasks.length > 3 && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setHistoryPage(prev => Math.max(1, prev - 1))}
                        disabled={historyPage === 1}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 border ${
                          historyPage === 1
                            ? 'bg-transparent text-white/40 border-white/10 cursor-not-allowed opacity-50'
                            : 'bg-white/10 text-white border-white/20 hover:bg-white/20 backdrop-blur-sm'
                        }`}
                        title="Previous page"
                      >
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M10 12L6 8L10 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      </button>
                      <span className="text-white/60 text-sm px-2">
                        {historyPage} / {Math.ceil(historyTasks.length / 3)}
                      </span>
                      <button
                        onClick={() => setHistoryPage(prev => Math.min(Math.ceil(historyTasks.length / 3), prev + 1))}
                        disabled={historyPage >= Math.ceil(historyTasks.length / 3)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 border ${
                          historyPage >= Math.ceil(historyTasks.length / 3)
                            ? 'bg-transparent text-white/40 border-white/10 cursor-not-allowed opacity-50'
                            : 'bg-white/10 text-white border-white/20 hover:bg-white/20 backdrop-blur-sm'
                        }`}
                        title="Next page"
                      >
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M6 4L10 8L6 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      </button>
                    </div>
                  )}
                </div>
                <div className="space-y-2 flex-1 overflow-y-auto">
              {historyTasks.slice((historyPage - 1) * 3, historyPage * 3).map((task) => {
                const isExpanded = expandedHistoryTaskId === task.id;
                return (
                  <div
                    key={task.id}
                    className="bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg p-3 transition-all duration-200 backdrop-blur-sm"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h3 className="text-base font-medium text-white mb-0.5">
                          {task.keyword}
                          {task.results && task.results.length > 0 && (
                            <span className="text-white/60 font-normal">, {task.results.length} {task.results.length === 1 ? 'article' : 'articles'}</span>
                          )}
                        </h3>
                        <div className="flex items-center gap-2 text-xs">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            task.status === 'completed' 
                              ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                              : 'bg-red-500/20 text-red-400 border border-red-500/30'
                          }`}>
                            {task.status === 'completed' ? 'Completed' : 'Failed'}
                          </span>
                          <span className="text-white/50 text-xs">
                            {new Date(task.created_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          if (isExpanded) {
                            setExpandedHistoryTaskId(null);
                          } else {
                            setExpandedHistoryTaskId(task.id);
                            // Don't set taskId here - it's only for Active tab
                            // We use expandedHistoryTaskId to track expanded state in History
                          }
                        }}
                        className="w-8 h-8 flex items-center justify-center bg-transparent text-blue-400 hover:text-blue-300 rounded transition-colors hover:bg-blue-500/10"
                        title={isExpanded ? 'Hide' : 'View'}
                      >
                        {isExpanded ? (
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M8 5L3 10H13L8 5Z" fill="currentColor"/>
                          </svg>
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M8 11L3 6H13L8 11Z" fill="currentColor"/>
                          </svg>
                        )}
                      </button>
                    </div>
                    
                    {/* Expanded Results Section */}
                    {isExpanded && task.results && task.results.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-white/10 space-y-2">
                        <p className="text-white/80 mb-2 text-sm">Found {task.results.length} result{task.results.length !== 1 ? 's' : ''}:</p>
                        {task.results.map((result) => (
                          <div
                            key={result.id}
                            className="border border-white/10 rounded-lg p-2 bg-white/5 hover:bg-white/10 transition-all duration-200 backdrop-blur-sm"
                          >
                            <h4 className="text-sm font-medium text-white/90 mb-1.5">
                              {result.title}
                            </h4>
                            <div className="flex items-center justify-between gap-3 flex-wrap">
                              <a
                                href={result.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-400 hover:text-blue-300 text-xs truncate flex-1 min-w-0 transition-colors"
                              >
                                {result.source_url}
                              </a>
                              {result.pdf_file && (
                                <a
                                  href={getPdfUrl(result.pdf_file)}
                                  download
                                  className="px-3 py-1.5 bg-[#22c55e] text-white rounded flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-[#22c55e] transition-colors text-xs font-medium"
                                  title="Download PDF"
                                >
                                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M3 2C2.44772 2 2 2.44772 2 3V13C2 13.5523 2.44772 14 3 14H13C13.5523 14 14 13.5523 14 13V3C14 2.44772 13.5523 2 13 2H3ZM3.5 3H12.5V13H3.5V3ZM4 4V12H12V4H4ZM5 5H11V6H5V5ZM5 7H11V8H5V7ZM5 9H8V10H5V9Z" fill="currentColor"/>
                                  </svg>
                                  <span>PDF</span>
                                </a>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Show message if no results */}
                    {isExpanded && (!task.results || task.results.length === 0) && (
                      <div className="mt-3 pt-3 border-t border-[#353638]">
                        <p className="text-[#adb2b8] text-sm">No results found.</p>
                      </div>
                    )}
                  </div>
                );
              })}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default NewsSearch;

