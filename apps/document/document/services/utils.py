import pymupdf4llm
import pymupdf
from docx import Document
import pandas as pd
import os
import re
import subprocess
import tempfile

import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple
from .ocr import (
    convert_pdf_to_images,
    ocr_image,
    ocr_image_with_lang,
    process_document,
    remove_corrected_text_header,
    assess_output_quality
)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def clean_document_text(text: str) -> str:
    text = re.sub(r'^\s*(INTERNAL|CONFIDENTIAL|PROPRIETARY|DRAFT)\s*\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(INTERNAL|CONFIDENTIAL|PROPRIETARY|DRAFT)\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)

    # Remove excessive whitespace and empty lines
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

    # Remove trailing/leading whitespace from lines
    text = '\n'.join(line.strip() for line in text.split('\n'))

    # Remove empty lines at start/end
    text = text.strip()

    # Remove page numbers pattern (optional)
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)

    # Remove standalone dates/timestamps (optional)
    text = re.sub(r'\n\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*\n', '\n', text)
    return text

async def extract_pdf_with_ocr(file_path: str,
                              suggested_languages: list[str] = None,
                              use_llm: bool = True) -> Tuple[str, List[Dict]]:
    """
    Extract text from PDF using OCR with page tracking information.

    Args:
        file_path (str): Path to the PDF file
        suggested_languages (list[str], optional): Languages for OCR (e.g., ['eng', 'vie'])
        use_llm (bool): Whether to use LLM for text correction and formatting

    Returns:
        Tuple[str, List[Dict]]: Extracted text and page information
            - str: Full extracted and processed text
            - List[Dict]: Page info with structure:
                [{"page_number": int, "start_position": int, "end_position": int, "text_length": int}]
    """
    try:
        logging.info(f"Starting OCR extraction for: {file_path}")

        list_of_scanned_images = convert_pdf_to_images(file_path, max_pages=0, skip_first_n_pages=0)

        logging.info(f"Converted {len(list_of_scanned_images)} pages to images")
        logging.info("Extracting text from converted pages...")

        lang_code = "+".join(suggested_languages) if suggested_languages else None

        with ThreadPoolExecutor() as executor:
            if lang_code:
                page_texts = list(
                    executor.map(lambda img: ocr_image_with_lang(img, lang_code), list_of_scanned_images)
                )
            else:
                page_texts = list(executor.map(ocr_image, list_of_scanned_images))

        logging.info("Text extraction from images complete")

        # Build page info and concatenate text
        page_info = []
        full_text = ""

        for page_num, page_text in enumerate(page_texts):
            # Clean page text
            cleaned_page_text = clean_document_text(page_text) if page_text.strip() else ""

            start_pos = len(full_text)

            # Add text to full_text (even if empty, to maintain page structure)
            if cleaned_page_text:
                full_text += cleaned_page_text

            # Add page separator between pages (not after last page)
            if page_num < len(page_texts) - 1:
                full_text += "\n\n"

            end_pos = len(full_text)

            # Create page info
            page_info_entry = {
                "page_number": page_num + 1,
                "start_position": start_pos,
                "end_position": end_pos,
                "text_length": len(cleaned_page_text),
                "ocr_extracted": True
            }

            # Add flag for empty pages
            if not cleaned_page_text:
                page_info_entry["empty_page"] = True

            page_info.append(page_info_entry)

        # Store original text and page info for quality assessment
        original_full_text = full_text
        original_page_info = page_info.copy()

        # If LLM processing is requested, process the text
        if use_llm and full_text.strip():
            logging.info("Processing with LLM for correction and formatting...")

            # Use existing LLM processing pipeline
            processed_text = await process_document(
                page_texts,  # Pass original page texts for better processing
                reformat_as_markdown=True,
                suppress_headers_and_page_numbers=True
            )

            if processed_text and processed_text.strip():
                processed_text = remove_corrected_text_header(processed_text)

                # Update page info positions based on processed text
                page_info = _recalculate_page_positions(processed_text, len(page_texts))

                # Quality assessment
                try:
                    quality_score, explanation = await assess_output_quality(original_full_text, processed_text)
                    if quality_score is not None:
                        logging.info(f"OCR Quality score: {quality_score}/100")
                        logging.info(f"Quality explanation: {explanation}")
                except Exception as e:
                    logging.warning(f"Quality assessment failed: {e}")

                full_text = processed_text
            else:
                logging.warning("LLM processing returned empty result, using raw OCR text")
                page_info = original_page_info  # Restore original page info

        # Final cleaning
        full_text = clean_document_text(full_text)

        logging.info(f"OCR extraction complete. Total pages: {len(page_info)}, Text length: {len(full_text)}")

        return full_text, page_info

    except Exception as e:
        logging.error(f"Error in extract_pdf_with_ocr: {e}")
        logging.error(traceback.format_exc())
        raise


def _recalculate_page_positions(processed_text: str, num_pages: int) -> List[Dict]:
    """
    Recalculate page positions after LLM processing.
    Since LLM can change text structure, we estimate page boundaries.
    """
    page_info = []
    text_length = len(processed_text)

    if num_pages <= 0:
        return page_info

    chars_per_page = text_length // num_pages

    for page_num in range(num_pages):
        start_pos = page_num * chars_per_page
        end_pos = min((page_num + 1) * chars_per_page, text_length)

        # For the last page, make sure we capture all remaining text
        if page_num == num_pages - 1:
            end_pos = text_length

        page_info.append({
            "page_number": page_num + 1,
            "start_position": start_pos,
            "end_position": end_pos,
            "text_length": end_pos - start_pos,
            "ocr_extracted": True,
            "estimated_after_llm": True
        })

    return page_info


def extract_text_with_ocr(file_path: str,
                          suggested_languages: list[str] = None,
                          use_llm: bool = True) -> Tuple[str, List[Dict]]:
    """
    Extract text with OCR support for PDF files.
    This is a sync wrapper around the async OCR function.

    Args:
        file_path (str): Path to the file
        suggested_languages (list[str], optional): Languages for OCR
        use_llm (bool): Whether to use LLM for text correction (only for OCR)
    """
    file_type = file_path.split('.')[-1].lower()

    if file_type == 'pdf':
        # Always use OCR for PDF in this function
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                extract_pdf_with_ocr(file_path, suggested_languages, use_llm)
            )
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(
                extract_pdf_with_ocr(file_path, suggested_languages, use_llm)
            )
    elif file_type in ['pptx', 'ppt']:
        try:
            if _is_libreoffice_available():
                return _convert_pptx_to_pdf_and_process(file_path, use_ocr=True,
                                                        suggested_languages=suggested_languages,
                                                        use_llm=use_llm)
            else:
                raise Exception("LibreOffice not available for PowerPoint OCR")
        except Exception as e:
            logger.error(f"PowerPoint OCR processing failed: {e}")
            raise
    else:
        # For non-PDF files, fall back to regular extraction
        text = extract_text(file_path)
        text = clean_document_text(text)
        page_info = [{
            "page_number": 1,
            "start_position": 0,
            "end_position": len(text),
            "estimated": False,
            "ocr_extracted": False
        }]
        return text, page_info


def extract_pptx_with_pages(file_path: str) -> Tuple[str, List[Dict]]:
    """Extract text from PowerPoint with slide information."""
    try:
        if _is_libreoffice_available():
            return _convert_pptx_to_pdf_and_process(file_path, use_ocr=False)
        else:
            raise Exception("LibreOffice not available for PowerPoint processing")
    except Exception as e:
        logger.error(f"PowerPoint extraction failed: {e}")
        raise


def _convert_pptx_to_pdf_and_process(file_path: str, use_ocr: bool = False,
                                     suggested_languages: list[str] = None,
                                     use_llm: bool = True) -> Tuple[str, List[Dict]]:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            conversion_cmd = [
                'libreoffice', '--headless', '--invisible', '--nodefault',
                '--nolockcheck', '--nologo', '--norestore',
                '--convert-to', 'pdf', '--outdir', temp_dir, file_path
            ]

            result = subprocess.run(conversion_cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                raise Exception(f"LibreOffice PowerPoint conversion failed: {result.stderr}")

            pdf_files = [f for f in os.listdir(temp_dir) if f.endswith('.pdf')]
            if not pdf_files:
                raise Exception("PowerPoint to PDF conversion failed - no PDF output")

            pdf_path = os.path.join(temp_dir, pdf_files[0])
            logger.info(f"PowerPoint converted to PDF: {pdf_files[0]}")

            if use_ocr:
                try:
                    loop = asyncio.get_event_loop()
                    text, page_info = loop.run_until_complete(
                        extract_pdf_with_ocr(pdf_path, suggested_languages, use_llm)
                    )
                except RuntimeError:
                    text, page_info = asyncio.run(
                        extract_pdf_with_ocr(pdf_path, suggested_languages, use_llm)
                    )
            else:
                text, page_info = extract_pdf_with_pages(pdf_path)

            # Update page_info to indicate these are slides, not PDF pages
            for page in page_info:
                page["page_number"] = page["page_number"]  # Add slide reference
                page["converted_from_pptx"] = True

            logger.info(f"PowerPoint processing complete: {len(page_info)} slides processed")
            return text, page_info

    except Exception as e:
        logger.error(f"LibreOffice conversion failed: {e}")
        raise


def extract_pdf_with_pages(file_path: str) -> Tuple[str, List[Dict]]:
    markdown_text = pymupdf4llm.to_markdown(file_path)
    cleaned_text = clean_document_text(markdown_text)
    doc = pymupdf.open(file_path)
    page_info = []
    cumulative_chars = 0

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_text = clean_document_text(page.get_text())

        if page_text.strip():
            page_info.append({
                "page_number": page_num + 1,
                "start_position": cumulative_chars,
                "end_position": cumulative_chars + len(page_text),
                "text_length": len(page_text)
            })
            cumulative_chars += len(page_text)

    doc.close()

    if not page_info:
        return cleaned_text, [{
            "page_number": 1,
            "start_position": 0,
            "end_position": len(cleaned_text),
            "estimated": True
        }]

    return cleaned_text, page_info


def extract_docx_with_pages(file_path: str) -> Tuple[str, List[Dict]]:
    try:
        if _is_libreoffice_available():
            return _convert_docx_to_pdf_and_extract(file_path)
    except Exception:
        pass

    return _extract_docx_direct(file_path)


def _is_libreoffice_available() -> bool:
    try:
        result = subprocess.run(['libreoffice', '--version'],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _convert_docx_to_pdf_and_extract(file_path: str) -> Tuple[str, List[Dict]]:
    with tempfile.TemporaryDirectory() as temp_dir:
        conversion_cmd = [
            'libreoffice', '--headless', '--invisible', '--nodefault',
            '--nolockcheck', '--nologo', '--norestore',
            '--convert-to', 'pdf', '--outdir', temp_dir, file_path
        ]

        result = subprocess.run(conversion_cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            raise Exception(f"LibreOffice conversion failed: {result.stderr}")

        pdf_files = [f for f in os.listdir(temp_dir) if f.endswith('.pdf')]
        if not pdf_files:
            raise Exception("PDF conversion failed")

        pdf_path = os.path.join(temp_dir, pdf_files[0])
        return extract_pdf_with_pages(pdf_path)


def _extract_docx_direct(file_path: str) -> Tuple[str, List[Dict]]:
    doc = Document(file_path)
    paragraphs = []
    page_info = []
    current_page = 1
    chars_per_page = 2000
    current_char_count = 0
    page_start = 0

    for para in doc.paragraphs:
        page_break_found = any(
            run.element.xpath('.//w:br[@w:type="page"]')
            for run in para.runs
        )

        text = _format_paragraph(para)
        if text.strip():
            paragraphs.append(text)
            current_char_count += len(text)

            if page_break_found or current_char_count > chars_per_page:
                page_end = len('\n\n'.join(paragraphs))
                page_info.append({
                    "page_number": current_page,
                    "start_position": page_start,
                    "end_position": page_end,
                    "text_length": page_end - page_start,
                    "estimated": not page_break_found
                })
                current_page += 1
                page_start = page_end
                current_char_count = 0

    if current_char_count > 0:
        page_end = len('\n\n'.join(paragraphs))
        page_info.append({
            "page_number": current_page,
            "start_position": page_start,
            "end_position": page_end,
            "text_length": page_end - page_start,
            "estimated": True
        })

    full_text = clean_document_text('\n\n'.join(paragraphs))

    if not page_info:
        page_info = [{
            "page_number": 1,
            "start_position": 0,
            "end_position": len(full_text),
            "estimated": True
        }]

    return full_text, page_info


def _format_paragraph(para) -> str:
    style = para.style.name

    if style.startswith("Heading"):
        level = int(style.split()[-1]) if style.split()[-1].isdigit() else 1
        return f"{'#' * level} {para.text}"
    elif style == "List Paragraph":
        return f"- {para.text}"
    else:
        text = ""
        for run in para.runs:
            run_text = run.text
            if run.bold:
                run_text = f"**{run_text}**"
            if run.italic:
                run_text = f"*{run_text}*"
            if run.underline:
                run_text = f"_{run_text}_"
            text += run_text
        return text


def extract_text_with_pages(file_path: str) -> Tuple[str, List[Dict]]:
    file_type = file_path.split('.')[-1].lower()

    if file_type == 'pdf':
        return extract_pdf_with_pages(file_path)
    elif file_type in ['docx', 'doc']:
        return extract_docx_with_pages(file_path)
    elif file_type in ['pptx', 'ppt']:  # Add this condition
        return extract_pptx_with_pages(file_path)
    else:
        text = extract_text(file_path)
        return text, [{
            "page_number": 1,
            "start_position": 0,
            "end_position": len(text),
            "estimated": False
        }]


def extract_text_from_txt(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return clean_document_text(text)


def extract_text_from_csv(file_path: str) -> str:
    df = pd.read_csv(file_path)
    text = df.to_string()
    return clean_document_text(text)


def read_file_content(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return clean_document_text(text)


def map_chunk_to_page_number(chunk_start: int, chunk_end: int, page_info: List[Dict]) -> int:
    if not page_info:
        return 1

    chunk_length = chunk_end - chunk_start
    chunk_midpoint = chunk_start + (chunk_length // 2)

    best_page = 1
    max_score = 0

    for page in page_info:
        page_start = page["start_position"]
        page_end = page["end_position"]

        # Calculate overlap
        overlap_start = max(chunk_start, page_start)
        overlap_end = min(chunk_end, page_end)
        overlap = max(0, overlap_end - overlap_start)

        # Skip pages with minimal overlap (less than 5% of chunk)
        if overlap < chunk_length * 0.05:
            continue

        # Calculate overlap percentage relative to chunk size
        overlap_percentage = overlap / chunk_length

        # Bonus points if chunk midpoint falls within this page
        midpoint_bonus = 0.3 if page_start <= chunk_midpoint <= page_end else 0

        # Bonus for high overlap percentage
        percentage_bonus = overlap_percentage * 0.7

        # Total score combines overlap percentage and midpoint position
        score = percentage_bonus + midpoint_bonus

        # Early exit for perfect overlap
        if overlap_percentage >= 0.95:
            return page["page_number"]

        if score > max_score:
            max_score = score
            best_page = page["page_number"]

    # Fallback: if no meaningful overlap found, use page containing midpoint
    if max_score == 0:
        for page in page_info:
            if page["start_position"] <= chunk_midpoint <= page["end_position"]:
                return page["page_number"]

    return best_page


def extract_text(file_path: str) -> str:
    file_type = file_path.split('.')[-1].lower()

    extractors = {
        'pdf': extract_text_from_pdf,
        'docx': extract_text_from_docx,
        'doc': extract_text_from_docx,
        'txt': extract_text_from_txt,
        'csv': extract_text_from_csv,
        'md': read_file_content,
        'py': read_file_content,
        'tex': read_file_content,
        'html': read_file_content,
        'pptx': extract_text_from_pptx,
        'ppt': extract_text_from_pptx,
    }

    if file_type not in extractors:
        raise ValueError(f"Unsupported file type: {file_type}")

    return extractors[file_type](file_path)


def extract_text_from_pdf(file_path: str, pages: list[int] = None,
                          write_images: bool = False, image_path: str = None) -> str:
    text = pymupdf4llm.to_markdown(file_path, pages=pages,
                                   write_images=write_images, image_path=image_path)
    return clean_document_text(text)


def extract_text_from_docx(file_path: str) -> str:
    text, _ = extract_docx_with_pages(file_path)
    return text


def extract_text_from_pptx(file_path: str) -> str:
    text, _ = extract_pptx_with_pages(file_path)
    return text


determine_chunk_page = map_chunk_to_page_number
