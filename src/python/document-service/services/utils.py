import pymupdf4llm
from docx import Document
import pandas as pd
import os
from pymongo import MongoClient


def extract_text_from_pdf(file_path: str, 
                          pages: list[int] = None,
                          write_images: bool = False,
                          image_path: str = None) -> str:
    return pymupdf4llm.to_markdown(file_path, pages=pages, write_images=write_images, image_path=image_path)


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    md_lines = []

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

        md_lines.append(text)
    
    return "\n\n".join(md_lines)


def extract_text_from_txt(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def extract_text_from_csv(file_path: str) -> str:
    df = pd.read_csv(file_path)
    return df.to_string()


def read_file_content(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


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
    }
    
    if file_type not in extractors:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    return extractors[file_type](file_path)


    
    return doc["text"]