"""
OCR module for extracting text from tweet screenshots.
Supports Persian (Farsi) and English languages.

Uses pytesseract (Tesseract OCR) - lightweight and reliable for multilingual text.
"""

import os
import re
import logging
from PIL import Image, ImageFilter, ImageOps

import pytesseract

# Configure logger
logger = logging.getLogger(__name__)


def clean_tweet_text(text: str) -> str:
    """
    Clean OCR-extracted tweet text by removing unwanted elements.
    
    Removes:
    - Author name lines (starting with < or } or numbers)
    - @username mentions anywhere
    - Date/time lines (e.g., "5:43 AM - Jan 16, 2026")
    - "Read X replies" lines
    - Engagement metrics (views, likes, retweets)
    - Very short garbage lines
    - OCR artifacts and UI elements
    
    Args:
        text: Raw OCR text
        
    Returns:
        Cleaned text with only the tweet content
    """
    if not text:
        return ''
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Patterns to skip entire lines
    # Date/time pattern with regular or Persian digits: "5:43 AM - Jan 16, 2026" or "4:04 PM ۰ Jan 20, 2026"
    date_pattern = re.compile(r'^\d{1,2}:\d{2}\s*(AM|PM)?\s*[۰-۹]*\s*[-–]?\s*\w+\s+\d{1,2},?\s*\d{4}', re.IGNORECASE)
    # "Read X replies" pattern
    replies_pattern = re.compile(r'read\s+\d+\s+repl', re.IGNORECASE)
    # Engagement metrics (views, likes, etc.)
    engagement_pattern = re.compile(r'^\d+[KMB]?\s*(views?|likes?|retweets?|reposts?|replies?|comments?)?\s*$', re.IGNORECASE)
    # Lines starting with < or } or | (author/UI indicators from OCR)
    author_indicator = re.compile(r'^[<{}\|]\s*\w*')
    # Lines that are just @username
    solo_username = re.compile(r'^[@＠]\s*\w+\s*$')
    # Lines starting with numbers and pipe/special chars (like "0 |")
    number_garbage = re.compile(r'^\d+\s*[\|｜]\s*')
    # Lines that look like button text / UI elements (short mixed chars)
    ui_garbage = re.compile(r'^[A-Za-z0-9\s]{1,15}$')
    # Lines with mostly non-word characters
    mostly_garbage = re.compile(r'^[\W\d\s]{2,}$')
    
    skip_header = True  # Skip author/username at the beginning
    
    for line in lines:
        line_stripped = line.strip()
        
        # Skip empty lines
        if not line_stripped:
            continue
        
        # Skip very short lines (likely garbage)
        if len(line_stripped) <= 2:
            continue
        
        # Skip lines starting with numbers and pipe (like "0 |")
        if number_garbage.match(line_stripped):
            # But keep the rest of the line if there's content after
            cleaned = number_garbage.sub('', line_stripped).strip()
            if cleaned and len(cleaned) > 3:
                line_stripped = cleaned
            else:
                continue
        
        # Skip lines starting with < or } or | (author name indicators)
        if author_indicator.match(line_stripped) and len(line_stripped) < 50:
            continue
        
        # Skip solo @username lines
        if solo_username.match(line_stripped):
            continue
        
        # Skip date/time lines
        if date_pattern.match(line_stripped):
            continue
        
        # Skip "Read X replies" lines
        if replies_pattern.search(line_stripped):
            continue
        
        # Skip engagement metrics
        if engagement_pattern.match(line_stripped):
            continue
        
        # Skip header lines (author name, etc.) at the beginning
        if skip_header and len(line_stripped) < 40:
            # Check if it looks like a name or username line
            if re.search(r'[@＠]\w+', line_stripped) or re.match(r'^[A-Za-z\s]+$', line_stripped):
                continue
        
        # Skip lines that are just UI garbage (like "Os 11 093 As")
        if ui_garbage.match(line_stripped) and not any('\u0600' <= c <= '\u06FF' for c in line_stripped):
            continue
        
        # Skip lines that are mostly non-word characters
        if mostly_garbage.match(line_stripped):
            continue
        
        # If we get here, it's likely actual tweet content
        skip_header = False
        
        # Remove inline @usernames from the text
        line_cleaned = re.sub(r'[@＠]\w+', '', line_stripped).strip()
        
        # Remove stray UI characters
        line_cleaned = re.sub(r'^[\|\}\{<>]+\s*', '', line_cleaned).strip()
        
        if line_cleaned and len(line_cleaned) > 2:
            cleaned_lines.append(line_cleaned)
    
    # Join lines
    result = '\n'.join(cleaned_lines)
    
    # Remove trailing garbage lines
    result_lines = result.split('\n')
    while result_lines:
        last_line = result_lines[-1].strip()
        # Remove if: very short, only ASCII chars, looks like UI element
        if (len(last_line) <= 5 or 
            re.match(r'^[A-Za-z0-9\s\|\.]+$', last_line) or
            not any('\u0600' <= c <= '\u06FF' or c.isalpha() for c in last_line)):
            result_lines.pop()
        else:
            break
    
    return '\n'.join(result_lines).strip()


def preprocess_image(img: Image.Image) -> Image.Image:
    """
    Preprocess image for better OCR accuracy.
    
    Applies:
    - Auto contrast enhancement
    - Sharpening filter
    
    Args:
        img: PIL Image object
        
    Returns:
        Preprocessed PIL Image
    """
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def ocr_image(img: Image.Image, lang: str = "eng+fas") -> str:
    """
    Perform OCR on an image.
    
    Args:
        img: PIL Image object
        lang: Tesseract language codes (default: English + Persian/Farsi)
        
    Returns:
        Extracted text string
    """
    # Convert to grayscale for better OCR
    gray = ImageOps.grayscale(img)
    return pytesseract.image_to_string(gray, lang=lang)


def extract_tweet_ocr(image_path: str) -> dict:
    """
    Extract text from a tweet screenshot.
    
    Args:
        image_path: Path to the screenshot image
        
    Returns:
        dict with keys:
            - 'text': Extracted text content
            - 'author': Empty string (not detected with simple OCR)
            - 'confidence': 1.0 (Tesseract doesn't provide per-result confidence easily)
    """
    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        return {
            'text': '',
            'author': '',
            'confidence': 0.0
        }
    
    try:
        logger.info(f"Running Tesseract OCR on {image_path}")
        
        # Open and preprocess image
        img = Image.open(image_path).convert("RGB")
        img = preprocess_image(img)
        
        # Perform OCR
        raw_text = ocr_image(img).strip()
        
        # Clean the text to remove author, date, engagement metrics, etc.
        text = clean_tweet_text(raw_text)
        
        logger.info(f"OCR completed: extracted {len(raw_text)} chars, cleaned to {len(text)} chars")
        
        return {
            'text': text,
            'author': '',  # Simple OCR doesn't detect author separately
            'confidence': 1.0 if text else 0.0
        }
        
    except Exception as e:
        logger.error(f"OCR extraction failed for {image_path}: {e}")
        return {
            'text': '',
            'author': '',
            'confidence': 0.0
        }
