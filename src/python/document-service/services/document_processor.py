from langchain_openai import AzureOpenAIEmbeddings
from pymongo import MongoClient
from .mongo_service import MongoService
from .qdrant_service import QdrantService
from .text_splitter import TextSplitter
from .config import ChunkingMethod, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
# ADD: Import OCR function
from .utils import extract_text, extract_text_with_pages, extract_text_with_ocr, clean_document_text
from .config import DEFAULT_QDRANT_HOST


class DocumentProcessor:
    def __init__(self,
                 collection_name: str,
                 embedding_model: AzureOpenAIEmbeddings,
                 mongo_client: MongoClient = None,
                 qdrant_host: str = DEFAULT_QDRANT_HOST,
                 qdrant_port: int = 6333,
                 vector_size: int = 3072):

        if not embedding_model:
            raise ValueError("embedding_model must be provided")

        self.embedding_model = embedding_model
        self.mongo_service = MongoService(mongo_client) if mongo_client else None
        self.qdrant_service = QdrantService(collection_name, qdrant_host, qdrant_port, vector_size)
        self.text_splitter = TextSplitter()

        print("DocumentProcessor initialized successfully!")

    def extract_and_save_to_mongo(self, file_path: str, document_id: str, user_id: str,
                                  document_name: str = None, file_type: str = None,
                                  metadata: dict = None):

        if not self.mongo_service:
            raise ValueError("MongoDB service not initialized")

        text = extract_text(file_path)

        text = clean_document_text(text)

        meta = metadata or {}
        meta.update({
            "document_name": document_name,
            "file_type": file_type
        })

        success = self.mongo_service.save_document(document_id, text, user_id, meta)

        if success:
            print(f"[MongoDB] Saved extracted text for document_id={document_id}")

        return text

    def process_and_embed(self,
                          text: str,
                          document_id: str,
                          user_id: str,
                          document_name: str = None,
                          file_type: str = None,
                          method: str = ChunkingMethod.RECURSIVE_CHARACTER,
                          chunk_size: int = DEFAULT_CHUNK_SIZE,
                          overlap: int = DEFAULT_CHUNK_OVERLAP,
                          metadata: dict = None,
                          page_info: list = None,
                          **kwargs):

        text = clean_document_text(text)

        if method == "auto":
            method = self.text_splitter.auto_select_method(file_type)

        if page_info:
            chunks, chunk_pages = self.text_splitter.split_text_with_pages(
                text, page_info, method, chunk_size, overlap, **kwargs
            )
        else:
            chunks = self.text_splitter.split_text(text, method, chunk_size, overlap, **kwargs)
            chunk_pages = [1] * len(chunks)


        chunks = [clean_document_text(chunk) for chunk in chunks if clean_document_text(chunk).strip()]

        if not chunks:
            print(f"No chunks created for document_id={document_id}")
            return False

        try:
            embeddings = self.embedding_model.embed_documents(chunks)
        except Exception as e:
            print(f"Error embedding chunks for document_id={document_id}: {e}")
            return False

        metadata_list = []
        for i, page_number in enumerate(chunk_pages):
            base_metadata = {
                "document_name": document_name,
                "chunk_method": method,
                "file_type": file_type,
                "document_id": document_id
            }
            if file_type in ['pdf', 'doc', 'docx']:
                base_metadata["page_number"] = page_number
            metadata_list.append(base_metadata)

        success = self.qdrant_service.upsert_chunks(chunks, embeddings, metadata_list, user_id)

        if success and self.mongo_service:
            mongo_metadata = {
                "document_name": document_name,
                "file_type": file_type
            }

            if metadata:
                mongo_metadata.update(metadata)

            print(f"[DocumentProcessor] Saving to MongoDB with metadata: {mongo_metadata}")

            self.mongo_service.save_document(document_id, text, user_id, mongo_metadata)

        return success

    def process_file(self, file_path: str, document_id: str, user_id: str,
                     document_name: str = None, file_type: str = None,
                     embed: bool = False, metadata: dict = None, **kwargs):

        if embed:
            try:
                text, page_info = extract_text_with_pages(file_path)
                return self.process_and_embed(
                    text=text,
                    document_id=document_id,
                    user_id=user_id,
                    document_name=document_name,
                    file_type=file_type,
                    metadata=metadata,
                    page_info=page_info,
                    **kwargs
                )
            except Exception as e:
                print(f"Error processing with pages: {e}, falling back to legacy method")
                text = extract_text(file_path)
                return self.process_and_embed(
                    text=text,
                    document_id=document_id,
                    user_id=user_id,
                    document_name=document_name,
                    file_type=file_type,
                    metadata=metadata,
                    **kwargs
                )
        else:
            if not self.mongo_service:
                raise ValueError("MongoDB service not initialized")

            text = extract_text(file_path)

            meta = metadata or {}
            meta.update({
                "document_name": document_name,
                "file_type": file_type
            })

            print(f"[DocumentProcessor] Saving to MongoDB only with metadata: {meta}")

            return self.mongo_service.save_document(document_id, text, user_id, meta)

    # ADD: New method for OCR processing
    def process_file_with_ocr(self, file_path: str, document_id: str, user_id: str,
                             document_name: str = None, file_type: str = None,
                             embed: bool = False, metadata: dict = None,
                             suggested_languages: list[str] = None,
                             use_llm: bool = True, **kwargs):
        """
        Process file using OCR extraction method.
        
        Args:
            file_path (str): Path to the file
            document_id (str): Unique document identifier
            user_id (str): User identifier
            document_name (str, optional): Name of the document
            file_type (str, optional): Type of the file
            embed (bool): Whether to create embeddings
            metadata (dict, optional): Additional metadata
            suggested_languages (list[str], optional): Languages for OCR (e.g., ['eng', 'vie'])
            use_llm (bool): Whether to use LLM for text correction
            **kwargs: Additional arguments for chunking
        """
        if embed:
            try:
                # Use OCR extraction with page info
                text, page_info = extract_text_with_ocr(
                    file_path, 
                    suggested_languages=suggested_languages,
                    use_llm=use_llm
                )
                
                # ADD: Mark metadata to indicate OCR was used
                ocr_metadata = metadata or {}
                ocr_metadata.update({
                    "extraction_method": "ocr",
                    "ocr_languages": suggested_languages or ["eng"],
                    "llm_enhanced": use_llm
                })
                
                return self.process_and_embed(
                    text=text,
                    document_id=document_id,
                    user_id=user_id,
                    document_name=document_name,
                    file_type=file_type,
                    metadata=ocr_metadata,
                    page_info=page_info,
                    **kwargs
                )
            except Exception as e:
                print(f"Error processing with OCR: {e}, falling back to regular extraction")
                # Fallback to regular processing
                return self.process_file(
                    file_path=file_path,
                    document_id=document_id,
                    user_id=user_id,
                    document_name=document_name,
                    file_type=file_type,
                    embed=embed,
                    metadata=metadata,
                    **kwargs
                )
        else:
            # For non-embedding case, use OCR for text extraction only
            if not self.mongo_service:
                raise ValueError("MongoDB service not initialized")

            try:
                # Extract text using OCR
                text, _ = extract_text_with_ocr(
                    file_path,
                    suggested_languages=suggested_languages,
                    use_llm=use_llm
                )
                
                # ADD: Mark metadata to indicate OCR was used
                meta = metadata or {}
                meta.update({
                    "document_name": document_name,
                    "file_type": file_type,
                    "extraction_method": "ocr",
                    "ocr_languages": suggested_languages or ["eng"],
                    "llm_enhanced": use_llm
                })

                print(f"[DocumentProcessor] Saving OCR text to MongoDB with metadata: {meta}")
                return self.mongo_service.save_document(document_id, text, user_id, meta)
                
            except Exception as e:
                print(f"Error with OCR extraction: {e}, falling back to regular extraction")
                # Fallback to regular method
                return self.extract_and_save_to_mongo(
                    file_path, document_id, user_id, document_name, file_type, metadata
                )

    def delete_document(self, document_id: str, user_id: str) -> bool:
        mongo_success = True
        qdrant_success = True

        if self.mongo_service:
            mongo_success = self.mongo_service.delete_document(document_id, user_id)
        qdrant_success = self.qdrant_service.delete_document_chunks(document_id, user_id)
        return mongo_success and qdrant_success

    def search_documents(self, query: str, user_id: str, collection_id: str = None, limit: int = 10):
        try:
            query_embedding = self.embedding_model.embed_query(query)
            return self.qdrant_service.search_documents(query_embedding, user_id, collection_id, limit)
        except Exception as e:
            print(f"Error in search_documents: {e}")
            return []