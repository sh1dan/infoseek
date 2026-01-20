"""
Celery tasks for the search app.
"""
import os
import base64
import uuid
import time
import logging
from urllib.parse import urlparse, parse_qs
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from .models import SearchTask, SearchResult

logger = logging.getLogger('search')


def extract_article_content(driver: WebDriver) -> dict:
    """
    Extract article title, author, and clean text content from the current page.
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        dict: Dictionary with 'title', 'author', and 'content' keys
    """
    try:
        # Extract title - try multiple selectors
        title = ""
        title_selectors = [
            'h1',
            '.content-part__top h1',
            'article h1',
            '[class*="content-part"] h1',
            '.article-title',
            'h1.article-title',
        ]
        
        for selector in title_selectors:
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, selector)
                title = title_elem.text.strip()
                if title:
                    logger.info(f"Found title with selector: {selector}")
                    break
            except NoSuchElementException:
                continue
        
        if not title:
            logger.warning("Could not find article title")
        
        # Extract author - try multiple selectors
        author = ""
        author_selectors = [
            '[class*="author"]',
            '[class*="content-part__author"]',
            '.article-author',
            '[itemprop="author"]',
            'meta[property="article:author"]',
        ]
        
        for selector in author_selectors:
            try:
                if selector.startswith('meta'):
                    author_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    author = author_elem.get_attribute('content') or ""
                else:
                    author_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    author = author_elem.text.strip()
                if author:
                    logger.info(f"Found author with selector: {selector}")
                    break
            except NoSuchElementException:
                continue
        
        if not author:
            logger.info("Could not find article author, using default")
            author = "Radio ZET"
        
        # Extract main article content - look for the specific sections
        content = ""
        content_selectors = [
            '.full-width-depends-on-screening__container.content-part__top',
            '.full-width-depends-on-screening__container.full-content__main',
            'section.content-part__top__left',
            'section.full-content__main__left',
            'article',
            '[class*="content-part"]',
            '[class*="full-content"]',
        ]
        
        # Try to get content from the main article sections
        content_parts = []
        for selector in content_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    # Get text content, excluding ads and unwanted elements
                    text = driver.execute_script("""
                        const el = arguments[0];
                        // Clone to avoid modifying original
                        const clone = el.cloneNode(true);
                        
                        // Remove unwanted elements from clone
                        const unwanted = clone.querySelectorAll(`
                            [class*="reklama"],
                            [id*="reklama"],
                            [class*="advertisement"],
                            [id*="google_ads"],
                            [class*="onnetwork"],
                            [data-adv-display-type],
                            [class*="share"],
                            [class*="reaction"],
                            [class*="recommended"],
                            [class*="related"],
                            [class*="stories"],
                            [class*="radio-program"],
                            [class*="content-part__tags"],
                            iframe,
                            [class*="advert"]
                        `);
                        unwanted.forEach(item => item.remove());
                        
                        // Get clean text
                        return clone.innerText || clone.textContent || '';
                    """, elem)
                    
                    if text and len(text.strip()) > 100:  # Only add if substantial content
                        content_parts.append(text.strip())
                        logger.info(f"Found content section with selector: {selector}, length: {len(text)}")
            except Exception as e:
                logger.debug(f"Error extracting content with selector {selector}: {str(e)}")
                continue
        
        # Combine all content parts
        if content_parts:
            content = "\n\n".join(content_parts)
        else:
            # Fallback: get all paragraph text
            try:
                paragraphs = driver.find_elements(By.CSS_SELECTOR, 'article p, .article-content p, [class*="content"] p')
                content = "\n\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
            except Exception as e:
                logger.warning(f"Could not extract article content: {str(e)}")
        
        if not content or len(content.strip()) < 200:
            logger.warning(f"Extracted content seems too short: {len(content) if content else 0} chars")
        
        return {
            'title': title,
            'author': author,
            'content': content
        }
        
    except Exception as e:
        logger.error(f"Error extracting article content: {str(e)}")
        return {
            'title': '',
            'author': 'Radio ZET',
            'content': ''
        }


def create_clean_html(title: str, author: str, content: str) -> str:
    """
    Create a clean HTML structure with minimal CSS for reading.
    
    Args:
        title: Article title
        author: Article author
        content: Article content text
    
    Returns:
        str: Clean HTML string
    """
    # Escape HTML entities
    import html
    title_escaped = html.escape(title)
    author_escaped = html.escape(author)
    
    # Convert content to paragraphs (split by double newlines)
    content_paragraphs = content.split('\n\n')
    content_html = '\n'.join([f'<p>{html.escape(p.strip())}</p>' for p in content_paragraphs if p.strip()])
    
    clean_html = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title_escaped}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #ffffff;
                padding: 40px 20px;
                max-width: 800px;
                margin: 0 auto;
            }}
            h1 {{
                font-size: 2em;
                font-weight: 700;
                margin-bottom: 20px;
                color: #1a1a1a;
                line-height: 1.2;
            }}
            .author {{
                font-size: 0.9em;
                color: #666;
                margin-bottom: 30px;
                font-style: italic;
            }}
            .content {{
                font-size: 1.1em;
                line-height: 1.8;
            }}
            .content p {{
                margin-bottom: 1.2em;
                text-align: justify;
            }}
            .content p:last-child {{
                margin-bottom: 0;
            }}
        </style>
    </head>
    <body>
        <h1>{title_escaped}</h1>
        <div class="author">{author_escaped}</div>
        <div class="content">
            {content_html}
        </div>
    </body>
    </html>
    """
    return clean_html


def extract_and_save_pdf_nuclear_swap(driver: WebDriver, output_path: str, source_url: str = None) -> dict:
    """
    Extract article content using Nuclear Swap method and save as PDF.
    
    This method:
    1. Extracts text from <p> tags inside the main article container
    2. Creates a clean HTML template with embedded CSS
    3. Overwrites the entire page using document.write (Nuclear Swap)
    4. Prints the clean page to PDF
    
    Args:
        driver: Selenium WebDriver instance
        output_path: Full path where the PDF should be saved
        source_url: Original article URL (optional, will use driver.current_url if not provided)
    
    Returns:
        dict: Dictionary with 'title', 'author', and 'content' keys
    """
    import html as html_escape
    
    try:
        # 1. Extract data while still on the original site
        # Save original URL before Nuclear Swap (must be done first!)
        original_url = source_url if source_url else driver.current_url
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        
        # Extract title
        title = ""
        try:
            title_elem = driver.find_element(By.TAG_NAME, "h1")
            title = title_elem.text.strip()
        except NoSuchElementException:
            logger.warning("Could not find h1 tag, trying alternative selectors")
            title_selectors = [
                '.content-part__top h1',
                'article h1',
                '[class*="content-part"] h1',
                '.article-title',
            ]
            for selector in title_selectors:
                try:
                    title_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    title = title_elem.text.strip()
                    if title:
                        break
                except:
                    continue
        
        if not title:
            title = "Untitled Article"
            logger.warning("Could not extract title, using default")
        
        # Extract author
        author = "InfoSeek News"
        author_selectors = [
            ".author",
            ".article-author",
            "[class*='author']",
            "[class*='content-part__author']",
            "[itemprop='author']",
        ]
        
        for selector in author_selectors:
            try:
                if selector.startswith('[') and 'itemprop' in selector:
                    author_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    author = author_elem.get_attribute('content') or author_elem.text.strip()
                else:
                    author_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    author = author_elem.text.strip()
                if author:
                    logger.info(f"Found author: {author}")
                    break
            except:
                continue
        
        # Extract publication date
        publication_date = ""
        date_selectors = [
            "meta[property='article:published_time']",
            "meta[name='article:published_time']",
            "meta[property='og:published_time']",
            "meta[name='datePublished']",
            "meta[itemprop='datePublished']",
            "time[datetime]",
            "time[pubdate]",
            "[class*='date']",
            "[class*='published']",
            "[class*='publication-date']",
            "[class*='content-part__date']",
        ]
        
        for selector in date_selectors:
            try:
                if selector.startswith('meta'):
                    date_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    publication_date = date_elem.get_attribute('content') or date_elem.get_attribute('datetime')
                elif selector.startswith('time'):
                    date_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    publication_date = date_elem.get_attribute('datetime') or date_elem.text.strip()
                else:
                    date_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    publication_date = date_elem.text.strip()
                
                if publication_date:
                    logger.info(f"Found publication date: {publication_date}")
                    # Try to format the date
                    try:
                        from datetime import datetime
                        # Check if it's a Unix timestamp (numeric string)
                        if publication_date.isdigit() or (publication_date.replace('.', '').isdigit() and len(publication_date) <= 13):
                            # Unix timestamp (seconds or milliseconds)
                            timestamp = float(publication_date)
                            if timestamp > 1e12:  # Milliseconds
                                timestamp = timestamp / 1000
                            dt = datetime.fromtimestamp(timestamp)
                            publication_date = dt.strftime('%d.%m.%Y')
                        # Try parsing ISO format
                        elif 'T' in publication_date:
                            dt = datetime.fromisoformat(publication_date.replace('Z', '+00:00'))
                            publication_date = dt.strftime('%d.%m.%Y')
                        elif len(publication_date) > 10:
                            # Try other common formats
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']:
                                try:
                                    dt = datetime.strptime(publication_date[:19], fmt)
                                    publication_date = dt.strftime('%d.%m.%Y')
                                    break
                                except:
                                    continue
                    except Exception as e:
                        logger.warning(f"Failed to parse date '{publication_date}': {str(e)}")
                        # If parsing fails, try to use as is or set empty
                        publication_date = ""
                    if publication_date:
                        break
            except:
                continue
        
        if not publication_date:
            logger.info("Could not extract publication date")
        
        # Extract text content from <p> tags inside main article container
        # Try multiple selectors to find the main content container
        possible_content_selectors = [
            "div.full-text",
            "article",
            "div.content",
            "div#article-body",
            ".full-width-depends-on-screening__container.full-content__main",
            ".full-content__main",
            "section.full-content__main__left",
        ]
        
        content_paragraphs = []
        main_block = None
        
        # Find the main content block
        for selector in possible_content_selectors:
            try:
                main_block = driver.find_element(By.CSS_SELECTOR, selector)
                logger.info(f"Found main content block with selector: {selector}")
                break
            except:
                continue
        
        if main_block:
            # Extract only <p> tags to avoid ads and scripts
            paragraphs = main_block.find_elements(By.TAG_NAME, "p")
            for p in paragraphs:
                text = p.text.strip()
                # Ignore very short paragraphs (likely photo captions, ads)
                if len(text) > 20:
                    # Filter out "Czerwony telefon Radia ZET" section and similar call-to-action text
                    text_upper = text.upper()
                    if not any(keyword in text_upper for keyword in [
                        'CZERWONY TELEFON',
                        'ZGŁOŚ SPRAWĘ',
                        'BYŁEŚ ŚWIADKIEM',
                        'MASZ TEMAT',
                        'POWINNIŚMY SIĘ ZAJĄĆ'
                    ]):
                        content_paragraphs.append(text)
        else:
            # Fallback: get all <p> tags on the page
            logger.warning("Main content block not found, using all <p> tags as fallback")
            all_ps = driver.find_elements(By.TAG_NAME, "p")
            for p in all_ps:
                text = p.text.strip()
                if len(text) > 50:
                    # Filter out "Czerwony telefon" section
                    text_upper = text.upper()
                    if not any(keyword in text_upper for keyword in [
                        'CZERWONY TELEFON',
                        'ZGŁOŚ SPRAWĘ',
                        'BYŁEŚ ŚWIADKIEM',
                        'MASZ TEMAT',
                        'POWINNIŚMY SIĘ ZAJĄĆ'
                    ]):
                        content_paragraphs.append(text)
        
        if not content_paragraphs:
            logger.warning("No content paragraphs found")
            content_paragraphs = ["Could not extract article content."]
        
        # Create clean HTML paragraphs
        full_text_html = "".join([f"<p>{html_escape.escape(text)}</p>" for text in content_paragraphs])
        
        # 2. Create clean HTML template with embedded CSS
        clean_html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{html_escape.escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&display=swap" rel="stylesheet">
    <style>
        @page {{ margin: 20mm; size: A4; }}
        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            background-color: #fff;
        }}
        .header {{
            border-bottom: 2px solid #e74c3c;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{
            font-size: 28px;
            color: #2c3e50;
            margin: 0 0 10px 0;
            line-height: 1.3;
        }}
        .meta {{
            font-size: 14px;
            color: #7f8c8d;
            font-style: italic;
        }}
        .meta a {{
            color: #5686fe;
            text-decoration: none;
            word-break: keep-all;
            overflow-wrap: anywhere;
            hyphens: none;
            -webkit-hyphens: none;
            -moz-hyphens: none;
        }}
        .meta a:hover {{
            text-decoration: underline;
        }}
        @media print {{
            .meta a {{
                color: #5686fe !important;
                text-decoration: underline;
            }}
        }}
        .content p {{
            margin-bottom: 15px;
            font-size: 16px;
            text-align: justify;
        }}
        .footer {{
            margin-top: 50px;
            text-align: center;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }}
        .footer-text {{
            font-size: 12px;
            color: #7f8c8d;
            margin-bottom: 8px;
        }}
        .footer-brand {{
            font-family: 'Silkscreen', monospace;
            font-size: 24px;
            font-weight: 700;
            color: #5686fe;
            letter-spacing: -0.04em;
            line-height: 1.1;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{html_escape.escape(title)}</h1>
        <div class="meta">Author: {html_escape.escape(author)}{f" | Date: {html_escape.escape(publication_date)}" if publication_date else ""} | Source: <a href="{html_escape.escape(original_url)}" target="_blank" rel="noopener noreferrer">{html_escape.escape(original_url)}</a></div>
    </div>
    
    <div class="content">
        {full_text_html}
    </div>

    <div class="footer">
        <div class="footer-text">Generated by</div>
        <div class="footer-brand">infoseek</div>
    </div>
</body>
</html>"""
        
        # 3. Nuclear Swap - completely replace the page
        driver.execute_script("document.open(); document.write(arguments[0]); document.close();", clean_html_template)
        
        # Wait for browser to render the new clean HTML
        time.sleep(1)
        
        # 4. Print to PDF using CDP
        pdf_data_result = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "paperWidth": 8.27,      # A4 width in inches
            "paperHeight": 11.69,    # A4 height in inches
            "marginTop": 0.4,
            "marginBottom": 0.4,
            "marginLeft": 0.4,
            "marginRight": 0.4,
            "displayHeaderFooter": False
        })
        
        # Decode base64 PDF data
        pdf_data = base64.b64decode(pdf_data_result['data'])
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write PDF to file
        with open(output_path, 'wb') as f:
            f.write(pdf_data)
        
        logger.info(f"PDF saved to {output_path}, size: {len(pdf_data)} bytes")
        
        # Return extracted data
        return {
            'title': title,
            'author': author,
            'publication_date': publication_date,
            'content': '\n\n'.join(content_paragraphs)
        }
        
    except Exception as e:
        logger.error(f"Error in Nuclear Swap PDF generation: {str(e)}")
        raise


def clean_page_for_pdf(driver: WebDriver) -> int:
    """
    Hide/remove unwanted elements (ads, navigation, footer) before saving PDF.
    Keeps only the main article content.
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        int: Length of text content after cleaning (0 if error)
    """
    # JavaScript to hide unwanted elements while preserving article content
    hide_script = """
    (function() {
        // Return value will be text length after cleaning
        let returnValue = 0;
        // Find the specific RadioZET sections to preserve:
        // 1. .full-width-depends-on-screening__container.content-part__top (header, title, lead, image)
        // 2. .full-width-depends-on-screening__container.full-content__main (main article body)
        let topSection = null;
        let mainSection = null;
        let mainContent = null;
        
        try {
            // Try multiple selector variations to find the sections
            const topSelectors = [
                '.full-width-depends-on-screening__container.content-part__top',
                'div.full-width-depends-on-screening__container.content-part__top',
                '[class*="full-width-depends-on-screening"][class*="content-part__top"]',
                '.content-part__top',
                'section.content-part__top__left',
            ];
            
            const mainSelectors = [
                '.full-width-depends-on-screening__container.full-content__main',
                'div.full-width-depends-on-screening__container.full-content__main',
                '[class*="full-width-depends-on-screening"][class*="full-content__main"]',
                '.full-content__main',
                'section.full-content__main__left',
            ];
            
            // Try to find top section
            for (const selector of topSelectors) {
                try {
                    topSection = document.querySelector(selector);
                    if (topSection) {
                        console.log('Found top section with selector:', selector);
                        break;
                    }
                } catch(e) {
                    continue;
                }
            }
            
            // Try to find main section
            for (const selector of mainSelectors) {
                try {
                    mainSection = document.querySelector(selector);
                    if (mainSection) {
                        console.log('Found main section with selector:', selector);
                        break;
                    }
                } catch(e) {
                    continue;
                }
            }
            
            // If we found both sections, create a clean wrapper
            if (topSection && mainSection) {
                // Create a wrapper div to hold both sections
                const wrapper = document.createElement('div');
                wrapper.className = 'article-wrapper';
                wrapper.style.display = 'block';
                wrapper.style.visibility = 'visible';
                wrapper.style.width = '100%';
                wrapper.style.maxWidth = '900px';
                wrapper.style.margin = '0 auto';
                wrapper.style.padding = '20px';
                wrapper.style.backgroundColor = '#ffffff';
                
                // Clone sections deeply
                const topClone = topSection.cloneNode(true);
                const mainClone = mainSection.cloneNode(true);
                
                // Clean up clones - remove ads and unwanted elements
                const cleanElement = (el) => {
                    if (!el) return;
                    
                    // Remove unwanted elements - be very thorough
                    const unwantedSelectors = [
                        '[class*="reklama"]',
                        '[id*="reklama"]',
                        '[class*="advertisement"]',
                        '[id*="advertisement"]',
                        '[id*="google_ads"]',
                        '[id*="google-ads"]',
                        '[class*="onnetwork"]',
                        '[data-adv-display-type]',
                        '[data-adv-display-replace]',
                        '[data-adv-display-counter]',
                        '[class*="share"]',
                        '[class*="reaction"]',
                        '[class*="zareaguj"]',
                        '[class*="recommended"]',
                        '[class*="related"]',
                        '[class*="tu-sie-dzieje"]',
                        '[class*="stories"]',
                        '[class*="radio-program"]',
                        '[class*="content-part__tags"]',
                        '[class*="redphone"]',
                        '[class*="embed-social"]',
                        '[class*="embed"]',
                        '[data-mrf-recirculation]',
                        '.stories__block_onn',
                        'iframe',
                        '[class*="advert"]',
                        '[id*="div-gpt-ad"]',
                        '[class*="ad-container"]',
                        '[class*="ad-wrapper"]',
                        '[class*="ad-banner"]',
                    ];
                    
                    unwantedSelectors.forEach(selector => {
                        try {
                            const unwanted = el.querySelectorAll(selector);
                            unwanted.forEach(item => item.remove());
                        } catch(e) {}
                    });
                    
                    // Also remove elements by text content
                    const allElements = Array.from(el.querySelectorAll('*'));
                    allElements.forEach(item => {
                        const text = (item.textContent || '').toUpperCase().trim();
                        const classes = (item.className || '').toLowerCase();
                        const id = (item.id || '').toLowerCase();
                        const tagName = item.tagName.toLowerCase();
                        
                        // Remove if it's clearly unwanted
                        if (text === 'TU SIĘ DZIEJE' ||
                            text === 'GRAJ O KASĘ' ||
                            text === 'REDAKCJA POLECA' ||
                            text === 'ZOBACZ TAKŻE' ||
                            text === 'WIĘCEJ NA TEMAT' ||
                            text === 'TERAZ W RADIU ZET' ||
                            text === 'TERAZ GRAMY' ||
                            text === 'WŁĄCZ RADIO' ||
                            text === 'POBIERZ APKĘ' ||
                            (text.length < 50 && text.includes('REKLAMA')) ||
                            classes.includes('stories__block_onn') ||
                            classes.includes('radio-program-widget') ||
                            id.includes('radio-program') ||
                            (tagName === 'section' && (classes.includes('recommended') || classes.includes('related') || classes.includes('stories'))) ||
                            (tagName === 'div' && (classes.includes('recommended') || classes.includes('related') || classes.includes('stories')))) {
                            item.remove();
                        }
                    });
                };
                
                cleanElement(topClone);
                cleanElement(mainClone);
                
                // Clear body and add only our clean content
                document.body.innerHTML = '';
                document.body.style.margin = '0';
                document.body.style.padding = '0';
                document.body.style.backgroundColor = '#ffffff';
                
                // Add wrapper to body
                document.body.appendChild(wrapper);
                wrapper.appendChild(topClone);
                wrapper.appendChild(mainClone);
                
                mainContent = wrapper;
                console.log('Created clean wrapper with both sections');
            } else if (topSection) {
                const wrapper = document.createElement('div');
                wrapper.className = 'article-wrapper';
                wrapper.style.display = 'block';
                wrapper.style.visibility = 'visible';
                wrapper.style.width = '100%';
                wrapper.style.maxWidth = '900px';
                wrapper.style.margin = '0 auto';
                wrapper.style.padding = '20px';
                wrapper.style.backgroundColor = '#ffffff';
                
                const topClone = topSection.cloneNode(true);
                const cleanElement = (el) => {
                    const unwanted = el.querySelectorAll('[class*="reklama"], [id*="reklama"], [class*="advertisement"], [id*="google_ads"], [class*="onnetwork"], [data-adv-display-type], [class*="share"], [class*="reaction"], [class*="recommended"], [class*="related"], [class*="stories"], iframe, [class*="advert"]');
                    unwanted.forEach(item => item.remove());
                };
                cleanElement(topClone);
                
                document.body.innerHTML = '';
                document.body.style.margin = '0';
                document.body.style.padding = '0';
                document.body.style.backgroundColor = '#ffffff';
                document.body.appendChild(wrapper);
                wrapper.appendChild(topClone);
                mainContent = wrapper;
                console.log('Using only top section');
            } else if (mainSection) {
                const wrapper = document.createElement('div');
                wrapper.className = 'article-wrapper';
                wrapper.style.display = 'block';
                wrapper.style.visibility = 'visible';
                wrapper.style.width = '100%';
                wrapper.style.maxWidth = '900px';
                wrapper.style.margin = '0 auto';
                wrapper.style.padding = '20px';
                wrapper.style.backgroundColor = '#ffffff';
                
                const mainClone = mainSection.cloneNode(true);
                const cleanElement = (el) => {
                    const unwanted = el.querySelectorAll('[class*="reklama"], [id*="reklama"], [class*="advertisement"], [id*="google_ads"], [class*="onnetwork"], [data-adv-display-type], [class*="share"], [class*="reaction"], [class*="recommended"], [class*="related"], [class*="stories"], iframe, [class*="advert"]');
                    unwanted.forEach(item => item.remove());
                };
                cleanElement(mainClone);
                
                document.body.innerHTML = '';
                document.body.style.margin = '0';
                document.body.style.padding = '0';
                document.body.style.backgroundColor = '#ffffff';
                document.body.appendChild(wrapper);
                wrapper.appendChild(mainClone);
                mainContent = wrapper;
                console.log('Using only main section');
            }
        } catch(e) {
            console.log('Error finding specific sections:', e);
        }
        
        // If still no content found, use body as fallback
        if (!mainContent) {
            mainContent = document.body;
            console.log('Using body as fallback');
        }
        
        // If we successfully created clean content by replacing body, we're done
        // The body now contains only our clean wrapper with article content
        // No need to hide anything else - body has been completely replaced
        
        // Hide "TU SIĘ DZIEJE", related content, social buttons, reactions, etc.
        // Hide these even if they're inside main content - they're not part of the article
        try {
            const unwantedSelectors = [
                // Related/recommended content
                '[class*="recommended"]',
                '[class*="related"]',
                '[class*="zareaguj"]',
                '[class*="tu-sie-dzieje"]',
                '[id*="recommended"]',
                '[id*="related"]',
                '.related-articles',
                '.recommended-articles',
                // Social sharing and reactions
                '[class*="share"]',
                '[class*="reaction"]',
                '[class*="content-part__share"]',
                '[class*="content-part__reaction"]',
                // Stories widget
                '[class*="stories"]',
                '[id*="stories"]',
                // Radio program widget
                '[class*="radio-program"]',
                '[id*="radio-program"]',
                // Tags section
                '[class*="content-part__tags"]',
                '[class*="tags"]',
                // MRF recirculation (related articles)
                '[data-mrf-recirculation]',
                // Redphone section
                '[class*="redphone"]',
                // Embed social (Twitter, etc.)
                '[class*="embed-social"]',
                '[class*="embed"]',
                // Stories block
                '.stories__block_onn',
            ];
            
            unwantedSelectors.forEach(selector => {
                try {
                    const unwantedElements = document.querySelectorAll(selector);
                    unwantedElements.forEach(el => {
                        // Hide even if in main content - these are not part of the article
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.height = '0';
                        el.style.width = '0';
                        el.style.opacity = '0';
                    });
                } catch(e) {}
            });
        } catch(e) {}
        
        // Hide elements that contain "REKLAMA" text
        try {
            const allDivs = document.querySelectorAll('div, section, aside');
            allDivs.forEach(el => {
                const text = (el.textContent || '').trim();
                const innerHTML = (el.innerHTML || '').toUpperCase();
                
                // If element contains "REKLAMA" text, hide it
                if (text.includes('REKLAMA') || innerHTML.includes('REKLAMA')) {
                    // But check if it's not the main article content
                    if (!mainContent || !mainContent.contains(el) || el === mainContent) {
                        // Only hide if it's a small element or clearly an ad container
                        const rect = el.getBoundingClientRect();
                        if (rect.height < 1000 || text.length < 500) {
                            el.style.display = 'none';
                        }
                    }
                }
            });
        } catch(e) {}
        
        // Hide Google AdSense containers and iframes
        try {
            // Google AdSense specific selectors
            const googleAdSelectors = [
                '[id*="google_ads_iframe"]',
                '[id*="google_ads"]',
                '[id*="google-ads"]',
                '[class*="google-ads"]',
                '[class*="google_ads"]',
                'div[id*="google_ads_iframe"]',
                'div[id*="google_ads"]',
            ];
            
            googleAdSelectors.forEach(selector => {
                try {
                    const adElements = document.querySelectorAll(selector);
                    adElements.forEach(el => {
                        // Hide all Google AdSense elements
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.height = '0';
                        el.style.width = '0';
                        el.style.overflow = 'hidden';
                    });
                } catch(e) {}
            });
        } catch(e) {}
        
        // Hide onnetwork ad containers (RadioZET specific)
        try {
            const onnetworkSelectors = [
                '.onnetwork-container',
                '[class*="onnetwork"]',
                '[data-adv-display-type]',
                '[data-adv-display-replace]',
                '[data-adv-display-counter]',
            ];
            
            onnetworkSelectors.forEach(selector => {
                try {
                    const adElements = document.querySelectorAll(selector);
                    adElements.forEach(el => {
                        // Check if it's an ad container
                        const hasAdvAttr = el.hasAttribute('data-adv-display-type') || 
                                          el.hasAttribute('data-adv-display-replace');
                        if (hasAdvAttr || el.className.includes('onnetwork')) {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                            el.style.height = '0';
                            el.style.width = '0';
                            el.style.overflow = 'hidden';
                        }
                    });
                } catch(e) {}
            });
        } catch(e) {}
        
        // Hide iframes that are clearly ads (but not inside main content)
        try {
            const iframes = document.querySelectorAll('iframe');
            iframes.forEach(iframe => {
                // Check if iframe is an ad
                const parent = iframe.parentElement;
                const isAdIframe = parent && (
                    parent.id.includes('google_ads') ||
                    parent.id.includes('ad') ||
                    parent.className.includes('ad') ||
                    parent.className.includes('reklama') ||
                    parent.className.includes('onnetwork')
                );
                
                if (isAdIframe || (!mainContent || !mainContent.contains(iframe))) {
                    iframe.style.display = 'none';
                    iframe.style.visibility = 'hidden';
                }
            });
        } catch(e) {}
        
        // Hide ALL elements with "reklama" or "ad" in class/id
        // But be careful not to hide main content
        try {
            const adSelectors = [
                '[class*="reklama"]',
                '[id*="reklama"]',
                '[class*="advertisement"]',
                '[id*="advertisement"]',
                '[class*="REKLAMA"]',
                '[id*="REKLAMA"]',
                '[data-ad]',
                '[data-advertisement]',
            ];
            
            adSelectors.forEach(selector => {
                try {
                    const adElements = document.querySelectorAll(selector);
                    adElements.forEach(el => {
                        // Only hide if it's not the main content itself
                        if (el !== mainContent && (!mainContent || !mainContent.contains(el))) {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                            el.style.height = '0';
                            el.style.width = '0';
                            el.style.overflow = 'hidden';
                        } else if (el !== mainContent && mainContent && mainContent.contains(el)) {
                            // Even if inside main content, hide if it's clearly an ad
                            const classes = (el.className || '').toLowerCase();
                            const id = (el.id || '').toLowerCase();
                            if (classes.includes('reklama') || id.includes('reklama') || 
                                classes.includes('advertisement') || id.includes('advertisement')) {
                                el.style.display = 'none';
                                el.style.visibility = 'hidden';
                            }
                        }
                    });
                } catch(e) {}
            });
            
            // Hide elements with "ad" in class/id, but be more careful
            try {
                const adElements = document.querySelectorAll('[class*="ad"]:not([class*="add"]):not([class*="advance"]):not([class*="admin"]), [id*="ad"]:not([id*="add"]):not([id*="advance"]):not([id*="admin"])');
                adElements.forEach(el => {
                    // Check if it's really an ad (not article content)
                    const classes = (el.className || '').toLowerCase();
                    const id = (el.id || '').toLowerCase();
                    const isAdContainer = classes.includes('ad-container') ||
                                        classes.includes('ad-wrapper') ||
                                        classes.includes('ad-banner') ||
                                        id.includes('ad-container') ||
                                        id.includes('ad-wrapper') ||
                                        id.includes('ad-banner') ||
                                        id.includes('google_ads');
                    
                    if (isAdContainer) {
                        if (el !== mainContent && (!mainContent || !mainContent.contains(el))) {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                        }
                    }
                });
            } catch(e) {}
        } catch(e) {}
        
        // Hide elements with "REKLAMA" text content
        try {
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => {
                const text = (el.textContent || '').toUpperCase();
                const classes = (el.className || '').toUpperCase();
                const id = (el.id || '').toUpperCase();
                
                // Check if element is clearly an ad
                if (text.includes('REKLAMA') || 
                    classes.includes('REKLAMA') || 
                    id.includes('REKLAMA') ||
                    text.includes('ADVERTISEMENT') ||
                    classes.includes('ADVERTISEMENT')) {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                }
            });
        } catch(e) {}
        
        // Hide social sharing buttons outside article
        try {
            const shareButtons = document.querySelectorAll('[class*="share"], [class*="social"]:not([class*="article"])');
            shareButtons.forEach(el => {
                if (!mainContent || !mainContent.contains(el)) {
                    el.style.display = 'none';
                }
            });
        } catch(e) {}
        
        // Style main content for better PDF output
        if (mainContent && mainContent !== document.body) {
            // Ensure main content is visible
            mainContent.style.display = 'block';
            mainContent.style.visibility = 'visible';
            mainContent.style.width = '100%';
            mainContent.style.maxWidth = '900px';
            mainContent.style.margin = '0 auto';
            mainContent.style.padding = '20px';
            mainContent.style.backgroundColor = '#ffffff';
            
            // Don't hide siblings - just hide specific ad containers
            // This prevents accidentally hiding important content
        }
        
        // Set clean background
        document.body.style.background = '#ffffff';
        document.body.style.padding = '0';
        document.body.style.margin = '0';
        
        // Clean up inside main content - hide ads and unwanted elements
        if (mainContent) {
            const allElements = mainContent.querySelectorAll('*');
            allElements.forEach(el => {
                const classes = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                const text = (el.textContent || '').toUpperCase().trim();
                const tagName = el.tagName.toLowerCase();
                
                // Check if element is an ad - be very thorough
                const isAd = classes.includes('reklama') || 
                           classes.includes('advertisement') ||
                           id.includes('reklama') ||
                           id.includes('advertisement') ||
                           id.includes('google_ads') ||
                           id.includes('google-ads') ||
                           classes.includes('onnetwork') ||
                           el.hasAttribute('data-adv-display-type') ||
                           el.hasAttribute('data-adv-display-replace') ||
                           el.hasAttribute('data-adv-display-counter') ||
                           // Check for ad containers
                           (classes.includes('ad') && (classes.includes('container') || classes.includes('wrapper') || classes.includes('banner'))) ||
                           (id.includes('ad') && (id.includes('container') || id.includes('wrapper') || id.includes('banner'))) ||
                           // Check for div-gpt-ad (Google AdSense)
                           (id.includes('div-gpt-ad') || classes.includes('div-gpt-ad')) ||
                           // Check for advert containers
                           (classes.includes('advert') && (classes.includes('container') || classes.includes('dfp'))) ||
                           // Hide iframes that are ads
                           (tagName === 'iframe' && (id.includes('google_ads') || id.includes('ad') || classes.includes('ad'))) ||
                           // Hide elements with "REKLAMA" text (but only if small element)
                           (text === 'REKLAMA' || (text.length < 50 && text.includes('REKLAMA')));
                
                // Hide social sharing buttons, reactions, and related content
                const isUnwanted = classes.includes('share') ||
                                 classes.includes('reaction') ||
                                 classes.includes('zareaguj') ||
                                 classes.includes('recommended') ||
                                 classes.includes('related') ||
                                 classes.includes('tu-sie-dzieje') ||
                                 classes.includes('stories') ||
                                 id.includes('recommended') ||
                                 id.includes('related') ||
                                 id.includes('mrf-recirculation') ||
                                 // Hide radio program widget
                                 (classes.includes('radio-program') || id.includes('radio-program')) ||
                                 // Hide tags section
                                 (classes.includes('content-part__tags')) ||
                                 // Hide "Redakcja poleca" sections
                                 (text.includes('REDAKCJA POLECA') || text.includes('WIĘCEJ NA TEMAT'));
                
                if (isAd || isUnwanted) {
                    // Make sure ads and unwanted elements stay hidden
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.height = '0';
                    el.style.width = '0';
                    el.style.opacity = '0';
                    el.style.overflow = 'hidden';
                    el.style.position = 'absolute';
                    el.style.left = '-9999px';
                } else {
                    // Restore visibility for article content
                    if (el.style.display === 'none' && !el.classList.contains('hidden')) {
                        // But check if parent is hidden - if so, don't restore
                        let parent = el.parentElement;
                        let parentHidden = false;
                        while (parent && parent !== mainContent) {
                            if (parent.style.display === 'none') {
                                parentHidden = true;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                        if (!parentHidden) {
                            el.style.display = '';
                        }
                    }
                    if (el.style.visibility === 'hidden') {
                        el.style.visibility = 'visible';
                    }
                    // Restore dimensions if they were set to 0
                    if (el.style.height === '0px' || el.style.height === '0') {
                        el.style.height = '';
                    }
                    if (el.style.width === '0px' || el.style.width === '0') {
                        el.style.width = '';
                    }
                }
            });
            
            // Ensure main content itself is visible
            mainContent.style.display = 'block';
            mainContent.style.visibility = 'visible';
        }
        
        // Final pass - remove any remaining ad elements by text content
        // But only if they're clearly ads, not article content
        try {
            const allRemaining = document.querySelectorAll('*');
            allRemaining.forEach(el => {
                // Skip if it's the main content
                if (el === mainContent) return;
                
                const text = (el.textContent || '').toUpperCase().trim();
                const classes = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                
                // Only hide if it's clearly an ad label/container
                const isAdLabel = (text === 'REKLAMA' || 
                                  (text.length < 20 && text.includes('REKLAMA'))) &&
                                  el.children.length === 0;
                
                const isAdContainer = (classes.includes('reklama') || 
                                      id.includes('reklama') ||
                                      id.includes('google_ads') ||
                                      classes.includes('onnetwork') ||
                                      el.hasAttribute('data-adv-display-type'));
                
                if ((isAdLabel || isAdContainer) && (!mainContent || !mainContent.contains(el))) {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.height = '0';
                    el.style.width = '0';
                }
            });
        } catch(e) {}
        
        // Verify content is not empty
        const finalTextLength = mainContent ? (mainContent.textContent || '').trim().length : 0;
        const finalInnerTextLength = mainContent ? (mainContent.innerText || '').trim().length : 0;
        const actualLength = Math.max(finalTextLength, finalInnerTextLength);
        
        console.log('Page cleaning complete. Main content preserved. Text length:', actualLength);
        
        // Return the text length so we can check it
        returnValue = actualLength;
        return returnValue;
        
    })();
    """
    
    try:
        content_length = driver.execute_script(hide_script)
        time.sleep(2)  # Wait for changes to apply and content to render
        
        if content_length and content_length < 200:
            logger.warning(f"Page cleaned but content seems short ({content_length} chars). May need adjustment.")
        else:
            logger.info(f"Page cleaned for PDF - unwanted elements hidden, article content preserved ({content_length} chars)")
        
        return content_length or 0
    except Exception as e:
        logger.warning(f"Error cleaning page: {str(e)}")
        return 0


def save_page_as_pdf(driver: WebDriver, output_path: str, clean_page: bool = True) -> None:
    """
    Save the current page as PDF using Chrome DevTools Protocol.
    Optionally cleans the page to show only article content.
    
    Args:
        driver: Selenium WebDriver instance
        output_path: Full path where the PDF should be saved
        clean_page: If True, hide ads/navigation before saving
    """
    # Clean page before saving if requested
    if clean_page:
        try:
            # First verify page has content before cleaning
            content_before = driver.execute_script("""
                return (document.body.innerText || document.body.textContent || '').trim().length;
            """)
            
            if content_before < 100:
                logger.warning(f"Page has little content ({content_before} chars), skipping cleaning")
                clean_page = False
            else:
                content_after = clean_page_for_pdf(driver)
                time.sleep(2)
                
                # Verify content is still there after cleaning
                if not content_after or content_after < 200:
                    logger.warning(f"Content seems too short after cleaning ({content_after} chars), trying without cleaning")
                    # Reload page to restore original state
                    driver.refresh()
                    time.sleep(3)
                    clean_page = False
                else:
                    logger.info(f"Content preserved: {content_before} -> {content_after} chars")
        except Exception as e:
            logger.warning(f"Error during page cleaning: {str(e)}, saving without cleaning")
            clean_page = False
    
    # Execute Chrome DevTools Protocol command to print page to PDF
    pdf_params = {
        'printBackground': True,
        'paperWidth': 8.5,
        'paperHeight': 11,
        'marginTop': 0.5,
        'marginBottom': 0.5,
        'marginLeft': 0.5,
        'marginRight': 0.5,
    }
    
    # Use execute_cdp_cmd for Chrome DevTools Protocol
    result = driver.execute_cdp_cmd('Page.printToPDF', pdf_params)
    
    # Decode base64 PDF data
    pdf_data = base64.b64decode(result['data'])
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write PDF to file
    with open(output_path, 'wb') as f:
        f.write(pdf_data)
    
    logger.info(f"PDF saved to {output_path}, size: {len(pdf_data)} bytes")


@shared_task(name='scrape_news_task')
def scrape_news_task(task_id: str, keyword: str, article_count: int = 3):
    """
    Celery task to scrape news based on a SearchTask keyword.
    
    Searches for news articles on RadioZET.pl (https://www.radiozet.pl)
    
    Args:
        task_id: UUID string of the SearchTask to process
        keyword: Search keyword to use for scraping
        article_count: Number of articles to scrape (default: 3)
        
    This task will:
    1. Update the SearchTask status to 'processing'
    2. Connect to remote Selenium WebDriver
    3. Navigate to RadioZET.pl and search for keyword
    4. Extract first N article links (where N = article_count)
    5. For each article: open, save as PDF, create SearchResult
    6. Update the SearchTask status to 'completed' or 'failed'
    """
    driver = None
    search_task = None
    
    try:
        # Get the SearchTask
        search_task = SearchTask.objects.get(id=task_id)
        # Use article_count from the task if not provided as parameter
        if article_count is None:
            article_count = search_task.article_count
        logger.info(f"Starting scraping task {task_id} for keyword: {keyword}, article_count: {article_count}")
        
        # Update status to processing
        search_task.status = 'processing'
        search_task.save()
        
        # Get Selenium URL from environment
        selenium_url = os.getenv('SELENIUM_URL', 'http://selenium:4444/wd/hub')
        
        # Configure remote WebDriver options
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Connect to remote Selenium WebDriver
        driver = webdriver.Remote(
            command_executor=selenium_url,
            options=options
        )
        
        # Set page load timeout
        driver.set_page_load_timeout(30)
        
        # Navigate directly to search page on RadioZET.pl
        # RadioZET uses URL-based search: /Wyszukaj?q=keyword
        search_url = f'https://www.radiozet.pl/Wyszukaj?q={keyword}'
        logger.info(f"Navigating to search page: {search_url}")
        driver.get(search_url)
        
        # Wait for page to load completely
        wait = WebDriverWait(driver, 15)
        
        # Wait for page to be ready
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        
        # Additional wait for dynamic content
        time.sleep(2)
        
        # Handle cookie consent popup if present
        # RadioZET uses OneTrust cookie consent
        cookie_accept_selectors = [
            (By.CSS_SELECTOR, 'button#onetrust-accept-btn-handler'),
            (By.CSS_SELECTOR, 'button[class*="onetrust-accept"]'),
            (By.CSS_SELECTOR, 'button[id*="accept"]'),
            (By.CSS_SELECTOR, 'button:contains("AKCEPTUJĘ")'),
            (By.CSS_SELECTOR, 'button:contains("Accept")'),
            (By.XPATH, '//button[contains(text(), "AKCEPTUJĘ")]'),
            (By.XPATH, '//button[contains(text(), "Accept")]'),
        ]
        
        cookie_accepted = False
        for by, selector in cookie_accept_selectors:
            try:
                cookie_button = wait.until(EC.element_to_be_clickable((by, selector)))
                logger.info("Found cookie consent button, clicking...")
                driver.execute_script("arguments[0].click();", cookie_button)
                time.sleep(2)  # Wait for popup to disappear
                cookie_accepted = True
                logger.info("Cookie consent accepted")
                break
            except (TimeoutException, NoSuchElementException):
                continue
        
        if not cookie_accepted:
            logger.info("No cookie consent popup found or already accepted")
        
        # Wait for search results page to load
        time.sleep(5)  # Wait for Google Custom Search to load
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        
        # Additional wait after cookie acceptance and for Google Custom Search to render
        time.sleep(3)
        
        # RadioZET uses Google Custom Search - look for results in gsc-results
        logger.info("Looking for Google Custom Search results...")
        
        # Wait for Google Custom Search results container
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc-results, .gsc-webResult')))
            logger.info("Google Custom Search results container found")
        except TimeoutException:
            logger.warning("Google Custom Search results container not found, trying alternative selectors")
        
        # Look for article links in Google Custom Search results
        # Google Custom Search uses specific classes: .gsc-webResult, .gs-title, etc.
        article_selectors = [
            # Google Custom Search specific selectors
            (By.CSS_SELECTOR, '.gsc-webResult .gs-title a'),
            (By.CSS_SELECTOR, '.gsc-result .gs-title a'),
            (By.CSS_SELECTOR, '.gsc-webResult a.gs-title'),
            (By.CSS_SELECTOR, 'a.gs-title'),
            (By.CSS_SELECTOR, '.gsc-results .gsc-webResult a'),
            # Fallback selectors
            (By.CSS_SELECTOR, '.gsc-webResult a[href*="radiozet.pl"]'),
            (By.CSS_SELECTOR, '.gsc-result a[href*="/wiadomosci"]'),
            (By.CSS_SELECTOR, '.gsc-result a[href*="/kultura"]'),
        ]
        
        article_links = []
        for by, selector in article_selectors:
            try:
                # Wait for at least one element to be present
                wait.until(EC.presence_of_element_located((by, selector)))
                time.sleep(2)  # Additional wait for dynamic content
                elements = driver.find_elements(by, selector)
                
                # Filter out invalid links - only get actual article links, not category pages
                valid_elements = []
                for el in elements:
                    href = el.get_attribute('href')
                    if href and el.is_displayed():
                        # Clean URL from Google tracking
                        if 'url?q=' in href:
                            parsed = urlparse(href)
                            if 'q' in parse_qs(parsed.query):
                                href = parse_qs(parsed.query)['q'][0]
                        
                        if href and 'radiozet.pl' in href:
                            # Exclude category/section pages - these are usually short URLs
                            # Category pages: /polityka, /biznes, /wiadomosci (without article path)
                            # Article pages: /wiadomosci/kultura/article-title, /kultura/article-title, etc.
                            
                            # Split URL to check path depth
                            url_parts = href.rstrip('/').split('/')
                            
                            # Skip if it's just a domain or category page (fewer than 5 parts)
                            # Example: https://wiadomosci.radiozet.pl/polityka = 4 parts (domain + 1 path)
                            # Example: https://wiadomosci.radiozet.pl/kultura/article = 5+ parts (domain + 2+ paths)
                            if len(url_parts) >= 5:
                                # Additional check: exclude if it ends with just a category name
                                last_part = url_parts[-1]
                                category_names = ['polityka', 'biznes', 'wiadomosci', 'sport', 'zdrowie', 'kultura', 'rozrywka']
                                
                                # If last part is a category name and URL is short, skip it
                                if last_part in category_names and len(url_parts) <= 4:
                                    continue
                                
                                # Include if it looks like an article (has more path segments or article-like structure)
                                valid_elements.append(el)
                                logger.debug(f"Valid article link found: {href}")
                
                if valid_elements:
                    # Get first N unique article links (where N = article_count)
                    seen_urls = set()
                    for el in valid_elements:
                        url = el.get_attribute('href')
                        if url and url not in seen_urls:
                            article_links.append(el)
                            seen_urls.add(url)
                            if len(article_links) >= article_count:
                                break
                    
                    if article_links:
                        logger.info(f"Found {len(article_links)} article links using selector: {selector}")
                        break
            except TimeoutException:
                continue
        
        if not article_links:
            logger.error("Could not find article links in Google Custom Search results")
            raise NoSuchElementException("Could not find article links in search results")
        
        # Process each article
        for idx, link_element in enumerate(article_links[:article_count], 1):
            try:
                # Get article URL and title from Google Custom Search result
                article_url = link_element.get_attribute('href')
                
                # Get title - in Google Custom Search, title is usually in the link text or parent element
                article_title = link_element.text.strip()
                if not article_title:
                    # Try to get title from parent .gs-title element
                    try:
                        parent = link_element.find_element(By.XPATH, './..')
                        article_title = parent.text.strip()
                    except:
                        article_title = link_element.get_attribute('title') or f"Article {idx}"
                
                if not article_url:
                    logger.warning(f"Article {idx} has no URL, skipping")
                    continue
                
                # Clean URL - remove Google tracking parameters
                if 'url?q=' in article_url:
                    # Extract actual URL from Google redirect
                    parsed = urlparse(article_url)
                    if 'q' in parse_qs(parsed.query):
                        article_url = parse_qs(parsed.query)['q'][0]
                        logger.debug(f"Extracted URL from Google redirect: {article_url}")
                
                # Remove any remaining tracking parameters (utm_*, ref, etc.)
                if '?' in article_url:
                    article_url = article_url.split('?')[0]
                
                # Ensure absolute URL
                if not article_url.startswith('http'):
                    # Handle relative URLs for RadioZET
                    if article_url.startswith('/'):
                        article_url = f"https://www.radiozet.pl{article_url}"
                    else:
                        article_url = f"https://www.radiozet.pl/{article_url}"
                
                # Final validation - make sure it's a real article URL
                url_parts = article_url.rstrip('/').split('/')
                if len(url_parts) < 5:
                    logger.warning(f"Skipping short URL (likely category page): {article_url}")
                    continue
                
                # Log the final cleaned URL
                logger.debug(f"Final cleaned article URL: {article_url}")
                
                # Save the final cleaned URL before opening the page
                final_article_url = article_url
                logger.info(f"Processing article {idx}: {article_title[:50]}... -> {final_article_url}")
                
                # Open the article in a new tab
                driver.execute_script("window.open(arguments[0], '_blank');", final_article_url)
                driver.switch_to.window(driver.window_handles[-1])
                
                # Wait for article to load
                wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                # Additional wait for content to fully render
                time.sleep(3)
                
                # Log the actual URL after page load (for debugging)
                actual_url_after_load = driver.current_url
                logger.info(f"Article {idx} loaded. Original URL: {final_article_url}, Current URL: {actual_url_after_load}")
                
                # Generate unique filename for PDF
                pdf_filename = f"{task_id}_{idx}_{uuid.uuid4().hex[:8]}.pdf"
                pdf_path = os.path.join(settings.MEDIA_ROOT, 'pdfs', pdf_filename)
                
                # Extract content and generate PDF using Nuclear Swap method
                logger.info(f"Extracting content and generating PDF using Nuclear Swap method for: {article_title[:50]}...")
                try:
                    # Always use the original URL we saved, not the current URL after load
                    article_data = extract_and_save_pdf_nuclear_swap(driver, pdf_path, final_article_url)
                    logger.info(f"PDF generated with source URL: {final_article_url}")
                except Exception as e:
                    logger.error(f"Failed to generate PDF with Nuclear Swap method: {str(e)}")
                    raise
                
                # Get relative path for FileField
                pdf_relative_path = os.path.join('pdfs', pdf_filename)
                
                # Use extracted title if available, otherwise fallback to search result title
                final_title = article_data.get('title', article_title) if article_data else article_title
                
                # Create SearchResult entry
                SearchResult.objects.create(
                    task=search_task,
                    title=final_title,
                    source_url=final_article_url,
                    pdf_file=pdf_relative_path,
                )
                
                # Close current tab and switch back to main window
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                
            except Exception as e:
                # Log error but continue with next article
                logger.warning(f"Error processing article {idx} for task {task_id}: {str(e)}")
                # Close any extra tabs
                try:
                    while len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                except:
                    pass
                continue
        
        # Update status to completed
        search_task.status = 'completed'
        search_task.save()
        logger.info(f"Task {task_id} completed successfully with {len(article_links)} results")
        
        return f"Task {task_id} completed successfully"
        
    except SearchTask.DoesNotExist:
        logger.error(f"Task {task_id} not found in database")
        return f"Task {task_id} not found"
    except Exception as e:
        # Update status to failed
        error_message = f"Scraping failed for task {task_id}: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        if search_task:
            try:
                search_task.status = 'failed'
                search_task.save()
            except Exception as save_error:
                logger.error(f"Failed to update task status: {str(save_error)}")
        
        # Re-raise to log in Celery
        raise Exception(error_message)
    finally:
        # Always close the driver
        if driver:
            try:
                driver.quit()
            except:
                pass


