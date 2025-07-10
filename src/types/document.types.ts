export interface DocumentUploadRequest {
    file: File;
    session_id?: string;
    user_id: string;
    embed?: boolean;
}

export interface UploadDocumentBody {
    file: Buffer;
    session_id?: string;
    user_id: string;
}

export interface DocumentProcessingResult {
    status: 'success' | 'error';
    document_id?: string;
    filename?: string;
    file_path?: string;
    collection_id?: string;
    error?: string;
    mongo_saved?: boolean;
}

export interface DocumentUploadResponse {
    success: boolean;
    doc_id: string;
    session_id: string;
    user_id: string;
    filename: string;
    embed: boolean;
    collection_name?: string;
    mongo_saved?: boolean;
    processing_result: DocumentProcessingResult;
    error?: string;
}

export type SupportedDocumentType =
    | 'pdf'
    | 'docx'
    | 'doc'
    | 'txt'
    | 'md'
    | 'csv'
    | 'py'
    | 'tex'
    | 'html';

export interface DocumentErrorResponse {
    success: false;
    error: string;
    doc_id?: string;
    session_id?: string;
    user_id?: string;
}