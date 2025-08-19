import 'reflect-metadata';
import { type FastifyInstance } from 'fastify';
import fp from 'fastify-plugin';
const errorHandlerPlugin = fp(async function errorHandlerPlugin(fastify: FastifyInstance) {
    fastify.setErrorHandler(async (error: any, request, reply) => {
        request.log.error(error, 'Unhandled error');
        const NODE_ENV = process.env.NODE_ENV
        const statusCode = error.statusCode || 500;
        let errorMessage = 'Internal Server Error';

        if (error instanceof Error) {
            errorMessage = error.message;
        } else if (typeof error === 'string') {
            errorMessage = error;
        } else if (error && typeof error === 'object' && error.message) {
            errorMessage = error.message;
        }

        const errorResponse: any = {
            success: false,
            error: errorMessage
        };

        if (NODE_ENV !== 'production') {
            errorResponse.debug = {
                statusCode,
                stack: error.stack,
                details: error
            };
        }

        reply.status(statusCode).send(errorResponse);
    });

    fastify.setNotFoundHandler(async (request, reply) => {
        reply.status(404).send({
            success: false,
            error: 'Route not found'
        });
    });
}, {
    name: 'error-handler'
});
export default errorHandlerPlugin