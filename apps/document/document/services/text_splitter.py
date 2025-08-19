from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter,
    SpacyTextSplitter,
    NLTKTextSplitter,
    MarkdownHeaderTextSplitter,
    HTMLHeaderTextSplitter,
    PythonCodeTextSplitter,
    LatexTextSplitter
)
from typing import List, Tuple, Dict
from .config import ChunkingMethod, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
from .utils import determine_chunk_page


class TextSplitter:
    def __init__(self):
        pass

    def get_splitter(self, method: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
                     overlap: int = DEFAULT_CHUNK_OVERLAP, **kwargs):

        splitters = {
            ChunkingMethod.RECURSIVE_CHARACTER: lambda: RecursiveCharacterTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, **kwargs
            ),
            ChunkingMethod.CHARACTER: lambda: CharacterTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, **kwargs
            ),
            ChunkingMethod.TOKEN: lambda: TokenTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, **kwargs
            ),
            ChunkingMethod.SPACY: lambda: SpacyTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, **kwargs
            ),
            ChunkingMethod.NLTK: lambda: NLTKTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, **kwargs
            ),
            ChunkingMethod.MARKDOWN_HEADER: lambda: MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "Header 1"),
                    ("##", "Header 2"),
                    ("###", "Header 3"),
                ], **kwargs
            ),
            ChunkingMethod.HTML_HEADER: lambda: HTMLHeaderTextSplitter(
                headers_to_split_on=[
                    ("h1", "Header 1"),
                    ("h2", "Header 2"),
                    ("h3", "Header 3"),
                ], **kwargs
            ),
            ChunkingMethod.PYTHON_CODE: lambda: PythonCodeTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, **kwargs
            ),
            ChunkingMethod.LATEX: lambda: LatexTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, **kwargs
            ),
        }

        return splitters.get(method, splitters[ChunkingMethod.RECURSIVE_CHARACTER])()

    def auto_select_method(self, file_type: str) -> str:
        auto_mapping = {
            "md": ChunkingMethod.MARKDOWN_HEADER,
            "py": ChunkingMethod.PYTHON_CODE,
            "tex": ChunkingMethod.LATEX,
            "html": ChunkingMethod.HTML_HEADER,
        }
        return auto_mapping.get(file_type, ChunkingMethod.RECURSIVE_CHARACTER)

    def split_text(self, text: str, method: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
                   overlap: int = DEFAULT_CHUNK_OVERLAP, **kwargs) -> List[str]:

        splitter = self.get_splitter(method, chunk_size, overlap, **kwargs)

        if method in [ChunkingMethod.MARKDOWN_HEADER, ChunkingMethod.HTML_HEADER]:
            chunks = splitter.split_text(text)
            return [chunk.page_content if hasattr(chunk, 'page_content') else str(chunk) for chunk in chunks]
        else:
            return splitter.split_text(text)

    def split_text_with_pages(self, text: str, page_info: List[Dict], method: str,
                              chunk_size: int = DEFAULT_CHUNK_SIZE,
                              overlap: int = DEFAULT_CHUNK_OVERLAP, **kwargs) -> Tuple[List[str], List[int]]:
        """Split text into chunks and determine page number for each chunk"""

        chunks = self.split_text(text, method, chunk_size, overlap, **kwargs)
        chunk_pages = []

        current_pos = 0
        for chunk in chunks:
            chunk_start = text.find(chunk, current_pos)
            if chunk_start == -1:
                chunk_start = current_pos

            chunk_end = chunk_start + len(chunk)
            page_number = determine_chunk_page(chunk_start, chunk_end, page_info)
            chunk_pages.append(page_number)

            current_pos = chunk_start + 1

        return chunks, chunk_pages