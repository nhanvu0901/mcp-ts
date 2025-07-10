import { FastifyInstance } from "fastify";
import {
    DocumentUploadSchema,
    DocumentUploadMongoSchema
} from "./schema/document.schema";
import { DocumentController } from "../controllers/document.controller";

async function documentRoutes(server: FastifyInstance): Promise<void> {

    server.route({
        url: "/upload",
        method: "POST",
        schema: DocumentUploadSchema,
        handler: DocumentController.uploadDocument
    });

    server.route({
        url: "/upload-mongo",
        method: "POST",
        schema: DocumentUploadMongoSchema,
        handler: DocumentController.uploadDocumentMongo
    });

}

export default documentRoutes;