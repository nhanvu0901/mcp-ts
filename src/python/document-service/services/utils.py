import pymupdf4llm
import pymupdf
from docx import Document
import pandas as pd
import os
from typing import Tuple, List, Dict
import re


def clean_document_text(text: str) -> str:
    """Clean document text by removing headers, watermarks, and artifacts"""

    # Remove common document headers/watermarks
    text = re.sub(r'\b(INTERNAL|CONFIDENTIAL|PROPRIETARY|DRAFT)\b', '', text, flags=re.IGNORECASE)

    # Remove repeated headers at line beginnings
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



def extract_text_from_pdf_with_pages(file_path: str) -> Tuple[str, List[Dict]]:
    doc = pymupdf.open(file_path)
    full_text = ""
    page_info = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_text = page.get_text()

        if page_text.strip():
            # Clean page text before processing
            page_text = clean_document_text(page_text)

            start_pos = len(full_text)
            full_text += page_text
            end_pos = len(full_text)

            page_info.append({
                "page_number": page_num + 1,
                "start_position": start_pos,
                "end_position": end_pos,
                "text_length": len(page_text)
            })

    doc.close()
    return full_text, page_info


def extract_text_from_docx_with_pages(file_path: str) -> Tuple[str, List[Dict]]:
    doc = Document(file_path)
    md_lines = []
    page_info = []

    chars_per_page = 2500
    current_char_count = 0
    current_page = 1

    for para in doc.paragraphs:
        style = para.style.name
        text = ""

        if style.startswith("Heading"):
            level = int(style.split()[-1])
            text = f"{'#' * level} {para.text}"
        elif style == "List Paragraph":
            text = f"- {para.text}"
        else:
            for run in para.runs:
                run_text = run.text
                if not run_text.strip():
                    text += run_text
                    continue
                if run.bold:
                    run_text = f"**{run_text}**"
                if run.italic:
                    run_text = f"*{run_text}*"
                if run.underline:
                    run_text = f"_{run_text}_"
                text += run_text

        start_pos = len("\n\n".join(md_lines))
        md_lines.append(text)
        current_char_count += len(text)

        if current_char_count > chars_per_page:
            page_info.append({
                "page_number": current_page,
                "start_position": start_pos,
                "end_position": len("\n\n".join(md_lines)),
                "estimated": True
            })
            current_page += 1
            current_char_count = 0

    if current_char_count > 0:
        page_info.append({
            "page_number": current_page,
            "start_position": len("\n\n".join(md_lines[:-1])) if len(md_lines) > 1 else 0,
            "end_position": len("\n\n".join(md_lines)),
            "estimated": True
        })

    full_text = "\n\n".join(md_lines)
    # Clean the complete text
    full_text = clean_document_text(full_text)

    return full_text, page_info


def extract_text_with_pages(file_path: str) -> Tuple[str, List[Dict]]:
    file_type = file_path.split('.')[-1].lower()

    if file_type == 'pdf':
        return extract_text_from_pdf_with_pages(file_path)
    elif file_type in ['docx', 'doc']:
        return extract_text_from_docx_with_pages(file_path)
    else:
        text = extract_text(file_path)
        text = clean_document_text(text)
        page_info = [{
            "page_number": 1,
            "start_position": 0,
            "end_position": len(text),
            "estimated": False
        }]
        return text, page_info


def determine_chunk_page(chunk_start: int, chunk_end: int, page_info: List[Dict]) -> int:
    best_page = 1
    max_overlap = 0

    for page in page_info:
        overlap_start = max(chunk_start, page["start_position"])
        overlap_end = min(chunk_end, page["end_position"])
        overlap = max(0, overlap_end - overlap_start)

        if overlap > max_overlap:
            max_overlap = overlap
            best_page = page["page_number"]

    return best_page


# ====== ORIGINAL/LEGACY FUNCTIONS ======

def extract_text_from_pdf(file_path: str,
                          pages: list[int] = None,
                          write_images: bool = False,
                          image_path: str = None) -> str:
    """Legacy PDF extraction for backward compatibility"""
    text = pymupdf4llm.to_markdown(file_path, pages=pages, write_images=write_images, image_path=image_path)
    return clean_document_text(text)


def extract_text_from_docx(file_path: str) -> str:
    """Legacy DOCX extraction for backward compatibility"""
    text, _ = extract_text_from_docx_with_pages(file_path)
    return text


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


def extract_text(file_path: str) -> str:
    """Legacy text extraction for backward compatibility"""
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
    }

    if file_type not in extractors:
        raise ValueError(f"Unsupported file type: {file_type}")

    return extractors[file_type](file_path)