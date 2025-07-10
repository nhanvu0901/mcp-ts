import {FastifyRequest, FastifyReply} from 'fastify';
import {v4 as uuidv4} from 'uuid';
import {writeFile, mkdir, unlink} from 'fs/promises';
import {join} from 'path';
import {Readable} from 'stream';
import {
    DocumentUploadResponse,
    UploadDocumentBody,
    DocumentProcessingResult
} from '../types/document.types';

export class DocumentController {
    public static async uploadDocument(
        request: FastifyRequest<{ Body: UploadDocumentBody }>,
        reply: FastifyReply
    ): Promise<DocumentUploadResponse> {
        try {
            const {fileData, sessionId, userId} = await DocumentController.parseMultipartData(request);

            if (!fileData) {
                return reply.status(400).send({
                    success: false,
                    error: 'No file uploaded'
                });
            }

            if (!userId) {
                return reply.status(400).send({
                    success: false,
                    error: 'user_id is required'
                });
            }

            const result = await DocumentController.processDocumentUpload(
                request,
                fileData,
                sessionId,
                userId,
                true
            );

            return reply.send(result);

        } catch (error) {
            request.log.error('Error uploading document:', error);
            return reply.status(500).send({
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error occurred'
            });
        }
    }

    public static async uploadDocumentMongo(
        request: FastifyRequest<{ Body: UploadDocumentBody }>,
        reply: FastifyReply
    ): Promise<DocumentUploadResponse> {
        try {
            const {fileData, sessionId, userId} = await DocumentController.parseMultipartData(request);

            if (!fileData) {
                return reply.status(400).send({
                    success: false,
                    error: 'No file uploaded'
                });
            }

            if (!userId) {
                return reply.status(400).send({
                    success: false,
                    error: 'user_id is required'
                });
            }

            const result = await DocumentController.processDocumentUpload(
                request,
                fileData,
                sessionId,
                userId,
                false
            );

            return reply.send(result);

        } catch (error) {
            request.log.error('Error uploading document to MongoDB:', error);
            return reply.status(500).send({
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error occurred'
            });
        }
    }

    private static async parseMultipartData(request: FastifyRequest): Promise<{
        fileData: { filename: string; mimetype: string; buffer: Buffer } | null;
        sessionId: string;
        userId: string | null;
    }> {
        const fields: Record<string, string> = {};
        let fileData: { filename: string; mimetype: string; buffer: Buffer } | null = null;

        const parts = request.parts();

        for await (const part of parts) {
            if (part.type === 'file') {
                const buffer = await DocumentController.streamToBuffer(part.file);
                fileData = {
                    filename: part.filename || 'unknown',
                    mimetype: part.mimetype || 'application/octet-stream',
                    buffer: buffer
                };
            } else {
                fields[part.fieldname] = (part as any).value;
            }
        }

        return {
            fileData,
            sessionId: fields.session_id || 'default',
            userId: fields.user_id || null
        };
    }

    private static async processDocumentUpload(
        request: FastifyRequest,
        fileData: { filename: string; mimetype: string; buffer: Buffer },
        sessionId: string,
        userId: string,
        embed: boolean
    ): Promise<DocumentUploadResponse> {
        const docId = uuidv4();
        const filename = fileData.filename;
        const docType = filename.split('.').pop()?.toLowerCase() || 'unknown';

        const allowedTypes = ['pdf', 'docx', 'doc', 'txt', 'md', 'csv', 'py', 'tex', 'html'];
        if (!allowedTypes.includes(docType)) {
            throw new Error(`Unsupported file type: ${docType}. Allowed types: ${allowedTypes.join(', ')}`);
        }

        const uploadDir = process.env.UPLOAD_DIR || '/app/data/uploads';
        await mkdir(uploadDir, {recursive: true});

        const filePath = join(uploadDir, `${docId}_${filename}`);
        await writeFile(filePath, fileData.buffer);

        request.log.info({
            docId,
            filename,
            docType,
            sessionId,
            userId,
            embed,
            filePath,
            fileSize: fileData.buffer.length
        }, 'Processing document upload');

        let processingResult: DocumentProcessingResult;

        try {
            const tools = await request.server.mcpClient.getTools();
            //Docker
            // const sharedVolumePath = `/app/data/uploads/${docId}_${filename}`;
            //Local
            const sharedVolumePath = `./data/uploads/${docId}_${filename}`;
            if (embed) {
                const processDocumentTool = tools.find(tool => tool.name === 'mcp__DocumentService__process_document');
                if (!processDocumentTool) {
                    throw new Error('process_document tool not found');
                }

                const result = await processDocumentTool.invoke({
                    file_path: sharedVolumePath,
                    filename: filename,
                    document_id: docId,
                    user_id: userId
                });

                processingResult = DocumentController.parseToolResult(result);
            } else {
                const uploadMongoTool = tools.find(tool => tool.name === 'upload_and_save_to_mongo');
                if (!uploadMongoTool) {
                    throw new Error('upload_and_save_to_mongo tool not found');
                }

                const result = await uploadMongoTool.invoke({
                    file_path: sharedVolumePath,
                    filename: filename,
                    document_id: docId
                });

                processingResult = DocumentController.parseToolResult(result);
            }

            await unlink(filePath).catch(err =>
                request.log.warn(`Failed to cleanup file ${filePath}: ${err.message}`)
            );

        } catch (error) {
            await unlink(filePath).catch(() => {
            });
            throw new Error(`MCP tool invocation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }

        if (processingResult.status === 'error') {
            throw new Error(`Document processing failed: ${processingResult.error}`);
        }

        return {
            success: true,
            doc_id: docId,
            filename: filename,
            session_id: sessionId,
            user_id: userId,
            embed: embed,
            processing_result: processingResult
        };
    }

    private static async streamToBuffer(stream: Readable): Promise<Buffer> {
        const chunks: Buffer[] = [];

        return new Promise((resolve, reject) => {
            stream.on('data', (chunk) => chunks.push(chunk));
            stream.on('end', () => resolve(Buffer.concat(chunks)));
            stream.on('error', reject);
        });
    }

    private static parseToolResult(result: any): DocumentProcessingResult {
        if (typeof result === 'string') {
            try {
                return JSON.parse(result);
            } catch {
                return {status: 'error', error: 'Invalid response format'};
            }
        }
        return result;
    }
}